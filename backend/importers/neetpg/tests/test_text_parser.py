"""Text parser tests — question / option / answer / explanation extraction."""
import unittest

from backend.importers.neetpg import text_parser
from backend.importers.neetpg.models import ParsedQuestion


SIMPLE_PAGE = """Q.1 A 23-year-old male presents with chest pain. ECG shows ST elevation.
A. Aspirin
B. Streptokinase
C. Metoprolol
D. Atorvastatin
Ans: B
Exp: STEMI management.
"""

TWO_Q_PAGE = """Q.1 First question stem.
A. opt1
B. opt2
C. opt3
D. opt4
Ans: A
Q.2 Second question stem.
A. optA
B. optB
C. optC
D. optD
Ans: D
"""


class ParseTests(unittest.TestCase):
    def test_single_question(self):
        qs, stats = text_parser.parse_page(SIMPLE_PAGE, page_number=1, source_sha16="abc")
        self.assertEqual(len(qs), 1)
        q = qs[0]
        self.assertEqual(q.question_number_in_pdf, 1)
        self.assertEqual(len(q.options), 4)
        self.assertEqual(q.options[1].label, "B")
        self.assertTrue(q.options[1].is_correct)
        self.assertEqual(q.answer_labels, ["B"])
        self.assertIn("STEMI", q.explanation)
        self.assertGreater(stats.questions_found, 0)

    def test_two_questions(self):
        qs, _ = text_parser.parse_page(TWO_Q_PAGE, page_number=2, source_sha16="abc")
        self.assertEqual(len(qs), 2)
        self.assertEqual(qs[0].answer_labels, ["A"])
        self.assertEqual(qs[1].answer_labels, ["D"])

    def test_no_questions(self):
        qs, stats = text_parser.parse_page("Just a paragraph of text.", page_number=3, source_sha16="abc")
        self.assertEqual(qs, [])
        self.assertEqual(stats.questions_found, 0)

    def test_assertion_reason(self):
        page = """Q.1 Assertion: Aspirin is an antipyretic. Reason: It inhibits COX.
A. Both true and reason explains
B. Both true but reason does not explain
C. Assertion true, reason false
D. Assertion false, reason true
Ans: A
"""
        qs, _ = text_parser.parse_page(page, page_number=4, source_sha16="abc")
        self.assertEqual(len(qs), 1)
        self.assertEqual(qs[0].question_type, "assertion_reason")

    def test_image_ref_counted(self):
        page = """Q.1 [image] What is shown?
A. X-ray
B. CT
C. MRI
D. USG
Ans: A
"""
        qs, stats = text_parser.parse_page(page, page_number=5, source_sha16="abc")
        self.assertEqual(len(qs), 1)
        self.assertTrue(qs[0].is_image_based)
        self.assertGreaterEqual(stats.image_refs_found, 1)


class ConfidenceTests(unittest.TestCase):
    def test_parse_confidence_components(self):
        page = """Q.1 Question.
A. o1
B. o2
C. o3
D. o4
Ans: A
Exp: Some explanation.
"""
        qs, _ = text_parser.parse_page(page, page_number=6, source_sha16="abc")
        self.assertGreater(qs[0].extraction_confidence, 0.95)


if __name__ == "__main__":
    unittest.main()