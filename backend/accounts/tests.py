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

    def test_supabase_sync_promotes_admin_from_user_metadata(self):
        """Supabase sync should promote admin when admin flags are present in user_metadata."""
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
                    "role": "admin",
                    "is_admin": True,
                },
                "app_metadata": {},
            }
        )

        user.refresh_from_db()
        self.assertEqual(user.role, "admin")
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)
