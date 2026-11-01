"""Wave 2 regression tests (W3 auth / accounts).

ACC-05   Supabase identities are linked by their user id (CustomUser.supabase_uid);
         admin / staff rows are never linked by email to an untrusted identity,
         and a row linked to one identity is never re-linked by email
ACC-07   an over-limit device can still reach /auth/subscribe/ (buy the 4-device plan)
ACC-12   a replayed verify heals a stranded order only after the signature check,
         never for legacy orders; an expired plan is a normal 409
ACC-10   starting the scholarship again in the same attempt returns the same set;
         starts are rate limited
ACC-20   renewal reminders are scheduled after migrate and skip stacked plans
UB-01    profile ai_tutor_daily_cap is the enforced TokenConfig cap
local    a blocked local-dev user gets code account_blocked

No network: the Supabase call is replaced by a fake token -> payload map and
payments use the local mock provider.
"""
import io
import logging
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import exceptions
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import PaymentAttempt, Subscription, TokenConfig, UserDevice
from accounts.payments_mock import sign_payment
from accounts.tests_wave1_auth import CONFIRMED, DEVICE_A, DEVICE_B, DEVICE_C, _SupabaseAuthTestCase

User = get_user_model()

UID_A = '11111111-1111-4111-8111-111111111111'
UID_B = '22222222-2222-4222-8222-222222222222'


def _identity(email, uid, *, app_metadata=None, user_metadata=None):
    return {
        'id': uid,
        'email': email,
        'email_confirmed_at': CONFIRMED,
        'user_metadata': user_metadata or {},
        'app_metadata': app_metadata or {},
    }


class SupabaseIdentityLinkingTests(_SupabaseAuthTestCase):
    def test_new_identity_creates_a_row_linked_by_uid(self):
        r = self.bearer('tok-new', _identity('fresh@example.com', UID_A)).get('/api/auth/profile/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(User.objects.get(email='fresh@example.com').supabase_uid, UID_A)

    def test_student_row_is_linked_on_first_sign_in_and_then_found_by_uid(self):
        row = User.objects.create_user(username='legacy', email='legacy@example.com', password='x-Long-passw0rd')
        r = self.bearer('tok-1', _identity('legacy@example.com', UID_A)).get('/api/auth/profile/')
        self.assertEqual((r.status_code, r.data['id']), (200, row.id))
        row.refresh_from_db()
        self.assertEqual(row.supabase_uid, UID_A)

        # The identity changes its (confirmed) email in Supabase: same row,
        # and the local email follows.
        r = self.bearer('tok-2', _identity('renamed@example.com', UID_A)).get('/api/auth/profile/')
        self.assertEqual((r.status_code, r.data['id']), (200, row.id))
        row.refresh_from_db()
        self.assertEqual(row.email, 'renamed@example.com')
        self.assertEqual(User.objects.count(), 1)

    def test_unlinked_admin_row_is_not_taken_over_by_a_confirmed_sign_up(self):
        # "Confirm email" off: GoTrue marks a fresh sign-up as confirmed.
        admin = User.objects.create_user(
            username='boss', email='boss@example.com', password='x-Long-passw0rd',
            role='admin', is_superuser=True, is_staff=True,
        )
        r = self.bearer('tok-evil', _identity('boss@example.com', UID_B)).get('/api/auth/profile/')
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.data['code'], 'account_link_required')
        admin.refresh_from_db()
        self.assertIsNone(admin.supabase_uid)
        self.assertEqual(User.objects.count(), 1)  # no second account was created either

    def test_db_promoted_admin_without_link_is_refused_too(self):
        User.objects.create_user(username='staffer', email='staffer@example.com', password='x', role='admin', is_staff=True)
        r = self.bearer('tok-s', _identity('staffer@example.com', UID_A)).get('/api/auth/admin/users/')
        self.assertEqual((r.status_code, r.data['code']), (401, 'account_link_required'))

    @mock.patch.dict('os.environ', {'CONTROL_TOWER_ADMIN_EMAILS': 'owner@example.com'})
    def test_allowlisted_admin_identity_links_its_admin_row(self):
        row = User.objects.create_user(
            username='owner', email='owner@example.com', password='x', role='admin', is_superuser=True, is_staff=True,
        )
        r = self.bearer('tok-owner', _identity('owner@example.com', UID_A)).get('/api/auth/admin/users/')
        self.assertEqual(r.status_code, 200)
        row.refresh_from_db()
        self.assertEqual(row.supabase_uid, UID_A)

    def test_app_metadata_admin_identity_links_its_admin_row(self):
        row = User.objects.create_user(username='meta', email='meta@example.com', password='x', role='admin', is_staff=True)
        r = self.bearer('tok-meta', _identity('meta@example.com', UID_A, app_metadata={'role': 'admin'})).get('/api/auth/profile/')
        self.assertEqual(r.status_code, 200)
        row.refresh_from_db()
        self.assertEqual((row.supabase_uid, row.is_superuser), (UID_A, True))

    def test_linked_admin_keeps_access_without_trusted_metadata(self):
        row = User.objects.create_user(
            username='promo', email='promo@example.com', password='x', role='admin', is_staff=True, supabase_uid=UID_A,
        )
        r = self.bearer('tok-p', _identity('promo@example.com', UID_A)).get('/api/auth/admin/users/')
        self.assertEqual(r.status_code, 200)
        row.refresh_from_db()
        self.assertEqual((row.role, row.is_superuser), ('admin', False))

    def test_row_linked_to_another_identity_is_not_relinked_by_email(self):
        row = User.objects.create_user(username='taken', email='taken@example.com', password='x', supabase_uid=UID_A)
        r = self.bearer('tok-b', _identity('taken@example.com', UID_B)).get('/api/auth/profile/')
        self.assertEqual((r.status_code, r.data['code']), (401, 'account_link_required'))
        row.refresh_from_db()
        self.assertEqual(row.supabase_uid, UID_A)

    def test_blocked_unlinked_row_is_reported_blocked_and_not_linked(self):
        row = User.objects.create_user(username='blk', email='blk@example.com', password='x', is_active=False)
        r = self.bearer('tok-blk', _identity('blk@example.com', UID_A)).get('/api/auth/profile/')
        self.assertEqual((r.status_code, r.data['code']), (401, 'account_blocked'))
        row.refresh_from_db()
        self.assertIsNone(row.supabase_uid)


class LinkSupabaseIdentityCommandTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='ops', email='ops@example.com', password='x', role='admin', is_superuser=True, is_staff=True,
        )

    def run_cmd(self, *args):
        out = io.StringIO()
        call_command('link_supabase_identity', *args, stdout=out)
        return out.getvalue()

    def test_links_with_an_explicit_uid(self):
        self.run_cmd('--email', 'OPS@example.com', '--uid', UID_A, '--apply')
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.supabase_uid, UID_A)

    def test_dry_run_by_default(self):
        out = self.run_cmd('--email', 'ops@example.com', '--uid', UID_A)
        self.assertIn('Would link', out)
        self.assertIn('Dry run', out)
        self.admin.refresh_from_db()
        self.assertIsNone(self.admin.supabase_uid)

    def test_refuses_a_uid_linked_to_another_account(self):
        User.objects.create_user(username='other', email='other@example.com', password='x', supabase_uid=UID_A)
        with self.assertRaises(CommandError):
            self.run_cmd('--email', 'ops@example.com', '--uid', UID_A, '--apply')

    def test_replacing_an_existing_link_needs_replace(self):
        User.objects.filter(pk=self.admin.pk).update(supabase_uid=UID_A)
        with self.assertRaises(CommandError):
            self.run_cmd('--email', 'ops@example.com', '--uid', UID_B, '--apply')
        self.run_cmd('--email', 'ops@example.com', '--uid', UID_B, '--replace', '--apply')
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.supabase_uid, UID_B)

    def test_rejects_a_malformed_uid(self):
        with self.assertRaises(CommandError):
            self.run_cmd('--email', 'ops@example.com', '--uid', 'not-a-uuid')

    @mock.patch('accounts.supabase_auth._is_configured', return_value=True)
    def test_looks_the_uid_up_and_requires_a_confirmed_email(self, _configured):
        users = [{'id': UID_A, 'email': 'ops@example.com', 'email_confirmed_at': None}]
        with mock.patch('accounts.supabase_auth.list_supabase_auth_users', return_value=users):
            with self.assertRaises(CommandError):
                self.run_cmd('--email', 'ops@example.com', '--apply')
            users[0]['email_confirmed_at'] = CONFIRMED
            self.run_cmd('--email', 'ops@example.com', '--apply')
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.supabase_uid, UID_A)


class DeviceLimitSubscribeTests(_SupabaseAuthTestCase):
    @override_settings(PAYMENTS_MOCK=True)
    @mock.patch.dict('os.environ', {'RAZORPAY_KEY_ID': 'rzp_test_localmock', 'RAZORPAY_KEY_SECRET': 'test-key-secret'})
    def test_over_limit_device_can_buy_the_four_device_plan(self):
        User.objects.create_user(username='dev', email='dev@example.com', password='x')
        payload = _identity('dev@example.com', UID_A)
        for device in (DEVICE_A, DEVICE_B):
            self.assertEqual(self.bearer('tok-dev', payload, device=device).get('/api/auth/tokens/').status_code, 200)
        third = self.bearer('tok-dev', payload, device=DEVICE_C)
        # (GET /api/auth/tokens/ is exempt since wave 3: the Header reads it on /subscription.)
        self.assertEqual(third.get('/api/auth/tokens/history/').data['code'], 'device_limit_reached')
        r = third.post('/api/auth/subscribe/order/', {'plan': '3_months'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        # It did not take a slot.
        self.assertFalse(UserDevice.objects.filter(device_fingerprint=DEVICE_C).exists())


@override_settings(PAYMENTS_MOCK=True, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
@mock.patch.dict('os.environ', {'RAZORPAY_KEY_ID': 'rzp_test_localmock', 'RAZORPAY_KEY_SECRET': 'test-key-secret'})
class StrandedPaymentHealingTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='buyer', email='buyer@local.test', password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def stranded(self, plan='3_months'):
        attempt = PaymentAttempt.objects.create(
            user=self.user, razorpay_order_id=f'order_{plan}_x', amount=449, plan=plan,
            status='successful', razorpay_payment_id='pay_1',
        )
        return attempt.razorpay_order_id

    def verify(self, order_id, signature=None):
        return self.client.post('/api/auth/subscribe/verify/', {
            'razorpay_order_id': order_id,
            'razorpay_payment_id': 'pay_1',
            'razorpay_signature': signature or sign_payment(order_id, 'pay_1', 'test-key-secret'),
        }, format='json')

    def test_replay_without_a_valid_signature_does_not_activate(self):
        order_id = self.stranded()
        r = self.verify(order_id, signature='forged')
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Subscription.objects.filter(user=self.user).exists())
        self.assertEqual(PaymentAttempt.objects.get(razorpay_order_id=order_id).status, 'successful')

    def test_signed_replay_heals_the_stranded_order(self):
        r = self.verify(self.stranded())
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data['is_subscribed'])

    def test_legacy_orders_are_never_healed(self):
        r = self.verify(self.stranded(plan='legacy'))
        self.assertEqual(r.status_code, 409)
        self.assertFalse(Subscription.objects.filter(user=self.user).exists())

    def test_expired_plan_is_a_plain_409_without_an_error_log(self):
        order_id = self.stranded()
        Subscription.objects.create(
            user=self.user, plan='3_months', razorpay_order_id=order_id, status='active',
            starts_at=timezone.now() - timedelta(days=100), expires_at=timezone.now() - timedelta(days=10),
        )
        with self.assertNoLogs('accounts.views', level=logging.ERROR):
            r = self.verify(order_id)
        self.assertEqual(r.status_code, 409)
        self.assertIn('no longer active', r.data['error'])


class ScholarshipStartLimitTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from questions.models import Question, Subject

        subject = Subject.objects.create(name='Medicine', code='med-w2')
        for i in range(12):
            Question.objects.create(
                question_text=f'Eligible {i}?', option_a='A', option_b='B', option_c='C', option_d='D',
                correct_answer='A', year=2024, subject=subject, is_scholarship_eligible=True,
            )

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='sch', email='sch@local.test', password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def ids(self):
        r = self.client.post('/api/auth/scholarship/start/')
        self.assertEqual(r.status_code, 200, r.data)
        return {q['id'] for q in r.data['questions']}

    def test_restarting_the_same_attempt_returns_the_same_questions(self):
        first = self.ids()
        self.assertEqual(len(first), 5)
        for _ in range(3):
            self.assertEqual(self.ids(), first)
        # A new attempt (after a submission) gets a fresh draw.
        User.objects.filter(pk=self.user.pk).update(scholarship_test_attempts=1)
        self.assertEqual(len(self.ids()), 5)

    def test_starts_are_rate_limited(self):
        for _ in range(10):
            self.ids()
        self.assertEqual(self.client.post('/api/auth/scholarship/start/').status_code, 429)


class RenewalReminderScheduleTests(TestCase):
    def test_post_migrate_schedules_reminders_once_per_migrate(self):
        from django.apps import apps

        from accounts import signals

        with mock.patch.object(signals, '_running_tests', return_value=False), \
                mock.patch('accounts.management.commands.send_subscription_reminders.schedule_subscription_reminders') as schedule:
            signals.renewal_reminders_post_migrate(sender=apps.get_app_config('questions'))
            schedule.assert_not_called()
            signals.renewal_reminders_post_migrate(sender=apps.get_app_config('accounts'))
            schedule.assert_called_once_with()

    def test_skipped_during_test_runs(self):
        from django.apps import apps

        from accounts import signals

        with mock.patch('accounts.management.commands.send_subscription_reminders.schedule_subscription_reminders') as schedule:
            signals.renewal_reminders_post_migrate(sender=apps.get_app_config('accounts'))
        schedule.assert_not_called()

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_stacked_plan_suppresses_the_reminder(self):
        from django.core import mail

        now = timezone.now()
        stacked = User.objects.create_user(username='stack', email='stack@local.test', password='x')
        single = User.objects.create_user(username='single', email='single@local.test', password='x')
        for user in (stacked, single):
            Subscription.objects.create(user=user, plan='1_month', status='active', expires_at=now + timedelta(days=7, hours=1))
        Subscription.objects.create(user=stacked, plan='1_year', status='active', expires_at=now + timedelta(days=372))
        cache.clear()
        call_command('send_subscription_reminders', days='7', stdout=io.StringIO())
        self.assertEqual([m.to for m in mail.outbox], [['single@local.test']])


class ProfileTutorCapTests(TestCase):
    def test_profile_reports_the_configured_cap(self):
        cfg = TokenConfig.get_config()
        cfg.ai_tutor_daily_cap = 5
        cfg.save()
        user = User.objects.create_user(username='cap', email='cap@local.test', password='x')
        client = APIClient()
        client.force_authenticate(user)
        self.assertEqual(client.get('/api/auth/profile/').data['ai_tutor_daily_cap'], 5)


@override_settings(LOCAL_DEV_AUTH=True)
class LocalBlockedUserTests(TestCase):
    def test_blocked_local_user_gets_account_blocked(self):
        from accounts.local_auth_authentication import LocalDevJWTAuthentication

        user = User.objects.create_user(username='lblk', email='lblk@local.test', password='x')
        token = str(AccessToken.for_user(user))
        User.objects.filter(pk=user.pk).update(is_active=False)
        request = APIRequestFactory().get('/api/auth/profile/', HTTP_AUTHORIZATION=f'Bearer {token}')
        with self.assertRaises(exceptions.AuthenticationFailed) as ctx:
            LocalDevJWTAuthentication().authenticate(request)
        self.assertEqual(ctx.exception.detail['code'], 'account_blocked')

    def test_active_local_user_still_authenticates(self):
        from accounts.local_auth_authentication import LocalDevJWTAuthentication

        user = User.objects.create_user(username='lok', email='lok@local.test', password='x')
        token = str(AccessToken.for_user(user))
        request = APIRequestFactory().get('/api/auth/profile/', HTTP_AUTHORIZATION=f'Bearer {token}')
        authed, _ = LocalDevJWTAuthentication().authenticate(request)
        self.assertEqual(authed.pk, user.pk)
