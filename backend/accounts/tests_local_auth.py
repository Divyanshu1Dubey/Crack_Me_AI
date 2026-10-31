"""Dev-only local auth must be inert unless explicitly enabled (DEBUG only)."""
from django.contrib.auth import get_user_model
from django.http import Http404
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory

from accounts.local_auth import LocalDevJWTAuthentication, LocalLoginView, LocalRegisterView

User = get_user_model()
PASSWORD = 'Local-Dev-Passw0rd!'


class LocalAuthDisabledTests(TestCase):
    @override_settings(LOCAL_DEV_AUTH=False)
    def test_views_404_and_authenticator_inert_when_disabled(self):
        User.objects.create_user(username='u1', email='u1@local.test', password=PASSWORD)
        factory = APIRequestFactory()
        request = factory.post('/api/auth/local/login/', {'email': 'u1@local.test', 'password': PASSWORD}, format='json')
        response = LocalLoginView.as_view()(request)
        self.assertEqual(response.status_code, 404)
        bearer = factory.get('/api/questions/', HTTP_AUTHORIZATION='Bearer whatever')
        self.assertIsNone(LocalDevJWTAuthentication().authenticate(bearer))


@override_settings(LOCAL_DEV_AUTH=True)
class LocalAuthEnabledTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def _login(self, identifier, password):
        request = self.factory.post('/api/auth/local/login/', {'email': identifier, 'password': password}, format='json')
        return LocalLoginView.as_view()(request)

    def test_login_by_email_returns_working_token(self):
        user = User.objects.create_user(username='stud', email='stud@local.test', password=PASSWORD)
        response = self._login('STUD@local.test', PASSWORD)
        self.assertEqual(response.status_code, 200, response.data)
        token = response.data['access']
        request = self.factory.get('/api/auth/profile/', HTTP_AUTHORIZATION=f'Bearer {token}')
        authed_user, _ = LocalDevJWTAuthentication().authenticate(request)
        self.assertEqual(authed_user.pk, user.pk)

    def test_wrong_password_is_401(self):
        User.objects.create_user(username='stud2', email='stud2@local.test', password=PASSWORD)
        self.assertEqual(self._login('stud2@local.test', 'nope-nope-nope').status_code, 401)

    def test_register_cannot_choose_role(self):
        request = self.factory.post('/api/auth/local/register/', {
            'email': 'new@local.test', 'username': 'newbie', 'password': PASSWORD,
            'role': 'admin', 'is_superuser': True,
        }, format='json')
        response = LocalRegisterView.as_view()(request)
        self.assertEqual(response.status_code, 201, response.data)
        user = User.objects.get(email='new@local.test')
        self.assertEqual(user.role, 'student')
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_staff)
        self.assertIn('access', response.data)

    def test_register_rejects_duplicate_email(self):
        User.objects.create_user(username='dup', email='dup@local.test', password=PASSWORD)
        request = self.factory.post('/api/auth/local/register/', {
            'email': 'DUP@local.test', 'password': PASSWORD,
        }, format='json')
        self.assertEqual(LocalRegisterView.as_view()(request).status_code, 400)


class LocalAuthSettingGuardTests(TestCase):
    def test_setting_requires_debug(self):
        # The settings module derives LOCAL_DEV_AUTH from DEBUG; under the
        # test runner DEBUG is False unless explicitly enabled.
        from django.conf import settings
        if not settings.DEBUG:
            self.assertFalse(settings.LOCAL_DEV_AUTH)
