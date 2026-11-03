"""Wave 4 (Z8): the conservative gate holds a Production Ready question whose
stem or options carry an answer / explanation label.

The stem and the options are public text (list rows, test payloads, search
results), so "Ans: (c)" or "Explanation: ..." glued into them would give the
answer away; ``questions.answer_leak.label_hold_reasons`` names the hold.
"""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from django.test import TestCase, override_settings

from ingestion.conservative_gate import apply_qa_v2_verdict
from ingestion.constants import QA_NEEDS_REVIEW, QA_PRODUCTION_READY
from ingestion.models import ImportJob, MaterialAsset, StagedQuestion
from questions.models import Question, Subject


def _payload(stem, *, qno, options=None):
    texts = options or ["Median nerve", "Ulnar nerve", "Radial nerve", "Axillary nerve"]
    return {
        "id": f"p001_q{qno:02d}",
        "stem": stem,
        "stem_raw": stem,
        "options": [{"label": label, "text": text} for label, text in zip("ABCD", texts)],
        "answer_labels": ["B"],
        "explanation": "Parser explanation.",
        "page_number": 1,
        "question_number_in_pdf": qno,
        "confidence_score": 0.95,
        "subject": "Anatomy",
        "image_ids": [],
    }


class GateHoldsAnswerLabelsTests(TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="z8_gate_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        media = tempfile.mkdtemp(prefix="z8_gate_media_")
        self.addCleanup(shutil.rmtree, media, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=media)
        override.enable()
        self.addCleanup(override.disable)
        Subject.objects.create(name="Anatomy", code="ANZ8G", exam_type="neet_pg")
        material = MaterialAsset.objects.create(
            sha256="9" * 64, sha256_short="9" * 16, original_filename="recall-z8.pdf",
            storage_path=str(self.tmp / "recall-z8.pdf"), file_size=1, page_count=1,
        )
        self.job = ImportJob.objects.create(material_asset=material, parent_exam="neet_pg",
                                            status="processing")

    def run_gate(self, payloads):
        qa = self.tmp / "08_qa"
        qa.mkdir(parents=True, exist_ok=True)
        (qa / "per_question_qa.json").write_text(json.dumps([
            {"status": QA_PRODUCTION_READY, "page_number": 1,
             "question_number_in_pdf": p["question_number_in_pdf"], "failing_axes": [], "payload": p}
            for p in payloads
        ]), encoding="utf-8")
        (qa / "summary.json").write_text("{}", encoding="utf-8")
        return apply_qa_v2_verdict(job=self.job, artefact_root=self.tmp)

    def test_label_in_the_stem_or_an_option_is_held_not_imported(self):
        counts = self.run_gate([
            _payload("Which nerve supplies the thenar muscles?", qno=1),
            _payload("Which nerve is injured in wrist drop? Ans: (c) Radial nerve", qno=2),
            _payload("Which nerve is injured in claw hand?", qno=3, options=[
                "Median nerve", "Ulnar nerve", "Radial nerve",
                "Axillary nerve Correct Answer: B. Ulnar nerve",
            ]),
            _payload("Which nerve winds round the surgical neck of the humerus?\n\n"
                     "Explanation: the axillary nerve runs with the posterior circumflex artery.", qno=4),
        ])
        self.assertEqual((counts["imported"], counts["held"]), (1, 3))
        self.assertEqual(Question.objects.get().question_text, "Which nerve supplies the thenar muscles?")
        staged = {sq.question_number_in_pdf: sq for sq in StagedQuestion.objects.filter(job=self.job)}
        self.assertEqual(sorted(staged), [2, 3, 4])
        self.assertEqual(staged[2].failing_axes, ["answer_label_in_public_text"])
        self.assertEqual(staged[3].failing_axes, ["answer_label_in_public_text"])
        self.assertEqual(staged[4].failing_axes, ["explanation_label_in_public_text"])
        self.assertIn("answer_label_in_public_text", staged[2].failure_reason)
        self.assertTrue(all(sq.qa_status == QA_NEEDS_REVIEW for sq in staged.values()))
        self.job.refresh_from_db()
        self.assertEqual((self.job.questions_imported, self.job.questions_staged_nr), (1, 3))

    def test_answer_prompts_and_assertion_reason_wording_still_import(self):
        counts = self.run_gate([_payload(
            "Assertion (A): Aspirin is an antipyretic.\nReason (R): It inhibits COX.\n"
            "Select the correct answer using the code given below:", qno=1, options=[
                "Both A and R are true and R is the correct explanation of A",
                "Both A and R are true but R is not the correct explanation of A",
                "A is true but R is false",
                "A is false but R is true",
            ])])
        self.assertEqual((counts["imported"], counts["held"]), (1, 0))
        self.assertFalse(StagedQuestion.objects.filter(job=self.job).exists())
