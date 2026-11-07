"""Coupon codes (2026-11-07): an admin creates a code, a student applies it on /subscription, the admin
sees who used it. Runs the real order / verify / webhook views against the local payment mock (no network,
no money); only the Razorpay SDK calls are replaced (accounts.payments_mock).
"""
import hashlib
import hmac
import json
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate

from accounts import coupons
from accounts.models import PaymentAttempt, Subscription, TokenTransaction
from accounts.models_coupons import Coupon, CouponRedemption
from accounts.payments_mock import MockCheckoutView

User = get_user_model()
ENV = {
    'RAZORPAY_KEY_ID': 'rzp_test_localmock',
    'RAZORPAY_KEY_SECRET': 'test-key-secret',
    'RAZORPAY_WEBHOOK_SECRET': 'test-webhook-secret',
}
ORDER = '/api/auth/subscribe/order/'
VERIFY = '/api/auth/subscribe/verify/'
VALIDATE = '/api/auth/coupons/validate/'
ADMIN = '/api/auth/admin/coupons/'


@override_settings(PAYMENTS_MOCK=True)
class CouponFlowTests(TestCase):
    def setUp(self):
        cache.clear()
        env = mock.patch.dict('os.environ', ENV)
        env.start()
        self.addCleanup(env.stop)
        self.student = User.objects.create_user(username='coupon-student', email='coupon-student@local.test',
                                                password='x-Long-passw0rd')
        self.other = User.objects.create_user(username='coupon-other', email='coupon-other@local.test',
                                              password='x-Long-passw0rd')
        self.admin = User.objects.create_superuser(username='coupon-admin', email='coupon-admin@local.test',
                                                   password='x-Long-passw0rd')

    @staticmethod
    def _client(user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    @staticmethod
    def _coupon(**fields):
        data = {'code': 'SAVE20', 'discount_type': Coupon.PERCENT, 'discount_value': 20}
        data.update(fields)
        return Coupon.objects.create(**data)

    def _order(self, plan, code, user=None):
        return self._client(user or self.student).post(ORDER, {'plan': plan, 'coupon_code': code}, format='json')

    def _pay(self, order_id, user=None):
        request = APIRequestFactory().post('/api/auth/subscribe/mock-checkout/', {'order_id': order_id}, format='json')
        force_authenticate(request, user=user or self.student)
        return MockCheckoutView.as_view()(request).data

    @staticmethod
    def _webhook(order_id, payment_id):
        body = json.dumps({'event': 'payment.captured',
                           'payload': {'payment': {'entity': {'id': payment_id, 'order_id': order_id}}}})
        sig = hmac.new(ENV['RAZORPAY_WEBHOOK_SECRET'].encode(), body.encode(), hashlib.sha256).hexdigest()
        return APIClient().post('/api/auth/subscribe/webhook/', data=body, content_type='application/json',
                                HTTP_X_RAZORPAY_SIGNATURE=sig)

    # ── student: checking a code ─────────────────────────────────────────
    def test_a_code_is_quoted_for_every_plan_in_any_case(self):
        self._coupon(description='For the PSM notes review (internal)', max_uses=50)
        r = self._client(self.student).post(VALIDATE, {'code': ' save20 '}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['code'], 'SAVE20')
        self.assertEqual({p: (q['original_amount'], q['discount_amount'], q['final_amount'])
                          for p, q in r.data['plans'].items()},
                         {'1_month': (129, 25, 104), '3_months': (449, 89, 360), '1_year': (1999, 399, 1600)})
        self.assertNotIn('description', r.data)
        self.assertNotIn('max_uses', r.data)
        one = self._client(self.student).post(VALIDATE, {'code': 'SAVE20', 'plan': '1_year'}, format='json')
        self.assertEqual(list(one.data['plans']), ['1_year'])

    def test_codes_that_cannot_be_used_say_why(self):
        now = timezone.now()
        self._coupon(code='OFFCODE', is_active=False)
        self._coupon(code='OLDCODE', valid_until=now - timedelta(days=1))
        self._coupon(code='SOONCODE', valid_from=now + timedelta(days=1))
        self._coupon(code='YEARONLY', plans=['1_year'])
        self._coupon(code='FORRAVI', assigned_user=self.other)
        cases = [('NOPE123', None, 'coupon_invalid'), ('OFFCODE', None, 'coupon_invalid'),
                 ('OLDCODE', None, 'coupon_expired'), ('SOONCODE', None, 'coupon_not_started'),
                 ('YEARONLY', '1_month', 'coupon_not_for_plan'), ('FORRAVI', None, 'coupon_not_for_you'),
                 ('YEARONLY', 'scholarship_1_month', 'coupon_not_for_plan')]
        for code, plan, expected in cases:
            r = self._client(self.student).post(VALIDATE, {'code': code, 'plan': plan}, format='json')
            self.assertEqual((r.status_code, r.data['code']), (400, expected), code)
            self.assertEqual(r.data['error'], coupons.MESSAGES[expected])
        self.assertEqual(self._client(self.other).post(VALIDATE, {'code': 'FORRAVI'}, format='json').status_code, 200)

    def test_checking_codes_is_rate_limited(self):
        client = self._client(self.student)
        codes = [client.post(VALIDATE, {'code': f'GUESS{i}'}, format='json').status_code for i in range(31)]
        self.assertEqual(codes[-1], 429)

    # ── paying with a code ───────────────────────────────────────────────
    def test_a_paid_checkout_charges_the_discount_and_is_redeemed_on_verify(self):
        self._coupon()
        r = self._order('1_month', 'save20')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data['amount'], r.data['coupon_code'], r.data['discount_amount']), (10400, 'SAVE20', 25))
        attempt = PaymentAttempt.objects.get(razorpay_order_id=r.data['order_id'])
        self.assertEqual(float(attempt.amount), 104.0)
        hold = CouponRedemption.objects.get(razorpay_order_id=r.data['order_id'])
        self.assertEqual(hold.status, 'reserved')

        paid = self._pay(r.data['order_id'])
        v = self._client(self.student).post(VERIFY, paid, format='json')
        self.assertEqual(v.status_code, 200, v.data)
        hold.refresh_from_db()
        sub = Subscription.objects.get(user=self.student)
        self.assertEqual((hold.status, hold.subscription_id, float(sub.amount_paid)), ('redeemed', sub.id, 104.0))
        self.assertTrue(TokenTransaction.objects.filter(user=self.student, note__contains='coupon=SAVE20').exists())

        payments = self._client(self.admin).get('/api/auth/admin/payments/').data
        self.assertEqual([p['coupon_code'] for p in payments if p['razorpay_order_id'] == r.data['order_id']], ['SAVE20'])
        invoice = self._client(self.student).get(f'/api/auth/subscribe/invoice/{sub.id}/').data
        self.assertEqual(invoice['coupon'], {'code': 'SAVE20', 'original_amount': 129.0, 'discount_amount': 25.0})

    def test_the_webhook_also_redeems_the_code(self):
        self._coupon(code='HOOK10', discount_type=Coupon.FIXED, discount_value=10)
        r = self._order('3_months', 'HOOK10')
        self.assertEqual(r.data['amount'], 43900)
        paid = self._pay(r.data['order_id'])
        self.assertEqual(self._webhook(r.data['order_id'], paid['razorpay_payment_id']).data['status'], 'activated')
        self.assertEqual(CouponRedemption.objects.get(razorpay_order_id=r.data['order_id']).status, 'redeemed')

    def test_a_full_discount_activates_the_plan_without_a_payment(self):
        self._coupon(code='FREEYEAR', discount_value=100, plans=['1_year'])
        r = self._order('1_year', 'FREEYEAR')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data['free_activation'])
        self.assertTrue(r.data['subscription']['is_active'])
        self.assertFalse(PaymentAttempt.objects.filter(user=self.student).exists())
        redemption = CouponRedemption.objects.get(coupon__code='FREEYEAR')
        self.assertEqual((redemption.status, float(redemption.final_amount), redemption.plan), ('redeemed', 0.0, '1_year'))
        self.assertTrue(Subscription.get_active_subscription(self.student).unlimited_ai)
        again = self._order('1_year', 'FREEYEAR')
        self.assertEqual((again.status_code, again.data['code']), (400, 'coupon_already_used'))

    def test_a_code_for_another_plan_or_the_scholarship_rate_is_refused_at_checkout(self):
        self._coupon(code='YEARONLY', plans=['1_year'])
        self.assertEqual(self._order('1_month', 'YEARONLY').data['code'], 'coupon_not_for_plan')
        self.assertEqual(self._order('scholarship_1_month', 'YEARONLY').data['code'], 'coupon_not_for_plan')
        self.assertFalse(PaymentAttempt.objects.filter(user=self.student).exists())

    # ── limits ───────────────────────────────────────────────────────────
    def test_the_last_use_is_not_sold_twice_and_an_abandoned_hold_expires(self):
        self._coupon(code='ONEUSE', max_uses=1)
        first = self._order('1_month', 'ONEUSE')
        self.assertEqual(first.status_code, 200)
        blocked = self._order('1_month', 'ONEUSE', user=self.other)
        self.assertEqual((blocked.status_code, blocked.data['code']), (400, 'coupon_used_up'))
        CouponRedemption.objects.filter(razorpay_order_id=first.data['order_id']).update(
            created_at=timezone.now() - timedelta(minutes=coupons.RESERVATION_MINUTES + 1))
        self.assertEqual(self._order('1_month', 'ONEUSE', user=self.other).status_code, 200)

    def test_a_student_can_retry_a_checkout_and_cannot_reuse_a_redeemed_code(self):
        self._coupon(code='RETRY15', discount_value=15, max_uses=5)
        first = self._order('1_month', 'RETRY15')
        second = self._order('3_months', 'RETRY15')
        self.assertEqual((first.status_code, second.status_code), (200, 200))
        statuses = dict(CouponRedemption.objects.values_list('razorpay_order_id', 'status'))
        self.assertEqual(statuses, {first.data['order_id']: 'released', second.data['order_id']: 'reserved'})
        paid = self._pay(second.data['order_id'])
        self.assertEqual(self._client(self.student).post(VERIFY, paid, format='json').status_code, 200)
        self.assertEqual(self._order('1_month', 'RETRY15').data['code'], 'coupon_already_used')
        # The abandoned first order, if paid after all, is still recorded as a use.
        late = self._pay(first.data['order_id'])
        self.assertEqual(self._client(self.student).post(VERIFY, late, format='json').status_code, 200)
        self.assertEqual(CouponRedemption.objects.filter(status='redeemed').count(), 2)

    # ── admin ────────────────────────────────────────────────────────────
    def test_only_admins_manage_codes(self):
        for client in (self._client(self.student), APIClient()):
            self.assertIn(client.get(ADMIN).status_code, (401, 403))
            self.assertIn(client.post(ADMIN, {'discount_value': 10}, format='json').status_code, (401, 403))
            self.assertIn(client.get(ADMIN + 'redemptions/').status_code, (401, 403))

    def test_admin_creates_edits_and_sees_who_used_a_code(self):
        admin = self._client(self.admin)
        created = admin.post(ADMIN, {'discount_type': 'percent', 'discount_value': 50, 'plans': ['1_year', '1_month'],
                                     'max_uses': 3, 'description': 'Reward for the anatomy question review',
                                     'assigned_email': 'COUPON-STUDENT@local.test'}, format='json')
        self.assertEqual(created.status_code, 201, created.data)
        code = created.data['code']
        self.assertRegex(code, coupons.CODE_RE)
        self.assertEqual(created.data['plans'], ['1_month', '1_year'])
        self.assertEqual(created.data['assigned_user']['id'], self.student.id)
        self.assertEqual((created.data['state'], created.data['redeemed']), ('live', 0))

        bad = admin.post(ADMIN, {'code': 'x', 'discount_type': 'percent', 'discount_value': 150, 'plans': ['forever'],
                                 'valid_from': '2026-12-01T00:00:00+05:30', 'valid_until': '2026-11-01T00:00:00+05:30',
                                 'assigned_email': 'nobody@local.test'}, format='json')
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(set(bad.data['errors']),
                         {'code', 'discount_value', 'plans', 'valid_until', 'assigned_email'})
        self.assertEqual(admin.post(ADMIN, {'code': code, 'discount_value': 5}, format='json').status_code, 400)

        r = self._order('1_month', code.lower())
        paid = self._pay(r.data['order_id'])
        self.assertEqual(self._client(self.student).post(VERIFY, paid, format='json').status_code, 200)
        listed = {c['code']: c for c in admin.get(ADMIN).data['results']}
        self.assertEqual((listed[code]['redeemed'], listed[code]['discount_given'], listed[code]['revenue']),
                         (1, 64.0, 65.0))
        used = admin.get(ADMIN + 'redemptions/', {'coupon': created.data['id'], 'status': 'redeemed'}).data['results']
        self.assertEqual([(u['user']['id'], u['plan'], u['final_amount']) for u in used], [(self.student.id, '1_month', 65.0)])

        coupon_url = f"{ADMIN}{created.data['id']}/"
        off = admin.patch(coupon_url, {'is_active': False}, format='json')
        self.assertEqual((off.status_code, off.data['state']), (200, 'off'))
        self.assertEqual(admin.patch(coupon_url, {'code': 'RENAMED'}, format='json').status_code, 400)
        self.assertEqual(admin.delete(coupon_url).status_code, 409)
        unused = admin.post(ADMIN, {'code': 'UNUSED-1', 'discount_type': 'fixed', 'discount_value': 30}, format='json')
        self.assertEqual(admin.delete(f"{ADMIN}{unused.data['id']}/").status_code, 204)
        self.assertFalse(Coupon.objects.filter(code='UNUSED-1').exists())
