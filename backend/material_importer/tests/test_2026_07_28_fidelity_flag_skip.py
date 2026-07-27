"""Unit tests for the 2026-07-28 fidelity-flag-skip fix.

Background:
    `BoxedMCQExtractorFidelity._row_value_html` previously rendered every
    non-label cell of a row into the option HTML. For a row shaped like
        Option | <text> | correct
    that meant the trailing `correct`/`incorrect` flag cell was
    concatenated into `option_a`, producing e.g.
        `<p>1, 2 and 3</p>\n<p>correct</p>`.

    The non-fidelity `BoxedMCQExtractor` (string path) reads the flag
    into a separate `option_correct` list and never lets it leak into
    the option text. These tests prove the fidelity path now mirrors
    that behaviour.

Run:
    python -m unittest backend.material_importer.tests.test_2026_07_28_fidelity_flag_skip
"""
from __future__ import annotations

import unittest

from material_importer.parser.docx_fidelity import Paragraph, Run, TableCell, TableRow
from material_importer.parser.docx_parser import BoxedMCQExtractorFidelity


def _row(label_text, value_texts, flag_text=None):
    """Build a `TableRow` for `_row_value_html`."""
    cells = [TableCell(paragraphs=[Paragraph(runs=[Run(text=label_text)])])]
    for v in value_texts:
        cells.append(TableCell(paragraphs=[Paragraph(runs=[Run(text=v)])]))
    if flag_text is not None:
        cells.append(TableCell(paragraphs=[Paragraph(runs=[Run(text=flag_text)])]))
    return TableRow(cells=cells)


class _Flags(unittest.TestCase):

    def test_three_cell_row_with_correct_flag_drops_flag(self):
        """The `correct` flag cell must NOT appear in the rendered HTML."""
        row = _row("Option", ["1, 2 and 3"], flag_text="correct")
        out = BoxedMCQExtractorFidelity._row_value_html(row, image_url_for=None)
        self.assertNotIn("correct", out.lower())
        self.assertIn("1, 2 and 3", out)

    def test_three_cell_row_with_incorrect_flag_drops_flag(self):
        row = _row("Option", ["2, 3 and 4"], flag_text="incorrect")
        out = BoxedMCQExtractorFidelity._row_value_html(row, image_url_for=None)
        self.assertNotIn("incorrect", out.lower())
        self.assertIn("2, 3 and 4", out)

    def test_two_cell_row_unchanged(self):
        """A row with no flag cell must render the value cell normally."""
        row = _row("Option", ["1 and 3 only"])
        out = BoxedMCQExtractorFidelity._row_value_html(row, image_url_for=None)
        self.assertIn("1 and 3 only", out)
        self.assertNotIn("correct", out.lower())

    def test_question_row_unchanged(self):
        """Question rows have multiple value cells and no flag — render all of them."""
        row = _row("Question", ["Stem sentence one.", "Stem sentence two."])
        out = BoxedMCQExtractorFidelity._row_value_html(row, image_url_for=None)
        self.assertIn("Stem sentence one.", out)
        self.assertIn("Stem sentence two.", out)

    def test_solution_row_unchanged(self):
        """Solution rows don't carry a flag cell."""
        row = _row("Solution", ["Both A and R are true."])
        out = BoxedMCQExtractorFidelity._row_value_html(row, image_url_for=None)
        self.assertIn("Both A and R are true.", out)
        self.assertNotIn("correct", out.lower())
        self.assertNotIn("incorrect", out.lower())

    def test_flag_cell_with_extra_whitespace_still_dropped(self):
        """Trailing whitespace in the flag cell shouldn't break the skip."""
        row = _row("Option", ["Frontal lobe"], flag_text="  CORRECT  ")
        out = BoxedMCQExtractorFidelity._row_value_html(row, image_url_for=None)
        self.assertNotIn("correct", out.lower())
        self.assertIn("Frontal lobe", out)

    def test_flag_value_with_real_content_not_dropped(self):
        """If the trailing cell is `Correct answer is B` it is content, not a flag."""
        row = _row("Option", ["Statement A"], flag_text="Correct answer is B")
        out = BoxedMCQExtractorFidelity._row_value_html(row, image_url_for=None)
        # Whole row should be preserved — flag text contains more than the
        # bare word, so it's content.
        self.assertIn("Statement A", out)
        self.assertIn("Correct answer is B", out)


if __name__ == "__main__":
    unittest.main()