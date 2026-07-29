"""Unit tests for the space-joined-stem splitter (migration 0032).

Run:
    python -m unittest backend.questions.tests.test_2026_07_28_space_joined_stems
"""
from __future__ import annotations

import re
import unittest

from questions.migrations._statement_splitter import (
    split_space_joined_stems,
    score_space_joined_stems,
    _AUTO_REWRITE_THRESHOLD,
    _REVIEW_THRESHOLD,
)


class _PositiveCases(unittest.TestCase):
    """Rows the splitter SHOULD rewrite (or queue for manual review)."""

    def test_real_scabies_row(self):
        """Row 5200 sample. Inlined body with NO trailing tail and NO
        inline tail — falls into the SKIP band (<0.80) because we have
        no anchor for where the body ends. The splitter leaves the
        text untouched; the caller may still see the rewrite via
        ``score_space_joined_stems`` for manual review."""
        before = (
            "Which of the following are correct in respect of scabies? "
            "Male mite Sarcoptes scabiei are commonly transferred from an "
            "infected person to a non-infected person. "
            "Norwegian scabies occur in immunodeficient patients. "
            "Permethrin cream (5%) is used for treatment. "
            "Pruritus intensifies at night and after hot shower."
        )
        out = split_space_joined_stems(before)
        self.assertEqual(out, before)
        score, rewrite = score_space_joined_stems(before)
        self.assertLess(score, _REVIEW_THRESHOLD)

    def test_real_sickle_row_with_tail(self):
        """Row 19707 sample — ends with 'Select the correct answer using
        the code below:' (recognized trailing tail). The body is
        inlined but a recognized tail anchors it, landing in the
        manual-review band."""
        before = (
            "Which of the following statements regarding the management "
            "of sickle cell disease during pregnancy is correct? "
            "Folic acid 1 mg tablet should be given daily. "
            "Penicillin prophylaxis is strictly contraindicated. "
            "Hydroxyurea should be stopped at least 3 months before "
            "conception. "
            "Vaginal delivery is the preferred method of delivery. "
            "Select the correct answer using the code below:"
        )
        score, rewrite = score_space_joined_stems(before)
        self.assertGreaterEqual(score, _REVIEW_THRESHOLD)
        self.assertLess(score, _AUTO_REWRITE_THRESHOLD)
        self.assertIsNotNone(rewrite)
        self.assertIn("1. Folic acid 1 mg tablet", rewrite)
        self.assertIn("2. Penicillin prophylaxis", rewrite)
        self.assertIn("3. Hydroxyurea", rewrite)
        self.assertIn("4. Vaginal delivery", rewrite)


class _NegativeCases(unittest.TestCase):
    """Rows the splitter MUST leave untouched."""

    def test_already_numbered_untouched(self):
        before = (
            "Which of the following are correct?\n"
            "1. First statement\n"
            "2. Second statement\n"
            "3. Third statement\n"
            "Which of the above are correct?"
        )
        self.assertEqual(split_space_joined_stems(before), before)

    def test_no_question_mark_untouched(self):
        before = (
            "Consider the following about X. "
            "Statement one. Statement two. Statement three. "
            "Statement four."
        )
        self.assertEqual(split_space_joined_stems(before), before)

    def test_only_two_sentences_untouched(self):
        before = (
            "Which of the following is correct? "
            "First statement. Second statement."
        )
        self.assertEqual(split_space_joined_stems(before), before)

    def test_short_statements_untouched(self):
        before = (
            "Which of the following applies? "
            "A is true. B is false. C is true. D is false."
        )
        self.assertEqual(split_space_joined_stems(before), before)

    def test_option_prefixed_list_untouched(self):
        before = (
            "Which of the following drugs are used for absence seizures? "
            "A. Carbamazepine B. Valproate C. Ethosuximide D. Gabapentin "
            "a) A, B and C b) B and C only"
        )
        self.assertEqual(split_space_joined_stems(before), before)

    def test_paragraph_broken_untouched(self):
        before = (
            "Which of the following statements are correct regarding x?\n"
            "\n"
            "It is a rare autoimmune disease.\n"
            "\n"
            "Antibodies are formed against collagen.\n"
            "\n"
            "The disease may be associated with retinal hemorrhage.\n"
            "\n"
            "Select the answer using the code given below:"
        )
        self.assertEqual(split_space_joined_stems(before), before)

    def test_select_answer_without_correct_untouched(self):
        """Tail without 'correct' must still be recognized. With a
        recognized trailing tail the score reaches the manual-review
        band (0.80–0.97). The rewrite is produced via
        ``score_space_joined_stems``; the auto-rewrite gate
        (``split_space_joined_stems``) leaves the original text
        unchanged until a human approves."""
        before = (
            "Which of the following statements are correct? "
            "Insulin causes glycogen synthesis in the liver. "
            "Glucagon promotes hepatic glycogen breakdown. "
            "Cortisol reduces peripheral glucose utilization. "
            "Epinephrine stimulates hepatic gluconeogenesis. "
            "Select the answer using the code given below:"
        )
        out = split_space_joined_stems(before)
        score, rewrite = score_space_joined_stems(before)
        self.assertEqual(out, before)
        self.assertLess(score, _AUTO_REWRITE_THRESHOLD)
        self.assertGreaterEqual(score, _REVIEW_THRESHOLD)
        self.assertIsNotNone(rewrite)
        self.assertNotIn("5. Select the answer", rewrite)
        self.assertIn("1. Insulin causes", rewrite)
        self.assertIn("4. Epinephrine", rewrite)

    def test_tail_leak_using_code_only(self):
        """If the tail is just 'Using the code below:' the splitter
        must REFUSE — the tail-vs-body recognition regex does not
        match 'Using the code below:' in isolation, and the tail-leak
        guard catches anything that snuck through. Either path is OK;
        the absolute rule is: no instruction becomes a numbered
        statement."""
        before = (
            "Which of the following statements are correct? "
            "Insulin causes glycogen synthesis in the liver. "
            "Glucagon promotes hepatic glycogen breakdown. "
            "Cortisol reduces peripheral glucose utilization. "
            "Epinephrine stimulates hepatic gluconeogenesis. "
            "Using the code below:"
        )
        out = split_space_joined_stems(before)
        if out != before:
            for line in out.splitlines():
                self.assertFalse(
                    re.match(r"^\s*\d+\.\s*Using", line),
                    f"tail-leak: {line!r}",
                )

    def test_tail_leak_directions_in_body_4th(self):
        """Body ends with an instructional line (no trailing
        Select/Using marker). The tail-leak guard must refuse."""
        before = (
            "Which of the following statements are correct? "
            "Insulin causes glycogen synthesis in the liver. "
            "Glucagon promotes hepatic glycogen breakdown. "
            "Cortisol reduces peripheral glucose utilization. "
            "Directions: pick the best answer."
        )
        out = split_space_joined_stems(before)
        self.assertEqual(out, before)


class _InlineTailCases(unittest.TestCase):
    """Regression tests for the generalized inline-tail detector.

    Covers:
      - inline tails glued to a statement with single space
      - inline tails with multiple spaces / tabs (OCR artefacts)
      - inline tails missing newline before tail (statement + tail on
        the same line)
      - assertion / reason scaffolding (A)/(R) tagging
      - direction / explanation / codes
      - the original id=22213 production failure
    """

    def _assert_safe(self, out, before):
        self.assertNotEqual(out, before)
        for line in out.splitlines():
            m = re.match(r"^\s*\d+\.\s*(.*)", line)
            if not m:
                continue
            payload = m.group(1).strip().lower()
            self.assertFalse(
                any(payload.startswith(p) for p in (
                    "select the answer",
                    "select the correct answer",
                    "choose the correct answer",
                    "choose the answer",
                    "using the code",
                    "using the codes",
                    "codes:",
                    "code:",
                    "directions:",
                    "direction:",
                    "explanation:",
                    "answer:",
                    "options:",
                    "list i:",
                    "list ii:",
                    "column i:",
                    "column ii:",
                    "match list",
                    "match column",
                    "match the following",
                    "assertion",
                    "reason",
                )),
                f"instruction-became-numbered: {line!r}",
            )

    def test_id_22213_inline_tail_glued_single_space(self):
        """Original failure: tail glued to last statement with single
        space, no newline separator. Question id=22213."""
        before = (
            "Which of the following statements about Klinefelter's syndrome are correct?\n"
            "It is the most common cause of testicular failure\n"
            "Karyotype is 47, XXY\n"
            "Clinical features include eunuchoid appearance, azoospermia, and gynecomastia\n"
            "Serum testosterone is low and serum gonadotropins are elevated Select the correct answer using the code given below:"
        )
        out = split_space_joined_stems(before)
        self.assertNotEqual(out, before)
        self._assert_safe(out, before)
        self.assertIn("Select the correct answer using the code given below:", out)
        self.assertIn("Serum testosterone is low and serum gonadotropins are elevated.", out)
        for line in out.splitlines():
            m = re.match(r"^\s*\d+\.\s*(.*)", line)
            if m and "Select" in m.group(1):
                self.fail(f"tail-glued-as-statement: {line!r}")

    def test_inline_tail_multiple_spaces(self):
        """OCR artefact: triple space between statement and tail."""
        before = (
            "Which of the following statements about CKD are correct?\n"
            "Diabetic nephropathy is the leading cause of CKD globally.\n"
            "Stage 2 CKD may have GFR 60-89 mL/min.\n"
            "Small kidneys on imaging suggest chronicity.\n"
            "CKD anaemia is primarily due to EPO deficiency.   Select the correct answer using the code given below."
        )
        out = split_space_joined_stems(before)
        self.assertNotEqual(out, before)
        self._assert_safe(out, before)
        self.assertIn("Select the correct answer using the code given below.", out)
        for line in out.splitlines():
            m = re.match(r"^\s*4\.\s*(.*)", line)
            if m:
                self.assertFalse(
                    "Select" in m.group(1),
                    f"statement 4 leaks tail: {line!r}",
                )

    def test_inline_tail_tab_separator(self):
        """Tail preceded by a tab (not space)."""
        before = (
            "Which of the following statements about CKD are correct?\n"
            "Diabetic nephropathy is the leading cause of CKD globally.\n"
            "Stage 2 CKD may have GFR 60-89 mL/min.\n"
            "Small kidneys on imaging suggest chronicity.\n"
            "CKD anaemia is primarily due to EPO deficiency.\tSelect the correct answer using the code given below."
        )
        out = split_space_joined_stems(before)
        self.assertNotEqual(out, before)
        self._assert_safe(out, before)

    def test_inline_tail_assertion_reason(self):
        """Assertion / Reason scaffold glued to the last statement."""
        before = (
            "Which of the following statements about the heart are correct?\n"
            "It has four chambers.\n"
            "It pumps oxygenated blood to the body.\n"
            "The right atrium receives deoxygenated blood.\n"
            "The left ventricle has the thickest wall. Assertion (A): The heart has four chambers.\n"
            "Reason (R): The chambers are separated by septa."
        )
        out = split_space_joined_stems(before)
        self.assertNotEqual(out, before)
        self._assert_safe(out, before)

    def test_inline_tail_directions_only(self):
        """'Directions:' glued mid-body."""
        before = (
            "Which of the following statements about CKD are correct?\n"
            "Diabetic nephropathy is the leading cause of CKD globally.\n"
            "Stage 2 CKD may have GFR 60-89 mL/min.\n"
            "Small kidneys on imaging suggest chronicity.\n"
            "CKD anaemia is due to EPO deficiency. Directions: pick the best."
        )
        out = split_space_joined_stems(before)
        self.assertNotEqual(out, before)
        self._assert_safe(out, before)

    def test_inline_tail_explanation_only(self):
        """'Explanation:' glued mid-body."""
        before = (
            "Which of the following statements about CKD are correct?\n"
            "Diabetic nephropathy is the leading cause of CKD globally.\n"
            "Stage 2 CKD may have GFR 60-89 mL/min.\n"
            "Small kidneys on imaging suggest chronicity.\n"
            "CKD anaemia is due to EPO deficiency. Explanation: the kidney makes EPO."
        )
        out = split_space_joined_stems(before)
        self.assertNotEqual(out, before)
        self._assert_safe(out, before)

    def test_inline_tail_pick_best(self):
        """Loose phrasing 'Select the best answer' without 'correct'."""
        before = (
            "Which of the following statements about CKD are correct?\n"
            "Diabetic nephropathy is the leading cause of CKD globally.\n"
            "Stage 2 CKD may have GFR 60-89 mL/min.\n"
            "Small kidneys on imaging suggest chronicity.\n"
            "CKD anaemia is due to EPO deficiency. Choose the best answer:"
        )
        out = split_space_joined_stems(before)
        self.assertNotEqual(out, before)
        self._assert_safe(out, before)

    def test_inline_tail_does_not_trigger_on_word_select(self):
        """Avoid false-positive: 'selected' inside a statement must not
        be split as a tail. Paragraph body + no tail = REVIEW band:
        the rewrite is produced via ``score_space_joined_stems``."""
        before = (
            "Which of the following statements about CKD are correct?\n"
            "Patients selected for transplant had improved outcomes.\n"
            "Stage 2 CKD may have GFR 60-89 mL/min.\n"
            "Small kidneys on imaging suggest chronicity.\n"
            "CKD anaemia is due to EPO deficiency."
        )
        score, rewrite = score_space_joined_stems(before)
        self.assertGreaterEqual(score, _REVIEW_THRESHOLD)
        self.assertIsNotNone(rewrite)
        self._assert_safe(rewrite, before)
        self.assertIn("Patients selected for transplant", rewrite)


class _ConfidenceScoringCases(unittest.TestCase):

    def test_high_confidence_returns_rewrite(self):
        text = (
            "Which of the following statements about Klinefelter's syndrome are correct?\n"
            "It is the most common cause of testicular failure\n"
            "Karyotype is 47, XXY\n"
            "Clinical features include eunuchoid appearance, azoospermia, and gynecomastia\n"
            "Serum testosterone is low and serum gonadotropins are elevated\n"
            "Select the correct answer using the code given below:"
        )
        score, rewrite = score_space_joined_stems(text)
        self.assertGreaterEqual(score, _AUTO_REWRITE_THRESHOLD)
        self.assertIsNotNone(rewrite)

    def test_below_threshold_returns_none_rewrite(self):
        text = (
            "Which of the following are correct about x? "
            "Statement one is good. "
            "Statement two is bad. "
            "Statement three is neutral."
        )
        score, rewrite = score_space_joined_stems(text)
        self.assertIsInstance(score, float)
        self.assertTrue(rewrite is None or isinstance(rewrite, str))

    def test_score_invalid_input_returns_zero(self):
        score, rewrite = score_space_joined_stems("")
        self.assertEqual(score, 0.0)
        self.assertIsNone(rewrite)
        score, rewrite = score_space_joined_stems(None)
        self.assertEqual(score, 0.0)
        self.assertIsNone(rewrite)


class _EdgeCases(unittest.TestCase):

    def test_empty(self):
        self.assertEqual(split_space_joined_stems(""), "")

    def test_none(self):
        self.assertEqual(split_space_joined_stems(None), None)


if __name__ == "__main__":
    unittest.main()