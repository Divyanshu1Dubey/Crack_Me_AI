"""import_neet_pg, wave 3: an admin-protected row is matched by its
display_number only when its content is not clearly another question's (a
backfill ordinal on an admin-edited row used to make the importer duplicate
that question and leave the numbered question's real row unrepaired)."""
from __future__ import annotations

from django.test import TestCase

from questions.management.commands import import_neet_pg as cmd
from questions.models import Question, Subject, compute_stem_hash
from questions.tests.test_wave2_import_neet_pg import MISSING, SOURCE_2025, run
from questions.text_encoding import normalize_text, read_text_file


class ProtectedRowWithOrdinalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        content = read_text_file(cmd.DEFAULT_PAPER_2025)
        cls.parsed = {q["number"]: q for q in cmd.parse_2025_text(content)}
        cls.legacy = {q["number"]: q for q in cmd.legacy_parse_2025_text(content)}

    def _imported(self):
        return Question.objects.filter(exam_source="NEET PG", year=2025, source=SOURCE_2025)

    def _legacy_row(self, number, *, display_number, **extra):
        subject, _ = Subject.objects.get_or_create(code="MED", defaults={"name": "General Medicine"})
        item = self.legacy[number]
        return Question.objects.create(
            question_text=normalize_text(item["question_text"]),
            option_a=normalize_text(item["option_a"]), option_b=normalize_text(item["option_b"]),
            option_c=normalize_text(item["option_c"]), option_d=normalize_text(item["option_d"]),
            correct_answer="A", explanation=cmd.LEGACY_PLACEHOLDER_EXPLANATION,
            subject=subject, year=2025, paper=1, difficulty="medium",
            exam_source="NEET PG", source=SOURCE_2025, display_number=display_number, **extra,
        )

    def _rows_with_options_of(self, number):
        item = self.parsed[number]
        signature = cmd._option_signature(normalize_text(item["option_b"]), normalize_text(item["option_c"]))
        return [q for q in self._imported() if cmd._option_signature(q.option_b, q.option_c) == signature]

    def test_admin_edited_row_with_another_questions_content_is_not_claimed_by_number(self):
        # An admin edited Q9's old row; a backfill then gave it the ordinal 2.
        protected = self._legacy_row(9, display_number=2, admin_edited=True)
        for mode in ((), ("--replace",)):
            run("--paper-2020", MISSING, *mode)
            # Q9 has exactly one row (the protected one), Q2 got its own row.
            self.assertEqual([q.pk for q in self._rows_with_options_of(9)], [protected.pk], mode)
            q2_hash = compute_stem_hash(normalize_text(self.parsed[2]["question_text"]))
            self.assertTrue([q for q in self._imported() if compute_stem_hash(q.question_text) == q2_hash], mode)
            self.assertEqual(self._imported().count(), 28, mode)
        protected.refresh_from_db()
        self.assertTrue(protected.admin_edited)
        self.assertEqual(protected.option_b, normalize_text(self.legacy[9]["option_b"]))   # never rewritten

    def test_admin_rewritten_row_still_matches_by_number(self):
        # Stem and options rewritten by an admin: no content key left, so the
        # number decides (unchanged behaviour).
        row = self._legacy_row(3, display_number=3, admin_edited=True)
        Question.objects.filter(pk=row.pk).update(question_text="Admin wording of question three?",
                                                  option_b="Admin B", option_c="Admin C")
        run("--paper-2020", MISSING)
        self.assertEqual(self._imported().count(), 28)
        self.assertFalse(self._imported().exclude(pk=row.pk).filter(display_number=3).exists())
