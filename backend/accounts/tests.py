from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse


User = get_user_model()


class AuthApiTests(TestCase):
    def test_login_endpoint_is_disabled_for_legacy_jwt_auth(self):
        username = "compat_user"
        password = "StrongPass123!"
        user = User.objects.create_user(
            username=username,
            email="compat@example.com",
            password=password,
        )

        response = self.client.post(
            reverse("login"),
            {"username": username, "password": password},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 410)
        payload = response.json()
        self.assertIn("error", payload)
        self.assertIn("Supabase Auth", payload["error"])

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

    def test_login_rejects_case_insensitive_username_for_legacy_flow(self):
        user = User.objects.create_user(
            username="CaseUser",
            email="case@example.com",
            password="StrongPass123!",
        )

        response = self.client.post(
            reverse("login"),
            {"username": "caseuser", "password": "StrongPass123!"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 410)
        payload = response.json()
        self.assertIn("error", payload)

    def test_superuser_login_is_also_disabled(self):
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
        payload = response.json()
        self.assertIn("error", payload)
