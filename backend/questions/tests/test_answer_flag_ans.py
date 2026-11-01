"""A bracketed "(Ans)" marks the answer on an option; "(ANS)" is the
autonomic nervous system. Both readings must hold at once: the Mistake
Notebook and the test review cut a locked option at the flag, and real
neurology options keep their abbreviation."""
from django.test import SimpleTestCase

from questions.answer_leak import CORRECT, cut_option_text, find_flags, redact_public_text


class AnsFlagTests(SimpleTestCase):
    def test_mixed_and_lower_case_ans_are_flags(self):
        for text in ('Dobutamine (Ans)', 'Dobutamine (ans)', 'Dobutamine [Ans.]', 'Dobutamine ( ans )'):
            flags = find_flags(text)
            self.assertEqual(len(flags), 1, text)
            self.assertEqual(flags[0].polarity, CORRECT, text)

    def test_upper_case_ans_is_the_autonomic_nervous_system(self):
        for text in ('Autonomic nervous system (ANS)', 'Disorders of the (ANS) and spinal cord'):
            self.assertEqual(find_flags(text), [], text)
            self.assertEqual(cut_option_text(text), text)

    def test_option_is_cut_at_the_first_flag(self):
        self.assertEqual(cut_option_text('Dobutamine (Ans) ✔'), 'Dobutamine')
        self.assertEqual(cut_option_text('Dobutamine (Ans) - first line inotrope'), 'Dobutamine')

    def test_words_containing_ans_are_untouched(self):
        for text in ('Transfusion (answers vary)', 'Dans syndrome', 'Ansa cervicalis (ansa)'):
            self.assertEqual(cut_option_text(text), text)

    def test_locked_row_redaction_uses_the_flag(self):
        row = {'question_text': 'Which drug is first line?', 'option_a': 'Noradrenaline',
               'option_b': 'Adrenaline', 'option_c': 'Dopamine', 'option_d': 'Dobutamine (Ans)'}
        redact_public_text(row)
        self.assertEqual(row['option_d'], 'Dobutamine')
        self.assertEqual(row['option_b'], 'Adrenaline')
