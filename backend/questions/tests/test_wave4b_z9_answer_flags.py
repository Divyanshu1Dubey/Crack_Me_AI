"""Wave 4b Z9: the answer-leak gaps Z2's and Z8's verifiers found
(questions.answer_leak).

FLAG      Correctness flags printed on an option -- a tick / cross,
          "(correct)", "[correct]", "(wrong)", "(right answer)" -- and on the
          options a stem lists inline ("A. Schwannoma ✅"), with the reason
          text after the flag (real rows: 24226 option D "Conjunctival
          xerosis ✔ (Conjunctival xerosis is the first ...)", the stems of
          10206 / 10222). Locked rows lose them on every payload: question
          list / detail, GET /api/tests/<id>/ (QuestionListSerializer), the
          test review rows (tests_engine.entitlement.lock_answer) and the
          mistake notebook. Not flags: "(ANS)", "(right)", "Correct".
ANS       "(ANS)" / "of the ANS: (a) ..." (the autonomic nervous system) is not
          an answer label.
BRACKET   A label inside brackets leaves no dangling bracket.
HTML      An "Explanation" heading (and labels) wrapped in rich-text tags.
REPAIR    plan_repair drops flags, fills an empty key from a single flag and
          reports a flag that names another option than the stored key (rows
          24224-24236 except 24233) in fix_answer_label_leaks's key-conflict
          report.

No AI provider, Supabase or network call is made.
"""
from __future__ import annotations

import json
import tempfile
from datetime import timedelta
from io import StringIO
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Subscription
from accounts.models_freemium import FreeShowcaseQuestion
from questions import answer_leak as al
from questions.models import MistakeNotebook, Question, QuestionRevisionSnapshot, Subject

User = get_user_model()

# Shapes of the restored production bank.
XEROSIS = ('Conjunctival xerosis ✔ (Conjunctival xerosis is the first clinical sign; '
           'night blindness is often earliest symptom.)')
PHRENODERMA = 'Follicular hyperkeratosis (phrenoderma) ✔ (Concept tested: EFA deficiency → phrenoderma)'
TICKED_DOSE = '1 mg ✔'
INICET_STEM = (
    '. Q. A patient presents with hearing loss and balance problems. Histopathology of the \n'
    'lesion shows Antony A and Antony B areas and Verocay bodies. What is the most likely \n'
    'diagnosis? \nA. Schwannoma ✅ \nB. Ependymoma \nC. Meningioma \nD. Medulloblastoma'
)
INICET_STEM_CLEAN = INICET_STEM.replace('Schwannoma ✅ \n', 'Schwannoma\n')
VITAMIN_A = 'The earliest clinical sign that alerts to vitamin A deficiency in a community is:'


def _premium(username):
    user = User.objects.create_user(username=username, email=f'{username}@example.com', password='unused-pw-1')
    Subscription.objects.create(user=user, plan='1_year', status='active',
                                expires_at=timezone.now() + timedelta(days=365))
    return user


def _client(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user)
    return client


def _rows(data):
    return data['results'] if isinstance(data, dict) and 'results' in data else data


# ── Detector: option flags ───────────────────────────────────────────────

class OptionFlagTests(SimpleTestCase):
    CUT = {
        XEROSIS: 'Conjunctival xerosis',
        PHRENODERMA: 'Follicular hyperkeratosis (phrenoderma)',
        TICKED_DOSE: '1 mg',
        'Adrenaline (✓)': 'Adrenaline',
        'Adrenaline ✔️': 'Adrenaline',
        '✔ Conjunctival xerosis': 'Conjunctival xerosis',
        '(correct) Adrenaline': 'Adrenaline',
        'Adrenaline (correct) 0.5 mg IM': 'Adrenaline',
        'Adrenaline [correct]': 'Adrenaline',
        'Adrenaline (Correct Answer)': 'Adrenaline',
        'Adrenaline (right answer)': 'Adrenaline',
        'Atropine (wrong)': 'Atropine',
        'Atropine (Incorrect)': 'Atropine',
        'Atropine ❌ (a muscarinic antagonist)': 'Atropine',
        'Adrenaline (1 mg ✓)': 'Adrenaline (1 mg)',
        # The flag column of the rich-text import pasted as a paragraph.
        '<p>Adrenaline</p>\n<p>correct</p>': '<p>Adrenaline</p>',
        '<p>Conjunctival xerosis ✔ (first sign)</p>': '<p>Conjunctival xerosis</p>',
        'Adrenaline\ncorrect': 'Adrenaline',
    }
    NOT_FLAGS = (
        # Upper-case "(ANS)" is the autonomic nervous system; a mixed-case
        # "(Ans)" marks the answer and is covered in test_answer_flag_ans.
        'Autonomic nervous system (ANS)',
        'Hepatic flexure (right)',
        'Right ventricle',
        'Tube (correctly placed)',
        'Correct',
        'Statement I is incorrect but Statement II is correct',
        'Both A and R are true and R is the correct explanation of A',
        '10 × 10^9/L',
        # A wrapped sentence, not a flag column (statement options).
        'Only 1 is\ncorrect',
        'Both 1 and 2 are\ncorrect',
        'Reason is\nwrong',
    )

    def test_flags_are_cut_with_the_reason_after_them(self):
        for text, expected in self.CUT.items():
            with self.subTest(text=text):
                self.assertTrue(al.has_option_leak(text))
                self.assertFalse(al.has_answer_label(text))  # a flag, not a label
                self.assertEqual(al.cut_option_text(text), expected)
                self.assertEqual(al.label_hold_reasons('Which one?', ['x', text]), ['answer_flag_in_option'])
                self.assertTrue(al.row_has_answer_label({'question_text': 'Which one?', 'option_c': text}))

    def test_not_flags(self):
        for text in self.NOT_FLAGS:
            with self.subTest(text=text):
                self.assertFalse(al.has_option_leak(text))
                self.assertEqual(al.cut_option_text(text), text)
                self.assertEqual(al.label_hold_reasons('Which one?', [text]), [])
                self.assertFalse(al.row_has_answer_label({'question_text': 'Which one?', 'option_a': text}))

    def test_polarity(self):
        self.assertEqual([f.polarity for f in al.find_flags(XEROSIS)], [al.CORRECT])
        self.assertEqual([f.polarity for f in al.find_flags('Atropine ❌')], [al.WRONG])
        self.assertEqual([f.polarity for f in al.find_flags('Atropine [wrong answer]')], [al.WRONG])

    def test_redact_public_text_cuts_options_in_every_row_shape(self):
        row = {'question_text': 'Dose?', 'option_a': '2 mg', 'option_b': TICKED_DOSE,
               'options': {'A': '2 mg', 'B': TICKED_DOSE, 'C': None, 'D': ''}}
        self.assertTrue(al.redact_public_text(row))
        self.assertEqual(row['option_b'], '1 mg')
        self.assertEqual(row['options'], {'A': '2 mg', 'B': '1 mg', 'C': None, 'D': ''})
        self.assertFalse(al.redact_public_text(row))
        listed = {'options': [{'label': 'A', 'text': '2 mg'}, {'label': 'B', 'text': TICKED_DOSE}, 'junk']}
        self.assertTrue(al.row_has_answer_label(listed))
        self.assertTrue(al.redact_public_text(listed))
        self.assertEqual(listed['options'], [{'label': 'A', 'text': '2 mg'}, {'label': 'B', 'text': '1 mg'}, 'junk'])
        self.assertFalse(al.row_has_answer_label({'question_text': 'Dose?', 'option_a': '2 mg', 'options': {}}))


# ── Detector: flags on the options a stem lists ──────────────────────────

class StemFlagTests(SimpleTestCase):
    CASES = {
        INICET_STEM: INICET_STEM_CLEAN,
        # The key line the importer left after them is a label: cut first.
        INICET_STEM + ' \nAnswer:  A': INICET_STEM_CLEAN,
        'What is the diagnosis? A. Schwannoma ✅ B. Ependymoma C. Meningioma':
            'What is the diagnosis? A. Schwannoma B. Ependymoma C. Meningioma',
        'Which is first-line?\n(a) Atropine\n(b) Adrenaline (correct) - first line in anaphylaxis\n(c) Steroid':
            'Which is first-line?\n(a) Atropine\n(b) Adrenaline\n(c) Steroid',
        'Which?\nA. ✅ Schwannoma\nB. Ependymoma': 'Which?\nA. Schwannoma\nB. Ependymoma',
        'Consider:\n1. Statement one ✔ (true because x)\n2. Statement two ✗\nWhich are correct?':
            'Consider:\n1. Statement one\n2. Statement two\nWhich are correct?',
        '<p>Which?</p>\n<p>A. Schwannoma ✅</p>\n<p>B. Ependymoma</p>':
            '<p>Which?</p>\n<p>A. Schwannoma</p>\n<p>B. Ependymoma</p>',
    }

    def test_listed_option_flags_and_their_reasons_go(self):
        for text, expected in self.CASES.items():
            with self.subTest(text=text):
                self.assertEqual(al.redact_stem_text(text), expected)
                self.assertIn('answer_flag_in_stem', al.label_hold_reasons(text, []))
                self.assertTrue(al.row_has_answer_label({'question_text': text}))
                row = {'question_text': text}
                self.assertTrue(al.redact_public_text(row))
                self.assertEqual(row['question_text'], expected)

    def test_the_flag_names_the_listed_option(self):
        self.assertEqual([(f.letter, f.polarity) for f in al.find_flags(INICET_STEM, stem=True)], [('A', al.CORRECT)])
        statements = al.find_flags('1. One ✔\n2. Two ✗', stem=True)
        self.assertEqual([(f.letter, f.polarity) for f in statements], [('', al.CORRECT), ('', al.WRONG)])

    def test_ticks_outside_listed_options_stay(self):
        for text in ('Compare the two:\nFeature | Disease X ✓ | Disease Y ✗',
                     'Which of these is (correct)?', 'Mark the correct statement about the ANS'):
            with self.subTest(text=text):
                self.assertEqual(al.find_flags(text, stem=True), [])
                self.assertEqual(al.redact_stem_text(text), text)
                self.assertEqual(al.label_hold_reasons(text, []), [])


# ── Detector: ANS, brackets, rich text ───────────────────────────────────

class DetectorGapTests(SimpleTestCase):
    def test_the_autonomic_nervous_system_is_not_an_answer_label(self):
        for text in (
            'Which is a feature of the autonomic nervous system (ANS)\n(a) Miosis\n(b) Ptosis',
            'Features of the ANS: (a) sweating (b) miosis',
            'There is involvement of the ANS. A 30-year-old man presents with syncope.',
            'Drugs acting on ANS: (a) Atropine (b) Adrenaline',
        ):
            with self.subTest(text=text):
                self.assertEqual(al.find_labels(text), [])
                self.assertEqual(al.cut_at_answer_label(text), text)
                self.assertEqual(al.label_hold_reasons(text, []), [])
        # Real keys still are labels.
        for text, letter in (('Atropine\nANS: B', 'B'), ('Ans: (b) Incidence Rate', 'B'), ('Gamma ANS. is c', 'C')):
            with self.subTest(text=text):
                self.assertEqual([lab.letter for lab in al.find_labels(text)], [letter])

    def test_a_label_in_brackets_leaves_no_dangling_bracket(self):
        for text, head in (
            ('Adrenaline (Correct Answer: B)', 'Adrenaline'),
            ('Adrenaline (Ans: B)', 'Adrenaline'),
            ('Adrenaline [Answer: B]', 'Adrenaline'),
            ('Adrenaline (1 mg, Correct Answer: B)', 'Adrenaline (1 mg)'),
        ):
            with self.subTest(text=text):
                self.assertEqual(al.cut_at_answer_label(text), head)
                self.assertEqual(al.cut_option_text(text), head)
        plan = al.plan_repair({'question_text': 'Drug of choice?', 'option_a': 'Adrenaline (Correct Answer: A)',
                               'option_b': 'b', 'option_c': 'c', 'option_d': 'd', 'correct_answer': 'A'})
        self.assertEqual(plan.changes, {'option_a': 'Adrenaline'})

    def test_rich_text_headings_and_labels(self):
        for text in (
            '<p>Which nerve?</p>\n<p>Explanation</p>\n<p>The radial nerve ...</p>',
            '<p>Which nerve?</p>\n<p><strong>Explanation</strong></p>\n<p>The radial nerve ...</p>',
            '<p>Which nerve?</p><p><strong>Explanation</strong></p><p>The radial nerve ...</p>',
            '<p>Which nerve?</p>\n<p><strong>Explanation</strong>: The radial nerve ...</p>',
            '<p>Which nerve?</p>\n<p><strong>Why:</strong> the radial nerve ...</p>',
            '<p>Which nerve?</p>\n<p>Detailed Explanations</p>\n<p>Q1 ...</p>',
            '<p>Which nerve?</p>\n<p><strong>Ans:</strong> (b)</p>',
            '<p>Which nerve?</p>\n<p><b>Correct Answer</b>: B</p>',
        ):
            with self.subTest(text=text):
                self.assertTrue(al.has_answer_label(text))
                self.assertEqual(al.cut_at_answer_label(text), '<p>Which nerve?</p>')
        # Z8's probe.
        self.assertEqual(
            al.label_hold_reasons('<p>Which nerve?</p>\n<p>Explanation</p>\n<p>The radial nerve ...</p>', []),
            ['explanation_label_in_public_text'],
        )
        # A heading with nothing after it is no label, as in plain text; nor
        # are prompts / assertion-reason wording in rich text.
        for text in ('<p>Explanation</p>', '<p>Which?</p>\n<p><strong>Explanation</strong></p>', 'Explanation',
                     'Choose the <strong>correct answer</strong>: (a) Gamma (b) Delta',
                     '<p>Select the <b>correct answer</b>:</p>\n<p>(a) 1 only</p>',
                     '<p>R is the correct <b>explanation</b> of A</p>'):
            with self.subTest(text=text):
                self.assertFalse(al.has_answer_label(text))


# ── Repair ───────────────────────────────────────────────────────────────

class FlagRepairTests(SimpleTestCase):
    BASE = dict(question_text=VITAMIN_A, option_a='Night blindness', option_b="Bitot's spots",
                option_c='Keratomalacia', option_d=XEROSIS, correct_answer='D', explanation='')

    def test_a_flag_on_the_key_is_dropped_and_its_reason_moved(self):
        plan = al.plan_repair(dict(self.BASE))
        self.assertFalse(plan.conflict)
        self.assertFalse(plan.deactivate)
        self.assertEqual(plan.category, 'option_answer_flag')
        self.assertEqual(plan.changes['option_d'], 'Conjunctival xerosis')
        self.assertTrue(plan.changes['explanation'].startswith('Conjunctival xerosis is the first clinical sign'))
        self.assertNotIn('correct_answer', plan.changes)
        kept = al.plan_repair({**self.BASE, 'explanation': 'Curated.', 'lock_explanation': True})
        self.assertNotIn('explanation', kept.changes)

    def test_a_flag_on_another_option_than_the_stored_key_is_a_conflict(self):
        # 24224-24236 (except 24233): key A, the tick on another option.
        plan = al.plan_repair({**self.BASE, 'correct_answer': 'A'})
        self.assertTrue(plan.conflict)
        self.assertEqual(plan.conflicts, ['option D is flagged as correct but the stored key is A (kept)'])
        self.assertNotIn('correct_answer', plan.changes)
        self.assertEqual(plan.changes['option_d'], 'Conjunctival xerosis')
        dose = al.plan_repair({'question_text': 'Dose of adrenaline in anaphylaxis?', 'option_a': '0.5 mg',
                               'option_b': TICKED_DOSE, 'option_c': '5 mg', 'option_d': '10 mg',
                               'correct_answer': 'A'})
        self.assertTrue(dose.conflict)
        self.assertEqual(dose.changes, {'option_b': '1 mg'})

    def test_an_empty_key_is_filled_from_a_single_flag(self):
        plan = al.plan_repair({**self.BASE, 'correct_answer': ''})
        self.assertFalse(plan.conflict)
        self.assertEqual(plan.changes['correct_answer'], 'D')
        locked = al.plan_repair({**self.BASE, 'correct_answer': '', 'lock_answer': True})
        self.assertNotIn('correct_answer', locked.changes)

    def test_several_correct_flags_or_a_wrong_flag_on_the_key(self):
        both = al.plan_repair({**self.BASE, 'option_a': 'Night blindness ✔', 'correct_answer': ''})
        self.assertTrue(both.conflict)
        self.assertNotIn('correct_answer', both.changes)
        wrong = al.plan_repair({**self.BASE, 'option_a': 'Night blindness (wrong)',
                                'option_d': 'Conjunctival xerosis', 'correct_answer': 'A'})
        self.assertEqual(wrong.conflicts, ['option A (the stored key) is flagged as wrong (kept)'])
        self.assertEqual(wrong.changes, {'option_a': 'Night blindness'})

    def test_stem_flags_are_dropped_and_checked_against_the_key(self):
        row = {'question_text': INICET_STEM, 'option_a': 'Schwannoma ✅', 'option_b': 'Ependymoma',
               'option_c': 'Meningioma', 'option_d': 'Medulloblastoma', 'correct_answer': 'A'}
        plan = al.plan_repair(row)
        self.assertFalse(plan.conflict)
        self.assertEqual(plan.changes['question_text'], INICET_STEM_CLEAN)
        self.assertEqual(plan.changes['option_a'], 'Schwannoma')
        conflict = al.plan_repair({**row, 'option_a': 'Schwannoma', 'correct_answer': 'C'})
        self.assertEqual(conflict.conflicts, ['the stem flags option A as correct but the stored key is C (kept)'])
        # With the key line after the options the stem is a pasted page: held.
        self.assertTrue(al.plan_repair({**row, 'question_text': INICET_STEM + ' \nAnswer:  A'}).deactivate)

    def test_an_option_that_is_only_a_flag_is_held(self):
        plan = al.plan_repair({**self.BASE, 'option_c': '✔'})
        self.assertTrue(plan.deactivate)
        self.assertEqual(plan.category, 'option_is_label')
        self.assertEqual(plan.changes, {})


class KeyConflictReportTests(TestCase):
    """fix_answer_label_leaks on rows shaped like 24224-24236."""

    @classmethod
    def setUpTestData(cls):
        subject = Subject.objects.create(name='Z9 Flags Nutrition', code='Z9FLAGN')
        common = dict(year=2024, subject=subject, correct_answer='A')
        cls.conflicts = []
        for index in range(12):
            letter = 'BCD'[index % 3]
            options = {f'option_{name}': f'Choice {name.upper()} {index}' for name in 'abcd'}
            options[f'option_{letter.lower()}'] += ' ✔ (Concept tested: nutrition)'
            cls.conflicts.append((
                Question.objects.create(question_text=f'Nutrition question {index}?', **options, **common),
                letter,
            ))
        # Like 24233: no tick.
        cls.clean = Question.objects.create(question_text='Nutrition question clean?', option_a='a',
                                            option_b='b', option_c='c', option_d='d', **common)
        # A tick on the stored key: repaired, not a conflict.
        cls.agrees = Question.objects.create(question_text='Nutrition question agrees?', option_a='Retinol ✅',
                                             option_b='b', option_c='c', option_d='d', **common)

    def _run(self, *args):
        out = StringIO()
        call_command('fix_answer_label_leaks', *args, stdout=out)
        return out.getvalue()

    def test_dry_run_lists_every_flag_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'plan.json'
            out = self._run('--json-report', str(path))
            plan = json.loads(path.read_text(encoding='utf-8'))
        ids = [question.pk for question, _ in self.conflicts]
        self.assertIn('Key conflicts (stored key kept): ' + ', '.join(map(str, ids)), out)
        for question, letter in self.conflicts:
            self.assertIn(f'Q{question.pk} (stored key A): option {letter} is flagged as correct but the '
                          f'stored key is A (kept)', out)
        by_id = {row['id']: row for row in plan['questions']}
        self.assertEqual(set(by_id), {*ids, self.agrees.pk})
        self.assertTrue(all(by_id[pk]['conflict'] and by_id[pk]['stored_key'] == 'A' for pk in ids))
        self.assertFalse(by_id[self.agrees.pk]['conflict'])
        self.assertEqual(by_id[self.agrees.pk]['after']['option_a'], 'Retinol')
        self.assertIn('DRY RUN', out)
        self.assertEqual(Question.objects.filter(needs_review=True).count(), 0)
        self.assertFalse(QuestionRevisionSnapshot.objects.exists())

    def test_apply_drops_the_ticks_and_keeps_the_stored_keys(self):
        self._run('--apply')
        for question, letter in self.conflicts:
            question.refresh_from_db()
            self.assertEqual(question.correct_answer, 'A')
            self.assertTrue(question.needs_review)
            self.assertTrue(question.is_active)
            self.assertNotIn('✔', getattr(question, f'option_{letter.lower()}'))
            self.assertIn('Concept tested: nutrition', question.explanation)
            self.assertTrue(question.revision_snapshots.exists())
        self.clean.refresh_from_db()
        self.assertFalse(self.clean.needs_review)
        self.agrees.refresh_from_db()
        self.assertEqual(self.agrees.option_a, 'Retinol')


# ── Serving guard on every payload ───────────────────────────────────────

class FlagServingGuardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='Z9 Flag Serving', code='Z9FSRV')
        cls.free = User.objects.create_user(username='z9fl-free', email='z9fl-free@example.com',
                                            password='unused-pw-2')
        cls.premium = _premium('z9fl-premium')
        common = dict(year=2024, subject=cls.subject)
        cls.locked = Question.objects.create(question_text=VITAMIN_A, option_a='Night blindness',
                                             option_b="Bitot's spots", option_c='Keratomalacia',
                                             option_d=XEROSIS, correct_answer='D', **common)
        cls.stem_locked = Question.objects.create(question_text=INICET_STEM, option_a='Schwannoma ✅',
                                                  option_b='Ependymoma', option_c='Meningioma',
                                                  option_d='Medulloblastoma', correct_answer='A', **common)
        cls.showcase = Question.objects.create(question_text=VITAMIN_A + ' (showcase)', option_a='Night blindness',
                                               option_b="Bitot's spots", option_c='Keratomalacia',
                                               option_d=XEROSIS, correct_answer='D', **common)
        FreeShowcaseQuestion.objects.create(question=cls.showcase, year=2024, position=0)
        for question in (cls.locked, cls.stem_locked, cls.showcase):
            question.refresh_from_db()  # saving normalises the text

    def setUp(self):
        cache.clear()

    def assert_cut(self, row, question):
        payload = json.dumps(row, default=str)
        for leak in ('✔', '✅', 'first clinical sign'):
            self.assertNotIn(leak, payload)
        if question.pk == self.stem_locked.pk:
            self.assertEqual(row['option_a'], 'Schwannoma')
            self.assertIn('A. Schwannoma', row['question_text'])
            self.assertIn('B. Ependymoma', row['question_text'])
        else:
            self.assertEqual(row['option_d'], 'Conjunctival xerosis')
            self.assertEqual(row['question_text'], question.question_text)

    def assert_full(self, row, question):
        for name in al.PUBLIC_TEXT_FIELDS:
            self.assertEqual(row[name], getattr(question, name), name)

    def _list_row(self, user, question):
        res = _client(user).get('/api/questions/', {'question_id': question.id})
        self.assertEqual(res.status_code, 200, res.data)
        return res.data['results'][0]

    def test_question_list_and_detail(self):
        for question in (self.locked, self.stem_locked):
            self.assert_cut(self._list_row(None, question), question)
            self.assert_cut(self._list_row(self.free, question), question)
            self.assert_full(self._list_row(self.premium, question), question)
            detail = _client().get(f'/api/questions/{question.id}/')
            self.assertEqual(detail.status_code, 200)
            self.assert_cut(detail.data, question)
            self.assert_full(_client(self.premium).get(f'/api/questions/{question.id}/').data, question)
        self.assert_full(self._list_row(self.free, self.showcase), self.showcase)

    def test_test_detail_payload(self):
        from tests_engine.models import Test

        test = Test.objects.create(title='Z9 flag test', test_type='mixed', is_published=True)
        test.questions.set([self.locked, self.stem_locked, self.showcase])
        res = _client(self.free).get(f'/api/tests/{test.id}/')
        self.assertEqual(res.status_code, 200, getattr(res, 'data', None))
        rows = {row['id']: row for row in res.data['questions']}
        self.assert_cut(rows[self.locked.id], self.locked)
        self.assert_cut(rows[self.stem_locked.id], self.stem_locked)
        self.assert_full(rows[self.showcase.id], self.showcase)
        rows = {row['id']: row for row in _client(self.premium).get(f'/api/tests/{test.id}/').data['questions']}
        self.assert_full(rows[self.locked.id], self.locked)

    def test_test_review_and_attempt_detail_endpoints(self):
        from tests_engine.models import QuestionResponse, Test, TestAttempt

        test = Test.objects.create(title='Z9 flag review', test_type='mixed', negative_marking=False)
        test.questions.set([self.locked, self.stem_locked])
        attempt = TestAttempt.objects.create(user=self.free, test=test, is_completed=True,
                                             completed_at=timezone.now())
        for question in (self.locked, self.stem_locked):
            QuestionResponse.objects.create(attempt=attempt, question=question, selected_answer='B',
                                            is_correct=False)
        api = _client(self.free)
        res = api.get(f'/api/tests/{test.id}/review/', {'attempt_id': attempt.id})
        self.assertEqual(res.status_code, 200, getattr(res, 'data', None))
        rows = {row['question_id']: row for row in res.data['questions']}
        self.assertEqual(rows[self.locked.id]['options']['D'], 'Conjunctival xerosis')
        self.assertEqual(rows[self.stem_locked.id]['options']['A'], 'Schwannoma')
        self.assertNotIn('✅', rows[self.stem_locked.id]['question_text'])
        self.assertNotIn('first clinical sign', json.dumps(res.data, default=str))
        res = api.get(f'/api/tests/attempts/{attempt.id}/')
        self.assertEqual(res.status_code, 200, getattr(res, 'data', None))
        details = {resp['question']: resp['question_detail'] for resp in res.data['responses']}
        self.assert_cut(details[self.locked.id], self.locked)
        self.assert_cut(details[self.stem_locked.id], self.stem_locked)

    def test_test_review_rows(self):
        from tests_engine.entitlement import lock_answer

        row = {'question_id': self.stem_locked.id, 'question_text': INICET_STEM, 'correct_answer': 'A',
               'options': {'A': 'Schwannoma ✅', 'B': 'Ependymoma', 'C': 'Meningioma', 'D': XEROSIS}}
        lock_answer(row)
        self.assertEqual(row['question_text'], INICET_STEM_CLEAN)
        self.assertEqual(row['options'], {'A': 'Schwannoma', 'B': 'Ependymoma', 'C': 'Meningioma',
                                          'D': 'Conjunctival xerosis'})

    def test_duplicate_member_previews(self):
        stem = 'Which tumour shows Verocay bodies?\nA. Schwannoma ✅\nB. Ependymoma\nAns: A'
        first = Question.objects.create(question_text=stem, option_a='Schwannoma', option_b='Ependymoma',
                                        option_c='c', option_d='d', correct_answer='A', year=2024,
                                        subject=self.subject)
        Question.objects.create(question_text=stem, option_a='Schwannoma', option_b='Ependymoma',
                                option_c='c', option_d='d', correct_answer='A', year=2024, subject=self.subject)
        res = _client(self.free).get(f'/api/questions/{first.id}/duplicates/')
        self.assertEqual(res.status_code, 200, res.data)
        previews = [member['question_text_preview'] for member in res.data['members']]
        self.assertEqual(len(previews), 2)
        for preview in previews:
            self.assertNotIn('✅', preview)
            self.assertNotIn('Ans', preview)
            self.assertIn('A. Schwannoma', preview)
        res = _client(self.premium).get(f'/api/questions/{first.id}/duplicates/')
        self.assertTrue(all('✅' in member['question_text_preview'] for member in res.data['members']))

    def test_mistake_notebook(self):
        for question in (self.locked, self.stem_locked):
            MistakeNotebook.objects.create(user=self.free, question=question, selected_answer='B',
                                           correct_answer=question.correct_answer, is_correct=False)
        res = _client(self.free).get('/api/analytics/mistake-notebook/')
        self.assertEqual(res.status_code, 200, getattr(res, 'data', None))
        rows = {row['question']: row for row in _rows(res.data)}
        self.assertTrue(rows[self.locked.id]['answer_locked'])
        self.assert_cut(rows[self.locked.id], self.locked)
        self.assert_cut(rows[self.stem_locked.id], self.stem_locked)
