"""Regression tests for the Import Center review follow-ups (wave 2, W10).

* publish is claimed atomically under the batch row lock; republish is
  refused while a publish runs and restores the previous publish state;
  summary writers never drop each other's keys
* a cancelled batch can publish what it staged; a rolled-back one cannot
* uploads (and zip members) are checked by content, not just extension
* dashboard duplicate rate comes from the batch counters
* search reports the total match count and each row's batch id
* DOCX parses without python-docx; PDF parses with PyMuPDF alone
* import_docx_fidelity --rollback keeps the old questions live unless
  --remove-published is passed
"""
from __future__ import annotations

import io
import os
import shutil
import sys
import tempfile
import zipfile
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from material_importer import api_views
from material_importer.batch_state import update_batch_summary
from material_importer.ingest_service import ingest_path
from material_importer.mock_test_builder import _record_batch_test_ids
from material_importer.models import ExtractedQuestion, ImportBatch, ImportMaterial
from material_importer.parser import ParserFactory
from material_importer.publishing import publish_extracted_question
from questions.models import Question, RemovedQuestion

User = get_user_model()

MCQ_TEXT = (
    "Q1. Which nerve is injured in wrist drop?\nA. Median\nB. Radial\nC. Ulnar\nD. Axillary\nAnswer: B\n\n"
    "Q2. Which vitamin deficiency causes scurvy?\nA. Vitamin A\nB. Vitamin B12\nC. Vitamin C\nD. Vitamin D\n"
    "Answer: C\n"
)


def _inline_background(target, *, name):  # replaces the daemon thread in tests
    target()


def _pdf_bytes(text: str = "Q1. Which nerve is injured in wrist drop?\nA. Median\nB. Radial\n"
                            "C. Ulnar\nD. Axillary\nAnswer: B") -> bytes:
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


def _docx_bytes(lines=("Q1. Which nerve is injured in wrist drop?", "A. Median", "B. Radial",
                       "C. Ulnar", "D. Axillary", "Answer: B")) -> bytes:
    from docx import Document
    d = Document()
    for line in lines:
        d.add_paragraph(line)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


class _AdminClientMixin:
    def setUp(self):
        super().setUp()
        self._media = tempfile.mkdtemp(prefix="w10_media_")
        self._override = override_settings(MEDIA_ROOT=self._media)
        self._override.enable()
        self.admin = User.objects.create_user(username="w10_admin", password="x",
                                              is_staff=True, is_superuser=True)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def tearDown(self):
        self._override.disable()
        shutil.rmtree(self._media, ignore_errors=True)
        super().tearDown()

    def make_batch(self, status="completed", **summary):
        return ImportBatch.objects.create(source_label="w10", root_path="/tmp/x",
                                          status=status, summary=summary)

    def make_eq(self, batch, idx=0, *, status="approved", filename="surgery.docx"):
        m = ImportMaterial.objects.filter(batch=batch).first() or ImportMaterial.objects.create(
            batch=batch, original_filename=filename, file_format="docx",
            file_size_bytes=10, file_sha256="e" * 64,
        )
        return ExtractedQuestion.objects.create(
            material=m, position_index=idx,
            question_text=f"W10 question {batch.id}-{idx}: which nerve is injured?",
            option_a="Median", option_b="Ulnar", option_c="Radial", option_d="Axillary",
            correct_answer="B", content_hash=f"w10-{batch.id}-{idx}", status=status,
        )


# ---------------------------------------------------------------------------
# Atomic publish claim / republish guard / summary writers
# ---------------------------------------------------------------------------


class PublishClaimTests(_AdminClientMixin, TestCase):
    def _running(self, minutes_ago=0):
        ts = (timezone.now() - timedelta(minutes=minutes_ago)).isoformat()
        return {"state": "running", "started_at": ts, "heartbeat_at": ts, "by": "other"}

    def test_claim_is_exclusive_until_the_run_goes_stale(self):
        batch = self.make_batch()
        claimed, _ = api_views._claim_publish(batch.id, self._running())
        self.assertTrue(claimed)
        claimed_again, current = api_views._claim_publish(batch.id, self._running())
        self.assertFalse(claimed_again, "a second claim must fail while the first is live")
        self.assertEqual(current["by"], "other")
        # A run that stopped reporting (dead thread) can be taken over.
        ImportBatch.objects.filter(pk=batch.pk).update(summary={"publish": self._running(minutes_ago=31)})
        claimed_stale, _ = api_views._claim_publish(batch.id, self._running())
        self.assertTrue(claimed_stale)

    def test_publish_refused_while_another_publish_runs(self):
        batch = self.make_batch(publish=self._running())
        self.make_eq(batch)
        r = self.client.post(f"/api/admin/import/batches/{batch.id}/publish/", {}, format="json")
        self.assertEqual(r.status_code, 409, r.data)
        self.assertEqual(Question.objects.count(), 0)

    def test_republish_refused_while_a_publish_runs(self):
        batch = self.make_batch(publish=self._running())
        with patch.object(api_views, "build_for_batch") as build:
            r = self.client.post(f"/api/admin/import/batches/{batch.id}/republish/")
        self.assertEqual(r.status_code, 409, r.data)
        build.assert_not_called()

    def test_republish_holds_the_slot_and_restores_the_previous_state(self):
        done = {"state": "done", "published": 3, "tests_built": 2}
        batch = self.make_batch(publish=done, uploaded_files=["a.docx"])
        seen = {}

        def fake_build(batch_id, max_per_test=100):
            # While the rebuild runs, a publish cannot start.
            seen["claimed"] = api_views._claim_publish(batch_id, self._running())[0]
            return 4

        with patch.object(api_views, "build_for_batch", side_effect=fake_build):
            r = self.client.post(f"/api/admin/import/batches/{batch.id}/republish/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["tests_built"], 4)
        self.assertFalse(seen["claimed"])
        batch.refresh_from_db()
        self.assertEqual(batch.summary["publish"], done)
        self.assertEqual(batch.summary["uploaded_files"], ["a.docx"])

    def test_test_id_recording_keeps_the_publish_heartbeat(self):
        running = self._running()
        batch = self.make_batch(publish=running, mock_test_ids=[5])
        _record_batch_test_ids(batch.id, "mock_test_ids", [7], replace=False)
        batch.refresh_from_db()
        self.assertEqual(batch.summary["mock_test_ids"], [5, 7])
        self.assertEqual(batch.summary["publish"], running)

    def test_update_batch_summary_writes_only_on_change(self):
        batch = self.make_batch(a=1)
        before = ImportBatch.objects.get(pk=batch.pk).updated_at
        self.assertEqual(update_batch_summary(batch.id, lambda s: s.get("a")), 1)
        self.assertEqual(ImportBatch.objects.get(pk=batch.pk).updated_at, before)
        update_batch_summary(batch.id, lambda s: s.update(b=2))
        self.assertEqual(ImportBatch.objects.get(pk=batch.pk).summary, {"a": 1, "b": 2})
        self.assertIsNone(update_batch_summary(999999, lambda s: s.update(c=3)))

    def test_concurrent_publishes_of_one_row_create_one_question(self):
        batch = self.make_batch()
        eq = self.make_eq(batch)
        stale_copy = ExtractedQuestion.objects.get(pk=eq.pk)
        self.assertTrue(publish_extracted_question(eq))
        # A second publisher holding a stale copy (no link yet) is refused.
        self.assertFalse(publish_extracted_question(stale_copy))
        self.assertEqual(Question.objects.count(), 1)


# ---------------------------------------------------------------------------
# Cancelled batches
# ---------------------------------------------------------------------------


class CancelledBatchPublishTests(_AdminClientMixin, TestCase):
    @patch.object(api_views, "_start_background", _inline_background)
    def test_cancelled_batch_publishes_its_staged_rows(self):
        batch = self.make_batch(status="cancelled")
        self.make_eq(batch, 0)
        self.make_eq(batch, 1, status="pending")  # still unreviewed: never published
        with self.captureOnCommitCallbacks(execute=True):
            r = self.client.post(f"/api/admin/import/batches/{batch.id}/publish/",
                                 {"only_publish": True}, format="json")
        self.assertEqual(r.status_code, 202, r.data)
        batch.refresh_from_db()
        self.assertEqual(batch.summary["publish"]["state"], "done")
        self.assertEqual(batch.summary["publish"]["published"], 1)
        self.assertEqual(Question.objects.count(), 1)

    def test_rolled_back_batch_cannot_publish(self):
        batch = self.make_batch(status="cancelled", rollback={"materials": 1})
        r = self.client.post(f"/api/admin/import/batches/{batch.id}/publish/", {}, format="json")
        self.assertEqual(r.status_code, 409)
        self.assertIn("rolled back", r.data["error"])

    def test_cancelled_before_anything_was_staged_cannot_publish(self):
        batch = self.make_batch(status="cancelled")
        r = self.client.post(f"/api/admin/import/batches/{batch.id}/publish/", {}, format="json")
        self.assertEqual(r.status_code, 409)

    def test_cancel_response_explains_staged_rows_stay_publishable(self):
        batch = self.make_batch(status="processing")
        r = self.client.post(f"/api/admin/import/batches/{batch.id}/cancel/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("can still be published", r.data["detail"])

    def test_rollback_marks_batch_and_keeps_other_summary_keys(self):
        batch = self.make_batch(uploaded_files=["a.docx"])
        self.make_eq(batch)
        r = self.client.post(f"/api/admin/import/batches/{batch.id}/rollback/",
                             {"confirm": True}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        batch.refresh_from_db()
        self.assertEqual(batch.status, "cancelled")
        self.assertEqual(batch.summary["uploaded_files"], ["a.docx"])
        self.assertEqual(batch.summary["rollback"]["questions"], 1)


# ---------------------------------------------------------------------------
# Upload content validation (magic bytes)
# ---------------------------------------------------------------------------


class UploadContentValidationTests(_AdminClientMixin, TestCase):
    def _upload(self, *files):
        return self.client.post("/api/admin/import/upload/", {"files": list(files)}, format="multipart")

    def test_renamed_file_is_rejected_by_content(self):
        html = SimpleUploadedFile("notes.pdf", b"<html><script>alert(1)</script></html>")
        pdf_as_docx = SimpleUploadedFile("paper.docx", _pdf_bytes())
        binary_txt = SimpleUploadedFile("notes.txt", b"MZ\x90\x00\x03\x00binary")
        not_zip = SimpleUploadedFile("bundle.zip", b"definitely not a zip")
        r = self._upload(html, pdf_as_docx, binary_txt, not_zip)
        self.assertEqual(r.status_code, 400, r.data)
        reasons = " | ".join(r.data["rejected"])
        self.assertIn("notes.pdf", reasons)
        self.assertIn("paper.docx: content is not a DOCX file", reasons)
        self.assertIn("notes.txt: not a text file", reasons)
        self.assertIn("bundle.zip: not a valid zip", reasons)
        self.assertEqual(ImportBatch.objects.count(), 0)

    @patch.object(api_views, "_start_background", lambda target, *, name: None)
    def test_real_files_are_accepted(self):
        r = self._upload(
            SimpleUploadedFile("paper.pdf", _pdf_bytes()),
            SimpleUploadedFile("paper.docx", _docx_bytes()),
            SimpleUploadedFile("notes.md", MCQ_TEXT.encode("utf-8")),
        )
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["files_accepted"], 3)
        self.assertEqual(r.data["files_rejected"], [])

    @patch.object(api_views, "_start_background", lambda target, *, name: None)
    def test_zip_member_with_wrong_content_is_dropped(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("good.pdf", _pdf_bytes())
            zf.writestr("fake.pdf", b"<html>not a pdf</html>")
        r = self._upload(SimpleUploadedFile("bundle.zip", buf.getvalue()))
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(any("fake.pdf" in s for s in r.data["files_rejected"]), r.data)
        names = [f for _root, _dirs, files in os.walk(self._media) for f in files]
        self.assertIn("good.pdf", names)
        self.assertNotIn("fake.pdf", names)


# ---------------------------------------------------------------------------
# Dashboard / search
# ---------------------------------------------------------------------------


class DashboardAndSearchTests(_AdminClientMixin, TestCase):
    def test_duplicate_rate_uses_batch_counters(self):
        ImportBatch.objects.create(source_label="a", root_path="/x", status="completed",
                                   questions_found=80, duplicates_skipped=10)
        ImportBatch.objects.create(source_label="b", root_path="/x", status="completed",
                                   questions_found=20, duplicates_skipped=15)
        r = self.client.get("/api/admin/import/dashboard/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["duplicate_rate"], 0.25)

    def test_duplicate_rate_is_zero_without_batches(self):
        r = self.client.get("/api/admin/import/dashboard/")
        self.assertEqual(r.data["duplicate_rate"], 0.0)

    def test_search_returns_total_count_and_batch_ids(self):
        batch = self.make_batch()
        for i in range(3):
            self.make_eq(batch, i)
        r = self.client.get("/api/admin/import/search/", {"q": "which nerve"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 3)
        self.assertEqual({row["batch_id"] for row in r.data["items"]}, {batch.id})


# ---------------------------------------------------------------------------
# Parser library fallbacks
# ---------------------------------------------------------------------------


class ParserFallbackTests(TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="w10_parse_")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _write(self, name, data: bytes) -> str:
        path = os.path.join(self.dir, name)
        with open(path, "wb") as fh:
            fh.write(data)
        return path

    def test_docx_parses_without_python_docx(self):
        path = self._write("q.docx", _docx_bytes())
        with patch.dict(sys.modules, {"docx": None}):  # import docx -> ImportError
            doc = ParserFactory().parse(path)
        self.assertEqual(doc.errors, [])
        self.assertEqual([(q.question_text, q.correct_answer) for q in doc.questions],
                         [("Which nerve is injured in wrist drop?", "B")])
        self.assertTrue(doc.parser_used.startswith("docx.xml_fallback"))

    def test_non_docx_without_python_docx_is_an_error_not_an_empty_parse(self):
        path = self._write("q.docx", b"%PDF-1.4 not a docx")
        with patch.dict(sys.modules, {"docx": None}):
            doc = ParserFactory().parse(path)
        self.assertTrue(doc.errors and "not a DOCX file" in doc.errors[0], doc.errors)

    def test_pdf_parses_with_pymupdf_alone(self):
        path = self._write("q.pdf", _pdf_bytes())
        with patch.dict(sys.modules, {"pypdf": None, "pdfplumber": None}):
            doc = ParserFactory().parse(path)
        self.assertEqual(doc.errors, [])
        self.assertEqual(len(doc.questions), 1)
        self.assertEqual(doc.questions[0].correct_answer, "B")
        self.assertEqual(len(doc.meta["sha256"]), 64)

    def test_textless_pdf_is_reported_as_scanned(self):
        import fitz
        pdf = fitz.open()
        pdf.new_page()
        path = self._write("blank.pdf", pdf.tobytes())
        pdf.close()
        doc = ParserFactory().parse(path)
        self.assertEqual(doc.errors, [])
        self.assertTrue(any("no extractable text" in w for w in doc.warnings))

    def test_unreadable_pdf_names_every_library(self):
        path = self._write("broken.pdf", b"%PDF-1.4\ngarbage")
        with patch.dict(sys.modules, {"pypdf": None, "pdfplumber": None}):
            doc = ParserFactory().parse(path)
        self.assertTrue(doc.errors and "PyMuPDF" in doc.errors[0], doc.errors)

    def test_health_counts_pymupdf_as_a_pdf_library(self):
        admin = User.objects.create_user(username="w10_health", password="x", is_staff=True)
        client = APIClient()
        client.force_authenticate(admin)
        r = client.get("/api/admin/import/health/")
        self.assertTrue(r.data["checks"]["parser_libraries"]["pdf"])


# ---------------------------------------------------------------------------
# import_docx_fidelity --rollback semantics
# ---------------------------------------------------------------------------


class FidelityRollbackTests(TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="w10_fidelity_")
        self._media = tempfile.mkdtemp(prefix="w10_fidelity_media_")
        self._override = override_settings(MEDIA_ROOT=self._media)
        self._override.enable()
        self.path = os.path.join(self.dir, "cms_mock.txt")
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write(MCQ_TEXT)
        self.report = os.path.join(self.dir, "report.json")
        # First import, approved and published.
        self.old_batch = ingest_path(self.path, force=True)
        ExtractedQuestion.objects.filter(material__batch=self.old_batch).update(status="approved")
        for eq in ExtractedQuestion.objects.filter(material__batch=self.old_batch):
            self.assertTrue(publish_extracted_question(eq))
        self.old_ids = list(Question.objects.values_list("id", flat=True))
        self.assertEqual(len(self.old_ids), 2)

    def tearDown(self):
        self._override.disable()
        shutil.rmtree(self.dir, ignore_errors=True)
        shutil.rmtree(self._media, ignore_errors=True)

    def _run(self, *flags):
        out = io.StringIO()
        call_command("import_docx_fidelity", self.path, "--force", "--report", self.report,
                     *flags, stdout=out)
        return out.getvalue()

    def test_rollback_keeps_published_questions_live(self):
        out = self._run("--rollback")
        self.assertIn("2 published question(s) kept live", out)
        self.assertEqual(Question.objects.filter(id__in=self.old_ids, is_active=True).count(), 2)
        self.assertFalse(RemovedQuestion.objects.exists())
        self.old_batch.refresh_from_db()
        self.assertEqual(self.old_batch.status, "cancelled")
        self.assertEqual(sorted(self.old_batch.summary["rollback"]["published_question_ids"]),
                         sorted(self.old_ids))
        self.assertEqual(self.old_batch.materials.count(), 0)
        # The re-import created a new batch with fresh staging rows.
        self.assertEqual(ImportBatch.objects.exclude(pk=self.old_batch.pk).count(), 1)

    def test_remove_published_takes_the_old_questions_out_of_the_bank(self):
        out = self._run("--rollback", "--remove-published")
        self.assertIn("2 published question(s) removed from the bank", out)
        self.assertEqual(Question.objects.filter(id__in=self.old_ids, is_active=True).count(), 0)
        self.assertEqual(RemovedQuestion.objects.filter(original_question_id__in=self.old_ids).count(), 2)

    def test_remove_published_needs_rollback(self):
        with self.assertRaises(CommandError):
            self._run("--remove-published")
        self.assertEqual(Question.objects.filter(id__in=self.old_ids, is_active=True).count(), 2)

    def test_no_build_publishes_without_building_tests(self):
        cmd = "material_importer.management.commands.import_docx_fidelity"
        with patch(f"{cmd}.publish_batch", return_value=0) as only_publish, \
                patch(f"{cmd}.publish_batch_and_build_tests") as publish_and_build:
            self._run("--publish", "--no-build")
        only_publish.assert_called_once()
        publish_and_build.assert_not_called()
