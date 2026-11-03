"""import_neet_pg, wave 2: AI outages during --enrich, the stored explanation
text, and display_number matches that the row's content must confirm
(review of audit issues AI-02 / QB-30 / C2).
"""
from __future__ import annotations

import os
import tempfile
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from ai_engine.services import AIOutputUnusable, AIUnavailable
from questions.management.commands import import_neet_pg as cmd
from questions.models import Question, QuestionBookmark, Subject
from questions.text_encoding import normalize_text, read_text_file

try:  # PyMuPDF is in requirements.txt; guard anyway so the suite degrades cleanly.
    import fitz  # noqa: F401
    HAVE_FITZ = True
except Exception:  # pragma: no cover
    HAVE_FITZ = False

MISSING = os.path.join(tempfile.gettempdir(), "does-not-exist-neet-pg-wave2.pdf")
SOURCE_2025 = cmd.source_label(2025)
SOURCE_2020 = cmd.source_label(2020)

PAPER_2020_QUESTIONS = [
    (1, "Upward movement of the thyroid gland is prevented due to?",
     ["Berry ligament", "Pretracheal fascia", "Sternothyroid muscle", "Thyrohyoid membrane"]),
    (2, "Wolffian duct remnant in female is",
     ["Pouch of Douglas", "Uterovesical pouch", "Gartner's cyst", "Broad ligament"]),
]


def run(*args):
    out = StringIO()
    call_command("import_neet_pg", *args, stdout=out, stderr=StringIO())
    return out.getvalue()


def make_2020_pdf(path, questions):
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    y = 72
    for number, stem, options in questions:
        for line in [f"{number}. {stem}"] + [f"({label})  {text}" for label, text in zip("ABCD", options)]:
            page.insert_text((72, y), line, fontsize=10)
            y += 14
    doc.save(path)
    doc.close()


def explanation(text="Thiamine is the cofactor of transketolase."):
    """A realistic explain_after_answer() result."""
    return {"why_correct": text, "core_concept": "Vitamin cofactors", "why_wrong": {}, "citations": []}


class EnrichAiFailureTests(TestCase):
    """--enrich used to abort the whole import on the first AI outage and to
    store the explanation *dict* (or outage text) as the explanation."""

    def setUp(self):
        if not HAVE_FITZ:
            self.skipTest("PyMuPDF not installed")
        self.pdf = os.path.join(tempfile.mkdtemp(), "paper_2020.pdf")
        make_2020_pdf(self.pdf, PAPER_2020_QUESTIONS)
        self.args = ("--paper-2025", MISSING, "--paper-2020", self.pdf, "--enrich")

    def _run_with(self, fake):
        with mock.patch("ai_engine.services.AIService", return_value=fake), \
                mock.patch.object(cmd.time, "sleep"):
            return run(*self.args)

    def _rows(self):
        return {r.display_number: r for r in Question.objects.filter(source=SOURCE_2020)}

    def test_explanation_outage_does_not_abort_the_import(self):
        fake = mock.MagicMock()
        fake.get_consensus_answer.side_effect = ["A", "C"]
        fake.explain_after_answer.side_effect = [AIUnavailable("All AI providers failed"), explanation()]
        output = self._run_with(fake)
        rows = self._rows()
        self.assertEqual(set(rows), {1, 2}, output)
        self.assertEqual(rows[1].explanation, cmd.LEGACY_PLACEHOLDER_EXPLANATION)
        self.assertEqual(rows[2].explanation, "Thiamine is the cofactor of transketolase.")
        self.assertTrue(all(r.needs_review for r in rows.values()))
        self.assertIn("unavailable", output)

    def test_unparseable_reply_is_not_stored(self):
        fake = mock.MagicMock()
        fake.get_consensus_answer.side_effect = ["B", "C"]
        fake.explain_after_answer.side_effect = AIOutputUnusable("The AI explanation could not be parsed")
        self._run_with(fake)
        rows = self._rows()
        self.assertEqual(set(rows), {1, 2})
        for row in rows.values():
            self.assertEqual(row.explanation, cmd.LEGACY_PLACEHOLDER_EXPLANATION)

    def test_answer_outage_skips_the_question_and_continues(self):
        fake = mock.MagicMock()
        fake.get_consensus_answer.side_effect = [AIUnavailable("offline", offline=True), "C"]
        fake.explain_after_answer.return_value = explanation()
        output = self._run_with(fake)
        rows = self._rows()
        self.assertEqual(set(rows), {2}, output)   # Q1: no key and no AI answer -> not invented
        self.assertEqual(rows[2].correct_answer, "C")

    def test_only_genuine_why_correct_text_is_stored(self):
        fake = mock.MagicMock()
        fake.get_consensus_answer.side_effect = ["A", "C"]
        fake.explain_after_answer.side_effect = [
            # Outage sentence in the body, and the unparsed final fallback.
            {"why_correct": "All AI services are temporarily unavailable. Please try again later."},
            {"why_correct": "raw model prose", "raw_response": "raw model prose"},
        ]
        self._run_with(fake)
        for row in self._rows().values():
            self.assertEqual(row.explanation, cmd.LEGACY_PLACEHOLDER_EXPLANATION)
            self.assertNotIn("{", row.explanation)

    def test_explanation_is_the_why_correct_string_not_the_dict(self):
        fake = mock.MagicMock()
        fake.get_consensus_answer.side_effect = ["A", "C"]
        fake.explain_after_answer.return_value = explanation("Berry's ligament fixes the gland to the cricoid.")
        self._run_with(fake)
        for row in self._rows().values():
            self.assertEqual(row.explanation, "Berry's ligament fixes the gland to the cricoid.")


class DisplayNumberMatchTests(TestCase):
    """backfill_display_number.py / audit_questions --apply store ordinals in
    display_number; a number match alone used to be trusted."""

    @classmethod
    def setUpTestData(cls):
        content = read_text_file(cmd.DEFAULT_PAPER_2025)
        cls.parsed = {q["number"]: q for q in cmd.parse_2025_text(content)}
        cls.legacy = {q["number"]: q for q in cmd.legacy_parse_2025_text(content)}

    def _imported(self):
        return Question.objects.filter(exam_source="NEET PG", year=2025, source=SOURCE_2025)

    def _legacy_row(self, number, *, display_number=None, answer="A", **extra):
        """A row as the old command stored it, optionally renumbered by a backfill."""
        subject, _ = Subject.objects.get_or_create(code="MED", defaults={"name": "General Medicine"})
        item = self.legacy[number]
        return Question.objects.create(
            question_text=normalize_text(item["question_text"]),
            option_a=normalize_text(item["option_a"]), option_b=normalize_text(item["option_b"]),
            option_c=normalize_text(item["option_c"]), option_d=normalize_text(item["option_d"]),
            correct_answer=answer, explanation=cmd.LEGACY_PLACEHOLDER_EXPLANATION,
            subject=subject, year=2025, paper=1, difficulty="medium",
            exam_source="NEET PG", source=SOURCE_2025, display_number=display_number, **extra,
        )

    def test_row_with_an_ordinal_number_is_adopted_not_duplicated(self):
        old_q2 = self._legacy_row(2, display_number=40)   # ordinal outside the paper's numbering
        run("--paper-2020", MISSING)
        self.assertEqual(self._imported().count(), 28)
        self.assertFalse(self._imported().filter(display_number=2).exists())   # default mode: untouched
        run("--paper-2020", MISSING, "--replace")
        old_q2.refresh_from_db()
        self.assertEqual(old_q2.display_number, 2)
        self.assertEqual(self._imported().count(), 28)

    def test_replace_rewrites_the_row_whose_content_matches(self):
        # A backfill gave Q9's old row the number 2 and Q2's old row the number 9.
        old_q2 = self._legacy_row(2, display_number=9, answer="B")
        old_q9 = self._legacy_row(9, display_number=2, answer="A")
        user = get_user_model().objects.create_user(username="np_w2", email="np_w2@example.com", password="x" * 12)
        QuestionBookmark.objects.create(user=user, question=old_q9)

        run("--paper-2020", MISSING, "--replace")

        old_q2.refresh_from_db()
        old_q9.refresh_from_db()
        self.assertEqual(old_q2.display_number, 2)
        self.assertEqual(old_q2.question_text, normalize_text(self.parsed[2]["question_text"]))
        self.assertEqual(old_q9.display_number, 9)
        self.assertEqual(old_q9.question_text, normalize_text(self.parsed[9]["question_text"]))
        self.assertEqual(old_q9.correct_answer, cmd.NEET_PG_2025_ANSWERS[9])
        # The student's bookmark still points at the Wernicke question.
        self.assertIn("Wernicke", QuestionBookmark.objects.get(user=user).question.question_text)
        self.assertEqual(self._imported().count(), 28)

    def test_rows_this_command_created_still_match_by_number_after_edits(self):
        run("--paper-2020", MISSING)
        row3 = self._imported().get(display_number=3)
        # An edited stem (options unchanged) is still Q3.
        Question.objects.filter(pk=row3.pk).update(question_text="Gaucher disease: which enzyme is deficient?")
        # An admin rewrote both the stem and the options of Q5.
        row5 = self._imported().get(display_number=5)
        Question.objects.filter(pk=row5.pk).update(
            question_text="Pick the loop diuretic", option_b="Bumetanide", option_c="Amiloride", admin_edited=True,
        )
        run("--paper-2020", MISSING)
        run("--paper-2020", MISSING, "--replace")
        self.assertEqual(self._imported().count(), 28)
        self.assertEqual(self._imported().filter(display_number=3).count(), 1)
        self.assertEqual(self._imported().filter(display_number=5).count(), 1)
        row5.refresh_from_db()
        self.assertEqual(row5.question_text, "Pick the loop diuretic")   # admin edit protected
