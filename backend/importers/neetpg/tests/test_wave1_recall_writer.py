"""Regression tests for the recall importer fixes (wave 1, group G11).

H8  images are linked by page, never to "the first question of the PDF"
H9  re-imports never overwrite admin-corrected rows; no "A" default; no
    first-Subject fallback; exam comes from the writer
M12 the recall importer API is admin-only, lists/details work, run_id and
    source_dir are validated
L7  the INI-CET views dispatch the INI-CET task
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from importers.image_linking import link_images_by_page
from importers.neetpg.db_writer import DjangoWriter
from importers.neetpg.models import ImageRecord, ParsedOption, ParsedQuestion
from questions.models import (
    Question,
    QuestionExtractionItem,
    QuestionImage,
    QuestionImportJob,
    QuestionSource,
    RecallSource,
    Subject,
)

User = get_user_model()


def _pq(stem, *, page=1, qno=1, answer=("B",), subject="Anatomy", image_based=False):
    return ParsedQuestion(
        source_sha16="s" * 16, page_number=page, question_number_in_pdf=qno,
        stem=stem, stem_raw=stem,
        options=[ParsedOption("A", "Median"), ParsedOption("B", "Ulnar"),
                 ParsedOption("C", "Radial"), ParsedOption("D", "Axillary")],
        answer_labels=list(answer), explanation="", subject=subject,
        is_image_based=image_based, confidence_score=0.9,
    )


class _WriterCase(TestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp(prefix="g11_recall_media_")
        self._override = override_settings(MEDIA_ROOT=self.media)
        self._override.enable()
        self.anatomy = Subject.objects.create(name="Anatomy", code="ANAY", exam_type="neet_pg")
        self.rs = RecallSource.objects.create(
            pdf_filename="NEET-PG-2021-recall.pdf", pdf_path="/x/recall.pdf",
            pdf_sha256="1" * 64, pdf_sha256_short="1" * 16,
        )

    def tearDown(self):
        self._override.disable()
        shutil.rmtree(self.media, ignore_errors=True)


class WriterNeverGuessesTests(_WriterCase):
    def test_new_question_without_answer_goes_to_review_not_live(self):
        w = DjangoWriter()
        self.assertIsNone(w.write_question(_pq("Which nerve is injured here?", answer=()), self.rs))
        self.assertEqual(Question.objects.count(), 0)
        self.assertEqual(QuestionExtractionItem.objects.count(), 1)
        self.assertEqual(w.stats.questions_staged_for_review, 1)

    def test_answer_beyond_d_is_not_stored(self):
        w = DjangoWriter()
        self.assertIsNone(w.write_question(_pq("Five option question?", answer=("E",)), self.rs))
        self.assertEqual(Question.objects.count(), 0)

    def test_unresolved_subject_is_not_given_the_first_subject(self):
        Subject.objects.create(name="Aaa Sorts First", code="AAAY")
        w = DjangoWriter()
        self.assertIsNone(w.write_question(_pq("Unmapped stem?", subject=None), self.rs))
        self.assertEqual(Question.objects.count(), 0)

    def test_exam_type_and_source_follow_the_writer(self):
        w = DjangoWriter(exam_type="fmge")
        q = w.write_question(_pq("FMGE recall about the ulnar nerve?"), self.rs)
        self.assertEqual((q.exam_type, q.exam_source), ("fmge", "FMGE (recall)"))

    def test_inicet_writer_is_exam_fixed(self):
        from importers.inicet.db_writer import DjangoWriter as IniWriter
        q = IniWriter().write_question(_pq("INI-CET recall about the ulnar nerve?"), self.rs)
        self.assertEqual((q.exam_type, q.exam_source), ("ini_cet", "INI-CET (recall)"))


class WriterProtectsExistingRowsTests(_WriterCase):
    def test_reimport_keeps_admin_corrections(self):
        w = DjangoWriter()
        q = w.write_question(_pq("Which nerve is injured in wrist drop?"), self.rs)
        Question.objects.filter(pk=q.pk).update(correct_answer="C", explanation="Admin text",
                                                admin_edited=True)
        again = DjangoWriter().write_question(_pq("Which nerve is injured in wrist drop?",
                                                  answer=("A",)), self.rs)
        self.assertEqual(again.pk, q.pk)
        q.refresh_from_db()
        self.assertEqual((q.correct_answer, q.explanation), ("C", "Admin text"))

    def test_reimport_only_fills_empty_fields_on_unprotected_rows(self):
        w = DjangoWriter()
        q = w.write_question(_pq("Which nerve is injured in claw hand?"), self.rs)
        Question.objects.filter(pk=q.pk).update(correct_answer="D", explanation="")
        p = _pq("Which nerve is injured in claw hand?", answer=("A",))
        p.explanation = "Parser explanation"
        DjangoWriter().write_question(p, self.rs)
        q.refresh_from_db()
        self.assertEqual(q.correct_answer, "D", "existing answer must not be overwritten")
        self.assertEqual(q.explanation, "Parser explanation", "empty field may be filled")

    def test_rollback_matches_exact_ref_and_keeps_shared_questions(self):
        w = DjangoWriter(source_job_ref="ingestion:5")
        own = w.write_question(_pq("Own question of job five?"), self.rs)
        shared = w.write_question(_pq("Shared question?", qno=2), self.rs)
        other_rs = RecallSource.objects.create(pdf_filename="b.pdf", pdf_path="/x/b.pdf",
                                               pdf_sha256="2" * 64, pdf_sha256_short="2" * 16)
        QuestionSource.objects.create(question=shared, recall_source=other_rs, page_number=1,
                                      question_number_in_pdf=1, import_job_id="77")
        self.assertEqual(DjangoWriter(source_job_ref="ingestion:5").rollback_for_job(), 1)
        own.refresh_from_db()
        shared.refresh_from_db()
        self.assertFalse(own.is_active)
        self.assertTrue(shared.is_active)
        self.assertEqual(DjangoWriter(source_job_ref="").rollback_for_job(), 0)


class ImageLinkingTests(_WriterCase):
    def _img(self, page, idx, sha):
        path = Path(self.media) / f"p{page}_{idx}.png"
        from PIL import Image
        Image.new("RGB", (3, 3), (page * 20, idx * 40, 90)).save(path, format="PNG")
        return ImageRecord(source_sha16="s" * 16, page_number=page, image_index_in_page=idx,
                           file_path=str(path), sha256=sha * 4, sha256_short=sha)

    def test_images_go_to_their_page_and_ambiguous_ones_are_flagged(self):
        w = DjangoWriter()
        written = []
        for p in (
            _pq("Page one text question?", page=1, qno=1),
            _pq("Page one image question?", page=1, qno=2, image_based=True),
            _pq("Only question on page two?", page=2, qno=3),
            _pq("Page three first figure?", page=3, qno=4, image_based=True),
            _pq("Page three second figure?", page=3, qno=5, image_based=True),
        ):
            written.append((p, w.write_question(p, self.rs)))
        by_qno = {p.question_number_in_pdf: row for p, row in written}
        images = [self._img(1, 0, "a" * 16), self._img(2, 0, "b" * 16), self._img(3, 0, "c" * 16)]
        # A logo repeated on three pages is decorative and never attached.
        images += [self._img(pg, 9, "f" * 16) for pg in (1, 2, 3)]

        stats = link_images_by_page(w, written, images, self.rs)

        self.assertEqual(stats["images_linked"], 2)
        self.assertEqual(stats["images_decorative_skipped"], 3)
        self.assertEqual(stats["images_unlinked"], 1)
        self.assertEqual(list(QuestionImage.objects.filter(question=by_qno[2]).values_list("sha256_short", flat=True)), ["a" * 16])
        self.assertEqual(list(QuestionImage.objects.filter(question=by_qno[3]).values_list("sha256_short", flat=True)), ["b" * 16])
        self.assertFalse(QuestionImage.objects.filter(question=by_qno[1]).exists(),
                         "the first question of the PDF must not collect other images")
        by_qno[4].refresh_from_db()
        by_qno[5].refresh_from_db()
        self.assertTrue(by_qno[4].needs_review and by_qno[5].needs_review)


class RecallApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="g11_recall_admin", password="x",
                                              is_superuser=True, is_staff=True)
        self.student = User.objects.create_user(username="g11_recall_student", password="x")
        self.job = QuestionImportJob.objects.create(job_type="pdf", status="completed",
                                                    source_filename="dir")
        self.client = APIClient()

    def test_list_and_detail_work_for_admin_only(self):
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get("/api/imports/neetpg/jobs/").status_code, 403)
        self.assertEqual(self.client.get(f"/api/imports/neetpg/jobs/{self.job.id}/").status_code, 403)
        self.client.force_authenticate(self.admin)
        r = self.client.get("/api/imports/neetpg/jobs/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data[0]["id"], self.job.id)
        r = self.client.get(f"/api/imports/neetpg/jobs/{self.job.id}/")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("stored_file_path", r.data)

    def test_report_is_admin_only_and_rejects_traversal(self):
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get("/api/imports/neetpg/reports/run1/").status_code, 403)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get("/api/imports/neetpg/reports/..%2F..%2Fsecrets/").status_code, 404)
        self.assertEqual(self.client.get("/api/imports/neetpg/reports/no-such-run/").status_code, 404)

    def test_source_dir_must_be_inside_an_allowed_root(self):
        self.client.force_authenticate(self.admin)
        outside = tempfile.mkdtemp(prefix="g11_outside_")
        allowed = tempfile.mkdtemp(prefix="g11_allowed_")
        try:
            with patch.dict("os.environ", {"RECALL_IMPORT_ALLOWED_ROOTS": allowed}):
                r = self.client.post("/api/imports/neetpg/jobs/", {"source_dir": outside}, format="json")
                self.assertEqual(r.status_code, 400)
                with patch("django_q.tasks.async_task", return_value="t-1") as task:
                    r = self.client.post("/api/imports/neetpg/jobs/", {"source_dir": allowed}, format="json")
                self.assertEqual(r.status_code, 202, r.data)
                self.assertEqual(task.call_args[0][0], "importers.neetpg.tasks.run_recall_import")
        finally:
            shutil.rmtree(outside, ignore_errors=True)
            shutil.rmtree(allowed, ignore_errors=True)

    def test_inicet_views_dispatch_the_inicet_task(self):
        from importers.inicet import views as ini_views
        self.assertEqual(ini_views.ImportJobListView.task_path, "importers.inicet.tasks.run_recall_import")
        self.assertEqual(ini_views.ImportJobRetryView.task_path, "importers.inicet.tasks.run_recall_import")
        self.assertEqual(ini_views.ImportReportView.config_module, "importers.inicet.config")
