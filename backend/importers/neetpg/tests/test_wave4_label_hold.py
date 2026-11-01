"""Wave 4 (Z8): the recall writer never puts an answer / explanation label
into a question's public text.

``DjangoWriter`` is the writer behind the ingestion gate and the NEET PG /
INI-CET recall runners (the runners call it without the gate in front). A
NEW question whose stem or options carry a label goes to the extraction
review queue, and a re-import never fills an empty option with such text.
"""
from __future__ import annotations

from django.test import TestCase

from importers.inicet.db_writer import DjangoWriter as IniCetWriter
from importers.neetpg.db_writer import DjangoWriter
from importers.neetpg.models import ParsedOption, ParsedQuestion
from questions.models import Question, QuestionExtractionItem, RecallSource, Subject


def _pq(stem, *, qno=1, options=("Median", "Ulnar", "Radial", "Axillary")):
    return ParsedQuestion(
        source_sha16="z" * 16, page_number=1, question_number_in_pdf=qno,
        stem=stem, stem_raw=stem,
        options=[ParsedOption(label, text) for label, text in zip("ABCD", options)],
        answer_labels=["C"], explanation="", subject="Anatomy", confidence_score=0.9,
    )


class WriterHoldsAnswerLabelsTests(TestCase):
    def setUp(self):
        Subject.objects.create(name="Anatomy", code="ANZ8W", exam_type="neet_pg")
        self.rs = RecallSource.objects.create(
            pdf_filename="NEET-PG-2021-z8.pdf", pdf_path="/x/z8.pdf",
            pdf_sha256="7" * 64, pdf_sha256_short="7" * 16,
        )

    def test_new_question_with_a_label_goes_to_review_not_live(self):
        w = DjangoWriter()
        self.assertIsNone(w.write_question(_pq("Which nerve is injured in wrist drop? Ans: (c) Radial"), self.rs))
        self.assertIsNone(w.write_question(_pq("Which nerve is injured in claw hand?", qno=2, options=(
            "Median", "Ulnar", "Radial", "Axillary Correct Answer: B. Ulnar")), self.rs))
        self.assertIsNone(IniCetWriter().write_question(_pq(
            "Which nerve winds round the humeral neck?\n\nExplanation: the axillary nerve.", qno=3), self.rs))
        self.assertEqual(Question.objects.count(), 0)
        self.assertEqual(w.stats.questions_staged_for_review, 2)
        notes = sorted(QuestionExtractionItem.objects.values_list("review_note", flat=True))
        self.assertEqual(len(notes), 3)
        self.assertEqual(sum("answer_label_in_public_text" in n for n in notes), 2)
        self.assertEqual(sum("explanation_label_in_public_text" in n for n in notes), 1)

    def test_question_without_a_label_is_written(self):
        q = DjangoWriter().write_question(_pq("Which nerve is injured in wrist drop?"), self.rs)
        self.assertIsNotNone(q)
        self.assertEqual((q.correct_answer, q.option_c), ("C", "Radial"))
        self.assertFalse(QuestionExtractionItem.objects.exists())

    def test_reimport_never_fills_an_empty_option_with_a_label(self):
        stem = "Which nerve is injured in wrist drop?"
        q = DjangoWriter().write_question(_pq(stem), self.rs)
        Question.objects.filter(pk=q.pk).update(option_c="", option_d="")
        again = DjangoWriter().write_question(_pq(stem, options=(
            "Median", "Ulnar", "Radial", "Axillary Explanation: the radial nerve supplies the extensors.")), self.rs)
        self.assertEqual(again.pk, q.pk)
        q.refresh_from_db()
        self.assertEqual(q.option_c, "Radial")  # a clean empty option is still filled
        self.assertEqual(q.option_d, "")
        self.assertEqual(Question.objects.count(), 1)
