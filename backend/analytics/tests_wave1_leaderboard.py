"""Leaderboard honesty and cost (AN-15 / AN-16 / FE-STU-16).

Before: accuracy defaulted to a made-up 76.5%, weekly XP was 35% of the
all-time total, the period toggle never changed the ranking, the invite
pointed at a 404 (/signup) behind a referral gate that could not be met,
the rival's real name and college were shown to everyone, and every request
aggregated the whole TestAttempt table and loaded every learner.
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

from analytics.models import DailyActivity, StudyStreak, XPEvent
from analytics.views import period_xp_by_user, _leaderboard_period_start
from questions.models import UserQuest
from tests_engine.models import Test, TestAttempt

User = get_user_model()
URL = '/api/analytics/leaderboard/'


class LeaderboardTests(TestCase):
    def setUp(self):
        cache.clear()
        self.test = Test.objects.create(title='LB test', test_type='mixed')
        self.alice = self._learner('alice_u', 1000, first_name='Alice', last_name='Realname', college='AIIMS Delhi')
        self.bob = self._learner('bob_u', 500)  # all-time >= this week's 130
        self.me = self._learner('me_u', 50, first_name='Mina')
        self.client = APIClient()
        self.client.force_authenticate(self.me)

    def _learner(self, username, xp, **extra):
        # A handle chosen at sign-up: one taken from the email address is
        # never shown (tests_wave4_analytics.LeaderboardNamesTests).
        user = User.objects.create_user(username=username, email=f'inbox.{username}@example.com', password='x', **extra)
        StudyStreak.objects.create(user=user, xp_points=xp, current_streak=2)
        return user

    def _active_this_week(self, user):
        """12 first answers today, 5 of them in a test (3 right), one 20 XP quest:
        bank 4 right x15 + 3 wrong x5 = 75, test 3 x10 + 5 = 35, quest 20 -> 130."""
        now = timezone.now()
        DailyActivity.objects.create(user=user, date=timezone.localdate(), questions_attempted=12, correct_answers=7)
        TestAttempt.objects.create(user=user, test=self.test, is_completed=True, completed_at=now,
                                   correct_count=3, incorrect_count=2)
        UserQuest.objects.create(user=user, quest_type='solve_questions', title='q', target_value=1,
                                 xp_reward=20, is_completed=True, is_claimed=True, completed_at=now,
                                 quest_date=timezone.localdate(), expires_at=now + timedelta(hours=1))
        # Older activity must not count towards this week.
        old = now - timedelta(days=40)
        DailyActivity.objects.create(user=user, date=timezone.localdate(old), questions_attempted=10, correct_answers=10)
        TestAttempt.objects.create(user=user, test=self.test, is_completed=True, completed_at=old,
                                   correct_count=10, incorrect_count=0)

    def _get(self, period):
        r = self.client.get(URL, {'period': period})
        self.assertEqual(r.status_code, 200, r.data)
        return r.data

    def test_period_xp_is_rebuilt_from_dated_activity_before_the_ledger(self):
        self._active_this_week(self.bob)
        start = _leaderboard_period_start('weekly')
        self.assertEqual(period_xp_by_user(start), {self.bob.id: 130})

    def test_add_xp_writes_the_ledger_used_for_periods(self):
        streak = StudyStreak.objects.get(user=self.bob)
        streak.add_xp(40)
        self.assertEqual(streak.xp_points, 540)
        self.assertEqual(list(XPEvent.objects.values_list('user_id', 'points')), [(self.bob.id, 40)])
        # Activity on the ledger's first day is not counted twice.
        DailyActivity.objects.create(user=self.bob, date=timezone.localdate(), questions_attempted=1, correct_answers=1)
        start = _leaderboard_period_start('weekly')
        expected = {self.bob.id: 40}
        if start.date() < timezone.localdate():
            # A day before the ledger existed is re-derived from activity rows.
            DailyActivity.objects.create(user=self.alice, date=start.date(), questions_attempted=2, correct_answers=2)
            expected[self.alice.id] = 30
        self.assertEqual(period_xp_by_user(start), expected)
        weekly = self._get('weekly')
        self.assertEqual(weekly['rival']['username'], 'bob_u')
        self.assertEqual(weekly['rival']['xp_points'], 40)

    def test_period_xp_never_exceeds_the_all_time_total(self):
        StudyStreak.objects.get(user=self.bob).add_xp(300)
        StudyStreak.objects.filter(user=self.bob).update(xp_points=0)  # admin progress reset
        self.assertEqual(period_xp_by_user(_leaderboard_period_start('weekly')), {})
        self.assertIsNone(self._get('weekly')['rival'])

    def test_weekly_ranking_uses_this_weeks_xp_not_all_time(self):
        self._active_this_week(self.bob)
        weekly = self._get('weekly')
        self.assertEqual(weekly['rival']['username'], 'bob_u')
        self.assertEqual(weekly['rival']['xp_points'], 130)
        self.assertEqual(weekly['me']['out_of'], 1)
        self.assertIsNone(weekly['me']['rank'])
        self.assertEqual((weekly['me']['weekly_xp'], weekly['me']['period_xp']), (0, 0))

        everything = self._get('all')
        self.assertEqual(everything['rival']['username'], 'alice_u')
        self.assertEqual(everything['rival']['xp_points'], 1000)
        self.assertEqual((everything['me']['rank'], everything['me']['out_of']), (3, 3))
        self.assertEqual(everything['me']['xp_points'], 50)

    def test_accuracy_is_null_without_tests(self):
        self._active_this_week(self.bob)
        data = self._get('all')
        self.assertIsNone(data['me']['accuracy'])
        self.assertIsNone(data['rival']['accuracy'])  # alice has no tests
        bob_view = APIClient()
        bob_view.force_authenticate(self.bob)
        # bob's tests: 3/5 this week + 10/10 earlier -> 13 of 15 answered.
        self.assertEqual(bob_view.get(URL, {'period': 'all'}).data['me']['accuracy'], 86.7)

    def test_rival_and_live_board_show_username_only(self):
        with override_settings(LEADERBOARD_LIVE_THRESHOLD=1):
            data = self._get('all')
        blob = json.dumps(data)
        self.assertNotIn('Realname', blob)
        self.assertNotIn('AIIMS', blob)
        self.assertNotIn('college', data['rival'])
        self.assertTrue(data['live_board_enabled'])
        self.assertEqual([row['username'] for row in data['live_board']], ['alice_u', 'bob_u', 'me_u'])
        self.assertTrue(all('college' not in row for row in data['live_board']))
        # The viewer still sees their own name.
        self.assertEqual(data['me']['username'], 'Mina')

    def test_staff_and_inactive_users_are_not_ranked(self):
        staff = self._learner('staff_u', 99999, is_staff=True)
        self._active_this_week(staff)
        gone = self._learner('gone_u', 5000)
        User.objects.filter(pk=gone.pk).update(is_active=False)
        data = self._get('all')
        self.assertEqual(data['rival']['username'], 'alice_u')
        self.assertEqual(data['me']['out_of'], 3)
        self.assertIsNone(self._get('weekly')['rival'])

    def test_invite_points_at_register_without_referral_promise(self):
        invite = self._get('weekly')['invite']
        self.assertIn('/register?ref=', invite['url'])
        self.assertNotIn('current_referrals', invite)
        self.assertNotIn('unlock', invite['cta'].lower())

    def test_query_count_does_not_grow_with_learners(self):
        def _count(period):
            cache.clear()
            with CaptureQueriesContext(connection) as ctx:
                self._get(period)
            return len(ctx.captured_queries)

        for i in range(3):
            self._active_this_week(self._learner(f'early_{i}', 10 + i))
        before = {p: _count(p) for p in ('weekly', 'monthly', 'all')}
        for i in range(25):
            self._active_this_week(self._learner(f'late_{i}', 20 + i))
        after = {p: _count(p) for p in ('weekly', 'monthly', 'all')}
        self.assertEqual(before, after)
