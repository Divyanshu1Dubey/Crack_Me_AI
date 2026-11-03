"""Regression tests for the ingestion review follow-ups (wave 3, Z8).

* the stale-job sweeper runs on its own: a django-q Schedule created
  idempotently after migrate (C15)
* with the shipped Q_CLUSTER settings django-q's re-delivery of a killed
  task is a no-op; the scheduled pass marks the job crashed and re-queues it
  (same job id), and the new task resumes after the last checkpoint
* auto-resume is capped, skips long-dead jobs and survives a broker failure
* the conservative gate is idempotent per job (no duplicate staged rows)
* the hub tiles count every job (/jobs/counts/), not the 200 newest
"""
from __future__ import annotations

import pydoc
import shutil
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from django_q.models import Schedule
from rest_framework.test import APIClient

from ingestion import signals
from ingestion.checkpoint import save_checkpoint
from ingestion.conservative_gate import apply_qa_v2_verdict
from ingestion.constants import (
    PIPELINE_ORDER,
    QA_EXTRACTION_FAILURE,
    QA_NEEDS_REVIEW,
    QA_PRODUCTION_READY,
    STAGE_CONSERVATIVE_GATE,
)
from ingestion.models import BatchRun, ImportJob, ImportLog, MaterialAsset, StagedQuestion
from ingestion.orchestrator import run_full_pipeline_for_job, stale_processing_after
from ingestion.schedules import RECOVERY_SCHEDULE_NAME, RECOVERY_TASK, ensure_recovery_schedule
from ingestion.tasks import recover_stale_jobs
from ingestion.tests.test_wave1_gate_and_rollback import _GateCase, _payload, _png_bytes

User = get_user_model()

SHIPPED_Q_CLUSTER = {"timeout": 3600, "retry": 3660}


class RecoveryScheduleTests(TestCase):
    def test_schedule_is_created_once_and_points_at_the_recovery_task(self):
        first = ensure_recovery_schedule()
        self.assertEqual((first.func, first.schedule_type, first.minutes, first.repeats),
                         (RECOVERY_TASK, Schedule.MINUTES, 10, -1))
        self.assertTrue(callable(pydoc.locate(first.func)), "django-q resolves func with pydoc.locate")
        next_run = first.next_run

        again = ensure_recovery_schedule()
        self.assertEqual(again.pk, first.pk)
        self.assertEqual(Schedule.objects.filter(name=RECOVERY_SCHEDULE_NAME).count(), 1)
        self.assertEqual(Schedule.objects.get(pk=first.pk).next_run, next_run, "a re-run keeps next_run")

    def test_edits_are_reset_duplicates_removed_and_zero_minutes_disables(self):
        sched = ensure_recovery_schedule()
        Schedule.objects.filter(pk=sched.pk).update(minutes=600, repeats=0, func="x.y")
        Schedule.objects.create(name=RECOVERY_SCHEDULE_NAME, func=RECOVERY_TASK,
                                schedule_type=Schedule.MINUTES, minutes=10)
        ensure_recovery_schedule()
        rows = list(Schedule.objects.filter(name=RECOVERY_SCHEDULE_NAME))
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0].pk, rows[0].minutes, rows[0].repeats, rows[0].func),
                         (sched.pk, 10, -1, RECOVERY_TASK))

        with override_settings(INGESTION_RECOVERY_SCHEDULE_MINUTES=15):
            self.assertEqual(ensure_recovery_schedule().minutes, 15)
        with override_settings(INGESTION_RECOVERY_SCHEDULE_MINUTES=0):
            self.assertIsNone(ensure_recovery_schedule())
        self.assertFalse(Schedule.objects.filter(name=RECOVERY_SCHEDULE_NAME).exists())

    def test_post_migrate_creates_it_once_per_migrate_and_never_in_tests(self):
        ingestion_app = apps.get_app_config("ingestion")
        signals.recovery_schedule_post_migrate(sender=ingestion_app, using="default")
        self.assertFalse(Schedule.objects.filter(name=RECOVERY_SCHEDULE_NAME).exists(),
                         "test runs must not create schedules")
        with patch.object(signals, "_running_tests", return_value=False):
            signals.recovery_schedule_post_migrate(sender=apps.get_app_config("questions"), using="default")
            self.assertFalse(Schedule.objects.filter(name=RECOVERY_SCHEDULE_NAME).exists())
            signals.recovery_schedule_post_migrate(sender=ingestion_app, using="default")
            signals.recovery_schedule_post_migrate(sender=ingestion_app, using="default")
        self.assertEqual(Schedule.objects.filter(name=RECOVERY_SCHEDULE_NAME).count(), 1)

    def test_a_schedule_failure_never_blocks_migrate(self):
        with patch.object(signals, "_running_tests", return_value=False), \
                patch("ingestion.schedules.ensure_recovery_schedule", side_effect=RuntimeError("db down")):
            signals.recovery_schedule_post_migrate(sender=apps.get_app_config("ingestion"), using="default")


class _StaleJobCase(TestCase):
    def setUp(self):
        self.material = MaterialAsset.objects.create(
            sha256="7" * 64, sha256_short="7" * 16, original_filename="recall.pdf",
            storage_path="/tmp/recall.pdf", file_size=1, page_count=1,
        )

    def job(self, status="processing", minutes_ago=0, **kw):
        job = ImportJob.objects.create(material_asset=self.material, parent_exam="ini_cet",
                                       status=status, **kw)
        if minutes_ago:
            ImportJob.objects.filter(pk=job.pk).update(
                updated_at=timezone.now() - timedelta(minutes=minutes_ago))
            job.refresh_from_db()
        return job


@override_settings(INGESTION_STALE_PROCESSING_SECONDS=None, Q_CLUSTER=SHIPPED_Q_CLUSTER)
class ScheduledRecoveryTests(_StaleJobCase):
    def test_redelivery_after_a_timeout_kill_is_a_no_op_with_the_shipped_settings(self):
        # Killed at the 60-min timeout; its last stage boundary was just
        # before. django-q re-presents the task `retry` s after it was taken.
        job = self.job(minutes_ago=59)
        self.assertGreater(stale_processing_after(), timedelta(seconds=SHIPPED_Q_CLUSTER["retry"]))
        with patch("ingestion.orchestrator._run_claimed_job") as run:
            self.assertTrue(run_full_pipeline_for_job(job.id)["noop"])
        run.assert_not_called()
        job.refresh_from_db()
        self.assertEqual(job.status, "processing", "so the scheduled sweeper has to recover it")

    def test_scheduled_pass_crashes_and_requeues_the_stale_job_only(self):
        batch = BatchRun.objects.create(name="b", status="running")
        stale = self.job(minutes_ago=75, batch_run=batch, summary={"q_task_id": "old-task"})
        live = self.job(minutes_ago=30, batch_run=batch)
        with patch("ingestion.tasks.dispatch_job", return_value="t-new") as dispatch:
            result = recover_stale_jobs()
        self.assertEqual(result, {"swept": [stale.id], "resumed": [stale.id]})
        dispatch.assert_called_once_with(stale.id)

        stale.refresh_from_db()
        live.refresh_from_db()
        self.assertEqual(stale.status, "queued")
        self.assertEqual(stale.error, {})
        self.assertIsNone(stale.completed_at)
        self.assertEqual(stale.summary, {"q_task_id": "t-new", "auto_resumes": 1})
        self.assertEqual(live.status, "processing")
        messages = list(ImportLog.objects.filter(job=stale).values_list("message", flat=True))
        self.assertTrue(any(m.startswith("Marked crashed by the stale-job sweeper") for m in messages))
        self.assertTrue(any(m.startswith("Re-queued automatically (1/2)") for m in messages))
        batch.refresh_from_db()
        self.assertEqual(batch.status, "running")

    def test_auto_resume_is_capped(self):
        job = self.job(minutes_ago=75, summary={"auto_resumes": 2})
        with patch("ingestion.tasks.dispatch_job") as dispatch:
            self.assertEqual(recover_stale_jobs(), {"swept": [job.id], "resumed": []})
        dispatch.assert_not_called()
        job.refresh_from_db()
        self.assertEqual(job.status, "crashed")
        self.assertTrue(ImportLog.objects.filter(job=job, message__startswith="Not re-queued automatically").exists())

        other = self.job(minutes_ago=75)
        with override_settings(INGESTION_MAX_AUTO_RESUMES=0), patch("ingestion.tasks.dispatch_job") as dispatch:
            self.assertEqual(recover_stale_jobs()["resumed"], [])
        dispatch.assert_not_called()
        other.refresh_from_db()
        self.assertEqual(other.status, "crashed")

    def test_a_long_dead_job_is_only_marked_crashed(self):
        job = self.job(minutes_ago=3 * 24 * 60)
        with patch("ingestion.tasks.dispatch_job") as dispatch:
            self.assertEqual(recover_stale_jobs(), {"swept": [job.id], "resumed": []})
        dispatch.assert_not_called()
        job.refresh_from_db()
        self.assertEqual(job.status, "crashed")

    def test_broker_failure_leaves_the_job_crashed(self):
        job = self.job(minutes_ago=75, summary={"q_task_id": "old"})
        with patch("ingestion.tasks.dispatch_job", side_effect=RuntimeError("broker down")):
            self.assertEqual(recover_stale_jobs()["resumed"], [])
        job.refresh_from_db()
        self.assertEqual(job.status, "crashed")
        self.assertTrue(job.error.get("swept"))
        self.assertEqual(job.summary, {"q_task_id": "old"}, "the resume count is not spent")

    def test_manual_sweep_command_only_marks_crashed_and_run_pending_recovers(self):
        from django.core.management import call_command
        import io

        swept_only = self.job(minutes_ago=75)
        with patch("ingestion.tasks.dispatch_job") as dispatch:
            call_command("ingestion_sweep_stale", stdout=io.StringIO())
        dispatch.assert_not_called()
        swept_only.refresh_from_db()
        self.assertEqual(swept_only.status, "crashed")

        recovered = self.job(minutes_ago=75)
        with patch("ingestion.tasks.dispatch_job", return_value="t-2"), \
                patch("ingestion.management.commands.ingestion_run_pending.dispatch_job") as pending_dispatch:
            out = io.StringIO()
            call_command("ingestion_run_pending", stdout=out)
        recovered.refresh_from_db()
        self.assertEqual(recovered.status, "queued")
        self.assertIn(f"#{recovered.id}", out.getvalue())
        pending_dispatch.assert_not_called()  # it has a task id now; no second task

    def test_requeued_job_resumes_after_its_checkpoint(self):
        tmp = Path(tempfile.mkdtemp(prefix="z8_resume_"))
        self.addCleanup(shutil.rmtree, tmp, True)
        job = self.job(minutes_ago=75)
        save_checkpoint(job=job, material=self.material, last_completed_stage="5_question_blocks",
                        last_processed_page=1, current_page=1, artifact_root=tmp,
                        artifact_sha16=self.material.sha256_short)
        ImportJob.objects.filter(pk=job.pk).update(updated_at=timezone.now() - timedelta(minutes=75))
        with patch("ingestion.tasks.dispatch_job", return_value="t-3"):
            self.assertEqual(recover_stale_jobs()["resumed"], [job.id])

        from mce.stages import StageResult
        ran: list[str] = []

        def fake_import(stage_name):
            if stage_name not in ran:
                ran.append(stage_name)
            return lambda ctx, **kw: StageResult(stage=stage_name)

        with override_settings(INGESTION_ARTEFACT_ROOT=tmp), \
                patch("ingestion.pipeline_stages._import_callable", side_effect=fake_import), \
                patch("ingestion.conservative_gate.apply_qa_v2_verdict",
                      return_value={"pr": 0, "nr": 0, "ef": 0, "staged": 0, "imported": 0, "held": 0}):
            result = run_full_pipeline_for_job(job.id)
        self.assertEqual(result["status"], "completed")
        mce_stages = [s for s in PIPELINE_ORDER if s != STAGE_CONSERVATIVE_GATE]
        self.assertEqual(ran, mce_stages[mce_stages.index("5_question_blocks") + 1:])
        job.refresh_from_db()
        self.assertEqual(job.status, "completed")


class GateIdempotentPerJobTests(_GateCase):
    def _rows(self):
        return [
            (QA_NEEDS_REVIEW, _payload("Which artery is ligated in this procedure?", page=1, qno=1)),
            (QA_EXTRACTION_FAILURE, _payload("Garbled stem", page=1, qno=2)),
            (QA_PRODUCTION_READY, _payload("No single answer here?", answer=("A", "B"), page=2, qno=3)),
        ]

    def test_second_run_for_the_same_job_stages_nothing_twice(self):
        self.write_qa(self._rows())
        first = apply_qa_v2_verdict(job=self.job, artefact_root=self.tmp)
        self.assertEqual((first["staged"], first["held"]), (3, 1))
        self.assertEqual(StagedQuestion.objects.filter(job=self.job).count(), 3)

        # The admin approved one row before the job was resumed.
        decided = StagedQuestion.objects.get(job=self.job, page_number=1, question_number_in_pdf=1)
        StagedQuestion.objects.filter(pk=decided.pk).update(review_status="approved")

        second = apply_qa_v2_verdict(job=self.job, artefact_root=self.tmp)
        self.assertEqual((second["nr"], second["ef"], second["held"]), (1, 1, 1))
        rows = StagedQuestion.objects.filter(job=self.job)
        self.assertEqual(rows.count(), 3, "resume must not duplicate staged rows")
        self.assertTrue(rows.filter(pk=decided.pk, review_status="approved").exists())
        self.job.refresh_from_db()
        self.assertEqual((self.job.questions_staged_nr, self.job.questions_staged_ef), (2, 1))

    def test_a_retry_job_keeps_the_original_jobs_rows(self):
        self.write_qa(self._rows())
        apply_qa_v2_verdict(job=self.job, artefact_root=self.tmp)
        retry = ImportJob.objects.create(material_asset=self.material, parent_exam=self.exam,
                                         status="processing", retry_of=self.job)
        apply_qa_v2_verdict(job=retry, artefact_root=self.tmp)
        self.assertEqual(StagedQuestion.objects.filter(job=self.job).count(), 3)
        self.assertEqual(StagedQuestion.objects.filter(job=retry).count(), 3)

    def test_images_imported_is_not_double_counted(self):
        rec = self.stage3_image(1, 0, _png_bytes(), "e" * 16)
        self.write_stage3(1, [rec])
        self.write_qa([(QA_PRODUCTION_READY, _payload("Identify the nerve injury shown here?",
                                                      image_ids=[rec["id"]]))])
        apply_qa_v2_verdict(job=self.job, artefact_root=self.tmp)
        self.job.refresh_from_db()
        self.assertEqual(self.job.images_imported, 1)
        apply_qa_v2_verdict(job=self.job, artefact_root=self.tmp)
        self.job.refresh_from_db()
        self.assertEqual(self.job.images_imported, 1)


class BulkIngestionScriptTests(TestCase):
    def test_jobs_get_their_exam_and_materials_the_exam_code(self):
        import contextlib
        import importlib.util
        import io

        import fitz
        from django.conf import settings

        tmp = Path(tempfile.mkdtemp(prefix="z8_bulk_"))
        self.addCleanup(shutil.rmtree, tmp, True)
        src = tmp / "inicet-pg"
        src.mkdir()
        doc = fitz.open()
        doc.new_page().insert_text((72, 72), "Q1. Which nerve?")
        (src / "INI-CET 2023 recall.pdf").write_bytes(doc.tobytes())
        doc.close()

        path = Path(settings.BASE_DIR) / "scripts" / "run_bulk_ingestion.py"
        spec = importlib.util.spec_from_file_location("z8_run_bulk_ingestion", path)
        script = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(script)
        with override_settings(MEDIA_ROOT=str(tmp / "media")), \
                patch.object(script, "dispatch_job", return_value="t-bulk"), \
                contextlib.redirect_stdout(io.StringIO()):
            script.ingest_directory(src, "inicet")
        job = ImportJob.objects.get()
        self.assertEqual(job.parent_exam, "ini_cet")
        self.assertEqual(job.material_asset.exam_hint, "ini_cet")
        self.assertEqual(job.summary["q_task_id"], "t-bulk")


class JobCountsEndpointTests(_StaleJobCase):
    def test_counts_cover_every_job_and_are_admin_only(self):
        ImportJob.objects.bulk_create(
            [ImportJob(material_asset=self.material, parent_exam="neet_pg", status="completed")
             for _ in range(205)]
            + [ImportJob(material_asset=self.material, parent_exam="neet_pg", status="crashed")
               for _ in range(2)]
        )
        self.job(status="queued")
        admin = User.objects.create_user(username="z8_ing_admin", password="x", is_staff=True, is_superuser=True)
        student = User.objects.create_user(username="z8_ing_student", password="x")
        client = APIClient()

        client.force_authenticate(student)
        self.assertEqual(client.get("/api/ingestion/jobs/counts/").status_code, 403)

        client.force_authenticate(admin)
        r = client.get("/api/ingestion/jobs/counts/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["total"], 208)
        self.assertEqual(r.data["counts"], {"queued": 1, "processing": 0, "completed": 205,
                                            "failed": 0, "cancelled": 0, "crashed": 2})
        self.assertEqual(len(client.get("/api/ingestion/jobs/").data), 200, "the list stays capped")

    @override_settings(INGESTION_STALE_PROCESSING_SECONDS=None, Q_CLUSTER=SHIPPED_Q_CLUSTER)
    def test_a_requeued_old_job_is_not_flagged_as_waiting_for_a_worker(self):
        job = self.job(minutes_ago=75)
        ImportJob.objects.filter(pk=job.pk).update(created_at=timezone.now() - timedelta(days=2))
        with patch("ingestion.tasks.dispatch_job", return_value="t-4"):
            self.assertEqual(recover_stale_jobs()["resumed"], [job.id])
        admin = User.objects.create_user(username="z8_ing_admin2", password="x", is_staff=True, is_superuser=True)
        client = APIClient()
        client.force_authenticate(admin)
        self.assertFalse(client.get(f"/api/ingestion/jobs/{job.id}/").data["waiting_for_worker"])
        ImportJob.objects.filter(pk=job.pk).update(updated_at=timezone.now() - timedelta(minutes=10))
        self.assertTrue(client.get(f"/api/ingestion/jobs/{job.id}/").data["waiting_for_worker"])
