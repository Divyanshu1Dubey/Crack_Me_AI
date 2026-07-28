"""Unit tests for the statement-list splitter helper (migration 0030).

Background:
    Several NEET PG rows landed in prod with the multi-statement stem
    inlined — either joined by '. ' or separated by '\\n' but missing
    bullet/number markers. This made the question-bank card render as
    one mashed paragraph.

    `split_inlined_statements()` rewrites those into numbered lists while
    leaving already-structured rows strictly untouched.

Run:
    python -m unittest backend.questions.tests.test_2026_07_28_statement_splitter
"""
from __future__ import annotations

import unittest

from questions.migrations._statement_splitter import (
    split_inlined_statements,
)


class _PositiveCases(unittest.TestCase):
    """Rows that the splitter SHOULD rewrite."""

    def test_real_respiratory_row_with_newline_no_markers(self):
        """Row 5386: '\\n' between statements, no bullet/number markers."""
        before = (
            "Consider the following statements with regard to respiratory examination:\n"
            "Change in note, when patient phonates \"EEE\" (Egophony) is characteristic of interstitial fibrosis\n"
            "Whispered pectoriloquy is characteristic of lung consolidation\n"
            "Monophonic wheeze is characteristic of asthma\n"
            "Hyper-resonant note on percussion is characteristic of pneumothorax\n"
            "Which of the above statements are correct?"
        )
        out = split_inlined_statements(before)
        self.assertIn("\n1. Change in note", out)
        self.assertIn("\n2. Whispered pectoriloquy", out)
        self.assertIn("\n3. Monophonic wheeze", out)
        self.assertIn("\n4. Hyper-resonant note", out)
        self.assertTrue(out.endswith("Which of the above statements are correct?"))

    def test_real_graves_row_with_newline_no_markers(self):
        """Row 5433: same shape, different topic."""
        before = (
            "Consider the following statements with regard to Graves' ophthalmopathy:\n"
            "Proptosis is often asymmetric and can even appear to be unilateral\n"
            "It is a clinical diagnosis\n"
            "Worsening of symptoms upon glucocorticoid withdrawal is common\n"
            "Radiation therapy is very effective in treatment\n"
            "Which of the above statements are correct?"
        )
        out = split_inlined_statements(before)
        self.assertIn("1. Proptosis is often asymmetric", out)
        self.assertIn("2. It is a clinical diagnosis.", out)
        self.assertIn("4. Radiation therapy", out)

    def test_real_doppler_row_inlined_with_periods(self):
        """Row 19135: all on one line, joined by '. '."""
        before = (
            "Consider the following about Doppler ultrasound changes in a compromised fetus: "
            "Umbilical artery — reduced, absent or reversed end-diastolic flow — indicates increased fetoplacental resistance. "
            "Middle cerebral artery — increased diastolic velocity and decreased S/D ratio — indicates \"brain sparing\" effect. "
            "Ductus venosus — absent/reversed a-wave — indicates fetal acidemia. "
            "In a normal pregnancy, the S/D ratio, PI and RI increase as gestational age advances. "
            "Which of the statements given above are correct?"
        )
        out = split_inlined_statements(before)
        self.assertIn("1. Umbilical artery", out)
        self.assertIn("2. Middle cerebral artery", out)
        self.assertIn("3. Ductus venosus", out)
        self.assertIn("4. In a normal pregnancy", out)

    def test_select_correct_answer_tail(self):
        """Rows ending with 'Select the correct answer using the code given below:'."""
        before = (
            "Consider the following conditions and classify them as causes of recurrent miscarriage:\n"
            "I. Antiphospholipid antibody syndrome (APAS) — Immune factor\n"
            "II. Polycystic ovary syndrome (PCOS) — Endocrine/metabolic cause\n"
            "III. TORCH infections — Common infective cause\n"
            "IV. Intrauterine adhesions — Anatomical cause\n"
            "Select the correctly classified pairs using the code given below:"
        )
        # NB: this row ALREADY has \\nI. markers; the splitter must skip it.
        out = split_inlined_statements(before)
        self.assertEqual(out, before)


class _NegativeCases(unittest.TestCase):
    """Rows the splitter MUST leave untouched."""

    def test_already_bulleted_untouched(self):
        before = (
            "Consider the following:\n"
            "- Intravenous tubes\n"
            "- Catheters\n"
            "- Gloves\n"
            "- Blood bags\n"
            "Which of the above-mentioned biomedical wastes will be segregated in Red bag as per the Biomedical Waste Management Rules, 2016?"
        )
        self.assertEqual(split_inlined_statements(before), before)

    def test_already_numbered_untouched(self):
        before = (
            "Consider the following:\n"
            "1. Intravenous tubes\n"
            "2. Catheters\n"
            "3. Gloves\n"
            "4. Blood bags\n"
            "Which of the above-mentioned biomedical wastes will be segregated in Red bag as per the Biomedical Waste Management Rules, 2016?"
        )
        self.assertEqual(split_inlined_statements(before), before)

    def test_already_roman_numeral_untouched(self):
        """Rows with \\nI. … \\nII. … have proper structure."""
        before = (
            "Consider the following conditions and classify them as causes of recurrent miscarriage:\n"
            "I. Antiphospholipid antibody syndrome (APAS) — Immune factor\n"
            "II. Polycystic ovary syndrome (PCOS) — Endocrine/metabolic cause\n"
            "Select the correctly classified pairs using the code given below:"
        )
        self.assertEqual(split_inlined_statements(before), before)

    def test_noun_list_not_split(self):
        """Row 5218: 'Insulin Islet amyloid polypeptide or amylin Glucagon Somatostatin'.
        No periods, no '\\n' — splitter must not mangle it."""
        before = (
            "Consider the following pancreatic hormones: "
            "Insulin Islet amyloid polypeptide or amylin Glucagon Somatostatin\n"
            "    Which of the above is/are secreted by beta cells of the pancreatic islets?"
        )
        # No periods → cannot split. Should return as-is.
        self.assertEqual(split_inlined_statements(before), before)

    def test_unrecognised_opener_untouched(self):
        """A question that starts with something other than 'Consider the following'."""
        before = (
            "A 25-year-old male presents with cystic fibrosis. Which of the following is correct?"
        )
        self.assertEqual(split_inlined_statements(before), before)

    def test_too_short_body_not_split(self):
        """If only 1 statement comes out, the splitter refuses."""
        before = (
            "Consider the following about Insulins: It is a hormone.\n"
            "Which of the above is/are correct?"
        )
        out = split_inlined_statements(before)
        self.assertEqual(out, before)


class _Idempotency(unittest.TestCase):

    def test_idempotent_on_already_clean_text(self):
        """Calling on already-numbered text is a no-op."""
        before = (
            "Consider the following about X:\n"
            "1. First statement.\n"
            "2. Second statement.\n"
            "Which of the above are correct?"
        )
        self.assertEqual(split_inlined_statements(before), before)

    def test_double_apply(self):
        """Running twice produces the same output as running once."""
        before = (
            "Consider the following statements with regard to X:\n"
            "Statement one\n"
            "Statement two\n"
            "Statement three\n"
            "Statement four\n"
            "Which of the above are correct?"
        )
        once = split_inlined_statements(before)
        twice = split_inlined_statements(once)
        self.assertEqual(once, twice)


class _EdgeCases(unittest.TestCase):

    def test_empty_input(self):
        self.assertEqual(split_inlined_statements(""), "")

    def test_none_input(self):
        self.assertEqual(split_inlined_statements(None), None)


if __name__ == "__main__":
    unittest.main()