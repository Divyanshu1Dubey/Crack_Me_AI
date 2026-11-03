"""Sign in with Google (AUTH_PROVIDER=django): real RS256 tokens against a local key; no network.

The ID tokens are signed with an RSA key made for the test and verified by
google.oauth2.id_token.verify_oauth2_token; only the certificate download
(accounts.google_identity._fetch_certs_document) is replaced, so signature,
expiry, issuer and audience checks are the library's own.
"""
import json
import re
import time
import uuid
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest import mock

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from google.auth import crypt, exceptions as google_exceptions, jwt as google_jwt
from rest_framework.test import APIClient

from accounts.models import AuthSession, UserIdentity

User = get_user_model()

CLIENT_ID = 'web-client-123.apps.googleusercontent.com'
KEY_ID = 'test-key-1'
PASSWORD = 'Native-Passw0rd!x'
GOOGLE = dict(
    AUTH_PROVIDER='django',
    GOOGLE_OAUTH_CLIENT_IDS=[CLIENT_ID],
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher', 'accounts.hashers.SupabaseBcryptPasswordHasher'],
    FRONTEND_URL='https://app.cracklabs.test',
    NATIVE_AUTH_ALLOW_SIGNUP=True,
)


def _key_and_cert():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'google-test')])
    now = datetime.now(dt_timezone.utc)
    cert = (
        x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=30))
        .sign(key, hashes.SHA256())
    )
    key_pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption(),
    ).decode()
    return key_pem, cert.public_bytes(serialization.Encoding.PEM).decode()


class _GoogleTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        key_pem, cls.cert_pem = _key_and_cert()
        cls.signer = crypt.RSASigner.from_string(key_pem, key_id=KEY_ID)

    def setUp(self):
        cache.clear()
        self.cert_fetches = 0

        def fake_fetch(url):
            self.cert_fetches += 1
            return json.dumps({KEY_ID: self.cert_pem}).encode(), 3600

        patcher = mock.patch('accounts.google_identity._fetch_certs_document', side_effect=fake_fetch)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client = APIClient()

    def credential(self, sub='google-sub-1', email='doc@gmail.com', *, aud=CLIENT_ID, iss='https://accounts.google.com',
                   exp_in=600, email_verified=True, **claims):
        now = int(time.time())
        payload = {
            'iss': iss, 'aud': aud, 'sub': sub, 'email': email, 'email_verified': email_verified,
            'iat': now, 'exp': now + exp_in, 'jti': uuid.uuid4().hex,
            'given_name': 'Asha', 'family_name': 'Rao', 'picture': 'https://lh3.googleusercontent.com/a/pic',
            **claims,
        }
        return google_jwt.encode(self.signer, payload).decode()

    def google(self, credential):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post('/api/auth/google/', {'credential': credential}, format='json')

    def assert_code(self, response, status_code, code):
        self.assertEqual((response.status_code, response.data.get('code')), (status_code, code), response.data)


def _student(username, email, *, password=PASSWORD, **fields):
    user = User.objects.create_user(username=username, email=email, password=password, **fields)
    user.email_verified_at = timezone.now()
    user.save(update_fields=['email_verified_at'])
    return user


@override_settings(**GOOGLE)
class GoogleTokenVerificationTests(_GoogleTestCase):
    def test_a_valid_token_is_accepted_once(self):
        credential = self.credential()
        self.assertEqual(self.google(credential).status_code, 201)
        self.assert_code(self.google(credential), 401, 'google_token_invalid')  # replayed
        self.assertEqual(self.cert_fetches, 1)  # certificates are cached

    def test_wrong_audience_issuer_expired_or_garbage_tokens_are_refused(self):
        for credential in (
            self.credential(aud='someone-elses-client.apps.googleusercontent.com'),
            self.credential(iss='https://evil.example.com'),
            self.credential(exp_in=-120),
            'not-a-jwt',
        ):
            self.assert_code(self.google(credential), 401, 'google_token_invalid')
        self.assertFalse(User.objects.filter(email='doc@gmail.com').exists())

    def test_a_token_signed_with_another_key_is_refused(self):
        other_key_pem, _ = _key_and_cert()
        forged = google_jwt.encode(crypt.RSASigner.from_string(other_key_pem, key_id=KEY_ID), {
            'iss': 'https://accounts.google.com', 'aud': CLIENT_ID, 'sub': 'x', 'email': 'x@gmail.com',
            'email_verified': True, 'iat': int(time.time()), 'exp': int(time.time()) + 600,
        }).decode()
        self.assert_code(self.google(forged), 401, 'google_token_invalid')

    def test_google_unreachable_is_503(self):
        cache.clear()
        with mock.patch('accounts.google_identity._fetch_certs_document',
                        side_effect=google_exceptions.TransportError('timed out')):
            self.assert_code(self.google(self.credential()), 503, 'google_unavailable')

    @override_settings(GOOGLE_OAUTH_CLIENT_IDS=[])
    def test_not_configured_is_503(self):
        self.assert_code(self.google(self.credential()), 503, 'google_not_configured')


@override_settings(**GOOGLE)
class GoogleSignInRuleTests(_GoogleTestCase):
    def test_a_known_sub_signs_in_its_own_account_whatever_the_token_email(self):
        owner = _student('owner', 'owner@example.com')
        other = _student('other', 'other@gmail.com')
        UserIdentity.objects.create(user=owner, provider='google', subject='sub-owner', source='supabase_import')
        response = self.google(self.credential(sub='sub-owner', email='other@gmail.com'))
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['user']['id'], owner.pk)
        self.assertFalse(response.data['created'])
        owner.refresh_from_db()
        self.assertEqual(owner.email, 'owner@example.com')  # the local email never changes
        self.assertEqual(AuthSession.objects.get(sid=response.data['session_id']).method, 'google')
        self.assertFalse(UserIdentity.objects.filter(user=other).exists())

    def test_a_new_email_creates_a_verified_student(self):
        response = self.google(self.credential(sub='sub-new', email='NewDoc@Gmail.com'))
        self.assertEqual(response.status_code, 201, response.data)
        user = User.objects.get(email='newdoc@gmail.com')
        self.assertEqual(user.role, 'student')
        self.assertFalse(user.is_staff or user.is_superuser)
        self.assertIsNotNone(user.email_verified_at)
        self.assertFalse(user.has_usable_password())
        self.assertTrue(user.username.startswith('learner_'))
        self.assertEqual((user.first_name, user.last_name), ('Asha', 'Rao'))
        identity = UserIdentity.objects.get(user=user)
        self.assertEqual((identity.subject, identity.source), ('sub-new', 'signup'))
        self.assertEqual(response.data['user']['auth_methods'], {'password': False, 'google': True})

    def test_an_existing_email_needs_the_emailed_link(self):
        user = _student('legacy', 'legacy@gmail.com')
        response = self.google(self.credential(sub='sub-legacy', email='legacy@gmail.com'))
        self.assert_code(response, 409, 'google_link_required')
        self.assertNotIn('access', response.data)
        self.assertFalse(UserIdentity.objects.exists())
        self.assertFalse(AuthSession.objects.exists())
        links = [t for m in mail.outbox for t in re.findall(r'/connect-google#token=(\S+)', m.body)]
        self.assertEqual(len(links), 1)
        self.assertEqual(mail.outbox[0].to, ['legacy@gmail.com'])

        confirmed = self.client.post('/api/auth/google/confirm-link/', {'token': links[0]}, format='json')
        self.assertEqual(confirmed.status_code, 200, confirmed.data)
        self.assertEqual(confirmed.data['user']['id'], user.pk)
        identity = UserIdentity.objects.get(provider='google', subject='sub-legacy')
        self.assertEqual((identity.user_id, identity.source), (user.pk, 'email_confirmed'))
        # Single-use, and Google sign-in now works directly.
        self.assert_code(self.client.post('/api/auth/google/confirm-link/', {'token': links[0]}, format='json'),
                         400, 'invalid_or_expired_link')
        self.assertEqual(self.google(self.credential(sub='sub-legacy', email='legacy@gmail.com')).status_code, 200)

    def test_the_link_stops_working_after_an_email_change(self):
        user = _student('mover', 'mover@gmail.com')
        self.google(self.credential(sub='sub-mover', email='mover@gmail.com'))
        [token] = [t for m in mail.outbox for t in re.findall(r'/connect-google#token=(\S+)', m.body)]
        User.objects.filter(pk=user.pk).update(email='moved@example.com')
        self.assert_code(self.client.post('/api/auth/google/confirm-link/', {'token': token}, format='json'),
                         400, 'invalid_or_expired_link')
        self.assertFalse(UserIdentity.objects.exists())

    def test_admin_accounts_are_never_linked_by_email(self):
        _student('chief', 'chief@gmail.com', role='admin', is_staff=True)
        self.assert_code(self.google(self.credential(sub='sub-chief', email='chief@gmail.com')), 409,
                         'account_link_required')
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(UserIdentity.objects.exists())

    def test_an_unverified_google_email_is_refused(self):
        self.assert_code(self.google(self.credential(email_verified=False)), 400, 'google_email_unverified')
        self.assertFalse(User.objects.filter(email='doc@gmail.com').exists())

    def test_blocked_accounts_are_refused(self):
        blocked = _student('blocked', 'blocked@example.com', is_active=False)
        UserIdentity.objects.create(user=blocked, provider='google', subject='sub-blocked', source='supabase_import')
        self.assert_code(self.google(self.credential(sub='sub-blocked')), 403, 'account_blocked')

    def test_an_email_shared_by_several_accounts_is_refused(self):
        _student('twin1', 'twin@gmail.com')
        _student('twin2', 'TWIN@gmail.com')
        self.assert_code(self.google(self.credential(sub='sub-twin', email='twin@gmail.com')), 409,
                         'account_link_required')


@override_settings(**GOOGLE)
class GoogleSettingsLinkTests(_GoogleTestCase):
    def signed_in(self, email):
        tokens = self.client.post('/api/auth/native/login/', {'email': email, 'password': PASSWORD}, format='json').data
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}', HTTP_X_SESSION_ID='dev_settingslink_1')
        return client, tokens

    def test_linking_needs_a_recent_sign_in(self):
        user = _student('linker', 'linker@example.com')
        client, tokens = self.signed_in('linker@example.com')
        AuthSession.objects.filter(sid=tokens['session_id']).update(created_at=timezone.now() - timedelta(hours=1))
        self.assert_code(client.post('/api/auth/google/link/', {'credential': self.credential(sub='sub-l')},
                                     format='json'), 403, 'reauthentication_required')
        client, _ = self.signed_in('linker@example.com')
        response = client.post('/api/auth/google/link/', {'credential': self.credential(sub='sub-l')}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['auth_methods'], {'password': True, 'google': True})
        self.assertEqual(UserIdentity.objects.get(subject='sub-l').user_id, user.pk)

    def test_a_google_account_of_another_user_cannot_be_linked(self):
        owner = _student('first', 'first@example.com')
        UserIdentity.objects.create(user=owner, provider='google', subject='sub-taken', source='signup')
        _student('second', 'second@example.com')
        client, _ = self.signed_in('second@example.com')
        self.assert_code(client.post('/api/auth/google/link/', {'credential': self.credential(sub='sub-taken')},
                                     format='json'), 409, 'identity_in_use')

    def test_unlinking_needs_another_way_to_sign_in(self):
        user = _student('both', 'both@example.com')
        UserIdentity.objects.create(user=user, provider='google', subject='sub-both', source='signup')
        client, _ = self.signed_in('both@example.com')
        response = client.delete('/api/auth/google/link/')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(UserIdentity.objects.filter(user=user).exists())

        google_only = User.objects.create_user(username='gonly', email='gonly@gmail.com', password=None)
        google_only.email_verified_at = timezone.now()
        google_only.save(update_fields=['email_verified_at'])
        UserIdentity.objects.create(user=google_only, provider='google', subject='sub-gonly', source='signup')
        signed = self.google(self.credential(sub='sub-gonly', email='gonly@gmail.com')).data
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {signed["access"]}', HTTP_X_SESSION_ID='dev_settingslink_2')
        self.assert_code(client.delete('/api/auth/google/link/'), 409, 'last_sign_in_method')
        self.assertTrue(UserIdentity.objects.filter(user=google_only).exists())
