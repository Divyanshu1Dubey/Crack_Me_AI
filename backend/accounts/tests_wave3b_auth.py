"""Wave 3b regression tests (Z4 auth / accounts): follow-ups other groups asked for.

Z5  admins, superusers and staff are never AI-metered or capped
    (ai_engine.views._is_unmetered_staff): the token wallet reports
    unlimited_ai for them (C12: Header pill 'Unlimited') and the profile
    reports no AI tutor cap / usage, so the usage banner never shows '0/2'
Z9  the scholarship challenge (start and verify) refuses callers with an
    active plan who are not staff -- a plan unlocks every answer, the
    scholarship questions included -- with 409 already_subscribed and
    without using up an attempt
"""
from datetime import timedelta
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Subscription

User = get_user_model()
START = '/api/auth/scholarship/start/'
VERIFY = '/api/auth/verify-scholarship/'


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def _user(username, **fields):
    return User.objects.create_user(username=username, email=f'{username}@local.test', password=None, **fields)


def _active_plan(user, plan='1_month', days=20):
    return Subscription.objects.create(
        user=user, plan=plan, status='active', expires_at=timezone.now() + timedelta(days=days),
    )


# ── Z5: unmetered staff ──────────────────────────────────────────────────

class UnmeteredStaffRuleParityTests(SimpleTestCase):
    def test_the_wallet_rule_is_the_ai_metering_rule(self):
        from accounts.serializers import _is_unmetered_staff as wallet_rule
        from ai_engine.views import _is_unmetered_staff as metering_rule

        for is_admin in (False, True):
            for is_superuser in (False, True):
                for is_staff in (False, True):
                    user = SimpleNamespace(is_admin=is_admin, is_superuser=is_superuser, is_staff=is_staff)
                    self.assertEqual(wallet_rule(user), metering_rule(user), vars(user))


class StaffAreNeverMeteredTests(TestCase):
    CASES = {
        'student': ({}, False),
        'adminrole': ({'role': 'admin'}, True),
        'superu': ({'is_superuser': True}, True),
        'staffonly': ({'is_staff': True}, True),
    }

    def setUp(self):
        cache.clear()

    def test_token_wallet_reports_unlimited_ai_for_admins_superusers_and_staff(self):
        for username, (fields, expected) in self.CASES.items():
            data = _client(_user(username, **fields)).get('/api/auth/tokens/').data
            self.assertIs(data['unlimited_ai'], expected, username)

    def test_a_metered_plan_does_not_meter_staff(self):
        staff = _user('staffplan', is_staff=True)
        _active_plan(staff, plan='1_month')
        self.assertIs(_client(staff).get('/api/auth/tokens/').data['unlimited_ai'], True)

    def test_profile_shows_no_ai_tutor_cap_or_usage_for_staff(self):
        from ai_engine.models_usage import AITutorDailyUsage
        from ai_engine.views import _ai_tutor_cap

        student = _user('capstudent')
        staff = _user('capstaff', is_staff=True)
        for user in (student, staff):
            AITutorDailyUsage.objects.create(user=user, date=timezone.localdate(), message_count=3)

        profile = _client(staff).get('/api/auth/profile/').data
        self.assertIsNone(profile['ai_tutor_daily_cap'])
        self.assertEqual(profile['ai_tutor_used_today'], 0)

        # A student still sees the real counter and the enforced cap.
        profile = _client(student).get('/api/auth/profile/').data
        self.assertEqual(profile['ai_tutor_daily_cap'], _ai_tutor_cap())
        self.assertEqual(profile['ai_tutor_used_today'], 3)


# ── Z9: scholarship challenge vs. active plans ───────────────────────────

class ScholarshipPlanHolderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from questions.models import Question, Subject

        subject = Subject.objects.create(name='Medicine W3b', code='med-w3b')
        cls.eligible = [
            Question.objects.create(
                question_text=f'Eligible W3b {i}?', option_a='A', option_b='B', option_c='C', option_d='D',
                correct_answer='A', year=2024, subject=subject, is_scholarship_eligible=True,
            ).pk
            for i in range(7)
        ]

    def setUp(self):
        cache.clear()

    def assert_refused(self, response):
        self.assertEqual(response.status_code, 409, response.data)
        self.assertEqual(response.data['code'], 'already_subscribed')
        # The subscription page shows `error` in the challenge modal.
        self.assertIn('without an active plan', response.data['error'])

    def assert_untouched(self, user):
        user.refresh_from_db()
        self.assertEqual(
            (user.scholarship_test_attempts, user.scholarship_test_passed,
             user.scholarship_granted_price, user.scholarship_challenge),
            (0, False, None, None),
        )

    def verify(self, client, user, ids=None):
        from accounts.views import _issue_scholarship_challenge

        ids = ids or self.eligible[:5]
        return client.post(VERIFY, {
            'answers': {str(qid): 'A' for qid in ids},
            'challenge_token': _issue_scholarship_challenge(user.pk, ids, 0),
        }, format='json')

    def test_an_active_plan_holder_can_neither_start_nor_verify(self):
        user = _user('w3bpaid')
        _active_plan(user)
        client = _client(user)
        self.assert_refused(client.post(START))
        # Even with a validly signed token and all-correct answers.
        self.assert_refused(self.verify(client, user))
        self.assert_untouched(user)

    def test_a_legacy_lifetime_member_is_refused_too(self):
        user = _user('w3blegacy', is_subscribed=True)  # grandfathered: no Subscription rows
        client = _client(user)
        self.assert_refused(client.post(START))
        self.assert_refused(self.verify(client, user))
        self.assert_untouched(user)

    def test_a_plan_bought_during_the_challenge_blocks_the_submission(self):
        user = _user('w3bmid')
        client = _client(user)
        r = client.post(START)
        self.assertEqual(r.status_code, 200, r.data)
        ids = [q['id'] for q in r.data['questions']]
        _active_plan(user)
        r = client.post(VERIFY, {
            'answers': {str(qid): 'A' for qid in ids}, 'challenge_token': r.data['challenge_token'],
        }, format='json')
        self.assert_refused(r)
        user.refresh_from_db()
        self.assertEqual((user.scholarship_test_attempts, user.scholarship_test_passed), (0, False))

    def test_an_expired_plan_does_not_block_the_challenge(self):
        user = _user('w3bexpired')
        Subscription.objects.create(
            user=user, plan='1_month', status='active', expires_at=timezone.now() - timedelta(days=1),
        )
        r = _client(user).post(START)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(len(r.data['questions']), 5)

    def test_staff_and_admins_with_a_plan_may_still_run_it(self):
        for username, fields in (('w3bstaff', {'is_staff': True}), ('w3badmin', {'role': 'admin'})):
            user = _user(username, **fields)
            _active_plan(user)
            client = _client(user)
            r = client.post(START)
            self.assertEqual(r.status_code, 200, (username, r.data))
            ids = [q['id'] for q in r.data['questions']]
            r = client.post(VERIFY, {
                'answers': {str(qid): 'A' for qid in ids}, 'challenge_token': r.data['challenge_token'],
            }, format='json')
            self.assertEqual((r.status_code, r.data.get('status')), (200, 'passed'), username)

    def test_free_students_are_unaffected(self):
        user = _user('w3bfree')
        client = _client(user)
        r = client.post(START)
        self.assertEqual(r.status_code, 200, r.data)
        ids = [q['id'] for q in r.data['questions']]
        r = client.post(VERIFY, {
            'answers': {str(qid): 'A' for qid in ids}, 'challenge_token': r.data['challenge_token'],
        }, format='json')
        self.assertEqual(r.data['status'], 'passed')
        user.refresh_from_db()
        self.assertEqual((user.scholarship_test_passed, user.scholarship_granted_price), (True, 79))
