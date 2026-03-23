import unittest
from ai_engine.upsc_cms_knowledge import (
    get_topic_importance,
    get_study_advice,
    get_exam_info,
    search_drug_of_choice,
    EXAM_PATTERN,
    HIGH_YIELD_TOPICS
)

class TestUpscCMSKnowledge(unittest.TestCase):
    def test_get_topic_importance(self):
        # Happy path
        # Let's use an exact topic from HIGH_YIELD_TOPICS for "General Medicine"
        topic = "Cardiology (MI, Heart Failure, Arrhythmias, Valvular diseases)"
        result = get_topic_importance("General Medicine", topic)
        self.assertEqual(result["importance"], "High Yield")
        self.assertEqual(result["subject_weight"], HIGH_YIELD_TOPICS["General Medicine"]["weight"])
        self.assertEqual(result["textbooks"], HIGH_YIELD_TOPICS["General Medicine"]["standard_textbooks"])

        # Edge case 1: Valid subject, invalid topic
        result = get_topic_importance("General Medicine", "Unknown Topic")
        self.assertEqual(result, {"importance": "Standard", "subject_weight": "Unknown", "textbooks": []})

        # Edge case 2: Invalid subject
        result = get_topic_importance("Unknown Subject", "ECG interpretation")
        self.assertEqual(result, {"importance": "Standard", "subject_weight": "Unknown", "textbooks": []})

    def test_get_study_advice(self):
        # Happy path
        result = get_study_advice("General Medicine")
        self.assertEqual(result["subject"], "General Medicine")
        self.assertEqual(result["weightage"], HIGH_YIELD_TOPICS["General Medicine"]["weight"])
        self.assertEqual(result["key_topics"], HIGH_YIELD_TOPICS["General Medicine"]["topics"][:5])
        self.assertEqual(result["recommended_books"], HIGH_YIELD_TOPICS["General Medicine"]["standard_textbooks"])
        self.assertEqual(result["tip"], f"Focus on {HIGH_YIELD_TOPICS['General Medicine']['topics'][0]} first as it's most commonly asked.")

        # Error condition: Invalid subject
        result = get_study_advice("Unknown Subject")
        self.assertEqual(result, {"error": "Subject not found"})

    def test_get_exam_info(self):
        # Happy path
        result = get_exam_info()
        self.assertEqual(result, EXAM_PATTERN)

    def test_search_drug_of_choice(self):
        # Happy path: exact match
        result = search_drug_of_choice("Typhoid")
        self.assertEqual(result, "Typhoid: Ceftriaxone / Azithromycin")

        # Happy path: case-insensitive partial match
        result = search_drug_of_choice("typhoid")
        self.assertEqual(result, "Typhoid: Ceftriaxone / Azithromycin")

        # Happy path: another exact match
        result = search_drug_of_choice("tuberculosis")
        self.assertEqual(result, "Tuberculosis: HRZE (Isoniazid, Rifampicin, Pyrazinamide, Ethambutol)")

        # Error condition: not found
        result = search_drug_of_choice("Unknown Disease")
        self.assertEqual(result, "Drug of choice not found in database")

if __name__ == '__main__':
    unittest.main()
