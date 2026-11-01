"""Wave 1 regression tests: payments and subscriptions (G4-auth-accounts, CFG-21).

Exercises the real order / verify / webhook views against the local mock
provider (accounts.payments_mock: same HMAC scheme as Razorpay, no network).

ACC-12  claim + activation are one transaction; replays report the real state;
        orders stranded by the old non-atomic code are recovered
ACC-15  a stacked purchase extends from the LATEST live expiry
ACC-08  a lifetime row outlives a stacked dated plan; a bare is_subscribed flag
        (no row; set by the removed unpaid endpoint) is never turned into one
ACC-22  the cached subscription status is invalidated on every change
ACC-23  admin grants reject unknown plans
ACC-19  no "complete your checkout" mail at order time; plan-specific receipt
CFG-21  order amounts, webhook signatures, unknown orders, verify/webhook CAS
"""
import hashlib
import hmac
import json
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import PaymentAttempt, Subscription, TokenTransaction
from accounts.payments_mock import sign_payment

User = get_user_model()
ENV = {
    'RAZORPAY_KEY_ID': 'rzp_test_localmock',
    'RAZORPAY_KEY_SECRET': 'test-key-secret',
    'RAZORPAY_WEBHOOK_SECRET': 'test-webhook-secret',
}


@override_settings(PAYMENTS_MOCK=True, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class _PaymentsTestCase(TestCase):
    def setUp(self):
        cache.clear()
        env = mock.patch.dict('os.environ', ENV)
        env.start()
        self.addCleanup(env.stop)
        self.user = User.objects.create_user(username='buyer', email='buyer@local.test', password='x-Long-passw0rd')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def order(self, plan='1_month', client=None):
        r = (client or self.client).post('/api/auth/subscribe/order/', {'plan': plan}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        return r.data

    def signed(self, order_id, payment_id='pay_test_0001', secret=None):
        return {
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': sign_payment(order_id, payment_id, secret or ENV['RAZORPAY_KEY_SECRET']),
        }

    def verify(self, data, client=None):
        return (client or self.client).post('/api/auth/subscribe/verify/', data, format='json')

    def webhook(self, order_id, payment_id='pay_test_0001', event='payment.captured', secret=None, signature=None):
        body = json.dumps({'event': event, 'payload': {'payment': {'entity': {'id': payment_id, 'order_id': order_id}}}})
        sig = signature if signature is not None else hmac.new(
            (secret or ENV['RAZORPAY_WEBHOOK_SECRET']).encode(), body.encode(), hashlib.sha256,
        ).hexdigest()
        return APIClient().post('/api/auth/subscribe/webhook/', data=body, content_type='application/json',
                                HTTP_X_RAZORPAY_SIGNATURE=sig)


class OrderAmountTests(_PaymentsTestCase):
    def test_plan_amounts(self):
        for plan, paise in (('1_month', 12900), ('3_months', 44900), ('1_year', 199900)):
            data = self.order(plan)
            self.assertEqual(data['amount'], paise, plan)
            self.assertEqual(PaymentAttempt.objects.get(razorpay_order_id=data['order_id']).plan, plan)

    def test_scholarship_rate_requires_a_passed_test(self):
        r = self.client.post('/api/auth/subscribe/order/', {'plan': 'scholarship_1_month'}, format='json')
        self.assertEqual(r.status_code, 403)
        User.objects.filter(pk=self.user.pk).update(scholarship_test_passed=True, scholarship_granted_price=79)
        self.user.refresh_from_db()
        self.client.force_authenticate(self.user)
        self.assertEqual(self.order('scholarship_1_month')['amount'], 7900)

    def test_order_creation_sends_no_checkout_nag_email(self):
        self.order('1_month')
        self.assertEqual(len(mail.outbox), 0)


class VerifyAtomicityTests(_PaymentsTestCase):
    def test_activation_failure_rolls_back_the_claim(self):
        order_id = self.order('1_month')['order_id']
        with mock.patch.object(Subscription, 'activate_from_payment', side_effect=RuntimeError('db down')):
            r = self.verify(self.signed(order_id))
        self.assertEqual(r.status_code, 500)
        self.assertEqual(PaymentAttempt.objects.get(razorpay_order_id=order_id).status, 'initiated')
        self.assertFalse(Subscription.objects.filter(user=self.user).exists())

        # A retry (the frontend's "Retry Verification") now activates.
        r = self.verify(self.signed(order_id))
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data['is_subscribed'])
        self.assertEqual(Subscription.objects.filter(user=self.user).count(), 1)
        self.assertEqual(TokenTransaction.objects.filter(user=self.user, transaction_type='purchase').count(), 1)

    def test_replay_reports_the_real_state_after_revoke(self):
        order_id = self.order('1_month')['order_id']
        self.assertEqual(self.verify(self.signed(order_id)).status_code, 200)
        Subscription.objects.filter(user=self.user).update(status='cancelled')
        r = self.verify(self.signed(order_id))
        self.assertEqual(r.status_code, 409)
        self.assertFalse(r.data['is_subscribed'])
        self.assertEqual(Subscription.objects.filter(user=self.user).count(), 1)  # not re-activated

    def test_stranded_order_is_recovered_on_verify(self):
        # State left by the old code: claim committed, activation never ran.
        order_id = self.order('3_months')['order_id']
        PaymentAttempt.objects.filter(razorpay_order_id=order_id).update(status='successful', razorpay_payment_id='pay_test_0001')
        r = self.verify(self.signed(order_id))
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data['is_subscribed'])
        self.assertEqual(r.data['subscription']['plan'], '3_months')
        # And only once.
        self.assertEqual(self.verify(self.signed(order_id)).status_code, 200)
        self.assertEqual(Subscription.objects.filter(user=self.user, razorpay_order_id=order_id).count(), 1)

    def test_bad_signature_does_not_overwrite_a_concurrent_webhook_claim(self):
        order_id = self.order('1_month')['order_id']

        def webhook_wins_then_signature_fails(_self, params):
            PaymentAttempt.objects.filter(razorpay_order_id=order_id).update(status='successful')
            raise ValueError('bad signature')

        with mock.patch('accounts.payments_mock._MockUtility.verify_payment_signature', webhook_wins_then_signature_fails):
            r = self.verify(self.signed(order_id))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(PaymentAttempt.objects.get(razorpay_order_id=order_id).status, 'successful')

    def test_unknown_order_is_never_activated(self):
        r = self.verify(self.signed('order_not_created_here'))
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Subscription.objects.filter(user=self.user).exists())

    def test_claim_lost_to_a_concurrent_request_does_not_activate_twice(self):
        from accounts.views import _claim_and_activate

        order_id = self.order('1_month')['order_id']
        attempt = PaymentAttempt.objects.get(razorpay_order_id=order_id)
        self.assertIsNotNone(_claim_and_activate(attempt, 'pay_a', user=self.user, source='verify'))
        # A second claimant working from the same (stale) attempt object.
        self.assertIsNone(_claim_and_activate(attempt, 'pay_b', user=self.user, source='webhook'))
        self.assertEqual(Subscription.objects.filter(user=self.user).count(), 1)

    def test_receipt_copy_matches_the_plan(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.verify(self.signed(self.order('1_month')['order_id']))
        monthly = [m for m in mail.outbox if self.user.email in m.to]
        self.assertEqual(len(monthly), 1)
        self.assertNotIn('unlimited AI', monthly[0].body)
        self.assertIn('100 AI Tutor tokens', monthly[0].body)

        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            self.verify(self.signed(self.order('1_year')['order_id'], payment_id='pay_test_0002'))
        yearly = [m for m in mail.outbox if self.user.email in m.to]
        self.assertIn('unlimited AI Tutor', yearly[0].body)


class WebhookTests(_PaymentsTestCase):
    def test_signature_is_required_and_checked(self):
        order_id = self.order('1_month')['order_id']
        self.assertEqual(self.webhook(order_id, signature='').status_code, 400)
        self.assertEqual(self.webhook(order_id, secret='wrong-secret').status_code, 400)
        self.assertFalse(Subscription.objects.filter(user=self.user).exists())

    def test_unconfigured_secret_rejects_everything(self):
        order_id = self.order('1_month')['order_id']
        with mock.patch.dict('os.environ', {'RAZORPAY_WEBHOOK_SECRET': ''}):
            self.assertEqual(self.webhook(order_id).status_code, 503)

    def test_unknown_order_and_other_events_are_ignored(self):
        self.assertEqual(self.webhook('order_unknown').data['status'], 'order_not_found')
        order_id = self.order('1_month')['order_id']
        self.assertEqual(self.webhook(order_id, event='payment.failed').data['status'], 'ignored')
        self.assertFalse(Subscription.objects.filter(user=self.user).exists())

    def test_activation_failure_returns_500_so_razorpay_retries(self):
        order_id = self.order('1_year')['order_id']
        with mock.patch.object(Subscription, 'activate_from_payment', side_effect=RuntimeError('boom')):
            self.assertEqual(self.webhook(order_id).status_code, 500)
        self.assertEqual(PaymentAttempt.objects.get(razorpay_order_id=order_id).status, 'initiated')
        self.assertEqual(self.webhook(order_id).data['status'], 'activated')
        self.assertEqual(self.webhook(order_id).data['status'], 'already_processed')
        self.assertEqual(Subscription.objects.filter(user=self.user).count(), 1)

    def test_verify_after_webhook_does_not_stack(self):
        order_id = self.order('1_month')['order_id']
        self.assertEqual(self.webhook(order_id).data['status'], 'activated')
        r = self.verify(self.signed(order_id))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data['is_subscribed'])
        self.assertEqual(Subscription.objects.filter(user=self.user).count(), 1)

    def test_webhook_recovers_a_stranded_order(self):
        order_id = self.order('1_month')['order_id']
        PaymentAttempt.objects.filter(razorpay_order_id=order_id).update(status='successful', razorpay_payment_id='pay_test_0001')
        self.assertEqual(self.webhook(order_id).data['status'], 'already_processed')
        self.assertEqual(Subscription.objects.filter(user=self.user, razorpay_order_id=order_id).count(), 1)


class StackingAndLifetimeTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='stack', email='stack@local.test', password='x-Long-passw0rd')

    def test_purchase_extends_from_the_latest_live_expiry(self):
        year = Subscription.activate_from_payment(self.user, '1_year', 1999)
        month1 = Subscription.activate_from_payment(self.user, '1_month', 129)
        self.assertEqual(month1.expires_at, year.expires_at + timedelta(days=30))
        month2 = Subscription.activate_from_payment(self.user, '1_month', 129)
        # Used to end on the same day as month1 (stacked on the 1-year row).
        self.assertEqual(month2.expires_at, month1.expires_at + timedelta(days=30))

    def test_a_bare_flag_is_not_turned_into_a_lifetime_plan_by_a_dated_purchase(self):
        # The removed unpaid /auth/subscribe/ endpoint left exactly this state
        # (flag, no Subscription row). A Rs 129 month used to add a lifetime
        # 'legacy' row with unlimited AI next to it.
        User.objects.filter(pk=self.user.pk).update(is_subscribed=True)
        self.user.refresh_from_db()
        monthly = Subscription.activate_from_payment(self.user, '1_month', 129)
        self.assertEqual(list(Subscription.objects.filter(user=self.user)), [monthly])
        self.assertFalse(Subscription.get_active_subscription(self.user).unlimited_ai)

        Subscription.objects.filter(pk=monthly.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
        self.assertIsNone(Subscription.get_active_subscription(self.user))
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_subscribed)

        from accounts.utils import is_premium
        self.assertFalse(is_premium(self.user))

    def test_a_real_legacy_row_still_outlives_a_dated_plan(self):
        legacy = Subscription.activate_from_payment(self.user, 'legacy', 199)
        monthly = Subscription.activate_from_payment(self.user, '1_month', 129)
        Subscription.objects.filter(pk=monthly.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
        self.assertEqual(Subscription.get_active_subscription(self.user).pk, legacy.pk)
        from accounts.utils import is_premium
        self.assertTrue(is_premium(self.user))

    def test_unknown_plan_is_refused(self):
        with self.assertRaises(ValueError):
            Subscription.activate_from_payment(self.user, 'lifetime_typo', 0)
        self.assertFalse(Subscription.objects.filter(user=self.user).exists())


class AdminGrantAndStatusCacheTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='member', email='member@local.test', password='x-Long-passw0rd')
        self.admin = User.objects.create_user(
            username='ops', email='ops@local.test', password='x-Long-passw0rd',
            role='admin', is_superuser=True, is_staff=True,
        )
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(self.admin)
        self.student_client = APIClient()
        self.student_client.force_authenticate(self.user)

    def manage(self, payload):
        return self.admin_client.post(f'/api/auth/admin/users/{self.user.id}/subscription/', payload, format='json')

    def status(self):
        r = self.student_client.get('/api/auth/subscribe/status/')
        self.assertEqual(r.status_code, 200)
        return r.data

    def test_admin_grant_rejects_unknown_plans(self):
        for plan in ('lifetime', '1-month', ['1_month']):
            r = self.manage({'action': 'grant', 'plan': plan})
            self.assertEqual(r.status_code, 400, plan)
        self.assertFalse(Subscription.objects.filter(user=self.user).exists())
        self.assertEqual(self.manage({'action': 'grant', 'plan': '1_month'}).status_code, 200)

    def test_status_cache_is_invalidated_on_grant_and_revoke(self):
        self.assertFalse(self.status()['is_subscribed'])  # now cached for 2 minutes
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.manage({'action': 'grant', 'plan': '1_month'}).status_code, 200)
        self.assertTrue(self.status()['is_subscribed'])
        self.assertEqual(self.manage({'action': 'revoke'}).status_code, 200)
        self.assertFalse(self.status()['is_subscribed'])

    def test_expired_dated_plan_is_not_reported_as_lifetime(self):
        Subscription.activate_from_payment(self.user, '1_month', 129)
        Subscription.objects.filter(user=self.user).update(expires_at=timezone.now() - timedelta(minutes=1))
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_subscribed)  # not flipped until the next read
        body = self.status()
        self.assertFalse(body['is_subscribed'])
        self.assertIsNone(body['subscription'])

        profile = self.student_client.get('/api/auth/profile/').data
        self.assertIsNone(profile['subscription_info'])
