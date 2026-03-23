from django.test import TestCase
from questions.management.commands.scrape_pyqs import infer_subject_topic, SUBJECT_MAP

class InferSubjectTopicTests(TestCase):
    def test_infer_subject_topic_happy_path_header(self):
        """Test inference when keyword is in section header."""
        header = "Section on Cardiology"
        text = "What is the heart rate?"
        subj_code, topic_name = infer_subject_topic(header, text)
        self.assertEqual(subj_code, 'MED')
        self.assertEqual(topic_name, 'Cardiology')

    def test_infer_subject_topic_happy_path_text(self):
        """Test inference when keyword is in question text."""
        header = "General Knowledge"
        text = "Which neurology symptom is this?"
        subj_code, topic_name = infer_subject_topic(header, text)
        self.assertEqual(subj_code, 'MED')
        self.assertEqual(topic_name, 'Neurology')

    def test_infer_subject_topic_case_insensitivity(self):
        """Test that inference is case-insensitive."""
        header = "NEONATOLOGY"
        text = "Baby weight"
        subj_code, topic_name = infer_subject_topic(header, text)
        self.assertEqual(subj_code, 'PED')
        self.assertEqual(topic_name, 'Neonatology')

    def test_infer_subject_topic_fallback(self):
        """Test fallback behavior when no keywords match."""
        header = "Random Header"
        text = "What is the meaning of life?"
        subj_code, topic_name = infer_subject_topic(header, text)
        self.assertEqual(subj_code, 'MED')
        self.assertEqual(topic_name, 'Cardiology')

    def test_infer_subject_topic_empty_inputs(self):
        """Test behavior with empty string inputs."""
        header = ""
        text = ""
        subj_code, topic_name = infer_subject_topic(header, text)
        self.assertEqual(subj_code, 'MED')
        self.assertEqual(topic_name, 'Cardiology')

    def test_infer_subject_topic_none_inputs(self):
        """Test behavior with None inputs."""
        # The current implementation uses f-strings: f"{None} {None}".lower() -> "none none"
        # Since 'none' is not in SUBJECT_MAP, it should return the fallback.
        header = None
        text = None
        subj_code, topic_name = infer_subject_topic(header, text)
        self.assertEqual(subj_code, 'MED')
        self.assertEqual(topic_name, 'Cardiology')

    def test_infer_subject_topic_multiple_keywords(self):
        """Test behavior when multiple keywords are present (should return first match in dict)."""
        # "cardiology" comes before "neurology" in SUBJECT_MAP
        # Let's verify by checking SUBJECT_MAP order
        first_key = list(SUBJECT_MAP.keys())[0] # cardiology
        last_key = list(SUBJECT_MAP.keys())[-1] # preventive

        header = f"Testing {last_key}"
        text = f"And {first_key}"

        # Since it iterates over SUBJECT_MAP.items(), it should find first_key first
        subj_code, topic_name = infer_subject_topic(header, text)
        self.assertEqual(subj_code, SUBJECT_MAP[first_key][0])
        self.assertEqual(topic_name, SUBJECT_MAP[first_key][1])
