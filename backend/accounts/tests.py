from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

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
        """POST to subscribe endpoint should activate premium subscription."""
        from .models import TokenTransaction

        self.assertFalse(self.user.is_subscribed)

        response = self.client.post(reverse("subscribe"))
        self.assertEqual(response.status_code, 200)

        self.user.refresh_from_db()
        self.assertTrue(self.user.is_subscribed)

        # Verify transaction
        tx = TokenTransaction.objects.filter(user=self.user, transaction_type="purchase").first()
        self.assertIsNotNone(tx)
        self.assertEqual(float(tx.price_paid), 199.00)

        # Subscribing again should return error
        response = self.client.post(reverse("subscribe"))
        self.assertEqual(response.status_code, 400)


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

