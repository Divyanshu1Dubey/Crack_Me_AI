"""Regression tests for the Import Center fixes (wave 1, group G11).

Covers: upload fills the batch it returns (H1); auto-test rebuild / rollback
only touch this batch's own tests and never delete attempted tests (H3);
rollback with delete_published really removes the live questions (M2);
background publish (M3); cancel semantics (M4); dedup keyed on stem +
options (M1); raster-only images (M6); PYQ year from the file name (L8);
image copy through storage (L9); build_for_batch filters before slicing
(L10); zip limits (L13); generate-mock strategies (L4); health (L5); and
no question is ever published without a valid answer.
"""
from __future__ import annotations

import io
import shutil
import tempfile
import zipfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from material_importer import api_views
from material_importer.duplicate_detector import DuplicateDetector
from material_importer.ingest_service import _persist_parsed_document, _store_image, ingest_path
from material_importer.mock_test_builder import (
    build_for_batch,
    delete_batch,
    publish_batch,
)
from material_importer.models import (
    ExtractedQuestion,
    ImportAuditLog,
    ImportBatch,
    ImportedImage,
    ImportMaterial,
)
from material_importer.parser.dataclasses import ParsedDocument, ParsedQuestion
from material_importer.publishing import publish_extracted_question, year_from_filename
from questions.models import Question, QuestionImage, RemovedQuestion, Subject
from tests_engine.models import Test, TestAttempt

User = get_user_model()


def _inline_background(target, *, name):  # replaces the daemon thread in tests
    target()


def _png_bytes() -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), (200, 30, 30)).save(buf, format="PNG")
    return buf.getvalue()


SVG_BYTES = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'


def _docx_bytes() -> bytes:
    from docx import Document
    buf = io.BytesIO()
    Document().save(buf)
    return buf.getvalue()


class _MediaTempMixin:
    def setUp(self):
        super().setUp()
        self._media = tempfile.mkdtemp(prefix="g11_media_")
        self._override = override_settings(MEDIA_ROOT=self._media)
        self._override.enable()

    def tearDown(self):
        self._override.disable()
        shutil.rmtree(self._media, ignore_errors=True)
        super().tearDown()


class _BatchFactoryMixin:
    """Helpers to build a batch with published staging rows."""

    def make_subject(self, name="Surgery", code="SURX"):
        return Subject.objects.get_or_create(name=name, defaults={"code": code, "exam_type": "cms"})[0]

    def make_batch(self, batch_id=None, status="completed", label="Test batch"):
        kwargs = {"source_label": label, "root_path": "/tmp/x", "status": status}
        if batch_id is not None:
            kwargs["id"] = batch_id
        return ImportBatch.objects.create(**kwargs)

    def make_material(self, batch, filename="surgery.docx"):
        return ImportMaterial.objects.create(
            batch=batch, original_filename=filename, file_format="docx",
            file_size_bytes=10, file_sha256="f" * 64,
        )

    def make_eq(self, material, idx, *, subject=None, publish=True, answer="B", status="approved"):
        eq = ExtractedQuestion.objects.create(
            material=material, position_index=idx,
            question_text=f"Question {material.id}-{idx}: which nerve is injured?",
            option_a="Median", option_b="Ulnar", option_c="Radial", option_d="Axillary",
            correct_answer=answer, content_hash=f"h{material.id}-{idx}",
            subject=subject, status=status,
        )
        if publish:
            self.assertTrue(publish_extracted_question(eq))
            eq.refresh_from_db()
        return eq


# ---------------------------------------------------------------------------
# H1 — upload fills the batch it returns
# ---------------------------------------------------------------------------


class UploadFillsReturnedBatchTests(_MediaTempMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_user(username="g11_admin", password="x",
                                              is_staff=True, is_superuser=True)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    @patch.object(api_views, "_start_background", _inline_background)
    def test_returned_batch_completes_and_owns_the_material(self):
        f = SimpleUploadedFile("tiny.docx", _docx_bytes())
        with self.captureOnCommitCallbacks(execute=True):
            r = self.client.post("/api/admin/import/upload/",
                                 {"files": f, "source_label": "H1"}, format="multipart")
        self.assertEqual(r.status_code, 201, r.data)
        batch = ImportBatch.objects.get(pk=r.data["batch_id"])
        self.assertEqual(ImportBatch.objects.count(), 1, "ingest must not create a second batch")
        self.assertIn(batch.status, {"completed", "partial"})
        self.assertEqual(batch.files_processed, 1)
        self.assertEqual(batch.materials.count(), 1)
        self.assertEqual(batch.materials.first().original_filename, "tiny.docx")
        # The upload metadata survives the end-of-ingest summary write.
        self.assertEqual(batch.summary.get("uploaded_files"), ["tiny.docx"])
        self.assertTrue(ImportAuditLog.objects.filter(batch=batch, code="ingest_done").exists())

    def test_cancelled_batch_is_not_restarted(self):
        work = tempfile.mkdtemp(dir=self._media)
        with open(f"{work}/a.txt", "w", encoding="utf-8") as fh:
            fh.write("Q1. Test?\nA. a\nB. b\nC. c\nD. d\nAnswer: A\n")
        batch = ImportBatch.objects.create(source_label="c", root_path=work, status="cancelled")
        out = ingest_path(path=work, batch=batch)
        self.assertEqual(out.status, "cancelled")
        self.assertEqual(out.materials.count(), 0)

    def test_cancel_between_files_stops_the_loop(self):
        work = tempfile.mkdtemp(dir=self._media)
        for name in ("a.txt", "b.txt", "c.txt"):
            with open(f"{work}/{name}", "w", encoding="utf-8") as fh:
                fh.write("Some notes.\n")
        batch = ImportBatch.objects.create(source_label="c", root_path=work, status="queued")
        from material_importer.parser import ParserFactory
        real_parse = ParserFactory.parse

        def parse_then_cancel(factory_self, path):
            ImportBatch.objects.filter(pk=batch.pk).update(status="cancelled")
            return real_parse(factory_self, path)

        with patch.object(ParserFactory, "parse", parse_then_cancel):
            out = ingest_path(path=work, batch=batch, force=True)
        self.assertEqual(out.status, "cancelled")
        self.assertEqual(out.materials.count(), 1, "loop must stop after the cancel")


# ---------------------------------------------------------------------------
# M4 — cancel is only for queued/processing batches
# ---------------------------------------------------------------------------


class CancelEndpointTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="g11_admin2", password="x",
                                              is_staff=True, is_superuser=True)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_partial_batch_cannot_be_cancelled(self):
        b = ImportBatch.objects.create(source_label="p", root_path="/tmp", status="partial")
        r = self.client.post(f"/api/admin/import/batches/{b.id}/cancel/")
        self.assertEqual(r.status_code, 409)

    def test_queued_batch_can_be_cancelled(self):
        b = ImportBatch.objects.create(source_label="q", root_path="/tmp", status="queued")
        r = self.client.post(f"/api/admin/import/batches/{b.id}/cancel/")
        self.assertEqual(r.status_code, 200)
        b.refresh_from_db()
        self.assertEqual(b.status, "cancelled")


# ---------------------------------------------------------------------------
# H3 / L10 / M2 — auto-test ownership, attempts survive, rollback
# ---------------------------------------------------------------------------


class AutoTestOwnershipTests(_MediaTempMixin, _BatchFactoryMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.student = User.objects.create_user(username="g11_student", password="x")
        self.subject = self.make_subject()
        self.batch = self.make_batch(batch_id=41)
        self.other_batch = self.make_batch(batch_id=410)
        m = self.make_material(self.batch)
        self.eqs = [self.make_eq(m, i, subject=self.subject) for i in range(3)]
        # Tests that a substring match on "batch 41" used to destroy.
        self.other_auto = Test.objects.create(title="Auto • Mixed • batch 410", test_type="mixed")
        self.unrelated = Test.objects.create(title="Weekly practice Batch 41 revision", test_type="mixed")
        TestAttempt.objects.create(user=self.student, test=self.other_auto)

    def test_rebuild_keeps_published_attempted_test_and_ignores_other_batches(self):
        self.assertEqual(build_for_batch(41), 2)  # subject test + mixed test
        mixed = Test.objects.get(title="Auto • Mixed • batch 41")
        mixed.is_published = True
        mixed.save(update_fields=["is_published"])
        attempt = TestAttempt.objects.create(user=self.student, test=mixed)

        self.assertEqual(build_for_batch(41), 2)  # republish

        mixed_after = Test.objects.get(title="Auto • Mixed • batch 41")
        self.assertEqual(mixed_after.id, mixed.id, "rebuild must upsert, not recreate")
        self.assertTrue(mixed_after.is_published, "admin publish flag must survive a rebuild")
        self.assertTrue(TestAttempt.objects.filter(pk=attempt.pk).exists())
        self.assertTrue(Test.objects.filter(pk=self.other_auto.pk).exists())
        self.assertTrue(Test.objects.filter(pk=self.unrelated.pk).exists())
        self.assertEqual(mixed_after.num_questions, 3)
        self.assertEqual(mixed_after.questions.count(), 3)

    def test_rollback_unpublishes_attempted_tests_and_deletes_the_rest(self):
        build_for_batch(41)
        mixed = Test.objects.get(title="Auto • Mixed • batch 41")
        attempt = TestAttempt.objects.create(user=self.student, test=mixed)
        subject_test = Test.objects.get(title=f"Auto • {self.subject.name} • batch 41")

        result = delete_batch(41)

        self.assertEqual(result["tests"], 1)
        self.assertEqual(result["tests_unpublished"], 1)
        self.assertFalse(Test.objects.filter(pk=subject_test.pk).exists())
        mixed.refresh_from_db()
        self.assertFalse(mixed.is_published)
        self.assertTrue(TestAttempt.objects.filter(pk=attempt.pk).exists())
        # Other batch's test and an unrelated "batch 41" title are untouched.
        self.assertTrue(Test.objects.filter(pk=self.other_auto.pk).exists())
        self.assertTrue(TestAttempt.objects.filter(test=self.other_auto).exists())
        self.assertTrue(Test.objects.filter(pk=self.unrelated.pk).exists())

    def test_rollback_keeps_published_questions_live_by_default_but_traceable(self):
        result = delete_batch(41)
        ids = [eq.published_question_id for eq in self.eqs]
        self.assertEqual(sorted(result["published_question_ids"]), sorted(ids))
        self.assertEqual(Question.objects.filter(id__in=ids, is_active=True).count(), 3)
        self.assertEqual(result["published_questions_removed"], 0)

    def test_rollback_delete_published_removes_questions_from_bank(self):
        ids = [eq.published_question_id for eq in self.eqs]
        result = delete_batch(41, delete_published=True)
        self.assertEqual(result["published_questions_removed"], 3)
        self.assertEqual(Question.objects.filter(id__in=ids, is_active=True).count(), 0)
        self.assertEqual(Question.objects.filter(id__in=ids, is_dropped=True).count(), 3)
        self.assertEqual(RemovedQuestion.objects.filter(original_question_id__in=ids).count(), 3)

    def test_stale_auto_test_retired_on_rebuild(self):
        build_for_batch(41)
        subject_test = Test.objects.get(title=f"Auto • {self.subject.name} • batch 41")
        # All questions lose their subject → the subject bucket disappears.
        ExtractedQuestion.objects.filter(material__batch_id=41).update(subject=None, inferred_subject="")
        build_for_batch(41)
        self.assertFalse(Test.objects.filter(pk=subject_test.pk).exists())


class BuildFiltersBeforeSlicingTests(_MediaTempMixin, _BatchFactoryMixin, TestCase):
    def test_unpublished_leading_rows_do_not_empty_the_test(self):
        subject = self.make_subject()
        batch = self.make_batch()
        m = self.make_material(batch)
        self.make_eq(m, 0, subject=subject, publish=False, status="pending")
        self.make_eq(m, 1, subject=subject, publish=False, status="pending")
        self.make_eq(m, 2, subject=subject)
        self.make_eq(m, 3, subject=subject)

        built = build_for_batch(batch.id, max_per_test=2)

        self.assertEqual(built, 2)
        mixed = Test.objects.get(title=f"Auto • Mixed • batch {batch.id}")
        self.assertEqual(mixed.questions.count(), 2)
        self.assertEqual(mixed.num_questions, 2)

    def test_no_live_questions_builds_and_counts_nothing(self):
        batch = self.make_batch()
        m = self.make_material(batch)
        self.make_eq(m, 0, publish=False, status="pending")
        self.assertEqual(build_for_batch(batch.id), 0)
        self.assertFalse(Test.objects.filter(title__endswith=f"batch {batch.id}").exists())


# ---------------------------------------------------------------------------
# Never publish without a valid answer
# ---------------------------------------------------------------------------


class AnswerGuardTests(_MediaTempMixin, _BatchFactoryMixin, TestCase):
    def test_question_without_answer_is_not_published(self):
        m = self.make_material(self.make_batch())
        eq = self.make_eq(m, 0, publish=False, answer="")
        self.assertFalse(publish_extracted_question(eq))
        eq.refresh_from_db()
        self.assertIsNone(eq.published_question_id)
        self.assertEqual(eq.status, "needs_review")
        self.assertEqual(Question.objects.count(), 0)

    def test_ingest_flags_missing_answer_as_needs_review(self):
        m = self.make_material(self.make_batch())
        doc = ParsedDocument(source_filename="x.docx", file_format="docx", detected_type="mcq_classic")
        doc.questions = [ParsedQuestion(position_index=0, question_text="Which drug is used?",
                                        option_a="A1", option_b="B1", option_c="C1", option_d="D1",
                                        correct_answer="")]
        _persist_parsed_document(m, doc, DuplicateDetector(), use_ai=False)
        self.assertEqual(ExtractedQuestion.objects.get(material=m).status, "needs_review")


# ---------------------------------------------------------------------------
# M1 — dedup keys on stem + options; duplicates staged, not dropped
# ---------------------------------------------------------------------------


class DedupStemPlusOptionsTests(_MediaTempMixin, _BatchFactoryMixin, TestCase):
    STEM = "Which of the following is not true?"

    def _doc(self, *questions):
        doc = ParsedDocument(source_filename="x.docx", file_format="docx", detected_type="mcq_classic")
        doc.questions = list(questions)
        return doc

    def _q(self, idx, opts, answer="A"):
        return ParsedQuestion(position_index=idx, question_text=self.STEM,
                              option_a=opts[0], option_b=opts[1], option_c=opts[2],
                              option_d=opts[3], correct_answer=answer)

    def test_same_generic_stem_different_options_are_both_kept(self):
        batch = self.make_batch()
        m = self.make_material(batch)
        dedup = DuplicateDetector()
        s = _persist_parsed_document(m, self._doc(
            self._q(0, ["Aspirin is an NSAID", "Insulin is a peptide", "Heparin is oral", "Warfarin is a coumarin"]),
            self._q(1, ["Liver makes bile", "Kidney makes urine", "Heart makes insulin", "Lung exchanges gas"]),
            # exact copy of #0 with shuffled options inside the same file → skipped
            self._q(2, ["Insulin is a peptide", "Aspirin is an NSAID", "Warfarin is a coumarin", "Heparin is oral"]),
        ), dedup, use_ai=False)
        self.assertEqual(s["questions_saved"], 2)
        self.assertEqual(s["questions_deduplicated"], 1)
        self.assertEqual(ExtractedQuestion.objects.filter(material=m).count(), 2)

        # The same question in ANOTHER file is staged as a visible duplicate.
        m2 = self.make_material(batch, filename="other.docx")
        s2 = _persist_parsed_document(m2, self._doc(
            self._q(0, ["Aspirin is an NSAID", "Insulin is a peptide", "Heparin is oral", "Warfarin is a coumarin"]),
        ), dedup, use_ai=False)
        self.assertEqual(s2["questions_saved"], 0)
        self.assertEqual(s2["duplicates_staged"], 1)
        dup = ExtractedQuestion.objects.get(material=m2)
        self.assertEqual(dup.status, "duplicate")
        self.assertIsNotNone(dup.duplicate_of_id)


# ---------------------------------------------------------------------------
# M6 / L9 — raster-only images, stored_path is a storage name
# ---------------------------------------------------------------------------


class ImageSafetyTests(_MediaTempMixin, _BatchFactoryMixin, TestCase):
    def test_svg_is_never_stored_and_png_is(self):
        m = self.make_material(self.make_batch())
        self.assertIsNone(_store_image(m, 0, SVG_BYTES, "image/svg+xml", "evil.svg"))
        # A PNG claimed as SVG is stored by its real type.
        name, url, mime = _store_image(m, 1, _png_bytes(), "image/svg+xml", "x.svg")
        self.assertTrue(name.endswith(".png"))
        self.assertEqual(mime, "image/png")

    def test_published_question_gets_its_own_image_copy_and_never_svg(self):
        subject = self.make_subject()
        m = self.make_material(self.make_batch())
        name, url, mime = _store_image(m, 0, _png_bytes(), "image/png", "fig1.png")
        png = ImportedImage.objects.create(material=m, original_filename="fig1.png",
                                           stored_path=name, public_url=url, mime_type=mime,
                                           size_bytes=10, sha256="a" * 64)
        svg = ImportedImage.objects.create(material=m, original_filename="evil.svg",
                                           stored_path="imported/evil.svg", public_url="/media/imported/evil.svg",
                                           mime_type="image/svg+xml", size_bytes=10, sha256="b" * 64)
        eq = self.make_eq(m, 0, subject=subject, publish=False)
        png.linked_questions.add(eq)
        svg.linked_questions.add(eq)

        self.assertTrue(publish_extracted_question(eq))
        eq.refresh_from_db()
        images = list(QuestionImage.objects.filter(question_id=eq.published_question_id))
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0].mime, "image/png")
        self.assertTrue(images[0].file, "the live question must own a file copy")


# ---------------------------------------------------------------------------
# L8 — PYQ year from the file name only
# ---------------------------------------------------------------------------


class YearFromFilenameTests(TestCase):
    def test_year_rules(self):
        self.assertEqual(year_from_filename("UPSC_CMS_PYQ_2019_Paper1.docx"), 2019)
        self.assertEqual(year_from_filename("cms pyqs 2015-2023.docx"), 0)
        self.assertEqual(year_from_filename("surgery_mocktest.docx"), 0)
        self.assertEqual(year_from_filename("future_2099.docx"), 0)

    def test_stem_year_is_ignored(self):
        subject = Subject.objects.create(name="PSM X", code="PSMX", exam_type="cms")
        batch = ImportBatch.objects.create(source_label="y", root_path="/tmp", status="completed")
        m = ImportMaterial.objects.create(batch=batch, original_filename="psm_notes.docx",
                                          file_format="docx", file_size_bytes=1, file_sha256="e" * 64)
        eq = ExtractedQuestion.objects.create(
            material=m, position_index=0,
            question_text="In 2015, WHO launched which strategy?",
            option_a="End TB", option_b="DOTS", option_c="Stop TB", option_d="RNTCP",
            correct_answer="A", content_hash="yy", subject=subject, status="approved",
        )
        self.assertTrue(publish_extracted_question(eq))
        eq.refresh_from_db()
        self.assertEqual(eq.published_question.year, 0)


# ---------------------------------------------------------------------------
# M3 / L4 / L5 / L13 — endpoints
# ---------------------------------------------------------------------------


class ImportCenterEndpointTests(_MediaTempMixin, _BatchFactoryMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_user(username="g11_admin3", password="x",
                                              is_staff=True, is_superuser=True)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    @patch.object(api_views, "_start_background", _inline_background)
    def test_publish_runs_in_background_and_records_state(self):
        subject = self.make_subject()
        batch = self.make_batch()
        m = self.make_material(batch)
        self.make_eq(m, 0, subject=subject, publish=False)
        with self.captureOnCommitCallbacks(execute=True):
            r = self.client.post(f"/api/admin/import/batches/{batch.id}/publish/", {}, format="json")
        self.assertEqual(r.status_code, 202, r.data)
        self.assertEqual(r.data["publish"]["state"], "running")
        batch.refresh_from_db()
        state = batch.summary["publish"]
        self.assertEqual(state["state"], "done")
        self.assertEqual(state["published"], 1)
        self.assertEqual(state["tests_built"], 2)

    def test_publish_refused_while_parsing(self):
        batch = self.make_batch(status="processing")
        r = self.client.post(f"/api/admin/import/batches/{batch.id}/publish/", {}, format="json")
        self.assertEqual(r.status_code, 409)

    def test_generate_mock_random_and_image_based(self):
        subject = self.make_subject()
        batch = self.make_batch()
        m = self.make_material(batch)
        eqs = [self.make_eq(m, i, subject=subject) for i in range(5)]
        ExtractedQuestion.objects.filter(pk=eqs[0].pk).update(image_refs=["image1.png"])

        r = self.client.post(f"/api/admin/import/batches/{batch.id}/generate-mock/",
                             {"strategy": "image_based", "question_count": 10}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["question_count"], 1)
        t = Test.objects.get(pk=r.data["test_id"])
        self.assertEqual(t.num_questions, 1)
        self.assertEqual(list(t.questions.values_list("id", flat=True)), [eqs[0].published_question_id])

        r = self.client.post(f"/api/admin/import/batches/{batch.id}/generate-mock/",
                             {"strategy": "random", "question_count": 3}, format="json")
        self.assertEqual(r.data["question_count"], 3)
        batch.refresh_from_db()
        self.assertEqual(len(batch.summary["mock_test_ids"]), 2)
        # Rollback retires the generated mocks too.
        delete_batch(batch.id)
        self.assertFalse(Test.objects.filter(id__in=batch.summary["mock_test_ids"]).exists())

    def test_health_reports_parsers_and_libraries(self):
        r = self.client.get("/api/admin/import/health/")
        self.assertEqual(r.status_code, 200)
        self.assertIn(".docx", r.data["checks"]["parsers"])
        self.assertNotIn("parsers_error", r.data["checks"])
        self.assertIn("parser_libraries", r.data["checks"])

    def _zip_upload(self, members: dict[str, bytes]):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            for name, data in members.items():
                zf.writestr(name, data)
        f = SimpleUploadedFile("bundle.zip", buf.getvalue(), content_type="application/zip")
        return self.client.post("/api/admin/import/upload/", {"files": f}, format="multipart")

    def test_zip_with_too_many_members_is_rejected(self):
        with patch.object(api_views, "MAX_ZIP_MEMBERS", 3):
            r = self._zip_upload({f"f{i}.txt": b"x" for i in range(5)})
        self.assertEqual(r.status_code, 400)
        self.assertTrue(any("limit" in s for s in r.data["rejected"]))

    def test_zip_expanding_past_the_limit_is_rejected(self):
        with patch.object(api_views, "MAX_ZIP_UNCOMPRESSED_BYTES", 1000):
            r = self._zip_upload({"big.txt": b"0" * 5000})
        self.assertEqual(r.status_code, 400)
        self.assertTrue(any("limit" in s for s in r.data["rejected"]))

    def test_zip_member_path_traversal_and_types_are_skipped(self):
        r = self._zip_upload({"../../evil.txt": b"x", "run.exe": b"MZ", "notes.txt": b"hello"})
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(any("run.exe" in s for s in r.data["files_rejected"]))
        import os
        for root, _dirs, files in os.walk(self._media):
            self.assertNotIn("run.exe", files)
        self.assertFalse(os.path.exists(os.path.join(self._media, "evil.txt")))
