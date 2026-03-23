import unittest
import sys
import os

# Add the current directory to sys.path to allow importing upsc_cms_knowledge
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from upsc_cms_knowledge import (
    get_topic_importance,
    get_study_advice,
    get_exam_info,
    search_drug_of_choice,
    EXAM_PATTERN,
    HIGH_YIELD_TOPICS
)

class TestUPSCCMSKnowledge(unittest.TestCase):
    def test_get_topic_importance_valid(self):
        # Case: existing subject and topic
        subject = "General Medicine"
        topic = "Cardiology (MI, Heart Failure, Arrhythmias, Valvular diseases)"
        result = get_topic_importance(subject, topic)
        self.assertEqual(result["importance"], "High Yield")
        self.assertEqual(result["subject_weight"], HIGH_YIELD_TOPICS[subject]["weight"])
        self.assertEqual(result["textbooks"], HIGH_YIELD_TOPICS[subject]["standard_textbooks"])

    def test_get_topic_importance_invalid_topic(self):
        # Case: existing subject but missing topic
        subject = "General Medicine"
        topic = "Non-existent Topic"
        result = get_topic_importance(subject, topic)
        self.assertEqual(result["importance"], "Standard")
        self.assertEqual(result["subject_weight"], "Unknown")
        self.assertEqual(result["textbooks"], [])

    def test_get_topic_importance_invalid_subject(self):
        # Case: missing subject
        subject = "Non-existent Subject"
        topic = "Cardiology"
        result = get_topic_importance(subject, topic)
        self.assertEqual(result["importance"], "Standard")
        self.assertEqual(result["subject_weight"], "Unknown")
        self.assertEqual(result["textbooks"], [])

    def test_get_study_advice_valid(self):
        # Case: existing subject
        subject = "Paediatrics"
        result = get_study_advice(subject)
        self.assertEqual(result["subject"], subject)
        self.assertEqual(result["weightage"], HIGH_YIELD_TOPICS[subject]["weight"])
        self.assertEqual(result["key_topics"], HIGH_YIELD_TOPICS[subject]["topics"][:5])
        self.assertEqual(result["recommended_books"], HIGH_YIELD_TOPICS[subject]["standard_textbooks"])
        self.assertIn(HIGH_YIELD_TOPICS[subject]["topics"][0], result["tip"])

    def test_get_study_advice_invalid(self):
        # Case: missing subject
        subject = "Non-existent Subject"
        result = get_study_advice(subject)
        self.assertEqual(result, {"error": "Subject not found"})

    def test_get_exam_info(self):
        # Case: returns EXAM_PATTERN
        result = get_exam_info()
        self.assertEqual(result, EXAM_PATTERN)
        self.assertEqual(result["name"], "UPSC Combined Medical Services (CMS) Examination")

    def test_search_drug_of_choice_found_exact(self):
        # Case: exact match (case-insensitive)
        condition = "Typhoid"
        result = search_drug_of_choice(condition)
        self.assertIn("Ceftriaxone", result)
        self.assertIn("Typhoid", result)

    def test_search_drug_of_choice_found_partial(self):
        # Case: partial match
        condition = "Meningitis"
        result = search_drug_of_choice(condition)
        self.assertIn("Ceftriaxone", result)
        self.assertIn("Meningitis_bacterial", result)

    def test_search_drug_of_choice_case_insensitive(self):
        # Case: case insensitive
        condition = "typhoid"
        result = search_drug_of_choice(condition)
        self.assertIn("Ceftriaxone", result)

    def test_search_drug_of_choice_not_found(self):
        # Case: no match
        condition = "Common Cold"
        result = search_drug_of_choice(condition)
        self.assertEqual(result, "Drug of choice not found in database")

if __name__ == "__main__":
    unittest.main()
