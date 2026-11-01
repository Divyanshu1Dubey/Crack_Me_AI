"""Regression tests for the ingestion pipeline fixes (wave 1, group G11).

H4  the MCE db_writer stage writes no live questions; the gate is the only writer
H5  the job's chosen exam is used (profile + Question.exam_type/exam_source)
H7  QuestionSource carries "ingestion:<id>"; rollback touches only that job
H9  re-import never overwrites an admin-corrected question
M7  Stage-3 image files are persisted; a shared image is linked to both questions
L2  BatchRun counters follow job outcomes
L3  'auto-all' is no longer accepted and legacy configs import PR only
L12 only queued jobs run (atomic claim); run_pending skips dispatched jobs
plus: a PR question without a single valid answer / subject is held for review
"""
from __future__ import annotations

import io
import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from ingestion.conservative_gate import apply_qa_v2_verdict, source_job_ref
from ingestion.constants import QA_NEEDS_REVIEW, QA_PRODUCTION_READY
from ingestion.models import BatchRun, ImportJob, MaterialAsset, StagedQuestion
from questions.models import (
    Question,
    QuestionImage,
    QuestionSource,
    RecallSource,
    Subject,
)


def _png_bytes(color=(10, 120, 200)) -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (6, 6), color).save(buf, format="PNG")
    return buf.getvalue()


def _payload(stem, *, answer=("B",), page=1, qno=1, subject="Anatomy", image_ids=()):
    return {
        "id": f"p{page:03d}_q{qno:02d}",
        "stem": stem,
        "stem_raw": stem,
        "options": [
            {"label": "A", "text": "Median nerve"},
            {"label": "B", "text": "Ulnar nerve"},
            {"label": "C", "text": "Radial nerve"},
            {"label": "D", "text": "Axillary nerve"},
        ],
        "answer_labels": list(answer),
        "explanation": "Parser explanation.",
        "page_number": page,
        "question_number_in_pdf": qno,
        "confidence_score": 0.95,
        "subject": subject,
        "image_ids": list(image_ids),
    }


class _GateCase(TestCase):
    exam = "neet_pg"

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="g11_gate_"))
        self.media = tempfile.mkdtemp(prefix="g11_media_")
        self._media_override = override_settings(MEDIA_ROOT=self.media)
        self._media_override.enable()
        self.anatomy = Subject.objects.create(name="Anatomy", code="ANAX", exam_type="neet_pg")
        self.material = MaterialAsset.objects.create(
            sha256="a" * 64, sha256_short="a" * 16, original_filename="recall-paper.pdf",
            storage_path=str(self.tmp / "recall-paper.pdf"), file_size=1, page_count=2,
        )
        self.job = ImportJob.objects.create(
            material_asset=self.material, parent_exam=self.exam, status="processing",
        )

    def tearDown(self):
        self._media_override.disable()
        shutil.rmtree(self.tmp, ignore_errors=True)
        shutil.rmtree(self.media, ignore_errors=True)

    def write_qa(self, rows: list[tuple[str, dict]]):
        qa = self.tmp / "08_qa"
        qa.mkdir(parents=True, exist_ok=True)
        (qa / "per_question_qa.json").write_text(json.dumps([
            {"status": status, "page_number": p["page_number"],
             "question_number_in_pdf": p["question_number_in_pdf"],
             "failing_axes": [], "payload": p}
            for status, p in rows
        ]), encoding="utf-8")
        (qa / "summary.json").write_text("{}", encoding="utf-8")

    def write_stage3(self, page: int, images: list[dict]):
        d = self.tmp / "03_images"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"p{page:03d}.json").write_text(json.dumps({"images": images}), encoding="utf-8")

    def stage3_image(self, page: int, idx: int, data: bytes, sha16: str) -> dict:
        d = self.tmp / "03_images"
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"p{page:03d}_img{idx:02d}.png"
        path.write_bytes(data)
        return {"id": f"p{page:03d}_img{idx:02d}_{sha16}", "page_number": page,
                "image_index_in_page": idx, "file_path": str(path), "mime": "image/png",
                "width": 6, "height": 6, "bytes": len(data), "sha256": sha16 * 4,
                "sha256_short": sha16, "modality": "pathology_gross"}


class GateWritesWithChosenExamTests(_GateCase):
    exam = "ini_cet"

    def test_pr_question_imported_as_the_jobs_exam_with_namespaced_ref(self):
        self.write_qa([(QA_PRODUCTION_READY, _payload("Which nerve supplies the thenar muscles?"))])
        counts = apply_qa_v2_verdict(job=self.job, artefact_root=self.tmp)
        self.assertEqual(counts["imported"], 1)
        q = Question.objects.get()
        self.assertEqual(q.exam_type, "ini_cet")
        self.assertEqual(q.exam_source, "INI-CET (recall)")
        self.assertEqual(q.correct_answer, "B")
        self.assertEqual(q.subject, self.anatomy)
        src = QuestionSource.objects.get(question=q)
        self.assertEqual(src.import_job_id, source_job_ref(self.job))
        self.assertEqual(src.import_job_id, f"ingestion:{self.job.id}")

    def test_orchestrator_profile_follows_parent_exam(self):
        from ingestion.orchestrator import _profile_for
        named_neet = MaterialAsset(original_filename="NEET-PG-2021.pdf", sha256_short="b" * 16)
        self.assertEqual(_profile_for(named_neet, "ini_cet").exam_type, "ini_cet")
        self.assertEqual(_profile_for(named_neet, "").exam_type, "neet_pg")


class GateHoldsUnstorableQuestionsTests(_GateCase):
    def test_missing_answer_multi_answer_and_unknown_subject_are_held(self):
        self.write_qa([
            (QA_PRODUCTION_READY, _payload("No answer was parsed for this one?", answer=(), qno=1)),
            (QA_PRODUCTION_READY, _payload("Two answers were parsed for this one?", answer=("A", "C"), qno=2)),
            (QA_PRODUCTION_READY, _payload("Zzqx unrelated words only", subject="", qno=3)),
        ])
        counts = apply_qa_v2_verdict(job=self.job, artefact_root=self.tmp)
        self.assertEqual(Question.objects.count(), 0, "nothing may go live with a guessed answer/subject")
        self.assertEqual(counts["held"], 3)
        self.assertEqual(counts["imported"], 0)
        axes = sorted(tuple(sq.failing_axes) for sq in StagedQuestion.objects.filter(job=self.job))
        self.assertIn(("answer_not_single_a_to_d",), axes)
        self.assertIn(("subject_unresolved",), axes)
        self.assertTrue(all(sq.qa_status == QA_NEEDS_REVIEW for sq in StagedQuestion.objects.all()))
        self.job.refresh_from_db()
        self.assertEqual(self.job.questions_staged_nr, 3)

    def test_needs_review_never_imports_even_with_legacy_auto_all(self):
        self.job.config = {"strategy": "auto-all", "force": False}
        self.job.save(update_fields=["config"])
        self.write_qa([(QA_NEEDS_REVIEW, _payload("Needs review stem about the radial nerve?"))])
        counts = apply_qa_v2_verdict(job=self.job, artefact_root=self.tmp)
        self.assertEqual(Question.objects.count(), 0)
        self.assertEqual(counts["nr"], 1)

    def test_auto_all_is_not_accepted_by_the_api(self):
        from ingestion.serializers import CreateJobSerializer
        s = CreateJobSerializer(data={"material_sha16": "a" * 16, "parent_exam": "neet_pg",
                                      "strategy": "auto-all"})
        self.assertFalse(s.is_valid())
        self.assertIn("strategy", s.errors)


class GateNeverOverwritesAdminEditsTests(_GateCase):
    def test_reimport_keeps_admin_corrected_answer_and_explanation(self):
        stem = "Which nerve supplies the thenar muscles?"
        self.write_qa([(QA_PRODUCTION_READY, _payload(stem))])
        apply_qa_v2_verdict(job=self.job, artefact_root=self.tmp)
        q = Question.objects.get()
        Question.objects.filter(pk=q.pk).update(
            correct_answer="A", explanation="Admin-corrected explanation.", admin_edited=True,
        )
        retry = ImportJob.objects.create(material_asset=self.material, parent_exam="neet_pg",
                                         status="processing", retry_of=self.job, version=2)
        apply_qa_v2_verdict(job=retry, artefact_root=self.tmp)
        q.refresh_from_db()
        self.assertEqual(Question.objects.count(), 1)
        self.assertEqual(q.correct_answer, "A")
        self.assertEqual(q.explanation, "Admin-corrected explanation.")


class GatePersistsImagesTests(_GateCase):
    def test_image_file_is_persisted_and_shared_image_linked_to_both(self):
        data = _png_bytes()
        rec = self.stage3_image(1, 0, data, "c" * 16)
        self.write_stage3(1, [rec])
        self.write_qa([
            (QA_PRODUCTION_READY, _payload("Identify the nerve injury shown in image one?",
                                           qno=1, image_ids=[rec["id"]])),
            (QA_PRODUCTION_READY, _payload("Which lesion is shown in the same picture again?",
                                           qno=2, image_ids=[rec["id"]])),
        ])
        counts = apply_qa_v2_verdict(job=self.job, artefact_root=self.tmp)
        self.assertEqual(counts["imported"], 2)
        images = list(QuestionImage.objects.order_by("id"))
        self.assertEqual(len(images), 2, "each question must get its own image row")
        self.assertEqual({im.question_id for im in images}, set(Question.objects.values_list("id", flat=True)))
        self.assertTrue(all(im.file for im in images), "image rows must point at a stored file")
        self.assertEqual(images[0].file.name, images[1].file.name, "the file is shared, not copied")

    def test_question_with_missing_image_file_is_held(self):
        rec = self.stage3_image(1, 0, _png_bytes(), "d" * 16)
        Path(rec["file_path"]).unlink()
        self.write_stage3(1, [rec])
        self.write_qa([(QA_PRODUCTION_READY, _payload("Identify the lesion in the image?",
                                                      image_ids=[rec["id"]]))])
        counts = apply_qa_v2_verdict(job=self.job, artefact_root=self.tmp)
        self.assertEqual(Question.objects.count(), 0)
        self.assertEqual(counts["held"], 1)


class DbWriterStageWritesNothingLiveTests(TestCase):
    def test_pass_page_questions_are_not_written_by_the_stage(self):
        from mce.profiles import get_profile
        from mce.stages import MceContext
        from mce.stages.stage_db_writer import run

        root = Path(tempfile.mkdtemp(prefix="g11_dbw_"))
        try:
            (root / "08_qa").mkdir(parents=True)
            (root / "08_qa" / "summary.json").write_text("{}", encoding="utf-8")
            (root / "08_qa" / "per_page_report.json").write_text(
                json.dumps({"1": {"status": "PASS"}}), encoding="utf-8")
            (root / "07_structured").mkdir(parents=True)
            (root / "07_structured" / "_index.json").write_text(json.dumps({"questions": [
                {"id": "p001_q01", "page_number": 1, "stem": "Unanswered PASS-page stem?",
                 "options": [{"label": "A", "text": "x"}], "answer_labels": []},
            ]}), encoding="utf-8")
            Subject.objects.create(name="Aaa First Subject", code="AAAX")
            ctx = MceContext(pdf_path=root / "x.pdf", pdf_filename="x.pdf", pdf_sha256="e" * 64,
                             pdf_sha256_short="e" * 16, page_count=1,
                             profile=get_profile("neet_pg"), artefact_root=root)
            res = run(ctx)
            self.assertEqual(Question.objects.count(), 0)
            self.assertEqual(RecallSource.objects.count(), 0)
            self.assertFalse(res.metrics["orm_writes"])
            self.assertEqual(res.metrics["pending_for_phase3"], 1)
        finally:
            shutil.rmtree(root, ignore_errors=True)


class RollbackTests(_GateCase):
    def test_rollback_hits_only_this_jobs_questions(self):
        self.write_qa([(QA_PRODUCTION_READY, _payload("Which nerve supplies the thenar muscles?"))])
        apply_qa_v2_verdict(job=self.job, artefact_root=self.tmp)
        own = Question.objects.get()

        # A legacy recall-import question whose QuestionImportJob id equals
        # this ingestion job's id — the old rollback deactivated it.
        rs = RecallSource.objects.create(pdf_filename="legacy.pdf", pdf_path="/x/legacy.pdf",
                                         pdf_sha256="9" * 64, pdf_sha256_short="9" * 16)
        legacy = Question.objects.create(
            question_text="Legacy recall question?", option_a="a", option_b="b", option_c="c",
            option_d="d", correct_answer="A", year=2020, subject=self.anatomy, exam_type="neet_pg",
        )
        QuestionSource.objects.create(question=legacy, recall_source=rs, page_number=1,
                                      question_number_in_pdf=1, import_job_id=str(self.job.id))

        call_command("ingestion_rollback", str(self.job.id), stdout=io.StringIO())

        own.refresh_from_db()
        legacy.refresh_from_db()
        self.assertFalse(own.is_active)
        self.assertTrue(legacy.is_active)

    def test_rollback_with_nothing_matched_aborts(self):
        with self.assertRaises(CommandError):
            call_command("ingestion_rollback", str(self.job.id), stdout=io.StringIO())


@override_settings(INGESTION_ARTEFACT_ROOT=Path(tempfile.gettempdir()) / "g11_ingestion_artefacts")
class OrchestratorClaimAndBatchCountersTests(TestCase):
    def setUp(self):
        self.material = MaterialAsset.objects.create(
            sha256="7" * 64, sha256_short="7" * 16, original_filename="t.pdf",
            storage_path="/tmp/t.pdf", file_size=1, page_count=1,
        )
        self.batch = BatchRun.objects.create(name="b", status="running", total_jobs=2)

    @patch("ingestion.conservative_gate.apply_qa_v2_verdict")
    @patch("ingestion.pipeline_stages._import_callable")
    def test_batch_counters_follow_jobs(self, mock_callable, mock_gate):
        from mce.stages import StageResult
        from ingestion.orchestrator import cancel_job, run_full_pipeline_for_job
        mock_callable.return_value = lambda ctx, **kw: StageResult(stage="x")
        mock_gate.return_value = {"pr": 0, "nr": 0, "ef": 0, "staged": 0, "imported": 0, "held": 0}
        j1 = ImportJob.objects.create(material_asset=self.material, parent_exam="neet_pg",
                                      status="queued", batch_run=self.batch)
        j2 = ImportJob.objects.create(material_asset=self.material, parent_exam="neet_pg",
                                      status="queued", batch_run=self.batch)
        self.assertEqual(run_full_pipeline_for_job(j1.id)["status"], "completed")
        self.batch.refresh_from_db()
        self.assertEqual((self.batch.completed_jobs, self.batch.failed_jobs, self.batch.status),
                         (1, 0, "running"))
        cancel_job(j2)
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.status, "done")

    def test_only_queued_jobs_are_run(self):
        from ingestion.orchestrator import run_full_pipeline_for_job
        job = ImportJob.objects.create(material_asset=self.material, parent_exam="neet_pg",
                                       status="processing")
        with patch("ingestion.orchestrator._run_claimed_job") as run_claimed:
            res = run_full_pipeline_for_job(job.id)
        self.assertTrue(res["noop"])
        run_claimed.assert_not_called()

    def test_run_pending_skips_jobs_that_already_have_a_task(self):
        dispatched = ImportJob.objects.create(material_asset=self.material, parent_exam="neet_pg",
                                              status="queued", summary={"q_task_id": "abc"})
        fresh = ImportJob.objects.create(material_asset=self.material, parent_exam="neet_pg",
                                         status="queued")
        with patch("ingestion.management.commands.ingestion_run_pending.dispatch_job",
                   return_value="new-task") as dispatch:
            call_command("ingestion_run_pending", stdout=io.StringIO())
        dispatch.assert_called_once_with(fresh.id)
        fresh.refresh_from_db()
        self.assertEqual(fresh.summary["q_task_id"], "new-task")
        dispatched.refresh_from_db()
        self.assertEqual(dispatched.summary["q_task_id"], "abc")
