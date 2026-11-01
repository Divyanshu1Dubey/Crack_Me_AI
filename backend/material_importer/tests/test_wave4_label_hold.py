"""Wave 4 (Z8): ``publish_extracted_question`` holds a row whose stem or
options carry an answer / explanation label: it goes back to
``needs_review`` with a note and nothing reaches the live bank.

The stem and the options are public text, so "Correct Answer: C" or
"Explanation: ..." glued into them would give the answer away
(``questions.answer_leak.label_hold_reasons``).
"""
from __future__ import annotations

import shutil
import tempfile

from django.test import TestCase, override_settings

from material_importer.models import ExtractedQuestion, ImportBatch, ImportMaterial
from material_importer.publishing import publish_extracted_question
from questions.models import Question

HOLD_NOTE = "Not published: answer / explanation label in the stem or options"


class PublishHoldsAnswerLabelsTests(TestCase):
    def setUp(self):
        media = tempfile.mkdtemp(prefix="z8_publish_media_")
        self.addCleanup(shutil.rmtree, media, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=media)
        override.enable()
        self.addCleanup(override.disable)
        batch = ImportBatch.objects.create(source_label="z8", root_path="/tmp/z8", status="completed")
        self.material = ImportMaterial.objects.create(
            batch=batch, original_filename="surgery.docx", file_format="docx",
            file_size_bytes=10, file_sha256="f" * 64,
        )

    def make_eq(self, idx, *, stem="Which nerve is injured in wrist drop?", option_d="Axillary", **extra):
        return ExtractedQuestion.objects.create(
            material=self.material, position_index=idx, question_text=stem,
            option_a="Median", option_b="Ulnar", option_c="Radial", option_d=option_d,
            correct_answer="C", content_hash=f"z8-{idx}", status="approved", **extra,
        )

    def test_label_in_an_option_or_the_stem_is_held_for_review(self):
        rows = [
            self.make_eq(0, option_d="Axillary Correct Answer: C. Radial"),
            self.make_eq(1, stem="Which nerve is injured in wrist drop? Ans: (c)"),
            self.make_eq(2, stem="Which nerve is injured in wrist drop?\n\n"
                                 "Explanation: the radial nerve supplies the wrist extensors."),
        ]
        for eq in rows:
            self.assertFalse(publish_extracted_question(eq))
            eq.refresh_from_db()
            self.assertEqual(eq.status, "needs_review")
            self.assertIsNone(eq.published_question_id)
            self.assertIn(HOLD_NOTE, eq.review_note)
        self.assertIn("answer_label_in_public_text", rows[0].review_note)
        self.assertIn("answer_label_in_public_text", rows[1].review_note)
        self.assertIn("explanation_label_in_public_text", rows[2].review_note)
        self.assertEqual(Question.objects.count(), 0)

    def test_note_is_added_once_and_earlier_notes_are_kept(self):
        eq = self.make_eq(0, option_d="Axillary Answer: C", review_note="Checked by the importer.")
        self.assertFalse(publish_extracted_question(eq))
        # An admin re-approves without fixing the text: still held, one note.
        ExtractedQuestion.objects.filter(pk=eq.pk).update(status="approved")
        eq.refresh_from_db()
        self.assertFalse(publish_extracted_question(eq))
        eq.refresh_from_db()
        self.assertEqual(eq.status, "needs_review")
        self.assertTrue(eq.review_note.startswith("Checked by the importer.\n"))
        self.assertEqual(eq.review_note.count(HOLD_NOTE), 1)
        self.assertEqual(Question.objects.count(), 0)

    def test_rows_without_a_label_still_publish(self):
        eq = self.make_eq(0, stem="Choose the correct answer: which nerve is injured in wrist drop?")
        self.assertTrue(publish_extracted_question(eq))
        eq.refresh_from_db()
        self.assertEqual(eq.status, "published")
        live = Question.objects.get()
        self.assertEqual((live.pk, live.correct_answer), (eq.published_question_id, "C"))
