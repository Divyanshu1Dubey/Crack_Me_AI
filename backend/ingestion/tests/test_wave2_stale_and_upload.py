"""Regression tests for the ingestion review follow-ups (wave 2, W10).

* a processing job whose worker died is resumed by a re-delivered task once
  it is stale, and the sweeper marks such jobs crashed (retry path)
* jobs created without an exam use their material's exam hint (profile,
  display, filter) and get it written on claim
* uploads must be real PDFs (magic bytes)
* batch status / counts are computed from the batch's jobs
"""
from __future__ import annotations

import io
import shutil
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from ingestion.models import BatchRun, ImportJob, ImportJobStage, ImportLog, MaterialAsset
from ingestion.orchestrator import (
    _profile_for,
    run_full_pipeline_for_job,
    stale_processing_after,
    sweep_stale_processing_jobs,
)

User = get_user_model()


def _admin_client():
    admin = User.objects.create_user(username="w10_ing_admin", password="x",
                                     is_staff=True, is_superuser=True)
    client = APIClient()
    client.force_authenticate(admin)
    return client


class _JobCase(TestCase):
    def setUp(self):
        self.material = MaterialAsset.objects.create(
            sha256="9" * 64, sha256_short="9" * 16, original_filename="Patho pyqs.pdf",
            storage_path="/tmp/patho.pdf", file_size=1, page_count=1,
        )

    def job(self, status="processing", minutes_ago=0, **kw):
        job = ImportJob.objects.create(material_asset=self.material,
                                       parent_exam=kw.pop("parent_exam", "neet_pg"),
                                       status=status, **kw)
        if minutes_ago:
            ImportJob.objects.filter(pk=job.pk).update(
                updated_at=timezone.now() - timedelta(minutes=minutes_ago))
            job.refresh_from_db()
        return job


@override_settings(INGESTION_STALE_PROCESSING_SECONDS=3600)
class StaleProcessingJobTests(_JobCase):
    def test_default_window_is_longer_than_the_q_cluster_timeout(self):
        with override_settings(INGESTION_STALE_PROCESSING_SECONDS=None,
                               Q_CLUSTER={"timeout": 3600, "retry": 3660}):
            self.assertGreater(stale_processing_after(), timedelta(seconds=3660))

    def test_redelivered_task_resumes_a_stale_processing_job(self):
        job = self.job(minutes_ago=90)
        with patch("ingestion.orchestrator._run_claimed_job", return_value={"status": "completed"}) as run:
            res = run_full_pipeline_for_job(job.id)
        self.assertEqual(res["status"], "completed")
        run.assert_called_once()
        self.assertTrue(ImportLog.objects.filter(job=job, message__startswith="Resuming job").exists())

    def test_live_processing_job_is_left_alone(self):
        job = self.job(minutes_ago=10)
        with patch("ingestion.orchestrator._run_claimed_job") as run:
            res = run_full_pipeline_for_job(job.id)
        self.assertTrue(res["noop"])
        run.assert_not_called()

    def test_sweeper_marks_only_stale_processing_jobs_crashed(self):
        batch = BatchRun.objects.create(name="b", status="running", total_jobs=2)
        stale = self.job(minutes_ago=90, batch_run=batch)
        stage = ImportJobStage.objects.create(job=stale, stage_name="5_question_blocks", status="running")
        live = self.job(minutes_ago=5, batch_run=batch)
        queued_old = self.job(status="queued", minutes_ago=600)

        self.assertEqual(sweep_stale_processing_jobs(dry_run=True), [stale.id])
        stale.refresh_from_db()
        self.assertEqual(stale.status, "processing", "a dry run changes nothing")

        self.assertEqual(sweep_stale_processing_jobs(), [stale.id])
        stale.refresh_from_db()
        live.refresh_from_db()
        queued_old.refresh_from_db()
        self.assertEqual(stale.status, "crashed")
        self.assertTrue(stale.error.get("swept"))
        self.assertIsNotNone(stale.completed_at)
        self.assertEqual(live.status, "processing")
        self.assertEqual(queued_old.status, "queued")
        self.assertTrue(ImportLog.objects.filter(job=stale, level="ERROR").exists())
        stage.refresh_from_db()
        self.assertEqual(stage.status, "failed", "the interrupted stage row is closed")
        batch.refresh_from_db()
        self.assertEqual(batch.failed_jobs, 1)

        # Crashed jobs are not re-run by a late re-delivery; they are retried.
        with patch("ingestion.orchestrator._run_claimed_job") as run:
            self.assertTrue(run_full_pipeline_for_job(stale.id)["noop"])
        run.assert_not_called()

    def test_sweep_command_and_run_pending_sweep_first(self):
        stale = self.job(minutes_ago=90)
        out = io.StringIO()
        call_command("ingestion_sweep_stale", "--dry-run", stdout=out)
        self.assertIn(f"#{stale.id}", out.getvalue())
        stale.refresh_from_db()
        self.assertEqual(stale.status, "processing")

        with patch("ingestion.management.commands.ingestion_run_pending.dispatch_job") as dispatch:
            call_command("ingestion_run_pending", "--no-sweep", stdout=io.StringIO())
            stale.refresh_from_db()
            self.assertEqual(stale.status, "processing")
            call_command("ingestion_run_pending", stdout=io.StringIO())
        dispatch.assert_not_called()
        stale.refresh_from_db()
        self.assertEqual(stale.status, "crashed")


@override_settings(INGESTION_ARTEFACT_ROOT=Path(tempfile.gettempdir()) / "w10_ingestion_artefacts")
class ExamHintTests(_JobCase):
    def setUp(self):
        super().setUp()
        # What scripts/run_bulk_ingestion.py stores: a hint spelling that is
        # not a choice value, and a job with no exam at all.
        MaterialAsset.objects.filter(pk=self.material.pk).update(exam_hint="inicet")
        self.material.refresh_from_db()

    def test_profile_uses_the_material_hint_when_the_job_has_no_exam(self):
        self.assertEqual(_profile_for(self.material, "").exam_type, "ini_cet")
        self.assertEqual(_profile_for(self.material, "neet_pg").exam_type, "neet_pg")

    def test_claim_writes_the_hint_exam_onto_the_job(self):
        job = self.job(status="queued", parent_exam="")
        with patch("ingestion.orchestrator._run_claimed_job", return_value={"status": "completed"}) as run:
            run_full_pipeline_for_job(job.id)
        self.assertEqual(run.call_args[0][0].parent_exam, "ini_cet")
        job.refresh_from_db()
        self.assertEqual(job.parent_exam, "ini_cet")

    def test_list_shows_and_filters_by_the_effective_exam(self):
        blank = self.job(status="queued", parent_exam="")
        other = MaterialAsset.objects.create(sha256="8" * 64, sha256_short="8" * 16,
                                             original_filename="NEET-PG-2021.pdf",
                                             storage_path="/tmp/n.pdf", exam_hint="neetpg")
        neet = ImportJob.objects.create(material_asset=other, parent_exam="", status="queued")
        client = _admin_client()

        r = client.get("/api/ingestion/jobs/", {"parent_exam": "ini_cet"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual([j["id"] for j in r.data], [blank.id])
        row = r.data[0]
        self.assertEqual((row["exam"], row["exam_label"]), ("ini_cet", "INI-CET"))
        self.assertEqual(row["material_filename"], "Patho pyqs.pdf")

        r = client.get("/api/ingestion/jobs/", {"parent_exam": "neet_pg"})
        self.assertEqual([j["id"] for j in r.data], [neet.id])


class MaterialUploadValidationTests(TestCase):
    def setUp(self):
        self._media = tempfile.mkdtemp(prefix="w10_ing_media_")
        self._override = override_settings(MEDIA_ROOT=self._media)
        self._override.enable()
        self.client = _admin_client()

    def tearDown(self):
        self._override.disable()
        shutil.rmtree(self._media, ignore_errors=True)

    def _pdf(self) -> bytes:
        import fitz
        doc = fitz.open()
        doc.new_page().insert_text((72, 72), "Q1. Test question?")
        data = doc.tobytes()
        doc.close()
        return data

    def test_non_pdf_content_is_rejected_before_anything_is_written(self):
        fake = SimpleUploadedFile("paper.pdf", b"<html>not a pdf</html>", content_type="application/pdf")
        r = self.client.post("/api/ingestion/materials/upload/", {"file": fake}, format="multipart")
        self.assertEqual(r.status_code, 400, r.data)
        self.assertFalse(MaterialAsset.objects.exists())
        self.assertFalse((Path(self._media) / "ingestion_uploads").exists())

    def test_docx_renamed_to_pdf_is_rejected(self):
        import zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("[Content_Types].xml", "<Types/>")
            zf.writestr("word/document.xml", "<w:document/>")
        r = self.client.post("/api/ingestion/materials/upload/",
                             {"file": SimpleUploadedFile("paper.pdf", buf.getvalue())}, format="multipart")
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn("Only PDF", r.data["detail"])

    def test_real_pdf_is_accepted(self):
        r = self.client.post("/api/ingestion/materials/upload/",
                             {"file": SimpleUploadedFile("paper.pdf", self._pdf()), "exam_hint": "neet_pg"},
                             format="multipart")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(MaterialAsset.objects.get().exam_hint, "neet_pg")


class DetailEndpointsTests(_JobCase):
    """The detail routes name their id job_id / batch_id / sha16 (they were 500s)."""

    def test_job_batch_and_material_detail_load(self):
        batch = BatchRun.objects.create(name="b", status="running")
        job = self.job(status="completed", batch_run=batch)
        client = _admin_client()

        r = client.get(f"/api/ingestion/jobs/{job.id}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.data["id"], r.data["exam_label"]), (job.id, "NEET PG"))

        r = client.get(f"/api/ingestion/batches/{batch.id}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual([j["id"] for j in r.data["jobs"]], [job.id])
        self.assertEqual(r.data["jobs"][0]["material_filename"], "Patho pyqs.pdf")

        r = client.get(f"/api/ingestion/materials/{self.material.sha256_short}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["original_filename"], "Patho pyqs.pdf")

        self.assertEqual(client.get("/api/ingestion/jobs/999999/").status_code, 404)
        self.assertEqual(client.get("/api/ingestion/batches/999999/").status_code, 404)

    def test_detail_routes_are_admin_only(self):
        job = self.job(status="completed")
        student = User.objects.create_user(username="w10_ing_student", password="x")
        client = APIClient()
        client.force_authenticate(student)
        self.assertEqual(client.get(f"/api/ingestion/jobs/{job.id}/").status_code, 403)


class BatchLiveCountsTests(_JobCase):
    def test_list_and_detail_count_the_jobs(self):
        # Stored counters as the bulk script left them: never updated.
        batch = BatchRun.objects.create(name="Bulk Import - INICET - 3 files", status="running",
                                        total_jobs=19, completed_jobs=0, failed_jobs=0)
        for status in ("completed", "completed", "crashed"):
            self.job(status=status, batch_run=batch)
        client = _admin_client()

        r = client.get("/api/ingestion/batches/")
        self.assertEqual(r.status_code, 200)
        row = r.data[0]
        self.assertEqual((row["total_jobs"], row["completed_jobs"], row["failed_jobs"], row["status"]),
                         (3, 2, 1, "done"))
        self.assertIn("created_at", row)

        r = client.get(f"/api/ingestion/batches/{batch.id}/")
        self.assertEqual((r.data["total_jobs"], r.data["completed_jobs"], r.data["failed_jobs"],
                          r.data["status"]), (3, 2, 1, "done"))

    def test_running_and_cancelled_batches(self):
        running = BatchRun.objects.create(name="r", status="open")
        self.job(status="completed", batch_run=running)
        self.job(status="queued", batch_run=running)
        cancelled = BatchRun.objects.create(name="c", status="cancelled")
        self.job(status="completed", batch_run=cancelled)
        r = _admin_client().get("/api/ingestion/batches/")
        by_name = {b["name"]: b for b in r.data}
        self.assertEqual(by_name["r"]["status"], "running")
        self.assertEqual(by_name["c"]["status"], "cancelled")
