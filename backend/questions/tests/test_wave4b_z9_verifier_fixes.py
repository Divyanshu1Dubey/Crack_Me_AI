"""Wave 4b Z9: the problems the wave-4b verifier found.

SEARCH    The text filters matched the raw stem / options of a locked row
          whose public text leaks its key, so the match named the key though
          the displayed text had it cut: GET /api/questions/?question_id=<id>
          &search="Schwannoma ✅" returned the row and "Ependymoma ✅" did
          not; GET /api/questions/recall_search/?drug=Correct Answer: B
          returned exactly the rows labelled B. A locked leaky row now stays
          in a text-filtered result only when the terms occur in the text
          the caller sees (questions.locked_text_search). Premium / staff
          callers and free-showcase rows keep the raw match.
FEEDBACK  POST /api/questions/feedback/ (AllowAny) answered 201 with the raw
          stem of any question, removed / held ones (is_active=False)
          included. Non-staff reporters now report on the active bank and
          get the stem as the question bank shows it to them.
TRAILING  A last line "correct" / "wrong" that ends a wrapped sentence
          ("Only 1 is\\ncorrect", "Both 1 and 2 are\\ncorrect") is not a flag
          column: not cut, not held by the import gates, not "repaired". A
          real trailing flag never fills an empty key (reported instead).

No AI provider, Supabase or network call is made.
"""
from __future__ import annotations

from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Subscription
from accounts.models_freemium import FreeShowcaseQuestion
from questions import answer_leak as al
from questions import locked_text_search
from questions.models import Question, QuestionFeedback, Subject

User = get_user_model()

TICKED_STEM = (
    'A patient presents with hearing loss. Histopathology shows Verocay bodies. '
    'What is the most likely diagnosis?\nA. Schwannoma ✅\nB. Ependymoma\nC. Meningioma\nD. Medulloblastoma'
)
LABELLED_OPTION = 'Antihistamine Correct Answer: B. Adrenaline'
PASTED_STEM = 'Which drug is first line in anaphylaxis?\nAns: (b) Adrenaline because it reverses shock'


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


class _Bank(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='Z9 Search Oracle', code='Z9SRCH')
        cls.free = User.objects.create_user(username='z9so-free', email='z9so-free@example.com',
                                            password='unused-pw-2')
        cls.premium = _premium('z9so-premium')
        cls.staff = User.objects.create_user(username='z9so-staff', email='z9so-staff@example.com',
                                             password='unused-pw-3', role='admin', is_staff=True)
        common = dict(year=2024, subject=cls.subject)
        cls.ticked = Question.objects.create(
            question_text=TICKED_STEM, option_a='Schwannoma', option_b='Ependymoma', option_c='Meningioma',
            option_d='Medulloblastoma', correct_answer='A', **common)
        cls.labelled = Question.objects.create(
            question_text='Drug of choice in anaphylactic shock?', option_a='Atropine', option_b='Adrenaline',
            option_c='Hydrocortisone', option_d=LABELLED_OPTION, correct_answer='B', **common)
        cls.pasted = Question.objects.create(
            question_text=PASTED_STEM, option_a='Atropine', option_b='Adrenaline', option_c='Hydrocortisone',
            option_d='Antihistamine', correct_answer='B', **common)
        cls.showcase = Question.objects.create(
            question_text='Showcase. ' + TICKED_STEM, option_a='Schwannoma', option_b='Ependymoma',
            option_c='Meningioma', option_d='Medulloblastoma', correct_answer='A', **common)
        FreeShowcaseQuestion.objects.create(question=cls.showcase, year=2024, position=0)
        cls.inactive = Question.objects.create(
            question_text=PASTED_STEM + ' (held)', option_a='Atropine', option_b='Adrenaline',
            option_c='Hydrocortisone', option_d='Antihistamine', correct_answer='B', is_active=False, **common)
        for question in (cls.ticked, cls.labelled, cls.pasted, cls.showcase, cls.inactive):
            question.refresh_from_db()  # saving normalises the text

    def setUp(self):
        cache.clear()


# ── Question-bank ?search= and recall search ─────────────────────────────

class SearchOracleTests(_Bank):
    def _list_ids(self, user, **params):
        res = _client(user).get('/api/questions/', params)
        self.assertEqual(res.status_code, 200, res.data)
        return [row['id'] for row in res.data['results']]

    def _recall_ids(self, user, **params):
        res = _client(user).get('/api/questions/recall_search/', params)
        self.assertEqual(res.status_code, 200, res.data)
        return [row['id'] for row in res.data['results']]

    def test_the_list_search_does_not_match_inside_a_cut_flag(self):
        self.assertIn('Schwannoma ✅', self.ticked.question_text)
        for user in (None, self.free):
            with self.subTest(user=getattr(user, 'username', 'anonymous')):
                one = {'question_id': self.ticked.id}
                # Both probes now look the same: no row.
                self.assertEqual(self._list_ids(user, search='"Schwannoma ✅"', **one), [])
                self.assertEqual(self._list_ids(user, search='"Ependymoma ✅"', **one), [])
                self.assertEqual(self._list_ids(user, search='✅', **one), [])
                self.assertNotIn(self.ticked.id, self._list_ids(user, search='"Schwannoma ✅"'))
                # Terms the caller sees still find the row.
                self.assertEqual(self._list_ids(user, search='Schwannoma', **one), [self.ticked.id])
                self.assertEqual(self._list_ids(user, search='Verocay Schwannoma', **one), [self.ticked.id])
                # A stem cut at its "Ans:" line: the key after it no longer matches.
                two = {'question_id': self.pasted.id}
                self.assertEqual(self._list_ids(user, search='"(b) Adrenaline"', **two), [])
                self.assertEqual(self._list_ids(user, search='reverses', **two), [])
                self.assertEqual(self._list_ids(user, search='anaphylaxis', **two), [self.pasted.id])

    def test_full_access_and_showcase_rows_keep_the_raw_match(self):
        for user in (self.premium, self.staff):
            with self.subTest(user=user.username):
                self.assertEqual(self._list_ids(user, question_id=self.ticked.id, search='"Schwannoma ✅"'),
                                 [self.ticked.id])
        for user in (None, self.free):
            with self.subTest(user=getattr(user, 'username', 'anonymous')):
                self.assertEqual(self._list_ids(user, question_id=self.showcase.id, search='"Schwannoma ✅"'),
                                 [self.showcase.id])

    def test_recall_search_keywords_and_q(self):
        for letter in 'ABCD':
            with self.subTest(letter=letter):
                self.assertNotIn(self.labelled.id, self._recall_ids(None, drug=f'Correct Answer: {letter}'))
        self.assertIn(self.labelled.id, self._recall_ids(None, drug='Antihistamine'))
        self.assertNotIn(self.ticked.id, self._recall_ids(None, diagnosis='Schwannoma ✅'))
        self.assertIn(self.ticked.id, self._recall_ids(None, diagnosis='Schwannoma'))
        self.assertNotIn(self.pasted.id, self._recall_ids(None, q='(b)'))
        self.assertNotIn(self.pasted.id, self._recall_ids(None, q='reverses'))
        self.assertIn(self.pasted.id, self._recall_ids(None, q='anaphylaxis'))
        # q also filters the stem by the whole phrase: one running from the
        # visible part into the cut part names the key as well.
        self.assertNotIn(self.pasted.id, self._recall_ids(None, q='anaphylaxis?\nAns: (b)'))
        # Premium callers read every answer: the raw match stays.
        self.assertIn(self.labelled.id, self._recall_ids(self.premium, drug='Correct Answer: B'))
        self.assertIn(self.pasted.id, self._recall_ids(self.premium, q='reverses'))
        self.assertIn(self.pasted.id, self._recall_ids(self.premium, q='anaphylaxis?\nAns: (b)'))

    def test_the_cached_set_follows_question_saves(self):
        question = Question.objects.create(
            question_text='Night blindness is due to the deficiency of?', option_a='Vitamin A',
            option_b='Vitamin B12', option_c='Vitamin C', option_d='Vitamin D', correct_answer='A',
            year=2024, subject=self.subject)
        self.assertNotIn(question.id, locked_text_search.leaky_public_texts())
        self.assertIsNotNone(cache.get(locked_text_search.CACHE_KEY))
        # A save that cannot change the public text keeps the cached set, as
        # does a save that leaves the row clean (imports, admin edits).
        question.ai_explanation = 'Retinol.'
        question.save(update_fields=['ai_explanation'])
        self.assertIsNotNone(cache.get(locked_text_search.CACHE_KEY))
        question.option_b = 'Vitamin B1'
        question.save()
        self.assertIsNotNone(cache.get(locked_text_search.CACHE_KEY))
        # One that leaves it leaking drops it; the next search sees the leak.
        question.question_text = ('Night blindness is due to the deficiency of?\nA. Vitamin A ✔ (first sign)'
                                  '\nB. Vitamin B12')
        question.save()
        self.assertIsNone(cache.get(locked_text_search.CACHE_KEY))
        self.assertEqual(self._list_ids(None, question_id=question.id, search='"first sign"'), [])
        self.assertEqual(self._list_ids(None, question_id=question.id, search='"Vitamin A"'), [question.id])
        self.assertIn(question.id, locked_text_search.leaky_public_texts())

    def test_a_scan_that_raced_a_leaky_save_is_not_cached(self):
        original = locked_text_search._visible_texts

        def racing(*args):
            locked_text_search.invalidate()  # a leaky row was saved meanwhile
            return original(*args)

        with mock.patch.object(locked_text_search, '_visible_texts', side_effect=racing):
            self.assertIn(self.ticked.id, locked_text_search.leaky_public_texts())
        self.assertIsNone(cache.get(locked_text_search.CACHE_KEY))
        locked_text_search.leaky_public_texts()
        self.assertIsNotNone(cache.get(locked_text_search.CACHE_KEY))

    def test_the_scan_sees_what_the_api_shows(self):
        texts = locked_text_search.leaky_public_texts()
        self.assertEqual(set(texts) & {self.ticked.id, self.labelled.id, self.pasted.id, self.showcase.id},
                         {self.ticked.id, self.labelled.id, self.pasted.id, self.showcase.id})
        self.assertNotIn(self.inactive.id, texts)  # removed / held rows are not served
        self.assertNotIn('✅', texts[self.ticked.id][0])
        self.assertIn('a. schwannoma', texts[self.ticked.id][0])
        self.assertEqual(texts[self.labelled.id][4], 'antihistamine')
        self.assertEqual(texts[self.pasted.id][0], 'which drug is first line in anaphylaxis?')


# ── Feedback echo ────────────────────────────────────────────────────────

class FeedbackEchoTests(_Bank):
    def _report(self, user, question):
        return _client(user).post('/api/questions/feedback/', {
            'question': question.id, 'category': 'wrong_answer', 'comment': 'z9 probe',
        }, format='json')

    def test_reporters_get_the_stem_as_the_bank_shows_it(self):
        for user in (None, self.free):
            with self.subTest(user=getattr(user, 'username', 'anonymous')):
                res = self._report(user, self.ticked)
                self.assertEqual(res.status_code, 201, res.data)
                self.assertNotIn('✅', res.data['question_text'])
                self.assertIn('A. Schwannoma', res.data['question_text'])
                res = self._report(user, self.pasted)
                self.assertEqual(res.status_code, 201, res.data)
                self.assertEqual(res.data['question_text'], 'Which drug is first line in anaphylaxis?')
        # The showcase row's answer is free: its stem is shown as stored.
        self.assertEqual(self._report(None, self.showcase).data['question_text'], self.showcase.question_text)
        self.assertEqual(self._report(self.premium, self.ticked).data['question_text'], self.ticked.question_text)

    def test_removed_or_held_questions_cannot_be_reported_by_non_staff(self):
        for user in (None, self.free, self.premium):
            with self.subTest(user=getattr(user, 'username', 'anonymous')):
                res = self._report(user, self.inactive)
                self.assertEqual(res.status_code, 400, res.data)
                self.assertIn('question', res.data)
                self.assertNotIn('Adrenaline', str(res.data))
        self.assertFalse(QuestionFeedback.objects.filter(question=self.inactive).exists())

    def test_staff_keep_the_raw_stem(self):
        res = self._report(self.staff, self.inactive)
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data['question_text'], self.inactive.question_text)
        self._report(None, self.ticked)
        res = _client(self.staff).get('/api/questions/feedback/')
        self.assertEqual(res.status_code, 200, res.data)
        rows = res.data['results'] if isinstance(res.data, dict) else res.data
        texts = {row['question']: row['question_text'] for row in rows}
        self.assertEqual(texts[self.ticked.id], self.ticked.question_text)
        self.assertEqual(texts[self.inactive.id], self.inactive.question_text)


# ── Trailing "correct" / "wrong" lines ───────────────────────────────────

class TrailingFlagLineTests(SimpleTestCase):
    SENTENCES = (
        'Only 1 is\ncorrect', 'Only 2 is\ncorrect', 'Both 1 and 2 are\ncorrect', 'Neither is\ncorrect',
        'Reason is\nwrong', 'Assertion is true but the reason is\nincorrect', 'Both are\nCorrect',
        '<p>Only 1 is</p>\n<p>correct</p>', 'Only 1 is<br>correct',
    )
    FLAG_COLUMNS = {
        'Adrenaline\ncorrect': 'Adrenaline',
        'Vitamin A\nCorrect': 'Vitamin A',
        '<p>Adrenaline</p>\n<p>correct</p>': '<p>Adrenaline</p>',
        'Atropine\nwrong': 'Atropine',
    }
    STATEMENTS = {
        'question_text': 'Consider the following:\n1. Statement one\n2. Statement two\nWhich is/are correct?',
        'option_a': 'Only 1 is\ncorrect', 'option_b': 'Only 2 is\ncorrect',
        'option_c': 'Both 1 and 2 are\ncorrect', 'option_d': 'Neither is\ncorrect',
    }

    def test_a_wrapped_sentence_is_not_a_flag(self):
        for text in self.SENTENCES:
            with self.subTest(text=text):
                self.assertEqual(al.find_flags(text), [])
                self.assertFalse(al.has_option_leak(text))
                self.assertEqual(al.cut_option_text(text), text)
                self.assertEqual(al.label_hold_reasons('Which?', [text]), [])

    def test_a_flag_column_still_is(self):
        for text, cut in self.FLAG_COLUMNS.items():
            with self.subTest(text=text):
                flags = al.find_flags(text)
                self.assertEqual(len(flags), 1)
                self.assertTrue(flags[0].trailing)
                self.assertEqual(al.cut_option_text(text), cut)
                self.assertEqual(al.label_hold_reasons('Which?', [text]), ['answer_flag_in_option'])

    def test_statement_options_are_left_alone(self):
        for key in ('', 'C'):
            with self.subTest(key=key):
                row = {**self.STATEMENTS, 'correct_answer': key}
                self.assertFalse(al.row_has_answer_label(row))
                plan = al.plan_repair(row)
                self.assertFalse(plan.needed)
                self.assertEqual(plan.changes, {})
                self.assertFalse(plan.conflict)

    def test_a_trailing_flag_never_fills_an_empty_key(self):
        row = {'question_text': 'Drug of choice in anaphylaxis?', 'option_a': 'Atropine',
               'option_b': 'Adrenaline\ncorrect', 'option_c': 'Hydrocortisone', 'option_d': 'Antihistamine',
               'explanation': ''}
        empty = al.plan_repair({**row, 'correct_answer': ''})
        self.assertNotIn('correct_answer', empty.changes)
        self.assertEqual(empty.changes['option_b'], 'Adrenaline')
        self.assertTrue(empty.conflict)
        self.assertEqual(empty.conflicts,
                         ['option B ends in a "correct" line (a flag column?) and the key is empty '
                          '(not applied, review)'])
        agrees = al.plan_repair({**row, 'correct_answer': 'B'})
        self.assertFalse(agrees.conflict)
        self.assertEqual(agrees.changes, {'option_b': 'Adrenaline'})
        differs = al.plan_repair({**row, 'correct_answer': 'A'})
        self.assertEqual(differs.conflicts, ['option B is flagged as correct but the stored key is A (kept)'])
        # A tick still fills an empty key.
        ticked = al.plan_repair({**row, 'option_b': 'Adrenaline ✔', 'correct_answer': ''})
        self.assertEqual(ticked.changes['correct_answer'], 'B')
