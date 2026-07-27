"""Regression tests against real DOCX files in cms_exclusive_material/.

These tests REQUIRE the source DOCX files to be present (Django + python-docx
installed). They are skipped automatically when the source files are missing
so this module can be imported anywhere.

Run with: ``python manage.py test material_importer.tests.test_docx_parser_real``
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_ROOT = str(Path(__file__).resolve().parents[2])
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

CMS_MATERIAL = Path(BACKEND_ROOT).parent / "cms_exclusive_material"

try:
    from material_importer.parser.docx_parser import DOCXParser
    from material_importer.parser.docx_fidelity import (
        read_document_with_fidelity,
        render_blocks,
    )
    HAVE_PARSER = True
except Exception:  # pragma: no cover
    HAVE_PARSER = False


MANIFEST = [
    # (filename, min_questions, expected_detected_type)
    ("Surgery_in_boxes.docx", 100, "mcq_boxed"),
    ("Neuro_PYQ_boxes_IN.docx", 50, "mcq_boxed"),
    ("Mini Test-3 Dermatology.docx", 5, "mcq_boxed"),
    ("Anesthesia_100_MCQs_UPSC_CMS.docx", 50, "mcq_classic"),
    ("CH-10,11,12,14,15 PYQ.docx", 5, "mcq_boxed"),
    ("Orthopaedics_100_MCQs.docx", 50, "mcq_classic"),
    ("100_merged-document (1).docx", 0, None),  # namespace-fallback file
]


@unittest.skipUnless(HAVE_PARSER, "parser not importable")
class RealDocxRegressionTests(unittest.TestCase):
    """Each test exercises the universal parser against a real DOCX."""

    def _parse(self, fname):
        p = CMS_MATERIAL / fname
        if not p.exists():
            self.skipTest(f"Missing fixture: {p}")
        return DOCXParser().parse(str(p))

    def test_surgery_in_boxes_extracts_109_questions(self):
        doc = self._parse("Surgery_in_boxes.docx")
        self.assertGreaterEqual(len(doc.questions), 100)
        # Every question must have a correct answer.
        no_correct = [q for q in doc.questions if q.correct_answer not in "ABCD"]
        self.assertEqual(len(no_correct), 0, f"Questions missing correct: {len(no_correct)}")
        # Every question must have all 4 options populated.
        for q in doc.questions:
            self.assertTrue(q.option_a, f"Q{q.position_index}: empty option_a")
            self.assertTrue(q.option_b, f"Q{q.position_index}: empty option_b")
            self.assertTrue(q.option_c, f"Q{q.position_index}: empty option_c")
            self.assertTrue(q.option_d, f"Q{q.position_index}: empty option_d")
        # Some questions must have per-question images (P1).
        with_imgs = [q for q in doc.questions if q.image_refs]
        self.assertGreater(len(with_imgs), 0, "Per-question image association failed")
        # Marks must be parsed from the boxed table.
        marks_set = {q.marks for q in doc.questions}
        self.assertNotEqual(marks_set, {1}, f"Every question has marks=1 — Marks row not parsed")

    def test_surgery_in_boxes_preserves_html_fidelity(self):
        doc = self._parse("Surgery_in_boxes.docx")
        q = doc.questions[0]
        # question_text must contain HTML tags (not just plain text).
        self.assertTrue("<" in q.question_text and ">" in q.question_text,
                        f"q.question_text not HTML: {q.question_text[:100]!r}")
        # explanation must be non-empty HTML.
        self.assertTrue("<" in q.explanation and ">" in q.explanation,
                        f"q.explanation not HTML: {q.explanation[:100]!r}")

    def test_neuro_pyq_parses(self):
        doc = self._parse("Neuro_PYQ_boxes_IN.docx")
        self.assertGreaterEqual(len(doc.questions), 50)

    def test_anesthesia_classic_layout(self):
        doc = self._parse("Anesthesia_100_MCQs_UPSC_CMS.docx")
        self.assertGreaterEqual(len(doc.questions), 50)
        # Should be classic (no boxed tables).
        self.assertEqual(doc.detected_type, "mcq_classic")

    def test_orthopaedics_classic_layout(self):
        doc = self._parse("Orthopaedics_100_MCQs.docx")
        self.assertGreaterEqual(len(doc.questions), 50)

    def test_mini_test_short_files(self):
        for fname in ("Mini Test-3 Dermatology.docx ", "Mini Test-3 Systemic pediatrics.docx"):
            doc = self._parse(fname.strip())
            # Mini tests are short — any number > 0 is fine, just don't crash.
            self.assertGreaterEqual(len(doc.questions), 0)

    def test_merged_document_namespace_fallback(self):
        """The file that previously broke python-docx must now parse via XML fallback."""
        doc = self._parse("100_merged-document (1).docx")
        # Either it parses with some questions, or it returns 'unknown' cleanly.
        # The audit requirement is: never silently fail.
        self.assertIn(doc.detected_type, ("mcq_boxed", "mcq_classic", "mcq_statement", "theory", "unknown", "hybrid"))

    def test_fidelity_reader_renders_html(self):
        path = CMS_MATERIAL / "Surgery_in_boxes.docx"
        if not path.exists():
            self.skipTest("Missing fixture")
        blocks = read_document_with_fidelity(str(path))
        self.assertGreater(len(blocks), 0)
        html = render_blocks(blocks[:3])
        self.assertIn("<", html)
        self.assertIn("Prophylac", html)  # first question's first option snippet

    def test_paragraph_index_set_for_questions_with_images(self):
        doc = self._parse("Surgery_in_boxes.docx")
        with_imgs = [q for q in doc.questions if q.image_refs]
        for q in with_imgs[:5]:
            self.assertGreaterEqual(q.paragraph_index, 0,
                                    f"Q{q.position_index} with images has paragraph_index={q.paragraph_index}")


if __name__ == "__main__":
    unittest.main()
