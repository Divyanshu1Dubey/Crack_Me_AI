"""Wave-3 analytics fixes.

* Mistake Notebook: a free user's notebook shows a question's answer key and
  explanation only where questions.views.user_can_view_answer would (free
  showcase questions, never scholarship-challenge ones). Having answered the
  question -- in a completed test (every wrong answer lands in the notebook)
  or in the bank while subscribed -- no longer unlocks it. Premium, admin
  and staff users keep everything.
* Leaderboard: late test submits are kept off the board (accuracy,
  tests_completed and the rebuilt pre-ledger XP).
* Event ingest: the country comes only from the one trusted edge header;
  a client-sent X-Vercel-IP-Country no longer outranks CF-IPCountry.
* prune_analytics_events: dry-run-by-default retention for AnalyticsEvent.
* Campaign "Publish now": a future scheduled time moves to now (the feeds
  hid the published row until then); an expired campaign is refused.
"""
from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Subscription
from accounts.models_freemium import FreeShowcaseQuestion
from analytics.models import AnalyticsEvent, Announcement, DailyActivity, StudyStreak
from analytics.views import QUEST_FREEZE_EVENT, XP_LEDGER_START_EVENT, _leaderboard_period_start, period_xp_by_user
from questions.mistakes import record_mistake
from questions.models import MistakeNotebook, Question, QuestionAttempt, Subject
from tests_engine.models import QuestionResponse, Test, TestAttempt

User = get_user_model()
NOTEBOOK = '/api/analytics/mistake-notebook/'
SECRET = 'wave3 secret explanation'


def _question(subject, i, **kw):
    data = dict(question_text=f'Wave3 notebook Q{i}', option_a='A1', option_b='B1', option_c='C1', option_d='D1',
                correct_answer='A', explanation=f'{SECRET} {i}', year=2024, subject=subject)
    data.update(kw)
    return Question.objects.create(**data)


class MistakeNotebookEntitlementTests(TestCase):
    def setUp(self):
        subject = Subject.objects.create(name='Wave3 Notebook', code='W3NB')
        self.plain = _question(subject, 1)                 # premium bank question
        self.showcase = _question(subject, 2)              # free showcase question
        self.scholarship = _question(subject, 3, is_scholarship_eligible=True)
        FreeShowcaseQuestion.objects.create(question=self.showcase, year=2024, position=0)
        # An admin also showcased a scholarship question: it must stay locked.
        FreeShowcaseQuestion.objects.create(question=self.scholarship, year=2024, position=1)
        self.test = Test.objects.create(title='Wave3 notebook test', test_type='mixed', negative_marking=False)
        self.test.questions.set([self.plain, self.showcase, self.scholarship])
        self.client = APIClient()

    def _login(self, username, **extra):
        user = User.objects.create_user(username=username, password='x', **extra)
        self.client.force_authenticate(user)
        return user

    def _take_test_wrong(self, user):
        """A completed test with every answer wrong, recorded the way the
        submit view records it (QuestionResponse rows + record_mistake). Built
        directly so it does not depend on which tests a free plan may start
        (attempts from before that gate, or from a lapsed plan, look the same)."""
        attempt = TestAttempt.objects.create(user=user, test=self.test, is_completed=True,
                                             completed_at=timezone.now(), incorrect_count=3)
        for question, picked in ((self.plain, 'B'), (self.showcase, 'C'), (self.scholarship, 'D')):
            QuestionResponse.objects.create(attempt=attempt, question=question, selected_answer=picked,
                                            is_correct=False)
            record_mistake(user, question, picked)
        self.assertEqual(MistakeNotebook.objects.filter(user=user).count(), 3)

    def _rows(self, url=NOTEBOOK):
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200, getattr(r, 'data', None))
        return {row['question']: row for row in r.data['results']}

    def _assert_locked(self, row):
        self.assertEqual((row['correct_answer'], row['explanation'], row['answer_locked']), ('', '', True))
        self.assertNotIn(SECRET, str(row))

    def _assert_visible(self, row, question):
        self.assertEqual((row['correct_answer'], row['explanation'], row['answer_locked']),
                         ('A', question.explanation, False))

    def test_free_user_test_mistakes_stay_locked_except_showcase(self):
        user = self._login('w3-nb-free')
        self._take_test_wrong(user)
        due_url = f'{NOTEBOOK}due/'
        for rows in (self._rows(), self._rows(due_url)):
            self._assert_locked(rows[self.plain.id])
            self._assert_visible(rows[self.showcase.id], self.showcase)
            self._assert_locked(rows[self.scholarship.id])
            # The student's own wrong pick is not secret.
            self.assertEqual(rows[self.plain.id]['selected_answer'], 'B')

        # Re-adding / annotating through POST does not reveal the key either.
        for question in (self.plain, self.scholarship):
            r = self.client.post(NOTEBOOK, {'question': question.id, 'user_note': 'why?'}, format='json')
            self.assertEqual(r.status_code, 200, r.data)
            self._assert_locked(r.data)
        r = self.client.post(NOTEBOOK, {'question': self.showcase.id, 'is_flagged': True}, format='json')
        self._assert_visible(r.data, self.showcase)

        # Neither do PATCH and the review action.
        entry = MistakeNotebook.objects.get(user=user, question=self.plain)
        r = self.client.patch(f'{NOTEBOOK}{entry.id}/', {'user_note': 'again'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self._assert_locked(r.data)
        r = self.client.post(f'{NOTEBOOK}{entry.id}/review/')
        self.assertEqual(r.status_code, 200, r.data)
        self._assert_locked(r.data)

    def test_lapsed_subscription_bank_answer_stays_locked(self):
        user = self._login('w3-nb-lapsed')
        Subscription.objects.create(user=user, plan='1_year', status='expired',
                                    expires_at=timezone.now() - timedelta(days=1))
        QuestionAttempt.objects.create(user=user, question=self.plain, selected_answer='B', is_correct=False)
        record_mistake(user, self.plain, 'B')
        self._assert_locked(self._rows()[self.plain.id])

    def test_premium_admin_and_staff_see_every_answer(self):
        premium = self._login('w3-nb-premium')
        Subscription.objects.create(user=premium, plan='1_year', status='active',
                                    expires_at=timezone.now() + timedelta(days=30))
        cases = [(premium, 'premium')]
        for username, extra in (('w3-nb-admin', {'role': 'admin'}), ('w3-nb-staff', {'is_staff': True})):
            cases.append((User.objects.create_user(username=username, password='x', **extra), username))
        for user, label in cases:
            self.client.force_authenticate(user)
            self._take_test_wrong(user)
            rows = self._rows()
            for question in (self.plain, self.showcase, self.scholarship):
                with self.subTest(user=label, question=question.id):
                    self._assert_visible(rows[question.id], question)


class LeaderboardLateAttemptTests(TestCase):
    def setUp(self):
        cache.clear()
        self.test = Test.objects.create(title='Wave3 late test', test_type='mixed')

    def _attempt(self, user, correct, incorrect, late=False):
        now = timezone.now()
        return TestAttempt.objects.create(user=user, test=self.test, is_completed=True, completed_at=now,
                                          correct_count=correct, incorrect_count=incorrect, is_late=late)

    def test_late_attempts_are_off_the_board(self):
        me = User.objects.create_user(username='w3-late-me', password='x')
        StudyStreak.objects.create(user=me, xp_points=50)
        self._attempt(me, 3, 1)
        self._attempt(me, 0, 4, late=True)
        client = APIClient()
        client.force_authenticate(me)
        data = client.get('/api/analytics/leaderboard/', {'period': 'all'}).data['me']
        self.assertEqual((data['tests_completed'], data['accuracy']), (1, 75.0))

    def test_rebuilt_period_xp_ignores_late_attempts(self):
        rival = User.objects.create_user(username='w3-late-rival', password='x')
        StudyStreak.objects.create(user=rival, xp_points=1000)
        start = _leaderboard_period_start('weekly')
        # A late test with two right answers; its answers are also in the
        # day's activity, but they are not question-bank answers.
        self._attempt(rival, 2, 0, late=True)
        DailyActivity.objects.create(user=rival, date=timezone.localdate(), questions_attempted=2, correct_answers=2)
        self.assertEqual(period_xp_by_user(start), {})
        # An on-time test with two right answers: 2 x 10 + 5 completion bonus.
        self._attempt(rival, 2, 0)
        DailyActivity.objects.filter(user=rival).update(questions_attempted=4, correct_answers=4)
        self.assertEqual(period_xp_by_user(start), {rival.id: 25})


class IngestCountryTrustTests(TestCase):
    URL = '/api/analytics/events/'

    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def _country(self, **headers):
        r = self.client.post(self.URL, {'event_name': 'page_view', 'country': 'ZZ'}, format='json', **headers)
        self.assertEqual(r.status_code, 200, r.data)
        return AnalyticsEvent.objects.get(pk=r.data['id']).country

    @override_settings(ANALYTICS_COUNTRY_HEADER='', TRUSTED_CLIENT_IP_HEADER='')
    def test_client_sent_vercel_header_is_ignored_by_default(self):
        self.assertIsNone(self._country(HTTP_X_VERCEL_IP_COUNTRY='US'))
        self.assertEqual(self._country(HTTP_X_VERCEL_IP_COUNTRY='US', HTTP_CF_IPCOUNTRY='in'), 'IN')

    @override_settings(ANALYTICS_COUNTRY_HEADER='', TRUSTED_CLIENT_IP_HEADER='X-Vercel-Forwarded-For')
    def test_vercel_header_counts_when_vercel_is_the_trusted_edge(self):
        self.assertEqual(self._country(HTTP_X_VERCEL_IP_COUNTRY='in', HTTP_CF_IPCOUNTRY='US'), 'IN')

    @override_settings(ANALYTICS_COUNTRY_HEADER='', TRUSTED_CLIENT_IP_HEADER='CF-Connecting-IP')
    def test_cloudflare_edge_reads_cf_ipcountry(self):
        self.assertEqual(self._country(HTTP_X_VERCEL_IP_COUNTRY='US', HTTP_CF_IPCOUNTRY='gb'), 'GB')

    def test_explicit_setting_wins_and_none_disables(self):
        with override_settings(ANALYTICS_COUNTRY_HEADER='CloudFront-Viewer-Country',
                               TRUSTED_CLIENT_IP_HEADER='CF-Connecting-IP'):
            self.assertEqual(self._country(HTTP_CLOUDFRONT_VIEWER_COUNTRY='de', HTTP_CF_IPCOUNTRY='US'), 'DE')
        with override_settings(ANALYTICS_COUNTRY_HEADER='none'):
            self.assertIsNone(self._country(HTTP_CF_IPCOUNTRY='IN', HTTP_X_VERCEL_IP_COUNTRY='IN'))


class PruneAnalyticsEventsTests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.old = AnalyticsEvent.objects.create(event_name='page_view', created_at=now - timedelta(days=500))
        self.recent = AnalyticsEvent.objects.create(event_name='page_view', created_at=now - timedelta(days=10))
        self.marker = AnalyticsEvent.objects.create(event_name=XP_LEDGER_START_EVENT,
                                                    created_at=now - timedelta(days=900))
        self.freeze = AnalyticsEvent.objects.create(event_name=QUEST_FREEZE_EVENT, user_id=1,
                                                    created_at=now - timedelta(days=600))

    def _run(self, *args):
        out = StringIO()
        call_command('prune_analytics_events', *args, stdout=out)
        return out.getvalue()

    def test_dry_run_deletes_nothing(self):
        output = self._run()
        self.assertIn('Dry run: 1 analytics event(s)', output)
        self.assertEqual(AnalyticsEvent.objects.count(), 4)

    def test_apply_keeps_recent_rows_and_server_ledger_rows(self):
        AnalyticsEvent.objects.bulk_create([
            AnalyticsEvent(event_name='page_view', created_at=timezone.now() - timedelta(days=450 + i))
            for i in range(5)
        ])
        output = self._run('--apply', '--batch-size', '2')
        self.assertIn('Deleted 6 analytics event(s)', output)
        self.assertEqual(set(AnalyticsEvent.objects.values_list('pk', flat=True)),
                         {self.recent.pk, self.marker.pk, self.freeze.pk})

    def test_days_below_the_dashboard_window_are_refused(self):
        with self.assertRaises(CommandError):
            self._run('--days', '7', '--apply')
        self.assertEqual(AnalyticsEvent.objects.count(), 4)


class CampaignSendNowTests(TestCase):
    FEED = '/api/analytics/announcements/'

    def setUp(self):
        cache.clear()
        self.admin = APIClient()
        self.admin.force_authenticate(User.objects.create_user(username='w3-camp-admin', password='x', role='admin'))
        self.student = APIClient()
        self.student.force_authenticate(User.objects.create_user(username='w3-camp-student', password='x'))

    def _send_now(self, campaign_id, client=None):
        return (client or self.admin).post(f'/api/analytics/admin/campaigns/{campaign_id}/send-now/')

    def _feed_titles(self):
        r = self.student.get(self.FEED)
        self.assertEqual(r.status_code, 200)
        return [row['title'] for row in r.data]

    def test_publish_now_pulls_a_future_schedule_forward(self):
        later = timezone.now() + timedelta(days=2)
        r = self.admin.post('/api/analytics/admin/campaigns/', {
            'title': 'Grand mock', 'message': 'Live on Sunday', 'scheduled_for': later.isoformat(),
            'audience_filter': {'role': 'student'},
        }, format='json')
        self.assertEqual((r.status_code, r.data['delivery_status']), (201, 'scheduled'), r.data)
        self.assertEqual(self._feed_titles(), [])

        before = timezone.now()
        r = self._send_now(r.data['id'])
        self.assertEqual(r.status_code, 200, r.data)
        campaign = Announcement.objects.get(pk=r.data['id'])
        self.assertEqual((campaign.delivery_status, campaign.is_active, campaign.delivery_count), ('sent', True, 1))
        # It used to keep the Sunday time, and the feeds hid it until then.
        self.assertTrue(before <= campaign.scheduled_for <= timezone.now())
        self.assertEqual(campaign.scheduled_for, campaign.sent_at)
        self.assertEqual(self._feed_titles(), ['Grand mock'])
        bundle = self.student.get('/api/analytics/dashboard/bundle/').data
        self.assertEqual([a['title'] for a in bundle['announcements']], ['Grand mock'])

    def test_past_or_missing_schedule_is_left_alone(self):
        past = timezone.now() - timedelta(days=1)
        old = Announcement.objects.create(title='Was due', message='m', delivery_status='draft', scheduled_for=past)
        plain = Announcement.objects.create(title='Unscheduled', message='m', delivery_status='draft')
        for campaign in (old, plain):
            self.assertEqual(self._send_now(campaign.id).status_code, 200)
        old.refresh_from_db()
        plain.refresh_from_db()
        self.assertEqual((old.scheduled_for, plain.scheduled_for), (past, None))
        self.assertEqual(sorted(self._feed_titles()), ['Unscheduled', 'Was due'])

    def test_expired_campaign_is_refused_and_left_unchanged(self):
        expired_at = timezone.now() - timedelta(hours=1)
        draft = Announcement.objects.create(title='Old draft', message='m', delivery_status='draft',
                                            expires_at=expired_at)
        pulled = Announcement.objects.create(title='Old sent', message='m', delivery_status='sent', is_active=False,
                                             delivery_count=3, expires_at=expired_at)
        for campaign in (draft, pulled):
            r = self._send_now(campaign.id)
            self.assertEqual((r.status_code, r.data.get('code')), (400, 'expired'), r.data)
        draft.refresh_from_db()
        pulled.refresh_from_db()
        self.assertEqual((draft.delivery_status, draft.sent_at, draft.delivery_count), ('draft', None, 0))
        self.assertEqual((pulled.is_active, pulled.delivery_count), (False, 3))
        self.assertEqual(self._feed_titles(), [])

        # After a later expiry is set, publishing works again.
        Announcement.objects.filter(pk=draft.pk).update(expires_at=timezone.now() + timedelta(days=7))
        self.assertEqual(self._send_now(draft.id).status_code, 200)
        self.assertEqual(self._feed_titles(), ['Old draft'])

    def test_students_cannot_publish(self):
        campaign = Announcement.objects.create(title='Draft', message='m', delivery_status='draft')
        self.assertEqual(self._send_now(campaign.id, client=self.student).status_code, 403)
        self.assertEqual(self._send_now(999999).status_code, 404)
        campaign.refresh_from_db()
        self.assertEqual(campaign.delivery_status, 'draft')
