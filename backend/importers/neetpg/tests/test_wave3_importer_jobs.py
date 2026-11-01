"""Each recall importer API sees only its own jobs (wave 3, Z8).

/api/imports/inicet/ and /api/imports/neetpg/ shared one queryset
(every job_type='pdf' job): each list showed the other exam's jobs and
POST /api/imports/inicet/jobs/<neetpg job>/retry/ re-ran a NEET PG folder
with the INI-CET task (importing it as INI-CET), and the reverse.
"""
from __future__ import annotations

import io
import shutil
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from questions.models import QuestionImportJob

User = get_user_model()

NEETPG_TASK = "importers.neetpg.tasks.run_recall_import"
INICET_TASK = "importers.inicet.tasks.run_recall_import"


class RecallImporterJobSeparationTests(TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="z8_recall_root_")
        self.addCleanup(shutil.rmtree, self.root, True)
        env = patch.dict("os.environ", {"RECALL_IMPORT_ALLOWED_ROOTS": self.root})
        env.start()
        self.addCleanup(env.stop)
        admin = User.objects.create_user(username="z8_recall_admin", password="x",
                                         is_staff=True, is_superuser=True)
        self.client = APIClient()
        self.client.force_authenticate(admin)

        def job(summary):
            return QuestionImportJob.objects.create(
                job_type="pdf", status="failed", source_filename="dir",
                stored_file_path=self.root, summary=summary,
            )

        self.legacy = job({"source_dir": self.root})  # created before the importer was recorded
        self.neet = job({"importer": "neetpg"})
        self.ini = job({"importer": "inicet"})

    def ids(self, url):
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200, r.data)
        return {row["id"] for row in r.data["results"]}

    def test_lists_and_details_are_per_importer(self):
        self.assertEqual(self.ids("/api/imports/neetpg/jobs/"), {self.legacy.id, self.neet.id})
        self.assertEqual(self.ids("/api/imports/inicet/jobs/"), {self.ini.id})
        self.assertEqual(self.client.get(f"/api/imports/inicet/jobs/{self.neet.id}/").status_code, 404)
        self.assertEqual(self.client.get(f"/api/imports/inicet/jobs/{self.legacy.id}/").status_code, 404)
        self.assertEqual(self.client.get(f"/api/imports/neetpg/jobs/{self.ini.id}/").status_code, 404)
        self.assertEqual(self.client.get(f"/api/imports/inicet/jobs/{self.ini.id}/").status_code, 200)

    def test_retry_never_crosses_importers(self):
        with patch("django_q.tasks.async_task", return_value="t-1") as task:
            r = self.client.post(f"/api/imports/inicet/jobs/{self.neet.id}/retry/")
            self.assertEqual(r.status_code, 404)
            r = self.client.post(f"/api/imports/neetpg/jobs/{self.ini.id}/retry/")
            self.assertEqual(r.status_code, 404)
            task.assert_not_called()

            r = self.client.post(f"/api/imports/inicet/jobs/{self.ini.id}/retry/")
            self.assertEqual(r.status_code, 200, r.data)
            self.assertEqual(task.call_args[0][:2], (INICET_TASK, self.ini.id))
            r = self.client.post(f"/api/imports/neetpg/jobs/{self.legacy.id}/retry/")
            self.assertEqual(r.status_code, 200, r.data)
            self.assertEqual(task.call_args[0][:2], (NEETPG_TASK, self.legacy.id))
        self.ini.refresh_from_db()
        self.assertEqual(self.ini.summary["importer"], "inicet", "retry keeps the importer")

    def test_a_new_job_records_its_importer(self):
        with patch("django_q.tasks.async_task", return_value="t-2") as task:
            r = self.client.post("/api/imports/inicet/jobs/", {"source_dir": self.root}, format="json")
        self.assertEqual(r.status_code, 202, r.data)
        self.assertEqual(task.call_args[0][0], INICET_TASK)
        job = QuestionImportJob.objects.get(id=r.data["job_id"])
        self.assertEqual(job.summary["importer"], "inicet")
        self.assertIn(job.id, self.ids("/api/imports/inicet/jobs/"))
        self.assertNotIn(job.id, self.ids("/api/imports/neetpg/jobs/"))

    def test_a_redelivered_task_of_a_killed_run_does_not_restart_it(self):
        from importers.inicet import tasks as ini_tasks
        from importers.neetpg import tasks as neet_tasks

        for module, runner in ((neet_tasks, "importers.neetpg.runner.run_import"),
                               (ini_tasks, "importers.inicet.runner.run_import")):
            killed = QuestionImportJob.objects.create(job_type="pdf", status="processing",
                                                      stored_file_path=self.root)
            done = QuestionImportJob.objects.create(job_type="pdf", status="completed",
                                                    stored_file_path=self.root)
            queued = QuestionImportJob.objects.create(job_type="pdf", status="queued",
                                                      stored_file_path=self.root)
            with patch(runner, return_value={"run_id": "r1", "summaries": []}) as run:
                res = module.run_recall_import(killed.id, self.root)
                self.assertEqual(res["status"], "failed")
                self.assertTrue(module.run_recall_import(done.id, self.root)["noop"])
                run.assert_not_called()
                module.run_recall_import(queued.id, self.root)
                run.assert_called_once()
            killed.refresh_from_db()
            queued.refresh_from_db()
            self.assertEqual(killed.status, "failed")
            self.assertIn("stopped before it finished", killed.error_report[-1]["message"])
            self.assertEqual(queued.status, "completed")

    def test_documented_manage_py_commands_exist(self):
        from django.core.management import BaseCommand, get_commands, load_command_class

        commands = get_commands()
        for name in ("neetpg_import_run", "neetpg_status", "neetpg_retry", "neetpg_rollback",
                     "neetpg_import", "neetpg_import_all", "neetpg_scan", "neetpg_dedup",
                     "neetpg_reconcile", "neetpg_repair", "neetpg_report"):
            self.assertEqual(commands.get(name), "importers", name)
            self.assertIsInstance(load_command_class("importers", name), BaseCommand)

    def test_cli_retry_uses_the_jobs_importer(self):
        with patch("django_q.tasks.async_task", return_value="t-3") as task:
            call_command("neetpg_retry", "--job-id", str(self.ini.id), stdout=io.StringIO())
        self.assertEqual(task.call_args[0][0], INICET_TASK)
        out = io.StringIO()
        call_command("neetpg_status", "--importer", "inicet", stdout=out)
        self.assertIn(f"{self.ini.id:>5}", out.getvalue())
