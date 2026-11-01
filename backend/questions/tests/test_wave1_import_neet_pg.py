"""import_neet_pg is non-destructive and never invents answers
(audit issues QB-01 / C2 / CFG-03).

The old command ran from build.sh on every deploy, deleted every
exam_source="NEET PG" question (cascading user history), and re-created them
with answer "A" for the 2020 paper, cut-off 2025 stems and exam_type "cms".
"""
from __future__ import annotations

import os
import re
import tempfile
from io import StringIO
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from questions.management.commands import import_neet_pg as cmd
from questions.models import Question, QuestionBookmark, RemovedQuestion, Subject, compute_stem_hash
from questions.text_encoding import normalize_text, read_text_file

try:  # PyMuPDF is in requirements.txt; guard anyway so the suite degrades cleanly.
    import fitz  # noqa: F401
    HAVE_FITZ = True
except Exception:  # pragma: no cover
    HAVE_FITZ = False

PAPER_2025 = cmd.DEFAULT_PAPER_2025
MISSING = os.path.join(tempfile.gettempdir(), "does-not-exist-neet-pg-2020.pdf")
SOURCE_2025 = cmd.source_label(2025)
SOURCE_2020 = cmd.source_label(2020)


def run(*args):
    out, err = StringIO(), StringIO()
    call_command("import_neet_pg", *args, stdout=out, stderr=err)
    return out.getvalue()


def make_2020_pdf(path, questions):
    """Write a small PDF in the 2020 paper's layout ("N. stem" + "(A)  opt")."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    y = 72
    for number, stem, options in questions:
        lines = [f"{number}. {stem}"] + [f"({label})  {text}" for label, text in zip("ABCD", options)]
        for line in lines:
            page.insert_text((72, y), line, fontsize=10)
            y += 14
    page.insert_text((72, y + 14), "Page 1 of 1", fontsize=10)
    doc.save(path)
    doc.close()


class ParserTests(SimpleTestCase):
    def test_2025_paper_parses_all_questions_with_intact_stems(self):
        parsed = cmd.parse_2025_text(read_text_file(PAPER_2025))
        self.assertEqual([q["number"] for q in parsed], list(range(1, 29)))
        by_number = {q["number"]: q for q in parsed}
        # The old regex split on the bare article " a ": stem "Which of the
        # following is", option A "loop diuretic?\n(a) Spironolactone".
        self.assertEqual(by_number[5]["question_text"], "Which of the following is a loop diuretic?")
        self.assertEqual(by_number[5]["option_a"], "Spironolactone")
        self.assertEqual(by_number[15]["question_text"], "Which of the following is a beta-lactam antibiotic?")
        # Page numbers between lines are dropped.
        self.assertEqual(by_number[4]["question_text"], "The most common site of metastasis for breast cancer is:")
        self.assertEqual(by_number[15]["option_c"], "Erythromycin")
        for q in parsed:
            for field in ("option_a", "option_b", "option_c", "option_d"):
                self.assertNotRegex(q[field], r"\([a-d]\)", (q["number"], field))

    def test_legacy_parser_reproduces_the_old_garbled_stem(self):
        legacy = {q["number"]: q for q in cmd.legacy_parse_2025_text(read_text_file(PAPER_2025))}
        self.assertEqual(legacy[5]["question_text"], "Which of the following is")

    def test_numbered_list_inside_a_stem_is_not_a_new_question(self):
        text = "\n".join([
            "40. Consider the statements:",
            "1. Statement one",
            "2. Statement two",
            "(A)  1 only", "(B)  2 only", "(C)  Both", "(D)  Neither",
            "41. Next question?",
            "(A)  a", "(B)  b", "(C)  c", "(D)  d",
        ])
        parsed = cmd.parse_2020_pdf_text(text)
        self.assertEqual([q["number"] for q in parsed], [40, 41])
        self.assertIn("Statement two", parsed[0]["question_text"])

    def test_2020_paper_parses_without_footer_noise(self):
        if not HAVE_FITZ:
            self.skipTest("PyMuPDF not installed")
        import fitz

        doc = fitz.open(cmd.DEFAULT_PAPER_2020)
        text = "".join(page.get_text() + "\n" for page in doc)
        doc.close()
        parsed = cmd.parse_2020_pdf_text(text)
        numbers = [q["number"] for q in parsed]
        # The paper has 299 questions numbered 1-300 (there is no question 70).
        self.assertEqual(len(parsed), 299)
        self.assertEqual(sorted(set(range(1, 301)) - set(numbers)), [70])
        for q in parsed:
            blob = " ".join(q[k] for k in ("question_text", "option_a", "option_b", "option_c", "option_d")).lower()
            self.assertNotIn("page ", blob, q["number"])
            self.assertNotIn("question paper contains", blob, q["number"])


class ImportCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.content_2025 = read_text_file(PAPER_2025)
        cls.parsed_2025 = {q["number"]: q for q in cmd.parse_2025_text(cls.content_2025)}
        cls.legacy_2025 = {q["number"]: q for q in cmd.legacy_parse_2025_text(cls.content_2025)}

    def _imported(self, year=2025):
        return Question.objects.filter(exam_source="NEET PG", year=year, source=cmd.source_label(year))

    def _legacy_row(self, number, *, answer="A", **extra):
        """A row exactly as the old command stored it."""
        subject, _ = Subject.objects.get_or_create(code="MED", defaults={"name": "General Medicine"})
        legacy = self.legacy_2025[number]
        fields = dict(
            question_text=normalize_text(legacy["question_text"]),
            option_a=normalize_text(legacy["option_a"]), option_b=normalize_text(legacy["option_b"]),
            option_c=normalize_text(legacy["option_c"]), option_d=normalize_text(legacy["option_d"]),
            correct_answer=answer,
            explanation=cmd.LEGACY_PLACEHOLDER_EXPLANATION,
            subject=subject, year=2025, paper=1, difficulty="medium",
            exam_source="NEET PG", source=SOURCE_2025,
        )
        fields.update(extra)
        return Question.objects.create(**fields)

    def test_first_run_creates_keyed_questions_as_neet_pg(self):
        output = run("--paper-2020", MISSING)
        rows = list(self._imported().order_by("display_number"))
        self.assertEqual(len(rows), 28, output)
        self.assertEqual([r.display_number for r in rows], list(range(1, 29)))
        for row in rows:
            self.assertEqual(row.exam_type, "neet_pg")
            self.assertEqual(row.correct_answer, cmd.NEET_PG_2025_ANSWERS[row.display_number])
            self.assertFalse(row.needs_review)
        self.assertEqual(rows[4].question_text, "Which of the following is a loop diuretic?")

    def test_second_run_deletes_and_changes_nothing(self):
        run("--paper-2020", MISSING)
        before = {r.pk: (r.updated_at, r.question_text, r.correct_answer) for r in self._imported()}
        output = run("--paper-2020", MISSING)
        after = {r.pk: (r.updated_at, r.question_text, r.correct_answer) for r in self._imported()}
        self.assertEqual(before, after)
        self.assertIn("left unchanged", output)

    def test_other_neet_pg_content_and_user_history_survive(self):
        subject, _ = Subject.objects.get_or_create(code="ANA", defaults={"name": "Anatomy"})
        other = Question.objects.create(
            question_text="Fixture NEET PG question kept across runs?",
            option_a="a", option_b="b", option_c="c", option_d="d", correct_answer="C",
            subject=subject, year=2024, exam_source="NEET PG", exam_type="neet_pg",
        )
        run("--paper-2020", MISSING)
        imported = self._imported().get(display_number=3)
        user = get_user_model().objects.create_user(username="np_user", email="np@example.com", password="x" * 12)
        bookmark = QuestionBookmark.objects.create(user=user, question=imported)

        run("--paper-2020", MISSING)
        run("--paper-2020", MISSING, "--replace")

        self.assertTrue(Question.objects.filter(pk=other.pk).exists())
        self.assertTrue(QuestionBookmark.objects.filter(pk=bookmark.pk).exists())
        self.assertTrue(Question.objects.filter(pk=imported.pk).exists())

    def test_legacy_rows_are_adopted_not_duplicated(self):
        garbled = self._legacy_row(5, answer="A")   # stem was cut to "Which of the following is"
        intact = self._legacy_row(2, answer="B")
        user = get_user_model().objects.create_user(username="np_legacy", email="npl@example.com", password="x" * 12)
        QuestionBookmark.objects.create(user=user, question=garbled)

        run("--paper-2020", MISSING)
        self.assertEqual(self._imported().count(), 28)   # 26 created + 2 adopted
        garbled.refresh_from_db()
        self.assertEqual(garbled.question_text, "Which of the following is")   # default mode: untouched
        self.assertEqual(garbled.exam_type, "cms")

        run("--paper-2020", MISSING, "--replace")
        self.assertEqual(self._imported().count(), 28)
        garbled.refresh_from_db()
        intact.refresh_from_db()
        self.assertEqual(garbled.question_text, "Which of the following is a loop diuretic?")
        self.assertEqual(garbled.option_a, "Spironolactone")
        self.assertEqual(garbled.correct_answer, "B")
        self.assertEqual(garbled.exam_type, "neet_pg")
        self.assertEqual(garbled.display_number, 5)
        self.assertEqual(intact.display_number, 2)
        self.assertTrue(QuestionBookmark.objects.filter(question=garbled).exists())

    def test_a_row_sharing_only_the_cut_off_stem_is_not_adopted_by_another_question(self):
        # Only Q7's old row exists; Q5 (processed first) shares its cut-off
        # stem "Which of the following is" but not its options.
        q7 = self._legacy_row(7, answer="A")
        self.assertEqual(q7.question_text, normalize_text(self.legacy_2025[5]["question_text"]))
        run("--paper-2020", MISSING, "--replace")
        q7.refresh_from_db()
        self.assertEqual(q7.display_number, 7)
        self.assertEqual(q7.question_text, self.parsed_2025[7]["question_text"])
        self.assertEqual(q7.correct_answer, cmd.NEET_PG_2025_ANSWERS[7])
        self.assertEqual(self._imported().count(), 28)
        self.assertEqual(self._imported().filter(display_number=5).count(), 1)

    def test_replace_skips_admin_edited_and_answer_locked_rows(self):
        edited = self._legacy_row(5, answer="C", admin_edited=True)
        locked = self._legacy_row(7, answer="D", lock_answer=True)
        run("--paper-2020", MISSING, "--replace")
        edited.refresh_from_db()
        locked.refresh_from_db()
        self.assertEqual(edited.correct_answer, "C")
        self.assertEqual(edited.question_text, "Which of the following is")
        self.assertEqual(locked.correct_answer, "D")

    def test_tombstone_recorded_against_the_old_garbled_stem_is_honoured(self):
        old_hash = compute_stem_hash(normalize_text(self.legacy_2025[5]["question_text"]))
        RemovedQuestion.objects.create(exam_source="NEET PG", year=2025, question_text_hash=old_hash)
        # The old parser cut several stems to the same "Which of the
        # following is"; the tombstone cannot say which one was removed, so
        # none of them may come back (the old command skipped them all too).
        sharing = {
            n for n, q in self.legacy_2025.items()
            if compute_stem_hash(normalize_text(q["question_text"])) == old_hash
        }
        self.assertIn(5, sharing)
        self.assertGreater(len(sharing), 1)

        output = run("--paper-2020", MISSING)
        created = set(self._imported().values_list("display_number", flat=True))
        self.assertFalse(created & sharing)
        self.assertEqual(created, set(range(1, 29)) - sharing)
        self.assertIn("old cut-off stem", output)

    def test_tombstone_on_the_current_stem_skips_only_that_question(self):
        RemovedQuestion.objects.create(
            exam_source="NEET PG", year=2025, source_number=5,
            question_text_hash=compute_stem_hash("Which of the following is a loop diuretic?"),
        )
        output = run("--paper-2020", MISSING)
        created = set(self._imported().values_list("display_number", flat=True))
        self.assertEqual(created, set(range(1, 29)) - {5})
        self.assertIn("admin-removed", output)

    def test_stem_already_in_the_bank_from_another_source_is_not_duplicated(self):
        subject, _ = Subject.objects.get_or_create(code="PHM", defaults={"name": "Pharmacology"})
        Question.objects.create(
            question_text="Which of the following is a loop diuretic?",
            option_a="a", option_b="b", option_c="c", option_d="d", correct_answer="B",
            subject=subject, year=2025, exam_source="NEET PG (recall)", exam_type="neet_pg",
        )
        run("--paper-2020", MISSING)
        self.assertFalse(self._imported().filter(display_number=5).exists())

    def test_dry_run_writes_nothing(self):
        legacy = self._legacy_row(5)
        output = run("--paper-2020", MISSING, "--replace", "--dry-run")
        self.assertEqual(self._imported().count(), 1)
        legacy.refresh_from_db()
        self.assertEqual(legacy.question_text, "Which of the following is")
        self.assertIn("Dry run", output)


class Paper2020Tests(TestCase):
    """The 2020 PDF has no answer key."""

    QUESTIONS = [
        (1, "Upward movement of the thyroid gland is prevented due to?",
         ["Berry ligament", "Pretracheal fascia", "Sternothyroid muscle", "Thyrohyoid membrane"]),
        (2, "Wolffian duct remnant in female is",
         ["Pouch of Douglas", "Uterovesical pouch", "Gartner's cyst", "Broad ligament"]),
    ]

    def setUp(self):
        if not HAVE_FITZ:
            self.skipTest("PyMuPDF not installed")
        tmp = tempfile.mkdtemp()
        self.pdf = os.path.join(tmp, "paper_2020.pdf")
        make_2020_pdf(self.pdf, self.QUESTIONS)
        self.args = ("--paper-2025", MISSING, "--paper-2020", self.pdf)

    def _imported(self):
        return Question.objects.filter(exam_source="NEET PG", year=2020, source=SOURCE_2020)

    def test_questions_without_an_answer_key_are_skipped_not_answered_a(self):
        output = run(*self.args)
        self.assertEqual(self._imported().count(), 0)
        self.assertIn("no answer key", output)

    def test_replace_hides_rows_the_old_command_answered_a(self):
        subject, _ = Subject.objects.get_or_create(code="MED", defaults={"name": "General Medicine"})
        old = Question.objects.create(
            question_text=self.QUESTIONS[0][1],
            option_a="Berry ligament", option_b="Pretracheal fascia",
            option_c="Sternothyroid muscle", option_d="Thyrohyoid membrane",
            correct_answer="A", explanation=cmd.LEGACY_PLACEHOLDER_EXPLANATION,
            subject=subject, year=2020, paper=1, exam_source="NEET PG", source=SOURCE_2020,
        )
        run(*self.args)
        old.refresh_from_db()
        self.assertTrue(old.is_active)   # default mode never touches existing rows

        run(*self.args, "--replace")
        old.refresh_from_db()
        self.assertFalse(old.is_active)
        self.assertTrue(old.needs_review)
        self.assertEqual(old.exam_type, "neet_pg")
        self.assertTrue(Question.objects.filter(pk=old.pk).exists())

    def test_enrich_answers_unkeyed_questions_and_flags_them_for_review(self):
        fake = mock.MagicMock()
        fake.get_consensus_answer.side_effect = ["A", "C"]
        fake.explain_after_answer.return_value = "AI explanation."
        with mock.patch("ai_engine.services.AIService", return_value=fake), \
                mock.patch.object(cmd.time, "sleep"):
            run(*self.args, "--enrich")
        rows = {r.display_number: r for r in self._imported()}
        self.assertEqual(rows[1].correct_answer, "A")
        self.assertEqual(rows[2].correct_answer, "C")
        self.assertTrue(all(r.needs_review for r in rows.values()))
        self.assertEqual(rows[1].explanation, "AI explanation.")

    def test_enrich_never_overrides_the_answer_key(self):
        fake = mock.MagicMock()
        fake.get_consensus_answer.return_value = "D"
        fake.explain_after_answer.return_value = ""
        with mock.patch("ai_engine.services.AIService", return_value=fake), \
                mock.patch.object(cmd.time, "sleep"):
            run("--paper-2020", MISSING, "--enrich", "--limit", "3")
        fake.get_consensus_answer.assert_not_called()
        rows = Question.objects.filter(source=SOURCE_2025)
        self.assertEqual(rows.count(), 28)
        for row in rows:
            self.assertEqual(row.correct_answer, cmd.NEET_PG_2025_ANSWERS[row.display_number])
            self.assertFalse(row.needs_review)


class DeployScriptTests(SimpleTestCase):
    def test_build_sh_no_longer_runs_import_neet_pg(self):
        build_sh = Path(settings.BASE_DIR) / "build.sh"
        commands = [
            line for line in build_sh.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        self.assertFalse(
            [line for line in commands if re.search(r"manage\.py\s+import_neet_pg\b", line)],
            "build.sh must not run the NEET PG importer on deploy",
        )
