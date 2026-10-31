"""Payment lifecycle against the local mock provider (no network, no money).

Exercises the real order / verify / webhook views; only the Razorpay SDK
calls are replaced by accounts.payments_mock (same HMAC signature scheme).
"""
import hashlib
import hmac
import json
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate

from accounts.models import PaymentAttempt, Subscription
from accounts.payments_mock import MockCheckoutView, sign_payment

User = get_user_model()
ENV = {
    'RAZORPAY_KEY_ID': 'rzp_test_localmock',
    'RAZORPAY_KEY_SECRET': 'test-key-secret',
    'RAZORPAY_WEBHOOK_SECRET': 'test-webhook-secret',
}


@override_settings(PAYMENTS_MOCK=True)
class MockPaymentLifecycleTests(TestCase):
    def setUp(self):
        self.env = mock.patch.dict('os.environ', ENV)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.user = User.objects.create_user(username='payer', email='payer@local.test', password='x-Long-passw0rd')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _order(self, plan='1_month'):
        r = self.client.post('/api/auth/subscribe/order/', {'plan': plan}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        return r.data['order_id']

    def _checkout(self, order_id, user=None):
        request = APIRequestFactory().post('/api/auth/subscribe/mock-checkout/', {'order_id': order_id}, format='json')
        force_authenticate(request, user=user or self.user)
        return MockCheckoutView.as_view()(request)

    def _webhook(self, order_id, payment_id):
        body = json.dumps({'event': 'payment.captured',
                           'payload': {'payment': {'entity': {'id': payment_id, 'order_id': order_id}}}})
        sig = hmac.new(ENV['RAZORPAY_WEBHOOK_SECRET'].encode(), body.encode(), hashlib.sha256).hexdigest()
        return APIClient().post('/api/auth/subscribe/webhook/', data=body, content_type='application/json',
                                HTTP_X_RAZORPAY_SIGNATURE=sig)

    def test_purchase_activates_exactly_once(self):
        order_id = self._order('1_month')
        paid = self._checkout(order_id)
        self.assertEqual(paid.status_code, 200, paid.data)
        r = self.client.post('/api/auth/subscribe/verify/', paid.data, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data['is_subscribed'])
        # Duplicate verify and a late webhook must not stack another period.
        self.assertEqual(self.client.post('/api/auth/subscribe/verify/', paid.data, format='json').status_code, 200)
        self.assertEqual(self._webhook(order_id, paid.data['razorpay_payment_id']).data['status'], 'already_processed')
        self.assertEqual(Subscription.objects.filter(user=self.user).count(), 1)
        attempt = PaymentAttempt.objects.get(razorpay_order_id=order_id)
        self.assertEqual(attempt.status, 'successful')
        sub = Subscription.objects.get(user=self.user)
        self.assertEqual(sub.plan, '1_month')
        self.assertAlmostEqual((sub.expires_at - timezone.now()).days, 29, delta=1)

    def test_tampered_signature_is_rejected(self):
        order_id = self._order('1_year')
        paid = dict(self._checkout(order_id).data)
        paid['razorpay_signature'] = sign_payment(order_id, paid['razorpay_payment_id'], 'wrong-secret')
        r = self.client.post('/api/auth/subscribe/verify/', paid, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Subscription.objects.filter(user=self.user).exists())
        self.assertNotEqual(PaymentAttempt.objects.get(razorpay_order_id=order_id).status, 'successful')

    def test_webhook_first_then_verify_does_not_stack(self):
        order_id = self._order('3_months')
        paid = self._checkout(order_id).data
        self.assertEqual(self._webhook(order_id, paid['razorpay_payment_id']).data['status'], 'activated')
        r = self.client.post('/api/auth/subscribe/verify/', paid, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Subscription.objects.filter(user=self.user).count(), 1)

    def test_unavailable_plans_are_refused(self):
        for plan in ('legacy', 'admin_grant', 'lifetime', ''):
            r = self.client.post('/api/auth/subscribe/order/', {'plan': plan}, format='json')
            self.assertEqual(r.status_code, 400, plan)
        self.assertFalse(PaymentAttempt.objects.filter(user=self.user).exists())

    def test_one_year_purchase_grants_unlimited_ai(self):
        order_id = self._order('1_year')
        paid = self._checkout(order_id).data
        self.assertEqual(self.client.post('/api/auth/subscribe/verify/', paid, format='json').status_code, 200)
        sub = Subscription.get_active_subscription(self.user)
        self.assertTrue(sub.unlimited_ai)

    def test_expired_subscription_is_not_active(self):
        order_id = self._order('1_month')
        paid = self._checkout(order_id).data
        self.client.post('/api/auth/subscribe/verify/', paid, format='json')
        Subscription.objects.filter(user=self.user).update(expires_at=timezone.now() - timedelta(minutes=1))
        self.assertIsNone(Subscription.get_active_subscription(self.user))
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_subscribed)

    def test_mock_checkout_is_scoped_to_order_owner(self):
        order_id = self._order('1_month')
        other = User.objects.create_user(username='other', email='other@local.test', password='x-Long-passw0rd')
        self.assertEqual(self._checkout(order_id, user=other).status_code, 404)


class MockCheckoutDisabledTests(TestCase):
    @override_settings(PAYMENTS_MOCK=False)
    def test_disabled_outside_mock_mode(self):
        user = User.objects.create_user(username='p2', email='p2@local.test', password='x-Long-passw0rd')
        request = APIRequestFactory().post('/x/', {'order_id': 'order_mock_x'}, format='json')
        force_authenticate(request, user=user)
        self.assertEqual(MockCheckoutView.as_view()(request).status_code, 404)
