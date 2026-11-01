"""Wave-2 analytics fixes.

* Feedback list: DRF-style next/previous links so admins can page back to
  older feedback (the list became paginated in wave 1).
* Study time: a malformed ?start= / ?end= is a 400, not a 500.
* Empty test submits (no answer) are not "tests taken" for the leaderboard,
  the rebuilt period XP, the dashboard and the score prediction.
* The XP-ledger start is stored once, so deleting the earliest ledger rows
  (they cascade with their user) does not move it.
* Public event ingest: server-only event names are refused, the name must be
  snake_case, odd payload types do not 500, and the country comes from the
  edge header.
* Admin announcements: ?all=1 is an alias of ?scope=all.
* Mistake notebook: scholarship-test answers stay hidden from non-subscribers.
* Background notifications reuse accounts.emails.run_in_background and the
  worker thread closes its own DB connection.
"""
import threading
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from analytics.models import AnalyticsEvent, Announcement, Feedback, StudyStreak, XPEvent
from analytics.views import (QUEST_FREEZE_EVENT, XP_LEDGER_START_EVENT, _leaderboard_period_start,
                             _run_in_background, _xp_ledger_first_day, period_xp_by_user)
from questions.models import MistakeNotebook, Question, QuestionAttempt, StudyTimeBreakdown, Subject
from tests_engine.models import Test, TestAttempt

User = get_user_model()


class FeedbackPagingTests(TestCase):
    URL = '/api/analytics/feedback/'

    def setUp(self):
        student = User.objects.create_user(username='fbp-student', password='x')
        base = timezone.now()
        for i in range(5):
            fb = Feedback.objects.create(user=student, title=f'fb {i}', message='m')
            Feedback.objects.filter(pk=fb.pk).update(created_at=base + timedelta(minutes=i))
        self.admin = APIClient()
        self.admin.force_authenticate(User.objects.create_user(username='fbp-admin', password='x', role='admin'))

    def test_admin_can_follow_next_to_older_feedback(self):
        first = self.admin.get(self.URL, {'page_size': 2}).data
        self.assertEqual((first['count'], len(first['results'])), (5, 2))
        self.assertIsNone(first['previous'])
        self.assertIn('page=2', first['next'])
        self.assertIn('page_size=2', first['next'])

        seen = [row['title'] for row in first['results']]
        url = first['next']
        while url:
            page = self.admin.get(url).data
            seen += [row['title'] for row in page['results']]
            url = page['next']
        self.assertEqual(seen, [f'fb {i}' for i in range(4, -1, -1)])  # newest first, nothing skipped

        last = self.admin.get(self.URL, {'page_size': 2, 'page': 3}).data
        self.assertIsNone(last['next'])
        self.assertIn('page=2', last['previous'])
        second = self.admin.get(self.URL, {'page_size': 2, 'page': 2}).data
        self.assertNotIn('page=', second['previous'])  # page 1 is the bare URL

    def test_default_page_without_more_rows_has_no_links(self):
        data = self.admin.get(self.URL).data
        self.assertEqual((data['count'], data['next'], data['previous']), (5, None, None))


class StudyTimeDateTests(TestCase):
    URL = '/api/analytics/study-time/'

    def setUp(self):
        self.user = User.objects.create_user(username='st-dates', password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        subject = Subject.objects.create(name='ST Subject', code='STS')
        today = timezone.localdate()
        for days_ago in (0, 10):
            StudyTimeBreakdown.objects.create(user=self.user, subject=subject, seconds=60,
                                              question_count=1, date=today - timedelta(days=days_ago))
        self.today = today

    def test_malformed_dates_are_a_400(self):
        for params in ({'start': 'not-a-date'}, {'end': '2026-13-45'}, {'start': '01/11/2026'}):
            r = self.client.get(self.URL, params)
            self.assertEqual(r.status_code, 400, params)
            self.assertIn('YYYY-MM-DD', r.data['error'])

    def test_valid_range_filters_rows(self):
        start = (self.today - timedelta(days=3)).isoformat()
        data = self.client.get(self.URL, {'start': start, 'end': self.today.isoformat()}).data
        self.assertEqual([row['date'] for row in data['breakdown']], [self.today.isoformat()])
        self.assertEqual(len(self.client.get(self.URL).data['breakdown']), 2)


class EmptySubmitTests(TestCase):
    """A submitted test with no answers is not a test taken."""

    def setUp(self):
        cache.clear()
        self.test = Test.objects.create(title='Empty-submit test', test_type='mixed')
        self.me = User.objects.create_user(username='es-me', password='x')
        StudyStreak.objects.create(user=self.me, xp_points=100)
        self.client = APIClient()
        self.client.force_authenticate(self.me)

    def _attempt(self, user, correct, incorrect, unanswered=0, days_ago=0):
        when = timezone.now() - timedelta(days=days_ago)
        attempt = TestAttempt.objects.create(user=user, test=self.test, is_completed=True, completed_at=when,
                                             correct_count=correct, incorrect_count=incorrect,
                                             unanswered_count=unanswered, score=correct - incorrect / 3)
        TestAttempt.objects.filter(pk=attempt.pk).update(started_at=when)
        return attempt

    def test_leaderboard_counts_only_answered_tests(self):
        self._attempt(self.me, 3, 1)
        for _ in range(4):
            self._attempt(self.me, 0, 0, unanswered=10)
        me = self.client.get('/api/analytics/leaderboard/', {'period': 'all'}).data['me']
        self.assertEqual(me['tests_completed'], 1)
        self.assertEqual(me['accuracy'], 75.0)

    def test_rebuilt_period_xp_gives_no_completion_xp_for_empty_submits(self):
        rival = User.objects.create_user(username='es-rival', password='x')
        StudyStreak.objects.create(user=rival, xp_points=1000)
        for _ in range(6):
            self._attempt(rival, 0, 0, unanswered=10)
        self.assertEqual(period_xp_by_user(_leaderboard_period_start('weekly')), {})
        self._attempt(rival, 2, 0)  # 2 x 10 + 5 completion bonus
        self.assertEqual(period_xp_by_user(_leaderboard_period_start('weekly')), {rival.id: 25})

    def test_dashboard_and_prediction_ignore_empty_submits(self):
        for day in (5, 4):
            self._attempt(self.me, 50, 50, days_ago=day)
        for day in (3, 2, 1):
            self._attempt(self.me, 0, 0, unanswered=100, days_ago=day)
        overall = self.client.get('/api/analytics/dashboard/').data['overall']
        self.assertEqual(overall['total_tests'], 2)
        bundle = self.client.get('/api/analytics/dashboard/bundle/').data['dashboard']['overall']
        self.assertEqual(bundle['total_tests'], 2)
        self.assertIn('total_time_minutes', bundle)
        # Two answered tests are not enough for a prediction (three needed).
        self.assertIsNone(self.client.get('/api/analytics/score-prediction/').data['predicted_score'])
        trend = self.client.get('/api/analytics/performance-trend/').data
        self.assertEqual(trend['total_tests'], 2)


class XPLedgerStartTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_ledger_start_survives_deleting_the_earliest_rows(self):
        early = User.objects.create_user(username='xp-early', password='x')
        late = User.objects.create_user(username='xp-late', password='x')
        long_ago = timezone.now() - timedelta(days=20)
        XPEvent.objects.create(user=early, points=10, created_at=long_ago)
        XPEvent.objects.create(user=late, points=10, created_at=timezone.now())
        first_day = _xp_ledger_first_day()
        self.assertEqual(first_day.date(), timezone.localtime(long_ago).date())
        self.assertEqual(AnalyticsEvent.objects.filter(event_name=XP_LEDGER_START_EVENT).count(), 1)

        early.delete()  # cascades to the earliest ledger row
        cache.clear()
        self.assertEqual(_xp_ledger_first_day(), first_day)
        self.assertEqual(AnalyticsEvent.objects.filter(event_name=XP_LEDGER_START_EVENT).count(), 1)

    def test_empty_ledger_has_no_start_and_writes_no_marker(self):
        self.assertIsNone(_xp_ledger_first_day())
        self.assertFalse(AnalyticsEvent.objects.filter(event_name=XP_LEDGER_START_EVENT).exists())


class IngestHardeningTests(TestCase):
    URL = '/api/analytics/events/'

    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def test_server_only_and_malformed_names_are_refused(self):
        for name in (QUEST_FREEZE_EVENT, XP_LEDGER_START_EVENT, 'Page View', 'page-view', '', 'x' * 65, 42):
            r = self.client.post(self.URL, {'event_name': name}, format='json')
            self.assertEqual(r.status_code, 400, name)
        self.assertFalse(AnalyticsEvent.objects.exists())

    def test_country_comes_from_the_edge_header(self):
        r = self.client.post(self.URL, {'event_name': 'page_view', 'path': '/blog/x', 'country': 'ZZ'},
                             format='json', HTTP_X_VERCEL_IP_COUNTRY='in')
        self.assertEqual(r.status_code, 200, r.data)
        ev = AnalyticsEvent.objects.get(pk=r.data['id'])
        self.assertEqual((ev.event_name, ev.path, ev.country), ('page_view', '/blog/x', 'IN'))
        r = self.client.post(self.URL, {'event_name': 'page_view'}, format='json', HTTP_CF_IPCOUNTRY='XX')
        self.assertIsNone(AnalyticsEvent.objects.get(pk=r.data['id']).country)

    def test_non_string_fields_do_not_500(self):
        r = self.client.post(self.URL, {'event_name': 'site_search', 'visitor_id': {'a': 1}, 'path': 7,
                                        'properties': ['not', 'a', 'dict']}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        ev = AnalyticsEvent.objects.get(pk=r.data['id'])
        self.assertEqual((ev.visitor_id, ev.path, ev.properties), (None, None, {}))
        self.assertEqual(self.client.post(self.URL, [1, 2], format='json').status_code, 400)


class AdminAnnouncementAliasTests(TestCase):
    def test_all_flag_lists_scheduled_and_expired_rows(self):
        admin = APIClient()
        admin.force_authenticate(User.objects.create_user(username='ann-alias-admin', password='x', role='admin'))
        live = Announcement.objects.create(title='Live', message='m', delivery_status='sent')
        scheduled = Announcement.objects.create(title='Later', message='m', delivery_status='scheduled',
                                                scheduled_for=timezone.now() + timedelta(days=2))
        expired = Announcement.objects.create(title='Old', message='m', delivery_status='sent',
                                              expires_at=timezone.now() - timedelta(days=1))
        ids = {a['id'] for a in admin.get('/api/analytics/announcements/').data}
        self.assertEqual(ids, {live.id})
        ids = {a['id'] for a in admin.get('/api/analytics/announcements/', {'all': '1'}).data}
        self.assertEqual(ids, {live.id, scheduled.id, expired.id})

        student = APIClient()
        student.force_authenticate(User.objects.create_user(username='ann-alias-student', password='x'))
        ids = {a['id'] for a in student.get('/api/analytics/announcements/', {'all': '1'}).data}
        self.assertEqual(ids, {live.id})  # the flag means nothing for students


class ScholarshipNotebookTests(TestCase):
    def test_scholarship_answers_hidden_from_free_users_who_answered(self):
        subject = Subject.objects.create(name='Sch Subject', code='SCH')
        plain = Question.objects.create(question_text='Plain', option_a='A', option_b='B', option_c='C',
                                        option_d='D', correct_answer='B', explanation='plain why', subject=subject,
                                        year=2024)
        scholarship = Question.objects.create(question_text='Scholarship', option_a='A', option_b='B', option_c='C',
                                              option_d='D', correct_answer='D', explanation='secret why',
                                              subject=subject, year=2024, is_scholarship_eligible=True)
        user = User.objects.create_user(username='sch-free', password='x')
        for q in (plain, scholarship):
            QuestionAttempt.objects.create(user=user, question=q, selected_answer='A', is_correct=False)
            MistakeNotebook.objects.create(user=user, question=q, selected_answer='A', correct_answer='',
                                           is_correct=False)
        client = APIClient()
        client.force_authenticate(user)
        rows = {r['question']: r for r in client.get('/api/analytics/mistake-notebook/').data['results']}
        self.assertEqual((rows[plain.id]['correct_answer'], rows[plain.id]['explanation']), ('B', 'plain why'))
        self.assertEqual((rows[scholarship.id]['correct_answer'], rows[scholarship.id]['explanation']), ('', ''))

        admin = User.objects.create_user(username='sch-admin', password='x', role='admin')
        QuestionAttempt.objects.create(user=admin, question=scholarship, selected_answer='A', is_correct=False)
        MistakeNotebook.objects.create(user=admin, question=scholarship, selected_answer='A', correct_answer='',
                                       is_correct=False)
        admin_client = APIClient()
        admin_client.force_authenticate(admin)
        row = admin_client.get('/api/analytics/mistake-notebook/').data['results'][0]
        self.assertEqual(row['correct_answer'], 'D')


class BackgroundNotificationTests(TestCase):
    """_run_in_background goes through accounts.emails.run_in_background."""

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_inline_run_keeps_the_request_connection(self):
        calls = []
        with mock.patch('analytics.views.connection') as conn, self.captureOnCommitCallbacks(execute=True):
            _run_in_background(calls.append, 'x')
            self.assertEqual(calls, [])  # waits for the commit
        self.assertEqual(calls, ['x'])
        conn.close.assert_not_called()

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend')
    def test_worker_thread_closes_its_connection(self):
        started = []
        real_thread = threading.Thread

        class RecordingThread(real_thread):
            def start(self):
                started.append(self)
                super().start()

        calls = []
        with mock.patch('accounts.emails.threading.Thread', RecordingThread), \
                mock.patch('analytics.views.connection') as conn:
            with self.captureOnCommitCallbacks(execute=True):
                _run_in_background(calls.append, 'y')
            for thread in started:
                thread.join(5)
        self.assertEqual(len(started), 1)
        self.assertEqual(calls, ['y'])
        conn.close.assert_called_once_with()
