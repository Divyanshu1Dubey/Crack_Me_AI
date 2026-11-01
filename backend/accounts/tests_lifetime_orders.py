"""A lifetime member cannot be sold another period (it would add nothing),
while dated plans keep stacking. Found by the local E2E suite."""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import PaymentAttempt, Subscription

User = get_user_model()
ENV = {'RAZORPAY_KEY_ID': 'rzp_test_localmock', 'RAZORPAY_KEY_SECRET': 'test-key-secret'}


@override_settings(PAYMENTS_MOCK=True)
class LifetimeMemberOrderTests(TestCase):
    def setUp(self):
        env = mock.patch.dict('os.environ', ENV)
        env.start()
        self.addCleanup(env.stop)
        self.user = User.objects.create_user(username='lifer', email='lifer@local.test', password='x-Long-passw0rd')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _order(self, plan):
        return self.client.post('/api/auth/subscribe/order/', {'plan': plan}, format='json')

    def test_lifetime_member_order_is_refused(self):
        Subscription.activate_from_payment(self.user, 'legacy', 0, razorpay_order_id='admin_manual_1',
                                           razorpay_payment_id='admin_granted')
        for plan in ('1_month', '3_months', '1_year'):
            r = self._order(plan)
            self.assertEqual(r.status_code, 409, (plan, r.data))
            self.assertEqual(r.data['code'], 'lifetime_member')
        self.assertFalse(PaymentAttempt.objects.filter(user=self.user).exists())

    def test_dated_plans_still_stack(self):
        Subscription.activate_from_payment(self.user, '1_year', 1999, razorpay_order_id='order_x',
                                           razorpay_payment_id='pay_x')
        r = self._order('1_month')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data['order_id'].startswith('order_mock_'))

    def test_free_user_can_order(self):
        self.assertEqual(self._order('1_month').status_code, 200)
