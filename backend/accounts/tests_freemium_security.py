"""Regression tests for Fix #1 + Fix #2 (security hardening).

Fix #1 — SubscribeVerifyView now verifies that the PaymentAttempt (if any)
belongs to the requesting user. Without this check, any authenticated
user who happens to learn another user's ``razorpay_order_id`` could
verify the payment against their own account and steal the subscription.

Fix #2 — TokenBalance.refund_token now restores purchased_tokens +
feedback_credits when an AI call fails after consuming a paid token.
The previous implementation only decremented daily/weekly counters and
silently lost paid tokens.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import (
    PaymentAttempt,
    Subscription,
    TokenBalance,
)


User = get_user_model()


class SubscribeVerifyOwnershipTests(TestCase):
    """Fix #1 — ownership check on payment verification."""

    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create_user(
            username='alice',
            email='alice@cracklabs.test',
            password='pw_alice_xyz_123',
        )
        cls.mallory = User.objects.create_user(
            username='mallory',
            email='mallory@cracklabs.test',
            password='pw_mallory_xyz_123',
        )

    def test_user_cannot_verify_someone_elses_order(self):
        """Mallory tries to verify a payment Alice made. Must be 403."""
        order_id = 'order_owned_by_alice'
        PaymentAttempt.objects.create(
            user=self.alice,
            razorpay_order_id=order_id,
            amount=129.0,
            plan='1_month',
            status='successful',
        )

        client = APIClient()
        client.force_authenticate(user=self.mallory)
        res = client.post(
            reverse('subscribe_verify'),
            {
                'razorpay_payment_id': 'pay_forged',
                'razorpay_order_id': order_id,
                'razorpay_signature': 'sig_forged',
            },
            format='json',
        )
        self.assertEqual(res.status_code, 403)
        self.assertIn('different account', res.json()['error'])

    def test_alice_can_verify_her_own_order(self):
        """Alice verifies her own order — proceeds past the ownership gate."""
        order_id = 'order_owned_by_alice_2'
        PaymentAttempt.objects.create(
            user=self.alice,
            razorpay_order_id=order_id,
            amount=129.0,
            plan='1_month',
            status='successful',
        )

        # We can't easily forge a real Razorpay signature in a unit test,
        # so we just check the gate fires BEFORE the signature check —
        # Alice's order is hers, so we should see the signature-check
        # error (400) rather than the ownership-check error (403).
        client = APIClient()
        client.force_authenticate(user=self.alice)
        res = client.post(
            reverse('subscribe_verify'),
            {
                'razorpay_payment_id': 'pay_alice',
                'razorpay_order_id': order_id,
                'razorpay_signature': 'sig_invalid_but_for_alice',
            },
            format='json',
        )
        # Either 400 (signature invalid) or 200 (signature valid by
        # accident) is acceptable — what matters is NOT 403.
        self.assertNotEqual(res.status_code, 403)


class RefundTokenRestoresPaidTokensTests(TestCase):
    """Fix #2 — refund_token must restore purchased_tokens."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='refund_user',
            email='refund@cracklabs.test',
            password='pw_refund_xyz_123',
        )
        # Create the TokenBalance explicitly — get_or_create is safer
        # than .get() because some test paths don't auto-create one.
        self.balance, _ = TokenBalance.objects.get_or_create(user=self.user)
        # User starts with 50 free (default) + 0 purchased.
        self.balance.purchased_tokens = 100
        self.balance.purchased_tokens_max = 100
        self.balance.feedback_credits = 20
        self.balance.feedback_credits_max = 20
        self.balance.save()

    def test_refund_restores_purchased_tokens(self):
        """User buys 10 tokens, consumes 5, AI fails → 5 are restored."""
        # Simulate consume: deduct 5 from purchased.
        self.balance.purchased_tokens = 95  # 100 - 5
        self.balance.total_tokens_used = 5
        self.balance.save()

        # AI call fails; refund 1 token.
        self.balance.refund_token(amount=1)

        self.balance.refresh_from_db()
        # The refund should have gone into purchased first (priority).
        self.assertEqual(self.balance.purchased_tokens, 96)
        # Lifetime counter should drop by 1.
        self.assertEqual(self.balance.total_tokens_used, 4)

    def test_refund_restores_feedback_credits_after_purchased_drained(self):
        """If purchased is at high-water, refund goes to feedback_credits."""
        # Bring purchased down to high-water (so refund can't restore more).
        self.balance.purchased_tokens = 100  # max
        self.balance.feedback_credits = 15  # 5 already spent
        self.balance.feedback_credits_max = 20
        self.balance.save()

        # Refund 2 — purchased can't grow (already at max), so it goes to feedback.
        self.balance.refund_token(amount=2)
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.purchased_tokens, 100)
        self.assertEqual(self.balance.feedback_credits, 17)

    def test_refund_decrements_daily_when_nothing_else_available(self):
        """If both purchased and feedback are at high-water, refund goes to free."""
        self.balance.purchased_tokens = 100
        self.balance.feedback_credits = 20
        self.balance.daily_tokens_used = 3
        self.balance.weekly_tokens_used = 3
        self.balance.save()

        self.balance.refund_token(amount=2)
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.daily_tokens_used, 1)
        self.assertEqual(self.balance.weekly_tokens_used, 1)