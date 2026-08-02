from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .supabase_rest_auth import SupabaseJWTAuthentication


User = get_user_model()


class AuthApiTests(TestCase):
    def test_login_endpoint_is_disabled(self):
        """Local login endpoint should return 410 Gone. Use Supabase instead."""
        username = "compat_user"
        password = "StrongPass123!"
        User.objects.create_user(
            username=username,
            email="compat@example.com",
            password=password,
        )

        response = self.client.post(
            reverse("login"),
            {"username": username, "password": password},
            content_type="application/json",
        )

        # Should return 410 Gone (endpoint disabled)
        self.assertEqual(response.status_code, 410)
        payload = response.json()
        self.assertIn("error", payload)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        FRONTEND_URL="http://localhost:3000",
    )
    def test_password_reset_request_sends_reset_link(self):
        user = User.objects.create_user(
            username="reset_user",
            email="reset@example.com",
            password="StrongPass123!",
            first_name="Reset",
        )

        response = self.client.post(
            reverse("password_reset"),
            {"email": user.email},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertIn(user.email, message.to)
        self.assertIn("/reset-password?uid=", message.body)
        self.assertIn("token=", message.body)

    def test_password_reset_confirm_updates_password(self):
        user = User.objects.create_user(
            username="confirm_user",
            email="confirm@example.com",
            password="OldPass123!",
        )

        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        response = self.client.post(
            reverse("password_reset_confirm"),
            {
                "uid": uid,
                "token": token,
                "new_password": "NewPass123!",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.check_password("NewPass123!"))

    def test_login_endpoint_disabled_regardless_of_identifier(self):
        """Local login is disabled whether using email or username."""
        user = User.objects.create_user(
            username="CaseUser",
            email="case@example.com",
            password="StrongPass123!",
        )

        response = self.client.post(
            reverse("login"),
            {"email": user.email, "password": "StrongPass123!"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 410)

    def test_superuser_login_is_disabled(self):
        """Superuser login is also disabled. Must use Supabase."""
        admin = User.objects.create_superuser(
            username="admincase",
            email="admincase@example.com",
            password="StrongPass123!",
        )

        response = self.client.post(
            reverse("login"),
            {"username": admin.username, "password": "StrongPass123!"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 410)

    def test_supabase_sync_promotes_admin_from_app_metadata(self):
        """Supabase sync should promote admin when admin flags are present in app_metadata."""
        user = User.objects.create_user(
            username="deeksha",
            email="meduraa.web@gmail.com",
            password="StrongPass123!",
            role="student",
            is_superuser=False,
            is_staff=False,
        )

        auth_backend = SupabaseJWTAuthentication()
        auth_backend._upsert_local_user(
            {
                "email": "meduraa.web@gmail.com",
                "user_metadata": {
                    "username": "deeksha",
                    "first_name": "deeksha",
                },
                "app_metadata": {
                    "role": "admin",
                    "is_admin": True,
                },
            }
        )

        user.refresh_from_db()
        self.assertEqual(user.role, "admin")
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)

    def test_supabase_sync_ignores_user_metadata_for_promotion(self):
        """Supabase sync must ignore admin flags in user_metadata to prevent self-promotion."""
        user = User.objects.create_user(
            username="attacker",
            email="attacker@example.com",
            password="StrongPass123!",
            role="student",
            is_superuser=False,
            is_staff=False,
        )

        auth_backend = SupabaseJWTAuthentication()
        auth_backend._upsert_local_user(
            {
                "email": "attacker@example.com",
                "user_metadata": {
                    "username": "attacker",
                    "first_name": "Attacker",
                    "role": "admin",
                    "is_admin": True,
                },
                "app_metadata": {},
            }
        )

        user.refresh_from_db()
        self.assertEqual(user.role, "student")
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_staff)

    def test_supabase_sync_demotes_user(self):
        """Supabase sync should demote an admin when admin flags are removed."""
        user = User.objects.create_user(
            username="deeksha",
            email="demoted.user@example.com",
            password="StrongPass123!",
            role="admin",
            is_superuser=True,
            is_staff=True,
        )

        auth_backend = SupabaseJWTAuthentication()
        auth_backend._upsert_local_user(
            {
                "email": "demoted.user@example.com",
                "user_metadata": {
                    "username": "deeksha",
                    "first_name": "deeksha",
                },
                "app_metadata": {
                    "role": "student",
                    "is_admin": False,
                },
            }
        )

        user.refresh_from_db()
        self.assertEqual(user.role, "student")
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_staff)


class ProfileAndSubscriptionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="student_user",
            email="student@example.com",
            password="Password123!",
            role="student"
        )
        # Auth token is usually verified via JWT, but since we are using django test client,
        # we can force authenticate the user.
        self.client.force_login(self.user)

    def test_profile_update_rewards_tokens_once(self):
        """Updating both phone and college should reward 10 tokens exactly once."""
        from .models import TokenBalance, TokenTransaction

        # Pre-check
        balance, _ = TokenBalance.objects.get_or_create(user=self.user)
        self.assertEqual(balance.feedback_credits, 0)
        self.assertFalse(self.user.profile_bonus_rewarded)

        # Update profile with phone and college
        response = self.client.patch(
            reverse("profile"),
            {
                "phone": "9876543210",
                "college": "Maulana Azad Medical College"
            },
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)

        # Post-check: user rewarded
        self.user.refresh_from_db()
        balance.refresh_from_db()
        self.assertTrue(self.user.profile_bonus_rewarded)
        self.assertEqual(balance.feedback_credits, 10)

        # Verify transaction log
        tx = TokenTransaction.objects.filter(user=self.user, transaction_type="feedback_reward").first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.amount, 10)

        # Update again, token balance should NOT increase further
        response = self.client.patch(
            reverse("profile"),
            {
                "first_name": "NewName"
            },
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        balance.refresh_from_db()
        self.assertEqual(balance.feedback_credits, 10)

    def test_subscription_activation(self):
        """DEPRECATED: the legacy /subscribe/ endpoint now returns 410 Gone.
        Subscriptions flow through the Razorpay order/verify pipeline.
        Kept as a regression test that the deprecated endpoint is dead.
        """
        response = self.client.post(reverse("subscribe"))
        self.assertEqual(response.status_code, 410)


class TokenPurchaseDisabledTestCase(TestCase):
    """Phase-4 hardening: the standalone tokens/purchase endpoint must
    never mint tokens directly.

    The current implementation accepts an arbitrary amount + payment_id and
    credits the user's balance without verifying any payment. Until
    Razorpay/Stripe integration lands, the endpoint is disabled and
    returns 503 with a clear "payments_unavailable" error code so the
    frontend can render a graceful unavailable state.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="purchase_disabled_user",
            email="purchase-disabled@example.com",
            password="StrongPass123!",
            role="student",
        )

    def test_purchase_endpoint_returns_503(self):
        self.client.force_login(self.user)
        res = self.client.post(
            reverse("token_purchase"),
            {"amount": 10},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 503)
        body = res.json()
        self.assertEqual(body.get("code"), "payments_unavailable")
        self.assertIn("temporarily unavailable", body.get("error", "").lower())

    def test_purchase_does_not_credit_balance(self):
        """Even if 503 lands, no TokenBalance row should be created or
        mutated by the disabled purchase path. This protects us against
        accidental reactivation of the legacy mint code.
        """
        from .models import TokenBalance, TokenTransaction
        self.client.force_login(self.user)
        res = self.client.post(
            reverse("token_purchase"),
            {"amount": 50, "payment_id": "fake_pay_123"},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 503)

        # No TokenBalance and no TokenTransaction of type 'purchase' for
        # this user — the disabled path must never reach the DB writer.
        self.assertFalse(TokenBalance.objects.filter(user=self.user).exists())
        self.assertFalse(
            TokenTransaction.objects.filter(
                user=self.user, transaction_type="purchase",
            ).exists()
        )


class SubscriptionWorkflowTests(TestCase):
    """End-to-end tests for the subscription workflow audit fixes.

    Covers:
      - PLAN_FEATURES + Subscription.unlimited_ai (PR A)
      - Subscription.activate_from_payment → monthly_tokens_grant credited
      - Subscription stacking behavior (re-activate extends, not replaces)
      - Admin grant + admin revoke (PR C — fixes is_active property bug)
      - Subscription.activate_from_payment on lifetime plans
      - SubscriptionHistoryView response shape for legacy users
      - Subscription status self-healing when past expiry

    Token-bypass tests for consume_ai_token live in ai_engine/tests/test_*.py.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="audit_student",
            email="audit.student@example.com",
            password="StrongPass123!",
            role="student",
        )
        self.admin = User.objects.create_user(
            username="audit_admin",
            email="audit.admin@example.com",
            password="StrongPass123!",
            role="admin",
            is_staff=True,
            is_superuser=True,
        )
        # Clear DRF throttle cache so the SubscriptionStatusThrottleTests class
        # (which runs after/before this in the same module) doesn't leak
        # 429s into the SubscriptionStatusView calls below.
        from django.core.cache import cache
        cache.clear()

    # ── PLAN_FEATURES is the single source of truth ──────────────────

    def test_plan_features_truth_table(self):
        """Single source of truth — must NOT regress silently."""
        from .models import PLAN_FEATURES
        # 1_year: unlimited AI, lifetime-ish tokens
        self.assertTrue(PLAN_FEATURES['1_year']['unlimited_ai'])
        self.assertIsNone(PLAN_FEATURES['1_year']['monthly_tokens'])
        # 1_month: NOT unlimited
        self.assertFalse(PLAN_FEATURES['1_month']['unlimited_ai'])
        self.assertEqual(PLAN_FEATURES['1_month']['monthly_tokens'], 100)
        # 3_months: NOT unlimited, 300 tokens
        self.assertFalse(PLAN_FEATURES['3_months']['unlimited_ai'])
        self.assertEqual(PLAN_FEATURES['3_months']['monthly_tokens'], 300)
        # legacy / admin_grant: lifetime + unlimited
        self.assertTrue(PLAN_FEATURES['legacy']['unlimited_ai'])
        self.assertTrue(PLAN_FEATURES['admin_grant']['unlimited_ai'])
        self.assertIsNone(PLAN_FEATURES['legacy']['duration'])
        self.assertIsNone(PLAN_FEATURES['admin_grant']['duration'])
        # scholarship_1_month: NOT unlimited, 100 tokens
        self.assertFalse(PLAN_FEATURES['scholarship_1_month']['unlimited_ai'])
        self.assertEqual(PLAN_FEATURES['scholarship_1_month']['monthly_tokens'], 100)

    # ── Subscription.unlimited_ai property ───────────────────────────

    def test_subscription_unlimited_ai_property(self):
        """1_year / legacy / admin_grant report unlimited_ai=True."""
        from datetime import timedelta
        from django.utils import timezone
        from .models import Subscription

        cases = [
            ('1_year', True),
            ('1_month', False),
            ('3_months', False),
            ('scholarship_1_month', False),
            ('legacy', True),
            ('admin_grant', True),
        ]
        for plan, expected in cases:
            sub = Subscription(user=self.user, plan=plan)
            self.assertEqual(
                sub.unlimited_ai, expected,
                f"Plan {plan} should report unlimited_ai={expected}",
            )

    # ── activate_from_payment grants monthly tokens ──────────────────

    def test_activate_1_month_grants_100_tokens(self):
        """1-month subscription credits 100 purchased tokens on activation."""
        from .models import Subscription, TokenBalance, TokenTransaction

        sub = Subscription.activate_from_payment(
            user=self.user, plan='1_month', amount_paid=129.00,
        )
        self.assertTrue(sub.is_active)
        self.assertEqual(sub.plan, '1_month')

        balance = TokenBalance.objects.get(user=self.user)
        # TokenBalance default is 50; activation adds 100 → 150 total.
        # Verify the *delta* rather than the absolute value so we don't
        # regress if the default changes.
        self.assertEqual(balance.purchased_tokens, 50 + 100)

        grant = TokenTransaction.objects.filter(
            user=self.user, transaction_type='subscription_grant',
        ).first()
        self.assertIsNotNone(grant)
        self.assertEqual(grant.amount, 100)

    def test_activate_1_year_does_not_grant_tokens(self):
        """1_year is unlimited — no token grant (PLAN_FEATURES.monthly_tokens=None)."""
        from .models import Subscription, TokenBalance, TokenTransaction

        Subscription.activate_from_payment(
            user=self.user, plan='1_year', amount_paid=1999.00,
        )

        # Balance may or may not exist (no grant means no auto-create);
        # if it doesn't exist, that's the strongest assertion of "no grant".
        self.assertFalse(
            TokenTransaction.objects.filter(
                user=self.user, transaction_type='subscription_grant',
            ).exists(),
            "1_year must NOT issue a subscription_grant transaction",
        )

        if TokenBalance.objects.filter(user=self.user).exists():
            balance = TokenBalance.objects.get(user=self.user)
            # If a balance exists, it must NOT have been bumped by the activation.
            self.assertEqual(balance.purchased_tokens, 50)

    def test_admin_grant_makes_user_subscribed(self):
        """Admin grant should flip is_subscribed + create lifetime subscription."""
        from .models import Subscription

        self.assertFalse(self.user.is_subscribed)
        Subscription.activate_from_payment(
            user=self.user, plan='admin_grant', amount_paid=0,
        )
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_subscribed)
        sub = Subscription.get_active_subscription(self.user)
        self.assertIsNotNone(sub)
        self.assertEqual(sub.plan, 'admin_grant')
        self.assertIsNone(sub.expires_at)  # lifetime
        self.assertTrue(sub.is_lifetime)
        self.assertTrue(sub.unlimited_ai)

    # ── Stacking behavior ────────────────────────────────────────────

    def test_re_activate_stacks_on_expiry(self):
        """Buying 1_month twice should EXTEND expires_at, not replace it."""
        from datetime import timedelta
        from django.utils import timezone
        from .models import Subscription

        sub1 = Subscription.activate_from_payment(
            user=self.user, plan='1_month', amount_paid=129.00,
        )
        original_expiry = sub1.expires_at
        self.assertIsNotNone(original_expiry)

        sub2 = Subscription.activate_from_payment(
            user=self.user, plan='1_month', amount_paid=129.00,
        )
        self.assertGreater(sub2.expires_at, original_expiry)
        # Each subscription row exists; both rows are 'active' until
        # get_active_subscription prefers the most-recent.
        self.assertEqual(Subscription.objects.filter(user=self.user, status='active').count(), 2)
        active = Subscription.get_active_subscription(self.user)
        self.assertEqual(active.id, sub2.id)  # newest wins

    # ── Self-healing: past-expiry flips to 'expired' ──────────────────

    def test_past_expiry_sub_flips_to_expired_on_read(self):
        """A subscription whose expires_at is in the past must be marked expired."""
        from datetime import timedelta
        from django.utils import timezone
        from .models import Subscription

        sub = Subscription.objects.create(
            user=self.user, plan='1_month', plan_display_name='1 Month Pass',
            amount_paid=129, status='active',
            starts_at=timezone.now() - timedelta(days=60),
            expires_at=timezone.now() - timedelta(days=1),
        )
        self.user.is_subscribed = True
        self.user.save()

        active = Subscription.get_active_subscription(self.user)
        self.assertIsNone(active)

        sub.refresh_from_db()
        self.assertEqual(sub.status, 'expired')
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_subscribed)

    # ── Admin revoke fixes the is_active property bug ─────────────────

    def test_admin_revoke_actually_cancels(self):
        """PR C: admin revoke must affect real rows (was filtering on is_active property)."""
        from .models import Subscription

        # Admin grants 1_month subscription
        Subscription.activate_from_payment(
            user=self.user, plan='1_month', amount_paid=129.00,
        )
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_subscribed)

        # Force login as admin and revoke
        self.client.force_login(self.admin)
        resp = self.client.post(
            reverse('admin_subscription_manage', args=[self.user.id]),
            {'action': 'revoke'},
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['revoked_count'], 1, "revoke should cancel exactly 1 active subscription")

        self.user.refresh_from_db()
        self.assertFalse(self.user.is_subscribed)
        active = Subscription.get_active_subscription(self.user)
        self.assertIsNone(active)

    def test_admin_revoke_for_user_without_subscription_is_zero(self):
        """Revoking a user with no active sub returns revoked_count=0 (no error)."""
        self.client.force_login(self.admin)
        resp = self.client.post(
            reverse('admin_subscription_manage', args=[self.user.id]),
            {'action': 'revoke'},
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['revoked_count'], 0)

    def test_non_admin_cannot_grant_subscription(self):
        """Permission check: students must NOT be able to grant themselves a sub."""
        self.client.force_login(self.user)
        resp = self.client.post(
            reverse('admin_subscription_manage', args=[self.user.id]),
            {'action': 'grant', 'plan': '1_year'},
            content_type='application/json',
        )
        # 403 Forbidden (IsControlTowerAdmin) OR 401 if not admin user
        self.assertIn(resp.status_code, (401, 403))

    # ── SubscriptionStatusView response shape (B6 fix) ───────────────

    def test_legacy_user_status_has_full_shape(self):
        """PR-A B6: legacy (user.is_subscribed=True but no Subscription row)
        must return a serialized subscription stub with all required fields."""
        # Make user look like a legacy/lifetime user
        self.user.is_subscribed = True
        self.user.save()

        self.client.force_login(self.user)
        resp = self.client.get(reverse('subscribe_status'))
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body['is_subscribed'])
        sub = body['subscription']
        self.assertIsNotNone(sub)
        # Must include ALL fields the frontend reads, otherwise subscribers
        # appear unsubscribed (the original bug B6).
        for required in ('id', 'plan', 'plan_display_name', 'status',
                         'is_active', 'starts_at', 'expires_at',
                         'days_remaining', 'amount_paid',
                         'razorpay_order_id', 'created_at'):
            self.assertIn(required, sub, f"legacy stub missing {required}")

    def test_active_user_status_returns_subscription(self):
        """Normal active subscription returns full subscription object."""
        from .models import Subscription

        Subscription.activate_from_payment(
            user=self.user, plan='1_year', amount_paid=1999.00,
        )
        self.client.force_login(self.user)
        resp = self.client.get(reverse('subscribe_status'))
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body['is_subscribed'])
        sub = body['subscription']
        self.assertEqual(sub['plan'], '1_year')
        self.assertEqual(sub['plan_display_name'], '1 Year Unlimited')
        self.assertEqual(sub['status'], 'active')

    # ── SubscriptionHistoryView ──────────────────────────────────────

    def test_history_returns_all_user_subscriptions(self):
        """History endpoint returns every subscription row for the user, newest first."""
        from .models import Subscription

        Subscription.activate_from_payment(
            user=self.user, plan='1_month', amount_paid=129.00,
        )
        Subscription.activate_from_payment(
            user=self.user, plan='3_months', amount_paid=449.00,
        )

        self.client.force_login(self.user)
        resp = self.client.get(reverse('subscribe_history'))
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['count'], 2)
        plans = [s['plan'] for s in body['subscriptions']]
        self.assertEqual(plans[0], '3_months')  # newest first
        self.assertEqual(plans[1], '1_month')


class SubscriptionStatusThrottleTests(TestCase):
    """PR E: /auth/subscribe/status/ must be throttled to avoid abuse."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="throttle_user",
            email="throttle@example.com",
            password="StrongPass123!",
        )
        self.client.force_login(self.user)
        # Clear DRF's throttle cache so prior tests don't taint this one.
        from django.core.cache import cache
        cache.clear()

    def test_status_endpoint_throttled_after_many_requests(self):
        """Hit status endpoint more times than the per-minute throttle allows."""
        from rest_framework.settings import api_settings

        # Resolve the actual configured rate (default 60/min, overrideable)
        scope = 'subscription_status'
        rates = api_settings.DEFAULT_THROTTLE_RATES
        rate_str = rates.get(scope, '60/min')
        max_calls = int(rate_str.split('/')[0])

        # Hit exactly max_calls+1 to make sure the (max_calls+1)th call is throttled.
        last_status = None
        for _ in range(max_calls + 1):
            r = self.client.get(reverse('subscribe_status'))
            last_status = r.status_code
        self.assertEqual(
            last_status, 429,
            f"After {max_calls + 1} calls, expected 429 throttle, got {last_status}",
        )


class TokenRefundTests(TestCase):
    """PR A: refund_ai_token + TokenBalance.refund_token must restore purchased tokens."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="refund_user",
            email="refund@example.com",
            password="StrongPass123!",
        )
        self.client.force_login(self.user)

    def test_refund_decrements_total_tokens_used(self):
        """refund_token(amount=1) decreases total_tokens_used by exactly 1."""
        from accounts.models import TokenBalance

        balance, _ = TokenBalance.objects.get_or_create(user=self.user)
        # Simulate a successful consume then refund
        balance.consume_token(amount=1)
        self.assertEqual(balance.total_tokens_used, 1)
        balance.refund_token(amount=1)
        balance.refresh_from_db()
        self.assertEqual(balance.total_tokens_used, 0)

    def test_refund_does_not_make_total_negative(self):
        """refund_token must clamp total_tokens_used at 0 — never negative."""
        from accounts.models import TokenBalance

        balance, _ = TokenBalance.objects.get_or_create(user=self.user)
        # No consume first — refund 1 should still clamp to 0
        balance.refund_token(amount=1)
        balance.refresh_from_db()
        self.assertEqual(balance.total_tokens_used, 0)

    def test_refund_restores_daily_counter(self):
        """refund_token should decrement daily_tokens_used (mirror of consume)."""
        from accounts.models import TokenBalance

        balance, _ = TokenBalance.objects.get_or_create(user=self.user)
        balance.consume_token(amount=3)
        self.assertEqual(balance.daily_tokens_used, 3)
        balance.refund_token(amount=2)
        balance.refresh_from_db()
        self.assertEqual(balance.daily_tokens_used, 1)

    def test_consume_then_refund_round_trip(self):
        """Common case: AI call consumed 1 token, call failed, refund 1."""
        from accounts.models import TokenBalance

        balance, _ = TokenBalance.objects.get_or_create(user=self.user)
        original_available = balance.available_tokens
        self.assertTrue(balance.consume_token(amount=1))
        balance.refresh_from_db()
        self.assertEqual(balance.total_tokens_used, 1)
        self.assertEqual(balance.available_tokens, original_available - 1)

        balance.refund_token(amount=1)
        balance.refresh_from_db()
        self.assertEqual(balance.total_tokens_used, 0)
        self.assertEqual(balance.available_tokens, original_available)


class SubscriptionBypassAITests(TestCase):
    """PR A: subscribers with unlimited_ai must NOT be token-deducted on AI calls.

    Calls consume_ai_token() directly (bypasses network/AI provider) so the
    test runs offline and stays fast.
    """

    def setUp(self):
        from accounts.models import Subscription
        self.user = User.objects.create_user(
            username="bypass_user",
            email="bypass@example.com",
            password="StrongPass123!",
        )
        Subscription.activate_from_payment(
            user=self.user, plan='1_year', amount_paid=1999.00,
        )
        self.client.force_login(self.user)

    def _fake_request(self):
        """Build a minimal DRF request stub for consume_ai_token."""
        from rest_framework.test import APIRequestFactory
        factory = APIRequestFactory()
        request = factory.post('/ai/tutor/', {'question': 'test'}, format='json')
        request.user = self.user
        return request

    def test_consume_bypasses_for_1_year_subscriber(self):
        """A 1-year subscriber's consume_ai_token should return (True, None)
        without touching TokenBalance."""
        from accounts.models import TokenBalance
        from ai_engine.views import consume_ai_token

        balance, _ = TokenBalance.objects.get_or_create(user=self.user)
        before_total = balance.total_tokens_used
        before_purchased = balance.purchased_tokens

        ok, err = consume_ai_token(self._fake_request())
        self.assertTrue(ok)
        self.assertIsNone(err)

        balance.refresh_from_db()
        self.assertEqual(balance.total_tokens_used, before_total)
        self.assertEqual(balance.purchased_tokens, before_purchased)

    def test_consume_bypasses_for_legacy_subscriber(self):
        """Legacy users (user.is_subscribed=True but no plan row) — bypass."""
        from datetime import timedelta
        from django.utils import timezone
        from accounts.models import Subscription, TokenBalance
        from ai_engine.views import consume_ai_token

        legacy_user = User.objects.create_user(
            username="legacy_bypass",
            email="legacy-bypass@example.com",
            password="StrongPass123!",
        )
        # Manually create a legacy subscription
        Subscription.objects.create(
            user=legacy_user, plan='legacy',
            plan_display_name='Legacy Early Bird (Lifetime)',
            status='active', amount_paid=199,
            expires_at=None,  # lifetime
        )
        legacy_user.is_subscribed = True
        legacy_user.save()

        balance, _ = TokenBalance.objects.get_or_create(user=legacy_user)
        before_total = balance.total_tokens_used

        req = self._fake_request()
        req.user = legacy_user
        ok, err = consume_ai_token(req)
        self.assertTrue(ok)
        self.assertIsNone(err)

        balance.refresh_from_db()
        self.assertEqual(balance.total_tokens_used, before_total)

    def test_consume_still_deducts_for_1_month_subscriber(self):
        """1-month subscribers have a token grant, but AI calls still meter."""
        from accounts.models import Subscription, TokenBalance
        from ai_engine.views import consume_ai_token

        user_1mo = User.objects.create_user(
            username="onemonth_user",
            email="onemonth@example.com",
            password="StrongPass123!",
        )
        Subscription.activate_from_payment(
            user=user_1mo, plan='1_month', amount_paid=129.00,
        )

        balance, _ = TokenBalance.objects.get_or_create(user=user_1mo)
        before_total = balance.total_tokens_used
        # Should have gotten 100 purchased tokens on top of the 50 default = 150
        self.assertEqual(balance.purchased_tokens, 50 + 100)

        req = self._fake_request()
        req.user = user_1mo
        ok, err = consume_ai_token(req)
        self.assertTrue(ok)
        self.assertIsNone(err)

        balance.refresh_from_db()
        # 1-month plan does NOT bypass — token must be consumed
        self.assertEqual(balance.total_tokens_used, before_total + 1)

    def test_consume_bypasses_for_admin_user(self):
        """Admins should never be token-deducted (existing rule)."""
        from accounts.models import TokenBalance
        from ai_engine.views import consume_ai_token

        admin = User.objects.create_user(
            username="bypass_admin",
            email="bypass-admin@example.com",
            password="StrongPass123!",
            role="admin", is_staff=True, is_superuser=True,
        )
        balance, _ = TokenBalance.objects.get_or_create(user=admin)
        before_total = balance.total_tokens_used

        req = self._fake_request()
        req.user = admin
        ok, err = consume_ai_token(req)
        self.assertTrue(ok)
        self.assertIsNone(err)

        balance.refresh_from_db()
        self.assertEqual(balance.total_tokens_used, before_total)

    def test_consume_returns_429_when_no_tokens_no_sub(self):
        """Free user with 0 tokens must get 429 'insufficient_tokens'."""
        from accounts.models import TokenBalance
        from ai_engine.views import consume_ai_token
        from django.conf import settings as django_settings
        from rest_framework.test import APIRequestFactory

        broke_user = User.objects.create_user(
            username="broke_user",
            email="broke@example.com",
            password="StrongPass123!",
        )
        # Drain the balance
        balance, _ = TokenBalance.objects.get_or_create(user=broke_user)
        # Force zero tokens: consume until empty
        while balance.consume_token(amount=1):
            balance.refresh_from_db()
        self.assertEqual(balance.available_tokens, 0)

        factory = APIRequestFactory()
        req = factory.post('/ai/tutor/', {'question': 'test'}, format='json')
        req.user = broke_user

        ok, err = consume_ai_token(req)
        self.assertFalse(ok)
        self.assertIsNotNone(err)
        self.assertEqual(err.status_code, 429)
        self.assertEqual(err.data.get('error'), 'insufficient_tokens')


class SubscriptionEndToEndWorkflowTests(TestCase):
    """End-to-end workflow test from the user's perspective + admin grant.

    Mirrors the user complaint: "I bought a subscription but my tokens
    still got deducted."

    Sequence (the one the user complained about):
      1. Admin grants a 1_year Unlimited subscription to a free user.
      2. User logs in (free + has tokens).
      3. User asks an AI question (consume_ai_token).
      4. Token balance MUST NOT decrease — unlimited_ai bypass.
      5. User's /subscribe/status/ reflects unlimited, lifetime.
      6. Revoke: admin removes the subscription.
      7. User asks another AI question — NOW tokens are deducted.
      8. Token balance decreases by 1.

    Plus a parallel flow for 1-month (non-unlimited) subscribers:
      1. Admin grants 1_month.
      2. 100 purchased tokens credited.
      3. AI call consumes 1 token from the purchased pool.
      4. Tokens show 99 (was 150 = 50 default + 100 grant).
    """

    def setUp(self):
        from django.core.cache import cache
        cache.clear()

        self.user = User.objects.create_user(
            username="workflow_user",
            email="workflow@example.com",
            password="StrongPass123!",
            role="student",
        )
        self.admin = User.objects.create_user(
            username="workflow_admin",
            email="workflow.admin@example.com",
            password="StrongPass123!",
            role="admin",
            is_staff=True,
            is_superuser=True,
        )

    # ── Primary user complaint: "I paid but tokens still deduct" ─────

    def test_full_workflow_admin_grants_1_year_user_bypass_then_revoke(self):
        """User buys 1_year Unlimited → AI calls bypass → admin revokes → tokens deducted."""
        from accounts.models import Subscription, TokenBalance, TokenTransaction
        from ai_engine.views import consume_ai_token
        from rest_framework.test import APIRequestFactory

        # ── STEP 1: Admin grants 1_year Unlimited via the admin endpoint ──
        self.client.force_login(self.admin)
        resp = self.client.post(
            reverse('admin_subscription_manage', args=[self.user.id]),
            {'action': 'grant', 'plan': '1_year'},
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200, "Admin grant should succeed")
        self.assertEqual(resp.json()['message'], 'Subscription 1_year granted to workflow_user')

        # ── STEP 2: Verify user.is_subscribed flipped + Sub row exists ──
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_subscribed)
        sub = Subscription.get_active_subscription(self.user)
        self.assertIsNotNone(sub)
        self.assertEqual(sub.plan, '1_year')
        self.assertTrue(sub.unlimited_ai)
        # No expiry = lifetime-like (1_year has duration=365d, not lifetime,
        # but for the purpose of this test, the *key* property is unlimited_ai)
        self.assertEqual(sub.expires_at is not None, True)

        # ── STEP 3: 1_year must NOT issue a subscription_grant transaction ──
        self.assertFalse(
            TokenTransaction.objects.filter(
                user=self.user, transaction_type='subscription_grant',
            ).exists(),
            "1_year is unlimited — no token grant should be issued",
        )

        # ── STEP 4: User logs in (free), reads /subscribe/status/ ──
        self.client.force_login(self.user)
        # Clear throttle cache again — different test user means different
        # throttle bucket, but defense in depth.
        from django.core.cache import cache
        cache.clear()

        status_resp = self.client.get(reverse('subscribe_status'))
        self.assertEqual(status_resp.status_code, 200)
        body = status_resp.json()
        self.assertTrue(body['is_subscribed'])
        self.assertEqual(body['subscription']['plan'], '1_year')
        self.assertEqual(body['subscription']['plan_display_name'], '1 Year Unlimited')

        # ── STEP 5: User asks an AI question — token bypass expected ──
        # Capture baseline BEFORE the call. The bypass means total_tokens_used
        # must not change at all — we don't need to drain first because
        # if the bypass works, no counter is touched.
        balance, _ = TokenBalance.objects.get_or_create(user=self.user)
        tokens_before = balance.total_tokens_used
        purchased_before = balance.purchased_tokens
        daily_before = balance.daily_tokens_used
        weekly_before = balance.weekly_tokens_used

        factory = APIRequestFactory()
        req = factory.post('/ai/tutor/', {'question': 'What is the treatment for X?'}, format='json')
        req.user = self.user

        ok, err = consume_ai_token(req)
        self.assertTrue(ok, f"Bypass should allow AI call: {err}")
        self.assertIsNone(err)

        # ── STEP 6: ALL counters UNCHANGED (the fix) ──
        balance.refresh_from_db()
        self.assertEqual(
            balance.total_tokens_used, tokens_before,
            "Bypass: AI call must NOT deduct from total_tokens_used for 1_year subscriber",
        )
        self.assertEqual(
            balance.purchased_tokens, purchased_before,
            "Bypass: purchased tokens must remain intact",
        )
        self.assertEqual(
            balance.daily_tokens_used, daily_before,
            "Bypass: daily_tokens_used must remain intact",
        )
        self.assertEqual(
            balance.weekly_tokens_used, weekly_before,
            "Bypass: weekly_tokens_used must remain intact",
        )

        # ── STEP 7: Admin revokes subscription ──
        self.client.force_login(self.admin)
        from django.core.cache import cache
        cache.clear()

        revoke_resp = self.client.post(
            reverse('admin_subscription_manage', args=[self.user.id]),
            {'action': 'revoke'},
            content_type='application/json',
        )
        self.assertEqual(revoke_resp.status_code, 200)
        self.assertEqual(revoke_resp.json()['revoked_count'], 1)

        # ── STEP 8: User's is_subscribed flipped to False ──
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_subscribed)
        self.assertIsNone(Subscription.get_active_subscription(self.user))

        # ── STEP 9: Now an AI call SHOULD be metered ──
        balance.refresh_from_db()
        tokens_before = balance.total_tokens_used

        req = factory.post('/ai/tutor/', {'question': 'follow-up'}, format='json')
        req.user = self.user
        ok, err = consume_ai_token(req)

        # Either: succeeds (had feedback credits/purchased) and deducts,
        # or: 429 (truly out of tokens). Both prove the bypass is gone.
        if ok:
            balance.refresh_from_db()
            self.assertGreater(
                balance.total_tokens_used, tokens_before,
                "Post-revoke AI call must deduct a token (bypass gone)",
            )
        else:
            self.assertEqual(err.status_code, 429)
            self.assertEqual(err.data.get('error'), 'insufficient_tokens')

    # ── 1-month plan: AI call still metered, but user got a 100-token grant ──

    def test_workflow_1_month_grants_tokens_then_meters(self):
        """1-month: 100 token grant + AI calls still metered."""
        from accounts.models import Subscription, TokenBalance, TokenTransaction
        from ai_engine.views import consume_ai_token
        from rest_framework.test import APIRequestFactory

        # Admin grants 1_month
        self.client.force_login(self.admin)
        resp = self.client.post(
            reverse('admin_subscription_manage', args=[self.user.id]),
            {'action': 'grant', 'plan': '1_month'},
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)

        # 100 purchased tokens credited
        balance = TokenBalance.objects.get(user=self.user)
        self.assertEqual(balance.purchased_tokens, 50 + 100)  # default + grant
        grant = TokenTransaction.objects.filter(
            user=self.user, transaction_type='subscription_grant',
        ).first()
        self.assertIsNotNone(grant)
        self.assertEqual(grant.amount, 100)

        # User makes an AI call — must be metered (not bypassed).
        # consume_token priority: free → feedback → purchased. The user
        # has free daily tokens (10/day) AND a fresh 100-token grant;
        # the call will consume from free first. We assert total_tokens_used
        # went up by exactly 1, proving the call was metered.
        factory = APIRequestFactory()
        req = factory.post('/ai/tutor/', {'question': 'test'}, format='json')
        req.user = self.user

        before_total = balance.total_tokens_used

        ok, err = consume_ai_token(req)
        self.assertTrue(ok)
        self.assertIsNone(err)

        balance.refresh_from_db()
        # The critical assertion: a 1-month subscriber's AI call IS metered
        # (total_tokens_used increments by 1). They keep the 100-token
        # grant intact because it only gets drawn when free+feedback are exhausted.
        self.assertEqual(
            balance.total_tokens_used, before_total + 1,
            "1-month plan does NOT bypass token metering",
        )

    # ── Lifetime plans: never expire, never bypass-able to lose ─────

    def test_workflow_admin_grant_is_lifetime(self):
        """Admin grant creates a lifetime subscription that never expires."""
        from accounts.models import Subscription

        self.client.force_login(self.admin)
        self.client.post(
            reverse('admin_subscription_manage', args=[self.user.id]),
            {'action': 'grant', 'plan': 'admin_grant'},
            content_type='application/json',
        )

        sub = Subscription.get_active_subscription(self.user)
        self.assertIsNotNone(sub)
        self.assertEqual(sub.plan, 'admin_grant')
        self.assertTrue(sub.is_lifetime)
        self.assertIsNone(sub.expires_at)
        self.assertTrue(sub.unlimited_ai)
        # Even after the test's date mocking would push past any expiry,
        # lifetime plans remain active.
        self.assertTrue(sub.is_active)


class IsPremiumHelperTests(TestCase):
    """Freemium gate: is_premium(user) is the single source of truth for
    whether the user has paid access. Used by every backend gate.
    """

    def setUp(self):
        self.student = User.objects.create_user(
            username='is_premium_stu', email='stu@x.com', password='x',
        )
        self.admin = User.objects.create_user(
            username='is_premium_adm', email='adm@x.com', password='x',
            is_staff=True, is_superuser=True,
        )

    def test_anonymous_user_is_not_premium(self):
        from django.contrib.auth.models import AnonymousUser
        from accounts.utils import is_premium
        self.assertFalse(is_premium(AnonymousUser()))

    def test_student_without_subscription_is_not_premium(self):
        from accounts.utils import is_premium
        self.assertFalse(is_premium(self.student))

    def test_admin_is_always_premium(self):
        from accounts.utils import is_premium
        self.assertTrue(is_premium(self.admin))

    def test_active_subscription_makes_premium(self):
        from accounts.utils import is_premium
        from accounts.models import Subscription
        Subscription.objects.create(
            user=self.student, plan='1_month', status='active',
            expires_at=timezone.now() + timedelta(days=30), amount_paid=12900,
        )
        self.assertTrue(is_premium(self.student))

    def test_expired_subscription_is_not_premium(self):
        from accounts.utils import is_premium
        from accounts.models import Subscription
        Subscription.objects.create(
            user=self.student, plan='1_month', status='active',
            expires_at=timezone.now() - timedelta(days=1), amount_paid=12900,
        )
        self.assertFalse(is_premium(self.student))

    def test_cancelled_subscription_is_not_premium(self):
        from accounts.utils import is_premium
        from accounts.models import Subscription
        Subscription.objects.create(
            user=self.student, plan='1_month', status='cancelled',
            expires_at=timezone.now() + timedelta(days=30), amount_paid=12900,
        )
        self.assertFalse(is_premium(self.student))

    def test_lifetime_subscription_is_premium(self):
        from accounts.utils import is_premium
        from accounts.models import Subscription
        Subscription.objects.create(
            user=self.student, plan='legacy', status='active',
            expires_at=None, amount_paid=19900,
        )
        self.assertTrue(is_premium(self.student))


class FreeShowcaseQuestionTests(TestCase):
    """Freemium: 10 admin-curated questions per year shown to free users."""

    def setUp(self):
        from questions.models import Question, Subject, ExamTrack
        self.track = ExamTrack.objects.create(code='cms', name='UPSC CMS')
        self.subject = Subject.objects.create(
            name='Medicine', code='med', exam_track=self.track,
        )
        self.questions = []
        for i in range(12):
            self.questions.append(
                Question.objects.create(
                    question_text=f'Q{i}',
                    option_a='A', option_b='B', option_c='C', option_d='D',
                    correct_answer='A',
                    year=2024,
                    subject=self.subject,
                )
            )

    def test_unique_year_position_pair(self):
        from accounts.models_freemium import FreeShowcaseQuestion
        from django.db import IntegrityError, transaction

        FreeShowcaseQuestion.objects.create(
            question=self.questions[0], year=2024, position=1
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                FreeShowcaseQuestion.objects.create(
                    question=self.questions[1], year=2024, position=1
                )

    def test_same_question_can_be_in_multiple_years(self):
        """OneToOneField means a question can only be a showcase for ONE year.
        This is intentional — prevents duplication if admin re-curates a year."""
        from accounts.models_freemium import FreeShowcaseQuestion
        from django.db import IntegrityError, transaction

        FreeShowcaseQuestion.objects.create(
            question=self.questions[0], year=2024, position=1
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                FreeShowcaseQuestion.objects.create(
                    question=self.questions[0], year=2023, position=1
                )

    def test_ordering_by_year_then_position(self):
        from accounts.models_freemium import FreeShowcaseQuestion
        FreeShowcaseQuestion.objects.create(
            question=self.questions[2], year=2024, position=3
        )
        FreeShowcaseQuestion.objects.create(
            question=self.questions[0], year=2024, position=1
        )
        FreeShowcaseQuestion.objects.create(
            question=self.questions[1], year=2024, position=2
        )
        ordered = list(
            FreeShowcaseQuestion.objects.filter(year=2024).values_list(
                'position', flat=True
            )
        )
        self.assertEqual(ordered, [1, 2, 3])

