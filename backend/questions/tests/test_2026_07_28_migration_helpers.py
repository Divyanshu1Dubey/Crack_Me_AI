"""Unit tests for the 0029_strip_flag_paragraphs helpers.

Background:
    `migration 0029` adds a `strip_flag_paragraphs()` scrubber that drops
    `<p>correct</p>` / `<p>incorrect</p>` paragraphs — a failure mode the
    high-fidelity DOCX extractor produced after migration 0027 ran.

Run:
    python -m unittest backend.questions.tests.test_2026_07_28_migration_helpers
"""
from __future__ import annotations

import unittest

from questions.migrations._data_cleanups import (
    strip_flag_paragraphs,
    strip_imported_html,
    strip_leaked_correct_incorrect,
)


class _FlagParaScrubber(unittest.TestCase):

    def test_strips_trailing_correct_paragraph(self):
        """The screenshot bug: `<p>1, 2 and 3</p>\\n<p>correct</p>` → `<p>1, 2 and 3</p>`."""
        s = "<p>1, 2 and 3</p>\n<p>correct</p>"
        out = strip_flag_paragraphs(s)
        self.assertNotIn("<p>correct</p>", out)
        self.assertIn("<p>1, 2 and 3</p>", out)

    def test_strips_trailing_incorrect_paragraph(self):
        s = "<p>2, 3 and 4</p>\n<p>incorrect</p>"
        out = strip_flag_paragraphs(s)
        self.assertNotIn("<p>incorrect</p>", out)
        self.assertIn("<p>2, 3 and 4</p>", out)

    def test_strips_with_inline_formatting(self):
        """Admin rich-text `<p><strong>correct</strong></p>` must also be stripped."""
        s = "<p>1, 2 and 3</p>\n<p><strong>correct</strong></p>"
        out = strip_flag_paragraphs(s)
        self.assertNotIn("correct", out.lower())
        self.assertIn("<p>1, 2 and 3</p>", out)

    def test_preserves_legit_correct_in_sentence(self):
        """`Statements 2 and 4 are correct` must NOT be touched."""
        s = "<p>Statements 2 and 4 are correct</p>"
        out = strip_flag_paragraphs(s)
        self.assertEqual(out, s)

    def test_preserves_legit_correct_in_list_item(self):
        """A list-item containing `correct` (not in a `<p>`) is not a flag paragraph."""
        s = "<ul><li>correct</li></ul>"
        out = strip_flag_paragraphs(s)
        self.assertEqual(out, s)

    def test_preserves_mid_paragraph_leak(self):
        """A `<p>` whose body is more than just the word must not be stripped."""
        s = "<p>text correct</p>"
        out = strip_flag_paragraphs(s)
        self.assertEqual(out, s)

    def test_idempotent(self):
        """Running twice is a no-op."""
        s = "<p>1, 2 and 3</p>\n<p>correct</p>"
        once = strip_flag_paragraphs(s)
        twice = strip_flag_paragraphs(once)
        self.assertEqual(once, twice)

    def test_empty_input(self):
        self.assertEqual(strip_flag_paragraphs(""), "")

    def test_no_p_tags(self):
        """If there's no `<p>` at all, the scrubber is a no-op."""
        s = "Statements 2 and 4 are correct"
        self.assertEqual(strip_flag_paragraphs(s), s)


class _Pipeline(unittest.TestCase):
    """The full 0029 pipeline: strip_imported_html → strip_leaked → strip_flag."""

    def test_full_pipeline_cleans_real_prod_row(self):
        """Real row id=26780 shape: `<p>1 and 3 only</p>\\n<p>incorrect</p>`."""
        s = "<p>1 and 3 only</p>\n<p>incorrect</p>"
        out = strip_flag_paragraphs(strip_leaked_correct_incorrect(strip_imported_html(s)))
        self.assertEqual(out, "1 and 3 only")

    def test_full_pipeline_preserves_legit_html(self):
        """A real explanation paragraph is left alone."""
        s = "<p>The correct answer is A because of X.</p>"
        out = strip_flag_paragraphs(strip_leaked_correct_incorrect(strip_imported_html(s)))
        # strip_imported_html drops <p> wrapper → text. <p>The correct answer is A because of X.</p>
        # The body is `The correct answer is A because of X.` — sentence with 'correct' inline.
        # 0027 trailing regex doesn't match (no trailing \\n…correct$), flag regex doesn't match
        # (the body is more than just 'correct').
        self.assertIn("The correct answer is A because of X.", out)


if __name__ == "__main__":
    unittest.main()