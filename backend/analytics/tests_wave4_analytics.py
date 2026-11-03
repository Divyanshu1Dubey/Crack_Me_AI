"""Wave-4 analytics fixes (security / performance second pass).

* Leaderboard: other learners are named only by a handle they chose. A
  Google sign-up has no username, so its account got the email address's
  local part (accounts.supabase_rest_auth._create_local_user, '_2', '_3', ...
  on a collision), and every signed-in user saw it on the rival card -- for
  a Gmail user that is the address. Such learners now have ``username: null``.
  Wave 4b: ``_public_name`` uses accounts.handles.exposes_email, and the
  viewer's card gets ``me.public_username`` (the name others see, or null).
* Mistake Notebook: "Due now" is served a page at a time (it returned every
  due entry -- for an active student most of the notebook -- with every
  Question column), the list takes ``?due=true`` for the page's tab, and the
  notebook loads only the question columns the serializer reads.
"""
import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Subscription
from accounts.models_freemium import FreeShowcaseQuestion
from analytics.models import StudyStreak
from analytics.views import _public_name
from questions.models import MistakeNotebook, Question, Subject, Topic

User = get_user_model()
LEADERBOARD = '/api/analytics/leaderboard/'
NOTEBOOK = '/api/analytics/mistake-notebook/'
DUE = f'{NOTEBOOK}due/'
HEAVY = 'W4 heavy AI text '


class PublicNameTests(TestCase):
    def _name(self, username, email):
        return _public_name(User(username=username, email=email))

    def test_email_derived_usernames_are_never_shown(self):
        long_local = 'x' * 145
        for username, email in (
            ('priya.sharma1990', 'priya.sharma1990@gmail.com'),     # Google sign-up
            ('Priya.Sharma1990', 'PRIYA.sharma1990@Gmail.com'),     # any case
            ('priya.sharma1990_2', 'priya.sharma1990@gmail.com'),   # collision suffix
            ('priya.sharma1990@gmail.com', 'other@example.com'),    # an address as username
            ('x' * 140, f'{long_local}@example.com'),               # cut to 140
            ('x' * 130 + '_3', f'{long_local}@example.com'),        # cut to 130 + suffix
            ('', 'someone@example.com'),
            ('   ', ''),
        ):
            with self.subTest(username=username):
                self.assertIsNone(self._name(username, email))
        self.assertIsNone(_public_name(None))

    def test_chosen_handles_are_shown(self):
        self.assertEqual(self._name('cardio_queen', 'priya.sharma1990@gmail.com'), 'cardio_queen')
        self.assertEqual(self._name('priya_sharma', 'priya@gmail.com'), 'priya_sharma')  # not a numeric suffix
        self.assertEqual(self._name('  ortho_ace ', ''), 'ortho_ace')                   # no email to compare


class LeaderboardNamesTests(TestCase):
    def setUp(self):
        cache.clear()
        # Google sign-ups: no username in the Supabase metadata, so the
        # account got the address's local part (the second one with a suffix).
        self.google = self._learner('priya.sharma1990', 'priya.sharma1990@gmail.com', 900)
        self.picked = self._learner('cardio_queen', 'r.verma@example.com', 500)
        self.google_dup = self._learner('priya.sharma1990_2', 'Priya.Sharma1990@outlook.com', 300)
        self.me = self._learner('me_handle', 'me.person@example.com', 10)
        self.client = APIClient()
        self.client.force_authenticate(self.me)

    def _learner(self, username, email, xp):
        user = User.objects.create_user(username=username, email=email, password='x')
        StudyStreak.objects.create(user=user, xp_points=xp, current_streak=1)
        return user

    def _get(self, period, client=None):
        r = (client or self.client).get(LEADERBOARD, {'period': period})
        self.assertEqual(r.status_code, 200, getattr(r, 'data', None))
        return r.data

    def test_rival_below_the_live_threshold_has_no_email_derived_name(self):
        data = self._get('all')
        self.assertFalse(data['live_board_enabled'])
        rival = data['rival']
        self.assertEqual((rival['user_id'], rival['username']), (self.google.id, None))
        # The chase target itself stays: XP, streak, gap.
        self.assertEqual((rival['xp_points'], rival['current_streak'], rival['xp_to_surpass']), (900, 1, 891))
        self.assertNotIn('priya', json.dumps(data).lower())

    def test_weekly_rival_from_the_xp_ledger_has_no_email_derived_name(self):
        StudyStreak.objects.get(user=self.google).add_xp(60)
        StudyStreak.objects.get(user=self.picked).add_xp(20)
        data = self._get('weekly')
        self.assertEqual((data['rival']['user_id'], data['rival']['username'], data['rival']['xp_points']),
                         (self.google.id, None, 60))
        self.assertNotIn('priya', json.dumps(data).lower())

    def test_live_board_names_only_chosen_handles(self):
        with override_settings(LEADERBOARD_LIVE_THRESHOLD=1):
            data = self._get('all')
        self.assertTrue(data['live_board_enabled'])
        self.assertEqual(
            [(row['user_id'], row['username']) for row in data['live_board']],
            [(self.google.id, None), (self.picked.id, 'cardio_queen'), (self.google_dup.id, None),
             (self.me.id, 'me_handle')],
        )
        self.assertNotIn('priya', json.dumps(data).lower())

    def test_a_chosen_handle_is_still_the_rivals_name(self):
        viewer = APIClient()
        viewer.force_authenticate(self.google)
        data = self._get('all', viewer)
        self.assertEqual((data['rival']['user_id'], data['rival']['username']), (self.picked.id, 'cardio_queen'))
        # The viewer's own card still names them (it is only theirs).
        self.assertEqual(data['me']['username'], 'priya.sharma1990')

    def test_the_viewer_is_told_the_name_others_see(self):
        """Wave 4b: ``me.public_username`` is the viewer's own board name
        (``_public_name``), shown on their card with a link to Settings;
        null when other learners see them without a name."""
        me = self._get('all')['me']
        self.assertEqual((me['username'], me['public_username']), ('me_handle', 'me_handle'))
        named = self._learner('ortho_meera', 'meera.iyer@example.com', 40)
        User.objects.filter(pk=named.pk).update(first_name='Meera', last_name='Iyer')
        google = APIClient()
        google.force_authenticate(self.google)
        named_client = APIClient()
        named_client.force_authenticate(User.objects.get(pk=named.pk))
        for client, card_name, board_name in ((google, 'priya.sharma1990', None),
                                              (named_client, 'Meera Iyer', 'ortho_meera')):
            for period in ('weekly', 'monthly', 'all'):
                with self.subTest(card=card_name, period=period):
                    me = self._get(period, client)['me']
                    self.assertEqual((me['username'], me['public_username']), (card_name, board_name))


def _question(subject, i, **kw):
    data = dict(question_text=f'W4 notebook Q{i}', option_a='A1', option_b='B1', option_c='C1', option_d='D1',
                correct_answer='B', explanation=f'W4 explanation {i}', year=2024, subject=subject,
                ai_explanation=HEAVY * 40, concept_explanation=HEAVY * 40, ai_references=[HEAVY] * 5)
    data.update(kw)
    return Question.objects.create(**data)


class MistakeNotebookPagingTests(TestCase):
    def setUp(self):
        self.subject = Subject.objects.create(name='W4 Notebook', code='W4NB')
        self.topic = Topic.objects.create(subject=self.subject, name='W4 Topic')
        self.user = User.objects.create_user(username='w4-nb-premium', password='x')
        Subscription.objects.create(user=self.user, plan='1_year', status='active',
                                    expires_at=timezone.now() + timedelta(days=30))
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.now = timezone.now()
        # 25 due entries, oldest review first in this list.
        self.due_ids = [self._entry(self.user, i, minutes_ago=200 - i).id for i in range(25)]
        # Not due: a review later on, and a mastered entry.
        self.later = self._entry(self.user, 90, minutes_ago=-60 * 24 * 2)
        self.mastered = self._entry(self.user, 91, minutes_ago=60 * 24, review_status='mastered')

    def _entry(self, user, i, minutes_ago, **kw):
        question = _question(self.subject, i, topic=self.topic)
        return MistakeNotebook.objects.create(
            user=user, question=question, selected_answer='A', correct_answer='B', is_correct=False,
            next_review_at=self.now - timedelta(minutes=minutes_ago), **kw)

    def _get(self, url, client=None, **params):
        r = (client or self.client).get(url, params)
        self.assertEqual(r.status_code, 200, getattr(r, 'data', None))
        return r.data

    @staticmethod
    def _ids(data):
        return [row['id'] for row in data['results']]

    def test_due_is_served_a_page_at_a_time_oldest_first(self):
        first = self._get(DUE)
        self.assertEqual((first['count'], first['page'], first['page_size']), (25, 1, 20))
        self.assertEqual(self._ids(first), self.due_ids[:20])
        second = self._get(DUE, page=2)
        self.assertEqual((second['count'], self._ids(second)), (25, self.due_ids[20:]))
        self.assertEqual(self._get(DUE, page=3)['results'], [])
        everything = self._get(DUE, page_size=500)  # capped at 100
        self.assertEqual((everything['page_size'], self._ids(everything)), (100, self.due_ids))
        self.assertEqual(self.client.get(DUE, {'page': 'x'}).status_code, 400)
        # The full row the page needs is still there (premium: the key too).
        row = first['results'][0]
        self.assertEqual((row['question_text'], row['option_b'], row['correct_answer'], row['explanation'],
                          row['subject_name'], row['topic_name'], row['exam_type'], row['answer_locked']),
                         ('W4 notebook Q0', 'B1', 'B', 'W4 explanation 0', 'W4 Notebook', 'W4 Topic', 'cms', False))

    def test_list_due_filter_is_the_due_set(self):
        page = self._get(NOTEBOOK, due='true', page_size=10)
        self.assertEqual((page['count'], self._ids(page)), (25, self.due_ids[:10]))
        self.assertEqual(self._ids(self._get(NOTEBOOK, due='true', page_size=10, page=3)), self.due_ids[20:])
        self.assertEqual(self._get(NOTEBOOK, due='true', review_status='mastered')['count'], 0)
        # Without the filter the list is every entry, as before.
        everything = self._get(NOTEBOOK, page_size=100)
        self.assertEqual(everything['count'], 27)
        self.assertEqual(set(self._ids(everything)), {*self.due_ids, self.later.id, self.mastered.id})

    def test_reviewed_entries_leave_the_due_set(self):
        self.assertEqual(self.client.post(f'{NOTEBOOK}{self.due_ids[0]}/review/').status_code, 200)
        page = self._get(NOTEBOOK, due='true')
        self.assertEqual((page['count'], self._ids(page)), (24, self.due_ids[1:21]))
        self.assertEqual(self._get(DUE)['count'], 24)

    def test_heavy_question_columns_are_not_loaded(self):
        with CaptureQueriesContext(connection) as ctx:
            self._get(DUE)
        selects = [q['sql'] for q in ctx.captured_queries if 'questions_mistakenotebook' in q['sql']
                   and 'question_text' in q['sql']]
        self.assertEqual(len(selects), 1, ctx.captured_queries)
        for column in ('ai_explanation', 'concept_explanation', 'ai_references', 'textbook_references',
                       'reference_text', 'why_correct'):
            self.assertNotIn(column, selects[0])

    def test_query_count_does_not_grow_with_rows(self):
        """A column the serializer reads but the queryset skipped would load per row."""
        free = User.objects.create_user(username='w4-nb-free', password='x')
        client = APIClient()
        client.force_authenticate(free)

        def _queries():
            with CaptureQueriesContext(connection) as ctx:
                data = self._get(DUE, client, page_size=100)
            return len(ctx.captured_queries), data

        def _add(start, n):
            for i in range(start, start + n):
                entry = self._entry(free, 100 + i, minutes_ago=50 - i)
                if i % 2 == 0:  # showcase: free users see these keys
                    FreeShowcaseQuestion.objects.create(question=entry.question, year=2024, position=i)

        _add(0, 4)
        before, data = _queries()
        self.assertEqual(data['count'], 4)
        rows = {row['question_text']: row for row in data['results']}
        self.assertEqual((rows['W4 notebook Q100']['correct_answer'], rows['W4 notebook Q100']['answer_locked']),
                         ('B', False))
        self.assertEqual((rows['W4 notebook Q101']['correct_answer'], rows['W4 notebook Q101']['explanation'],
                          rows['W4 notebook Q101']['answer_locked']), ('', '', True))
        _add(4, 12)
        after, data = _queries()
        self.assertEqual(data['count'], 16)
        self.assertEqual(before, after)

    def test_patch_and_review_still_save_the_entry(self):
        entry_id = self.due_ids[3]
        r = self.client.patch(f'{NOTEBOOK}{entry_id}/', {'user_note': 'W4 note', 'is_flagged': True}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data['user_note'], r.data['question_text']), ('W4 note', 'W4 notebook Q3'))
        entry = MistakeNotebook.objects.get(pk=entry_id)
        self.assertEqual((entry.user_note, entry.is_flagged, entry.selected_answer), ('W4 note', True, 'A'))
        r = self.client.post(f'{NOTEBOOK}{entry_id}/review/')
        self.assertEqual((r.data['review_status'], r.data['review_count']), ('learning', 1))
        entry.refresh_from_db()
        self.assertEqual((entry.review_count, entry.user_note), (1, 'W4 note'))
