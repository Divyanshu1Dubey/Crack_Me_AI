"""infer_subject_topic (scrape_pyqs). Ported from branch add-test-scrape-pyqs (fde86f3)."""
from django.test import SimpleTestCase

from questions.management.commands.scrape_pyqs import SUBJECT_MAP, infer_subject_topic


class InferSubjectTopicTests(SimpleTestCase):
    def test_keyword_in_header(self):
        self.assertEqual(infer_subject_topic('Section on Cardiology', 'What is the heart rate?'), ('MED', 'Cardiology'))

    def test_keyword_in_text(self):
        self.assertEqual(infer_subject_topic('General Knowledge', 'Which neurology symptom is this?'), ('MED', 'Neurology'))

    def test_case_insensitive(self):
        self.assertEqual(infer_subject_topic('NEONATOLOGY', 'Baby weight'), ('PED', 'Neonatology'))

    def test_fallback(self):
        self.assertEqual(infer_subject_topic('Random Header', 'What is the meaning of life?'), ('MED', 'Cardiology'))

    def test_empty_inputs(self):
        self.assertEqual(infer_subject_topic('', ''), ('MED', 'Cardiology'))

    def test_none_inputs(self):
        self.assertEqual(infer_subject_topic(None, None), ('MED', 'Cardiology'))

    def test_first_keyword_in_map_order_wins(self):
        first_key = list(SUBJECT_MAP)[0]
        last_key = list(SUBJECT_MAP)[-1]
        self.assertEqual(infer_subject_topic(f'Testing {last_key}', f'And {first_key}'), SUBJECT_MAP[first_key])

    # Regression: 'ent' used to match inside ordinary words.
    def test_ent_does_not_match_inside_words(self):
        for text in ('A patient presents with fever', 'Best treatment of the present illness'):
            self.assertNotEqual(infer_subject_topic('Questions', text), ('SUR', 'General Surgery'), text)

    def test_ent_as_a_word_still_matches(self):
        self.assertEqual(infer_subject_topic('ENT', 'Tonsillitis'), ('SUR', 'General Surgery'))

    def test_prefix_keywords_still_match_plural(self):
        self.assertEqual(infer_subject_topic('Pediatrics', 'Fever in a child'), ('PED', 'Neonatology'))
