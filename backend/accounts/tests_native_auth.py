"""Django-native sign-in (AUTH_PROVIDER=django): passwords, sessions, devices, verification, reset.

Hermetic: SQLite, the locmem mail backend, no network (GoTrue is never called
in django mode; tests that could reach it patch urlopen and assert it stayed
unused). Supabase mode, the code default, keeps its behaviour: every native
endpoint answers 404 there and the native authenticator is inert.
"""
import re
from datetime import datetime, timedelta
from unittest import mock

import bcrypt
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import identify_hasher
from django.core import mail
from django.core.cache import cache
from django.conf import settings
from django.core.checks import run_checks
from django.test import Client, RequestFactory, TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework.throttling import SimpleRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.hashers import SupabaseBcryptPasswordHasher, encoded_from_supabase_hash
from accounts.models import AuthSession, PendingSignup, Subscription, TokenBalance, UserDevice
from accounts.native_auth_authentication import NativeJWTAuthentication
from accounts.native_sessions import issue_session_tokens

User = get_user_model()

FAST_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher', 'accounts.hashers.SupabaseBcryptPasswordHasher']
PASSWORD = 'Native-Passw0rd!x'
NEW_PASSWORD = 'Brand-New-Passw0rd!y'
ATTACKER_PASSWORD = 'Attacker-Chosen-Pw!9'
CLOUDFLARE_EDGE = '173.245.48.10'  # inside Cloudflare's published 173.245.48.0/20
DEVICE_A = 'dev_aaaaaaaaaaaa_1'
DEVICE_B = 'dev_bbbbbbbbbbbb_2'
DEVICE_C = 'dev_cccccccccccc_3'
DEVICE_D = 'dev_dddddddddddd_4'
DEVICE_E = 'dev_eeeeeeeeeeee_5'
PROBE = '/api/auth/tokens/history/'  # authenticated and device-limited

NATIVE = dict(
    AUTH_PROVIDER='django',
    PASSWORD_HASHERS=FAST_HASHERS,
    FRONTEND_URL='https://app.cracklabs.test',
    NATIVE_AUTH_ALLOW_SIGNUP=True,
    GOOGLE_OAUTH_CLIENT_IDS=[],
)


def supabase_bcrypt(password: str, *, prefix=b'2a') -> str:
    """A GoTrue-style hash (cost 4 for speed) in the stored Django form."""
    raw = bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt(4, prefix=prefix)).decode()
    return encoded_from_supabase_hash(raw)


def make_user(username, email, *, password=PASSWORD, verified=True, **fields):
    user = User.objects.create_user(username=username, email=email, password=password, **fields)
    if verified:
        user.email_verified_at = timezone.now()
        user.save(update_fields=['email_verified_at'])
    return user


def bearer(access, device=None):
    client = APIClient()
    headers = {'HTTP_AUTHORIZATION': f'Bearer {access}'}
    if device:
        headers['HTTP_X_SESSION_ID'] = device
    client.credentials(**headers)
    return client


def mail_links(pattern):
    return [m for message in mail.outbox for m in re.findall(pattern, message.body)]


class _NativeTestCase(TestCase):
    def setUp(self):
        cache.clear()  # DRF throttle and per-email buckets
        self.client = APIClient()

    def login(self, email, password=PASSWORD, ip='10.0.0.1'):
        return self.client.post('/api/auth/native/login/', {'email': email, 'password': password},
                                format='json', REMOTE_ADDR=ip)

    def assert_code(self, response, status_code, code):
        self.assertEqual((response.status_code, response.data.get('code')), (status_code, code), response.data)


# ── Hasher ───────────────────────────────────────────────────────────────

class SupabaseBcryptHasherTests(TestCase):
    def test_2a_2b_and_2y_hashes_verify(self):
        hasher = SupabaseBcryptPasswordHasher()
        for prefix in (b'2a', b'2b'):
            encoded = supabase_bcrypt(PASSWORD, prefix=prefix)
            self.assertTrue(hasher.verify(PASSWORD, encoded))
            self.assertFalse(hasher.verify('wrong-password', encoded))
        # $2y$ (PHP / some GoTrue exports) is the same algorithm.
        raw = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt(4, prefix=b'2b')).decode()
        encoded = encoded_from_supabase_hash('$2y$' + raw[4:])
        self.assertTrue(encoded.startswith('supabase_bcrypt$$2y$'))
        self.assertTrue(hasher.verify(PASSWORD, encoded))
        self.assertTrue(hasher.must_update(encoded))

    def test_passwords_over_72_bytes_never_raise(self):
        hasher = SupabaseBcryptPasswordHasher()
        long_password = 'x' * 72 + 'tail-ignored-by-bcrypt'
        encoded = supabase_bcrypt(long_password)  # GoTrue hashed (only) the first 72 bytes
        self.assertTrue(hasher.verify(long_password, encoded))
        self.assertTrue(hasher.verify('x' * 72 + 'another tail', encoded))  # GoTrue semantics
        self.assertFalse(hasher.verify('y' * 100, encoded))
        self.assertFalse(hasher.verify('é' * 80, supabase_bcrypt(PASSWORD)))

    def test_only_bcrypt_hashes_are_imported(self):
        self.assertEqual(encoded_from_supabase_hash(''), '')
        self.assertEqual(encoded_from_supabase_hash('plain-text'), '')
        raw = bcrypt.hashpw(b'pw', bcrypt.gensalt(4)).decode()
        self.assertEqual(encoded_from_supabase_hash(raw + '\n'), 'supabase_bcrypt$' + raw)  # stripped
        self.assertEqual(encoded_from_supabase_hash(raw + 'x'), '')
        self.assertFalse(SupabaseBcryptPasswordHasher().verify(PASSWORD, 'supabase_bcrypt$not-a-hash'))

    @override_settings(AUTH_PROVIDER='django')  # the real PASSWORD_HASHERS: Argon2 first
    def test_first_sign_in_rehashes_to_argon2(self):
        cache.clear()
        user = make_user('imported', 'imported@example.com', password=None)
        User.objects.filter(pk=user.pk).update(password=supabase_bcrypt(PASSWORD))
        response = APIClient().post('/api/auth/native/login/', {'email': 'IMPORTED@example.com', 'password': PASSWORD},
                                    format='json')
        self.assertEqual(response.status_code, 200, response.data)
        user.refresh_from_db()
        self.assertEqual(identify_hasher(user.password).algorithm, 'argon2')
        self.assertTrue(user.check_password(PASSWORD))


# ── Sign-in ──────────────────────────────────────────────────────────────

@override_settings(**NATIVE)
class NativeLoginTests(_NativeTestCase):
    def test_imported_supabase_password_signs_in_with_the_token_shape_of_local_mode(self):
        user = make_user('stud', 'stud@example.com', password=None)
        User.objects.filter(pk=user.pk).update(password=supabase_bcrypt(PASSWORD))
        response = self.login('Stud@Example.com')
        self.assertEqual(response.status_code, 200, response.data)
        for key in ('access', 'refresh', 'session_id', 'user'):
            self.assertIn(key, response.data)
        self.assertEqual(response.data['user']['id'], user.pk)
        self.assertEqual(response.data['user']['auth_methods'], {'password': True, 'google': False})
        self.assertTrue(response.data['user']['email_verified'])
        session = AuthSession.objects.get(sid=response.data['session_id'])
        self.assertEqual((session.user_id, session.method), (user.pk, 'password'))
        user.refresh_from_db()
        self.assertIsNotNone(user.last_login)
        self.assertFalse(user.password.startswith('supabase_bcrypt$'))  # re-hashed with the preferred hasher

    def test_long_password_over_72_bytes(self):
        long_password = 'L0ng-' * 20  # 100 bytes
        user = make_user('longpw', 'long@example.com', password=None)
        User.objects.filter(pk=user.pk).update(password=supabase_bcrypt(long_password))
        self.assert_code(self.login('long@example.com', 'Z' * 100), 401, 'invalid_credentials')
        self.assertEqual(self.login('long@example.com', long_password).status_code, 200)

    def test_wrong_password_and_unknown_email_get_the_same_answer(self):
        make_user('known', 'known@example.com')
        wrong = self.login('known@example.com', 'not-the-password')
        unknown = self.login('nobody@example.com', 'not-the-password')
        self.assert_code(wrong, 401, 'invalid_credentials')
        self.assert_code(unknown, 401, 'invalid_credentials')
        self.assertEqual(wrong.data, unknown.data)
        self.assertFalse(AuthSession.objects.exists())

    def test_a_username_is_not_accepted(self):
        make_user('handle_only', 'handle@example.com')
        self.assert_code(self.login('handle_only'), 400, 'invalid_request')

    def test_an_email_shared_by_two_accounts_is_refused(self):
        make_user('dup1', 'dup@example.com')
        make_user('dup2', 'DUP@example.com')
        self.assert_code(self.login('dup@example.com'), 401, 'invalid_credentials')

    def test_unverified_email_cannot_sign_in_and_gets_a_link(self):
        make_user('legacy', 'legacy@example.com', verified=False)
        with self.captureOnCommitCallbacks(execute=True):
            self.assert_code(self.login('legacy@example.com', 'wrong-password'), 401, 'invalid_credentials')
        self.assertEqual(len(mail.outbox), 0)  # nothing without the right password
        with self.captureOnCommitCallbacks(execute=True):
            self.assert_code(self.login('legacy@example.com'), 401, 'email_not_confirmed')
        self.assertEqual(len(mail_links(r'/verify-email#uid=\S+&token=\S+')), 1)
        self.assertFalse(AuthSession.objects.exists())

    def test_blocked_user_is_told_only_with_the_right_password(self):
        make_user('blocked', 'blocked@example.com', is_active=False)
        self.assert_code(self.login('blocked@example.com', 'wrong-password'), 401, 'invalid_credentials')
        self.assert_code(self.login('blocked@example.com'), 403, 'account_blocked')
        self.assertFalse(AuthSession.objects.exists())

    def test_every_failed_sign_in_costs_one_password_hash(self):
        """A blocked account used to cost two checks (ModelBackend, then the 'blocked?' check): the
        extra time told which emails belong to blocked accounts."""
        from django.contrib.auth.hashers import MD5PasswordHasher

        make_user('active', 'active@example.com')
        make_user('blocked', 'blocked@example.com', is_active=False)
        costs = {}
        for email in ('active@example.com', 'blocked@example.com', 'nobody@example.com'):
            with mock.patch.object(MD5PasswordHasher, 'encode', autospec=True,
                                   side_effect=MD5PasswordHasher.encode) as encode:
                self.assert_code(self.login(email, 'wrong-password'), 401, 'invalid_credentials')
            costs[email] = encode.call_count
        self.assertEqual(costs, {'active@example.com': 1, 'blocked@example.com': 1, 'nobody@example.com': 1})

    def test_axes_counts_failures_on_blocked_accounts(self):
        make_user('blocked', 'blocked@example.com', is_active=False)
        for _ in range(4):
            self.assert_code(self.login('blocked@example.com', 'guess', ip='10.0.0.67'), 401, 'invalid_credentials')
        self.assert_code(self.login('blocked@example.com', 'guess', ip='10.0.0.67'), 429, 'too_many_attempts')
        self.assert_code(self.login('blocked@example.com', ip='10.0.0.67'), 429, 'too_many_attempts')
        self.assert_code(self.login('blocked@example.com', ip='10.0.0.8'), 403, 'account_blocked')

    def test_the_verification_mail_after_a_correct_password_says_so(self):
        make_user('legacy2', 'legacy2@example.com', verified=False)
        with self.captureOnCommitCallbacks(execute=True):
            self.assert_code(self.login('legacy2@example.com'), 401, 'email_not_confirmed')
        [message] = mail.outbox
        self.assertIn('correct password', message.body)
        self.assertIn('https://app.cracklabs.test/forgot-password', message.body)
        self.assertNotIn('you can ignore this email', message.body)

    def test_axes_locks_one_account_per_client_ip(self):
        make_user('target', 'target@example.com')
        for _ in range(4):
            self.assert_code(self.login('target@example.com', 'guess', ip='10.0.0.66'), 401, 'invalid_credentials')
        # The fifth failure (AXES_FAILURE_LIMIT) locks this (account, IP) ...
        self.assert_code(self.login('target@example.com', 'guess', ip='10.0.0.66'), 429, 'too_many_attempts')
        # ... even for the right password.
        self.assert_code(self.login('target@example.com', ip='10.0.0.66'), 429, 'too_many_attempts')
        # The owner elsewhere is not locked out.
        self.assertEqual(self.login('target@example.com', ip='10.0.0.7').status_code, 200)

    def test_drf_rate_limit_answers_429_with_code_and_retry_after(self):
        # Regression: Throttled(wait=..., detail=<dict>) raised TypeError inside DRF (HTTP 500).
        with mock.patch.dict(SimpleRateThrottle.THROTTLE_RATES, {'native_login': '2/min'}):
            for i in range(2):
                self.assert_code(self.login(f'nobody{i}@example.com', 'guess', ip='10.2.0.1'), 401, 'invalid_credentials')
            limited = self.login('nobody9@example.com', 'guess', ip='10.2.0.1')
            self.assert_code(limited, 429, 'too_many_attempts')
            self.assertGreaterEqual(int(limited['Retry-After']), 1)
            # Another client IP has its own bucket.
            self.assert_code(self.login('nobody9@example.com', 'guess', ip='10.2.0.2'), 401, 'invalid_credentials')
        with mock.patch.dict(SimpleRateThrottle.THROTTLE_RATES, {'native_refresh': '1/min'}):
            self.client.post('/api/auth/native/refresh/', {'refresh': 'x'}, format='json', REMOTE_ADDR='10.2.0.3')
            refused = self.client.post('/api/auth/native/refresh/', {'refresh': 'x'}, format='json', REMOTE_ADDR='10.2.0.3')
            self.assertIn(refused.status_code, (401, 429), refused.data)  # never 500

    def test_per_email_limit_counts_failures_from_every_ip(self):
        make_user('spray', 'spray@example.com')
        with mock.patch.dict(SimpleRateThrottle.THROTTLE_RATES, {'native_login_email': '3/hour'}):
            for i in range(3):
                self.login('spray@example.com', 'guess', ip=f'10.1.0.{i + 1}')
            self.assert_code(self.login('spray@example.com', ip='10.1.0.99'), 429, 'too_many_attempts')
            # Successes do not count: another address is unaffected.
            make_user('other', 'other@example.com')
            self.assertEqual(self.login('other@example.com', ip='10.1.0.99').status_code, 200)

    def test_no_supabase_call_in_django_mode(self):
        make_user('nocall', 'nocall@example.com')
        with mock.patch('accounts.supabase_rest_auth.request.urlopen') as urlopen:
            access = self.login('nocall@example.com').data['access']
            self.assertEqual(bearer(access, DEVICE_A).get('/api/auth/profile/').status_code, 200)
            # A Supabase-shaped token is simply invalid here.
            self.assertEqual(bearer('eyJhbGciOiJFUzI1NiJ9.eyJzdWIiOiJ4In0.sig').get(PROBE).status_code, 401)
        urlopen.assert_not_called()


# ── Sessions ─────────────────────────────────────────────────────────────

@override_settings(**NATIVE)
class NativeSessionTests(_NativeTestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user('sess', 'sess@example.com')

    def refresh(self, token):
        return self.client.post('/api/auth/native/refresh/', {'refresh': token}, format='json')

    def test_refresh_rotates_and_reuse_revokes_the_session(self):
        first = self.login('sess@example.com').data
        rotated = self.refresh(first['refresh'])
        self.assertEqual(rotated.status_code, 200, rotated.data)
        self.assertNotEqual(rotated.data['refresh'], first['refresh'])
        self.assertEqual(rotated.data['session_id'], first['session_id'])
        self.assertEqual(bearer(rotated.data['access'], DEVICE_A).get(PROBE).status_code, 200)

        # Another tab -- or this browser, whose rotation answer was lost -- presents the
        # just-rotated token: tokens EQUIVALENT to the current ones (same refresh jti).
        racing = self.refresh(first['refresh'])
        self.assertEqual(racing.status_code, 200, racing.data)
        session = AuthSession.objects.get(sid=first['session_id'])
        self.assertEqual(RefreshToken(racing.data['refresh'])['jti'], session.refresh_jti)
        self.assertEqual(RefreshToken(rotated.data['refresh'])['jti'], session.refresh_jti)
        self.assertEqual(bearer(racing.data['access'], DEVICE_A).get(PROBE).status_code, 200)

        # Later reuse of a rotated token: the whole session is revoked.
        AuthSession.objects.filter(sid=first['session_id']).update(rotated_at=timezone.now() - timedelta(minutes=5))
        self.assert_code(self.refresh(first['refresh']), 401, 'session_revoked')
        self.assertEqual(AuthSession.objects.get(sid=first['session_id']).revoked_reason, 'refresh_reuse')
        self.assert_code(self.refresh(rotated.data['refresh']), 401, 'session_revoked')
        self.assert_code(bearer(rotated.data['access'], DEVICE_A).get(PROBE), 401, 'session_revoked')

    def test_a_lost_rotation_answer_does_not_end_the_session(self):
        """The browser kept the old refresh token (the rotating answer never arrived): within the
        reuse window it gets the equivalent of the current token, and its next refresh rotates normally."""
        first = self.login('sess@example.com').data
        self.assertEqual(self.refresh(first['refresh']).status_code, 200)  # answer lost on the way
        retried = self.refresh(first['refresh'])                            # the browser retries with the old one
        self.assertEqual(retried.status_code, 200, retried.data)
        later = self.refresh(retried.data['refresh'])                       # 15 minutes later
        self.assertEqual(later.status_code, 200, later.data)
        self.assertIsNone(AuthSession.objects.get(sid=first['session_id']).revoked_at)
        self.assertEqual(bearer(later.data['access'], DEVICE_A).get(PROBE).status_code, 200)

    def test_logout_revokes_the_session(self):
        tokens = self.login('sess@example.com').data
        self.assertEqual(
            self.client.post('/api/auth/native/logout/', {'refresh': tokens['refresh']}, format='json').status_code, 200,
        )
        self.assert_code(self.refresh(tokens['refresh']), 401, 'session_revoked')
        self.assert_code(bearer(tokens['access'], DEVICE_A).get(PROBE), 401, 'session_revoked')
        # Unknown / garbage tokens: still a plain 200.
        self.assertEqual(self.client.post('/api/auth/native/logout/', {'refresh': 'junk'}, format='json').status_code, 200)

    def test_tokens_without_a_native_session_are_refused(self):
        plain = RefreshToken.for_user(self.user)  # no session_id claim
        self.assert_code(bearer(str(plain.access_token)).get(PROBE), 401, 'token_not_valid')
        self.assert_code(self.refresh(str(plain)), 401, 'token_not_valid')
        tokens = self.login('sess@example.com').data
        self.assertEqual(bearer(tokens['refresh']).get(PROBE).status_code, 401)  # a refresh token is no bearer

    def test_an_expired_session_ends(self):
        tokens = self.login('sess@example.com').data
        AuthSession.objects.filter(sid=tokens['session_id']).update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assert_code(bearer(tokens['access'], DEVICE_A).get(PROBE), 401, 'session_revoked')
        self.assert_code(self.refresh(tokens['refresh']), 401, 'session_revoked')

    def test_password_change_revokes_the_other_sessions(self):
        mine = self.login('sess@example.com').data
        other = self.login('sess@example.com').data
        me = bearer(mine['access'], DEVICE_A)
        self.assert_code(
            me.post('/api/auth/native/password/', {'current_password': 'wrong', 'new_password': NEW_PASSWORD},
                    format='json'),
            400, 'invalid_credentials',
        )
        response = me.post('/api/auth/native/password/', {'current_password': PASSWORD, 'new_password': NEW_PASSWORD},
                           format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['revoked_sessions'], 1)
        self.assert_code(bearer(other['access'], DEVICE_B).get(PROBE), 401, 'session_revoked')
        self.assertEqual(me.get(PROBE).status_code, 200)
        self.assert_code(self.login('sess@example.com'), 401, 'invalid_credentials')
        self.assertEqual(self.login('sess@example.com', NEW_PASSWORD).status_code, 200)

    def test_blocking_revokes_every_session(self):
        tokens = self.login('sess@example.com').data
        admin = User.objects.create_user(username='ops', email='ops@example.com', password=None, role='admin',
                                         is_staff=True)
        ops = APIClient()
        ops.force_authenticate(admin)
        self.assertEqual(
            ops.patch(f'/api/auth/admin/users/{self.user.pk}/block/', {'blocked': True}, format='json').status_code, 200,
        )
        self.assertEqual(AuthSession.objects.get(sid=tokens['session_id']).revoked_reason, 'blocked')
        self.assertEqual(self.refresh(tokens['refresh']).status_code, 401)
        self.assert_code(bearer(tokens['access'], DEVICE_A).get(PROBE), 401, 'account_blocked')


# ── Devices ──────────────────────────────────────────────────────────────

@override_settings(**NATIVE)
class NativeDeviceLimitTests(_NativeTestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user('devices', 'devices@example.com')

    def device(self, device_id):
        tokens = self.login('devices@example.com').data
        return bearer(tokens['access'], device_id), tokens

    def test_two_devices_without_a_plan(self):
        for device_id in (DEVICE_A, DEVICE_B):
            client, _ = self.device(device_id)
            self.assertEqual(client.get(PROBE).status_code, 200)
        third, _ = self.device(DEVICE_C)
        self.assert_code(third.get(PROBE), 401, 'device_limit_reached')
        # The profile (Settings) stays reachable so a device can be freed.
        self.assertEqual(third.get('/api/auth/profile/').status_code, 200)

    def test_four_devices_with_a_plan(self):
        now = timezone.now()
        Subscription.objects.create(user=self.user, plan='1_year', plan_display_name='1 Year', amount_paid=0,
                                    status='active', starts_at=now, expires_at=now + timedelta(days=365))
        for device_id in (DEVICE_A, DEVICE_B, DEVICE_C, DEVICE_D):
            client, _ = self.device(device_id)
            self.assertEqual(client.get(PROBE).status_code, 200)
        fifth, _ = self.device(DEVICE_E)
        self.assert_code(fifth.get(PROBE), 401, 'device_limit_reached')

    def test_signing_in_again_on_a_browser_keeps_one_slot(self):
        first, first_tokens = self.device(DEVICE_A)
        self.assertEqual(first.get(PROBE).status_code, 200)
        again, _ = self.device(DEVICE_A)
        self.assertEqual(again.get(PROBE).status_code, 200)
        self.assertEqual(UserDevice.objects.filter(user=self.user, is_active=True).count(), 1)
        self.assert_code(first.get(PROBE), 401, 'device_inactive')  # the replaced session
        self.assertEqual(AuthSession.objects.get(sid=first_tokens['session_id']).revoked_reason, 'device_logout')

    def test_a_logged_out_device_loses_its_session_and_refresh(self):
        phone, phone_tokens = self.device(DEVICE_A)
        laptop, _ = self.device(DEVICE_B)
        self.assertEqual(phone.get(PROBE).status_code, 200)
        self.assertEqual(laptop.get(PROBE).status_code, 200)
        device = UserDevice.objects.get(user=self.user, device_fingerprint=DEVICE_A)
        self.assertEqual(laptop.post('/api/auth/devices/logout/', {'device_id': device.pk}, format='json').status_code,
                         200)
        self.assertEqual(AuthSession.objects.get(sid=phone_tokens['session_id']).revoked_reason, 'device_logout')
        self.assert_code(phone.get(PROBE), 401, 'device_inactive')
        refresh = self.client.post('/api/auth/native/refresh/', {'refresh': phone_tokens['refresh']}, format='json')
        self.assert_code(refresh, 401, 'device_inactive')

    def test_an_admin_force_logout_ends_the_native_session(self):
        phone, phone_tokens = self.device(DEVICE_A)
        self.assertEqual(phone.get(PROBE).status_code, 200)
        device = UserDevice.objects.get(user=self.user, device_fingerprint=DEVICE_A)
        ops = APIClient()
        ops.force_authenticate(User.objects.create_user(username='ops2', email='ops2@example.com', password=None,
                                                        role='admin', is_staff=True))
        self.assertEqual(ops.post(f'/api/auth/admin/users/{self.user.pk}/devices/', {'device_id': device.pk},
                                  format='json').status_code, 200)
        self.assertEqual(AuthSession.objects.get(sid=phone_tokens['session_id']).revoked_reason, 'device_logout')
        self.assert_code(phone.get(PROBE), 401, 'device_inactive')

    def _old_device(self, device_id, days_ago):
        row = UserDevice.objects.create(user=self.user, device_fingerprint=device_id, device_name='old',
                                        is_active=True, session_id=None)
        UserDevice.objects.filter(pk=row.pk).update(last_login=timezone.now() - timedelta(days=days_ago))

    def test_devices_unseen_for_30_days_do_not_block_a_returning_browser(self):
        # After the outage every device row was older than 30 days; the browser in use (its own row
        # the oldest of three) got device_limit_reached on every page although no slot was in use.
        self._old_device(DEVICE_A, 40)
        self._old_device(DEVICE_B, 35)
        self._old_device(DEVICE_C, 34)
        client, _ = self.device(DEVICE_A)
        self.assertEqual(client.get(PROBE).status_code, 200)

    def test_recently_used_devices_still_hold_their_slots(self):
        self._old_device(DEVICE_A, 40)
        self._old_device(DEVICE_B, 1)
        self._old_device(DEVICE_C, 1)
        client, _ = self.device(DEVICE_A)
        self.assert_code(client.get(PROBE), 401, 'device_limit_reached')

    def test_admins_are_exempt(self):
        make_user('boss', 'boss@example.com', role='admin', is_staff=True)
        for device_id in (DEVICE_A, DEVICE_B, DEVICE_C):
            tokens = self.login('boss@example.com').data
            self.assertEqual(bearer(tokens['access'], device_id).get(PROBE).status_code, 200)


# ── Sign-up and email verification ───────────────────────────────────────

@override_settings(**NATIVE)
class NativeRegisterTests(_NativeTestCase):
    def register(self, client=None, **data):
        body = {'email': 'newbie@example.com', 'password': PASSWORD, 'username': 'newbie_doc', **data}
        with self.captureOnCommitCallbacks(execute=True):
            return (client or self.client).post('/api/auth/native/register/', body, format='json')

    def verify(self, client=None, **data):
        with self.captureOnCommitCallbacks(execute=True):
            return (client or self.client).post('/api/auth/native/verify-email/', data, format='json')

    def test_no_account_exists_before_the_link_is_opened(self):
        users_before = User.objects.count()
        response = self.register()
        self.assertEqual(response.status_code, 202, response.data)
        self.assertTrue(response.data['needs_email_confirmation'])
        self.assertEqual(User.objects.count(), users_before)
        pending = PendingSignup.objects.get(email='newbie@example.com')
        self.assertNotIn(PASSWORD, pending.password)
        [token] = mail_links(r'/verify-email#token=(\S+)')
        self.assertNotEqual(pending.token_hash, token)  # only a digest is stored

        # Opening the link needs the password chosen at sign-up; a refusal consumes nothing.
        self.assert_code(self.verify(token=token), 400, 'password_required')
        self.assert_code(self.verify(token=token, password='not-the-password'), 400, 'password_mismatch')
        self.assertFalse(User.objects.filter(email='newbie@example.com').exists())
        created = self.verify(token=token, password=PASSWORD)
        self.assertEqual(created.status_code, 201, created.data)
        user = User.objects.get(email='newbie@example.com')
        self.assertEqual(created.data['user']['id'], user.pk)
        self.assertEqual(user.role, 'student')
        self.assertEqual(user.username, 'newbie_doc')
        self.assertIsNotNone(user.email_verified_at)
        self.assertTrue(user.check_password(PASSWORD))
        self.assertTrue(TokenBalance.objects.filter(user=user).exists())
        self.assertFalse(PendingSignup.objects.exists())
        self.assertTrue(any('Welcome' in m.subject for m in mail.outbox))
        # Single-use.
        self.assert_code(self.verify(token=token, password=PASSWORD), 400, 'invalid_or_expired_link')
        self.assertEqual(self.login('newbie@example.com').status_code, 200)

    def test_a_second_sign_up_never_replaces_the_first_ones_password(self):
        """Owner first, then someone else with the same address: whichever mail the owner opens, the
        account gets the owner's password (verifier probe: the second sign-up used to overwrite it)."""
        owner, other = APIClient(), APIClient()
        self.assertEqual(self.register(client=owner).status_code, 202)
        self.assertEqual(self.register(client=other, password=ATTACKER_PASSWORD).status_code, 202)
        self.assertEqual(PendingSignup.objects.filter(email='newbie@example.com').count(), 2)
        first, newest = mail_links(r'/verify-email#token=(\S+)')
        created = self.verify(client=owner, token=newest, password=PASSWORD)  # the owner opens the newest mail
        self.assertEqual(created.status_code, 201, created.data)
        user = User.objects.get(email='newbie@example.com')
        self.assertTrue(user.check_password(PASSWORD))
        self.assertFalse(user.check_password(ATTACKER_PASSWORD))
        self.assertFalse(PendingSignup.objects.exists())  # every open sign-up of the address is gone
        self.assert_code(self.verify(token=first, password=PASSWORD), 400, 'invalid_or_expired_link')

    def test_someone_elses_sign_up_cannot_become_the_owners_account(self):
        """Someone else first (pre-hijack), then the owner: opening the stranger's mail creates nothing
        without the stranger's password, and the owner's own sign-up still works from either mail."""
        stranger, owner = APIClient(), APIClient()
        self.register(client=stranger, password=ATTACKER_PASSWORD)
        [strangers_link] = mail_links(r'/verify-email#token=(\S+)')
        self.assert_code(self.verify(client=owner, token=strangers_link, password=PASSWORD), 400, 'password_mismatch')
        self.assertFalse(User.objects.filter(email='newbie@example.com').exists())
        self.register(client=owner)  # the owner signs up after all
        created = self.verify(client=owner, token=strangers_link, password=PASSWORD)
        self.assertEqual(created.status_code, 201, created.data)
        user = User.objects.get(email='newbie@example.com')
        self.assertTrue(user.check_password(PASSWORD))
        self.assertFalse(user.check_password(ATTACKER_PASSWORD))

    def test_open_sign_ups_per_address_are_capped(self):
        from accounts.native_auth import MAX_PENDING_SIGNUPS_PER_EMAIL

        with mock.patch.dict(SimpleRateThrottle.THROTTLE_RATES, {'native_register_email': '100/hour',
                                                                 'native_register': '100/hour'}):
            for i in range(MAX_PENDING_SIGNUPS_PER_EMAIL + 2):
                self.assertEqual(self.register(password=f'{PASSWORD}-{i}').status_code, 202)
        self.assertEqual(PendingSignup.objects.filter(email='newbie@example.com').count(),
                         MAX_PENDING_SIGNUPS_PER_EMAIL)
        newest = mail_links(r'/verify-email#token=(\S+)')[-1]
        self.assert_code(self.verify(token=newest, password=f'{PASSWORD}-0'), 400, 'password_mismatch')  # evicted
        last = f'{PASSWORD}-{MAX_PENDING_SIGNUPS_PER_EMAIL + 1}'
        self.assertEqual(self.verify(token=newest, password=last).status_code, 201)

    def test_an_existing_address_gets_the_same_answer_and_no_second_account(self):
        make_user('already', 'Already@Example.com')
        new_address = self.register(email='fresh@example.com').data
        taken = self.register(email='already@example.com')
        self.assertEqual(taken.status_code, 202)
        self.assertEqual(taken.data, new_address)
        self.assertFalse(PendingSignup.objects.filter(email='already@example.com').exists())
        self.assertEqual(User.objects.filter(email__iexact='already@example.com').count(), 1)
        self.assertTrue(any('already have' in m.subject for m in mail.outbox))

    def test_the_link_expires(self):
        self.register()
        [token] = mail_links(r'/verify-email#token=(\S+)')
        PendingSignup.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assert_code(self.verify(token=token, password=PASSWORD), 400, 'invalid_or_expired_link')
        self.assertFalse(User.objects.filter(email='newbie@example.com').exists())

    def test_a_weak_password_is_refused(self):
        self.assert_code(self.register(password='123'), 400, 'invalid_password')
        self.assertFalse(PendingSignup.objects.exists())

    def test_the_chosen_username_never_shows_the_email(self):
        self.register(username='newbie')  # the email's local part
        [token] = mail_links(r'/verify-email#token=(\S+)')
        self.assertEqual(self.verify(token=token, password=PASSWORD).status_code, 201)
        self.assertTrue(User.objects.get(email='newbie@example.com').username.startswith('learner_'))

    @override_settings(NATIVE_AUTH_ALLOW_SIGNUP=False)
    def test_sign_up_can_be_closed(self):
        self.assert_code(self.register(), 403, 'signup_disabled')

    def test_resend_verification_replaces_the_link(self):
        self.register()
        [old] = mail_links(r'/verify-email#token=(\S+)')
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/auth/native/resend-verification/', {'email': 'newbie@example.com'},
                                        format='json')
        self.assertEqual(response.status_code, 202)
        new = mail_links(r'/verify-email#token=(\S+)')[-1]
        self.assertNotEqual(old, new)
        self.assert_code(self.verify(token=old, password=PASSWORD), 400, 'invalid_or_expired_link')
        self.assertEqual(self.verify(token=new, password=PASSWORD).status_code, 201)
        unknown = self.client.post('/api/auth/native/resend-verification/', {'email': 'ghost@example.com'},
                                   format='json')
        self.assertEqual((unknown.status_code, unknown.data), (202, response.data))

    def test_existing_account_link_is_single_use_and_expires(self):
        user = make_user('oldtimer', 'oldtimer@example.com', verified=False)
        with self.captureOnCommitCallbacks(execute=True):
            self.login('oldtimer@example.com')
        [(uid, token)] = mail_links(r'/verify-email#uid=([^&\s]+)&token=(\S+)')
        response = self.verify(uid=uid, token=token)
        self.assertEqual(response.status_code, 200, response.data)
        user.refresh_from_db()
        self.assertIsNotNone(user.email_verified_at)
        self.assert_code(self.verify(uid=uid, token=token), 400, 'invalid_or_expired_link')

        stale = make_user('stale', 'stale@example.com', verified=False)
        from accounts.native_auth import email_verification_token_generator as generator
        with mock.patch.object(type(generator), '_now', return_value=datetime.now() - timedelta(days=3)):
            old_token = generator.make_token(stale)
        from accounts.native_auth import _uid
        self.assert_code(self.verify(uid=_uid(stale), token=old_token), 400, 'invalid_or_expired_link')


# ── Password reset ───────────────────────────────────────────────────────

@override_settings(**NATIVE)
class NativePasswordResetTests(_NativeTestCase):
    def request_reset(self, email):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post('/api/auth/password-reset/', {'email': email}, format='json')

    def confirm(self, uid, token, password=NEW_PASSWORD):
        return self.client.post('/api/auth/password-reset/confirm/',
                                {'uid': uid, 'token': token, 'new_password': password}, format='json')

    def test_same_answer_for_any_address_and_the_link_is_in_the_fragment(self):
        make_user('resetme', 'resetme@example.com', verified=False)
        unknown = self.request_reset('ghost@example.com')
        self.assertEqual(unknown.status_code, 202)
        self.assertEqual(len(mail.outbox), 0)
        known = self.request_reset('RESETME@example.com')
        self.assertEqual((known.status_code, known.data), (202, unknown.data))
        self.assertEqual(len(mail_links(r'https://app\.cracklabs\.test/reset-password#uid=[^&\s]+&token=\S+')), 1)

    def test_confirm_sets_the_password_verifies_the_email_and_revokes_sessions(self):
        user = make_user('resetme', 'resetme@example.com', verified=False)
        old_session = issue_session_tokens(user, None, 'password')
        self.request_reset('resetme@example.com')
        [(uid, token)] = mail_links(r'/reset-password#uid=([^&\s]+)&token=(\S+)')

        self.assert_code(self.confirm(uid, token, password='123'), 400, 'invalid_password')  # validators apply
        response = self.confirm(uid, token)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data['password_reset'])
        self.assertIn('access', response.data)
        user.refresh_from_db()
        self.assertIsNotNone(user.email_verified_at)
        self.assertEqual(AuthSession.objects.get(sid=old_session['session_id']).revoked_reason, 'password_reset')
        self.assert_code(self.confirm(uid, token), 400, 'invalid_or_expired_link')  # single-use
        self.assert_code(self.login('resetme@example.com'), 401, 'invalid_credentials')
        self.assertEqual(self.login('resetme@example.com', NEW_PASSWORD).status_code, 200)

    def test_the_link_expires(self):
        make_user('late', 'late@example.com')
        self.request_reset('late@example.com')
        [(uid, token)] = mail_links(r'/reset-password#uid=([^&\s]+)&token=(\S+)')
        later = datetime.now() + timedelta(hours=2)  # the generator works on naive local time
        with mock.patch('django.contrib.auth.tokens.PasswordResetTokenGenerator._now', return_value=later):
            self.assert_code(self.confirm(uid, token), 400, 'invalid_or_expired_link')

    def test_blocked_accounts_get_no_link(self):
        make_user('blocked', 'blocked@example.com', is_active=False)
        self.assertEqual(self.request_reset('blocked@example.com').status_code, 202)
        self.assertEqual(len(mail.outbox), 0)

    def test_per_address_limit(self):
        make_user('flood', 'flood@example.com')
        with mock.patch.dict(SimpleRateThrottle.THROTTLE_RATES, {'password_reset_email': '2/hour'}):
            for _ in range(2):
                self.assertEqual(self.request_reset('flood@example.com').status_code, 202)
            self.assert_code(self.request_reset('flood@example.com'), 429, None)
        self.assertEqual(len(mail.outbox), 2)


# ── Rate limits, client address and lockouts ─────────────────────────────

@override_settings(**NATIVE)
class NativeRateLimitTests(_NativeTestCase):
    """Every throttled native view answers 429 too_many_attempts (never 500), per the documented key."""

    def post(self, path, data, ip='10.3.0.1'):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(path, data, format='json', REMOTE_ADDR=ip)

    def assert_limited(self, path, data, rates, *, other_ip_allowed=True, code='too_many_attempts'):
        with mock.patch.dict(SimpleRateThrottle.THROTTLE_RATES, rates):
            self.assertNotEqual(self.post(path, data).status_code, 429)
            limited = self.post(path, data)
            self.assertEqual(limited.status_code, 429, getattr(limited, 'data', limited.content[:200]))
            if code:
                self.assert_code(limited, 429, code)
            self.assertGreaterEqual(int(limited['Retry-After']), 1)
            if other_ip_allowed:
                self.assertNotEqual(self.post(path, data, ip='10.3.0.2').status_code, 429)

    def test_register_per_ip_and_per_email(self):
        self.assert_limited('/api/auth/native/register/', {'email': 'a@example.com', 'password': PASSWORD},
                            {'native_register': '1/hour'})
        cache.clear()
        self.assert_limited('/api/auth/native/register/', {'email': 'b@example.com', 'password': PASSWORD},
                            {'native_register_email': '1/hour'}, other_ip_allowed=False)

    def test_resend_verification_per_ip_and_per_email(self):
        self.assert_limited('/api/auth/native/resend-verification/', {'email': 'a@example.com'},
                            {'native_verify': '1/hour'})
        cache.clear()
        self.assert_limited('/api/auth/native/resend-verification/', {'email': 'a@example.com'},
                            {'native_verify_email': '1/hour'}, other_ip_allowed=False)

    def test_verify_email_per_link(self):
        link = {'token': 'x' * 43, 'password': PASSWORD}
        self.assert_limited('/api/auth/native/verify-email/', link, {'native_verify_link': '1/hour'},
                            other_ip_allowed=False)
        # Another link (another student behind the same NAT address) has its own budget.
        with mock.patch.dict(SimpleRateThrottle.THROTTLE_RATES, {'native_verify_link': '1/hour'}):
            self.assert_code(self.post('/api/auth/native/verify-email/', {**link, 'token': 'y' * 43}),
                             400, 'invalid_or_expired_link')

    @override_settings(GOOGLE_OAUTH_CLIENT_IDS=['web.apps.googleusercontent.com'])
    def test_google_sign_in_and_confirm_link(self):
        from google.auth import exceptions as google_exceptions

        # Hermetic: Google's certificates are never fetched (503 google_unavailable instead).
        with mock.patch('accounts.google_identity._fetch_certs_document',
                        side_effect=google_exceptions.TransportError('no network in tests')):
            self.assert_limited('/api/auth/google/', {'credential': 'not-a-jwt'}, {'google_signin': '1/min'})
        cache.clear()
        self.assert_limited('/api/auth/google/confirm-link/', {'token': 'not-a-link'}, {'google_signin': '1/min'})

    def test_password_reset_per_ip(self):
        # accounts.views keeps DRF's throttled body there (no code), as in supabase mode.
        self.assert_limited('/api/auth/password-reset/', {'email': 'a@example.com'}, {'password_reset': '1/min'},
                            code=None)


@override_settings(**NATIVE)
class NativeClientAddressTests(_NativeTestCase):
    """Per-IP limits and lockouts key on crack_cms.client_ip: forged forwarding headers never count."""

    def attempt(self, **meta):
        return self.client.post('/api/auth/native/login/', {'email': 'a@example.com', 'password': 'x'},
                                format='json', **meta)

    @override_settings(TRUSTED_CLIENT_IP_HEADER='CF-Connecting-IP', TRUSTED_CLIENT_IP_HEADER_FROM='cloudflare')
    def test_documented_header_without_num_proxies_cannot_be_steered(self):
        """Verifier probe: TRUSTED_CLIENT_IP_HEADER=CF-Connecting-IP and no NUM_PROXIES let every
        request with a new forged X-Forwarded-For / CF-Connecting-IP into a new bucket. With the
        (opt-in) Cloudflare restriction the forged headers no longer count."""
        with override_settings(REST_FRAMEWORK={**settings.REST_FRAMEWORK, 'NUM_PROXIES': None}), \
                mock.patch.dict(SimpleRateThrottle.THROTTLE_RATES, {'native_login': '1/min'}):
            statuses = [
                self.attempt(REMOTE_ADDR='10.9.9.9', HTTP_X_FORWARDED_FOR=forged, HTTP_CF_CONNECTING_IP=forged)
                .status_code
                for forged in ('198.51.100.1', '198.51.100.2', '198.51.100.3')
            ]
        self.assertEqual(statuses, [401, 429, 429])

    @override_settings(TRUSTED_CLIENT_IP_HEADER='CF-Connecting-IP', TRUSTED_CLIENT_IP_HEADER_FROM='cloudflare')
    def test_behind_railway_and_cloudflare_each_visitor_has_a_bucket(self):
        railway_proxy = '100.64.0.2'
        with override_settings(REST_FRAMEWORK={**settings.REST_FRAMEWORK, 'NUM_PROXIES': 1}), \
                mock.patch.dict(SimpleRateThrottle.THROTTLE_RATES, {'native_login': '1/min'}):
            # Through Cloudflare: the hop Railway appended is a Cloudflare address, so CF-Connecting-IP counts.
            via_cf = {'REMOTE_ADDR': railway_proxy, 'HTTP_X_FORWARDED_FOR': f'203.0.113.7, {CLOUDFLARE_EDGE}'}
            self.assertEqual(self.attempt(HTTP_CF_CONNECTING_IP='203.0.113.7', **via_cf).status_code, 401)
            self.assertEqual(self.attempt(HTTP_CF_CONNECTING_IP='203.0.113.7', **via_cf).status_code, 429)
            self.assertEqual(self.attempt(HTTP_CF_CONNECTING_IP='203.0.113.8', **via_cf).status_code, 401)
            # Around Cloudflare (the *.up.railway.app hostname): the visitor's own address, whatever it claims.
            direct = {'REMOTE_ADDR': railway_proxy, 'HTTP_X_FORWARDED_FOR': '198.51.100.50, 198.51.100.9'}
            self.assertEqual(self.attempt(HTTP_CF_CONNECTING_IP='203.0.113.20', **direct).status_code, 401)
            self.assertEqual(self.attempt(HTTP_CF_CONNECTING_IP='203.0.113.21', **direct).status_code, 429)
            spoofed_hop = {'REMOTE_ADDR': railway_proxy,
                           'HTTP_X_FORWARDED_FOR': f'{CLOUDFLARE_EDGE}, 198.51.100.9'}  # a forged entry is not the hop
            self.assertEqual(self.attempt(HTTP_CF_CONNECTING_IP='203.0.113.22', **spoofed_hop).status_code, 429)

    @override_settings(TRUSTED_CLIENT_IP_HEADER='CF-Connecting-IP')
    def test_axes_locks_the_visitor_not_the_edge(self):
        make_user('edge', 'edge@example.com')
        conf = {**settings.REST_FRAMEWORK, 'NUM_PROXIES': 1}
        via_cf = {'REMOTE_ADDR': '100.64.0.2', 'HTTP_X_FORWARDED_FOR': f'203.0.113.7, {CLOUDFLARE_EDGE}'}
        with override_settings(REST_FRAMEWORK=conf):
            for _ in range(5):
                self.client.post('/api/auth/native/login/', {'email': 'edge@example.com', 'password': 'guess'},
                                 format='json', HTTP_CF_CONNECTING_IP='203.0.113.7', **via_cf)
            locked = self.client.post('/api/auth/native/login/', {'email': 'edge@example.com', 'password': PASSWORD},
                                      format='json', HTTP_CF_CONNECTING_IP='203.0.113.7', **via_cf)
            self.assert_code(locked, 429, 'too_many_attempts')
            # Another visitor behind the same Cloudflare edge is not locked out.
            other = self.client.post('/api/auth/native/login/', {'email': 'edge@example.com', 'password': PASSWORD},
                                     format='json', HTTP_CF_CONNECTING_IP='203.0.113.99', **via_cf)
            self.assertEqual(other.status_code, 200, other.data)


@override_settings(
    PASSWORD_HASHERS=FAST_HASHERS,
    # The admin login page renders {% static %}; tests have no collected manifest.
    STORAGES={**settings.STORAGES, 'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}},
)
class AxesLockoutParameterTests(TestCase):
    """AXES_LOCKOUT_PARAMETERS per path: native sign-in per (account, IP); Django admin also per username."""

    def setUp(self):
        cache.clear()
        self.staff = User.objects.create_user(username='staffer', email='staffer@example.com', password=PASSWORD,
                                              is_staff=True, is_superuser=True, role='admin')
        self.staff.email_verified_at = timezone.now()
        self.staff.save(update_fields=['email_verified_at'])

    def admin_login(self, password, ip):
        client = Client()
        response = client.post('/admin/login/?next=/admin/', {'username': 'staffer', 'password': password,
                                                              'next': '/admin/'}, REMOTE_ADDR=ip)
        return response, client

    def test_admin_login_locks_the_username_from_anywhere(self):
        response, client = self.admin_login(PASSWORD, '10.6.0.200')  # control: the password works
        self.assertEqual(response.status_code, 302)
        self.assertIn('_auth_user_id', client.session)
        for i in range(5):
            response, _ = self.admin_login('guess', f'10.6.0.{i + 1}')  # five addresses, one username
            self.assertNotEqual(response.status_code, 302)
        response, client = self.admin_login(PASSWORD, '10.6.0.99')  # right password, fresh address
        self.assertNotEqual(response.status_code, 302)
        self.assertNotIn('_auth_user_id', client.session)

    @override_settings(**NATIVE)
    def test_native_sign_in_of_the_same_account_is_locked_per_address_only(self):
        for i in range(5):
            self.admin_login('guess', f'10.6.1.{i + 1}')
        response = APIClient().post('/api/auth/native/login/', {'email': 'staffer@example.com', 'password': PASSWORD},
                                    format='json', REMOTE_ADDR='10.6.1.99')
        self.assertEqual(response.status_code, 200, response.data)

    def test_the_parameters_by_path(self):
        from accounts.throttles import axes_lockout_parameters

        factory = RequestFactory()
        self.assertEqual(axes_lockout_parameters(factory.post('/api/auth/native/login/')), [['username', 'ip_address']])
        self.assertEqual(axes_lockout_parameters(factory.post('/admin/login/')), ['username', 'ip_address'])
        self.assertEqual(axes_lockout_parameters(factory.post('/api/auth/local/login/')), ['username', 'ip_address'])
        self.assertEqual(settings.AXES_LOCKOUT_PARAMETERS, 'accounts.throttles.axes_lockout_parameters')


# ── Supabase mode (the default) is unchanged ─────────────────────────────

class SupabaseModeUnchangedTests(TestCase):
    NATIVE_POSTS = (
        '/api/auth/native/login/', '/api/auth/native/refresh/', '/api/auth/native/logout/',
        '/api/auth/native/register/', '/api/auth/native/verify-email/', '/api/auth/native/resend-verification/',
        '/api/auth/native/password/', '/api/auth/google/', '/api/auth/google/confirm-link/',
        '/api/auth/google/link/',
    )

    def setUp(self):
        cache.clear()

    @override_settings(AUTH_PROVIDER='supabase')
    def test_native_endpoints_404_and_config_reports_supabase(self):
        make_user('sb', 'sb@example.com')
        client = APIClient()
        for path in self.NATIVE_POSTS:
            self.assertEqual(client.post(path, {'email': 'sb@example.com', 'password': PASSWORD}, format='json')
                             .status_code, 404, path)
        self.assertEqual(client.delete('/api/auth/google/link/').status_code, 404)
        self.assertFalse(AuthSession.objects.exists())
        self.assertEqual(client.get('/api/auth/config/').data,
                         {'auth_provider': 'supabase', 'google_client_id': '', 'signup_enabled': False})
        # Password reset keeps answering 410 and sends nothing.
        with self.captureOnCommitCallbacks(execute=True):
            gone = client.post('/api/auth/password-reset/', {'email': 'sb@example.com'}, format='json')
        self.assertEqual((gone.status_code, gone.data.get('error')), (410, 'endpoint_gone'))
        self.assertEqual(client.post('/api/auth/password-reset/confirm/', {}, format='json').status_code, 410)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(AUTH_PROVIDER='supabase')
    def test_the_native_authenticator_is_inert(self):
        user = make_user('inert', 'inert@example.com')
        tokens = issue_session_tokens(user, None, 'password')
        request = APIRequestFactory().get(PROBE, HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')
        self.assertIsNone(NativeJWTAuthentication().authenticate(request))
        self.assertEqual(bearer(tokens['access']).get(PROBE).status_code, 401)

    @override_settings(AUTH_PROVIDER='django', GOOGLE_OAUTH_CLIENT_IDS=['web-client.apps.googleusercontent.com'],
                       NATIVE_AUTH_ALLOW_SIGNUP=True)
    def test_config_in_django_mode(self):
        self.assertEqual(APIClient().get('/api/auth/config/').data, {
            'auth_provider': 'django', 'google_client_id': 'web-client.apps.googleusercontent.com',
            'signup_enabled': True,
        })


# ── Dev-only local auth against a django-mode backend ────────────────────

@override_settings(LOCAL_DEV_AUTH=True, **NATIVE)
class LocalAuthInDjangoModeTests(_NativeTestCase):
    def test_local_login_issues_native_sessions(self):
        from accounts.local_auth import LocalLoginView, LocalRefreshView

        make_user('localdev', 'localdev@local.test')
        factory = APIRequestFactory()
        response = LocalLoginView.as_view()(factory.post('/api/auth/local/login/',
                                                         {'email': 'localdev@local.test', 'password': PASSWORD},
                                                         format='json'))
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(AuthSession.objects.filter(sid=response.data['session_id'], method='local').exists())
        self.assertEqual(bearer(response.data['access'], DEVICE_A).get(PROBE).status_code, 200)
        rotated = LocalRefreshView.as_view()(factory.post('/api/auth/local/refresh/',
                                                          {'refresh': response.data['refresh']}, format='json'))
        self.assertEqual(rotated.status_code, 200, rotated.data)
        self.assertIn('refresh', rotated.data)


# ── Deploy checks ────────────────────────────────────────────────────────

class NativeDeployCheckTests(TestCase):
    def ids(self, **settings_overrides):
        with override_settings(**settings_overrides):
            return {m.id for m in run_checks(include_deployment_checks=True) if m.id.startswith('accounts.')}

    def test_django_mode_warnings(self):
        found = self.ids(AUTH_PROVIDER='django', DEBUG=False, JWT_SIGNING_KEY='', GOOGLE_OAUTH_CLIENT_IDS=[],
                         EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend', TRUSTED_CLIENT_IP_HEADER='',
                         REST_FRAMEWORK={'NUM_PROXIES': None})
        self.assertTrue({'accounts.W004', 'accounts.W005', 'accounts.W006', 'accounts.W007'} <= found, found)
        self.assertFalse({'accounts.W001', 'accounts.W002'} & found)

    def test_configured_django_mode_is_quiet(self):
        found = self.ids(AUTH_PROVIDER='django', DEBUG=False, JWT_SIGNING_KEY='a-separate-signing-key-' + 'x' * 40,
                         GOOGLE_OAUTH_CLIENT_IDS=['web.apps.googleusercontent.com'],
                         EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend', EMAIL_HOST='smtp.example.com',
                         TRUSTED_CLIENT_IP_HEADER='CF-Connecting-IP', TRUSTED_CLIENT_IP_HEADER_FROM='cloudflare',
                         REST_FRAMEWORK={**settings.REST_FRAMEWORK, 'NUM_PROXIES': 1})
        self.assertFalse({'accounts.W004', 'accounts.W005', 'accounts.W006', 'accounts.W007', 'accounts.E001'} & found,
                         found)

    def test_a_header_read_from_any_peer_warns_until_hardened(self):
        base = dict(AUTH_PROVIDER='django', DEBUG=False, TRUSTED_CLIENT_IP_HEADER='CF-Connecting-IP',
                    REST_FRAMEWORK={**settings.REST_FRAMEWORK, 'NUM_PROXIES': 1})
        self.assertIn('accounts.W007', self.ids(**base, TRUSTED_CLIENT_IP_HEADER_FROM=''))
        self.assertIn('accounts.W007', self.ids(**base, TRUSTED_CLIENT_IP_HEADER_FROM='any'))
        self.assertNotIn('accounts.W007', self.ids(**base, TRUSTED_CLIENT_IP_HEADER_FROM='cloudflare'))
        # The Transform Rule secret hardens it too (only requests through our Cloudflare zone carry it).
        self.assertNotIn('accounts.W007', self.ids(**base, TRUSTED_CLIENT_IP_HEADER_FROM='',
                                                   TRUSTED_CLIENT_IP_SECRET='edge-secret-value'))

    def test_migration_0029_reverse_keeps_the_newest_signup_per_address(self):
        import importlib

        from django.apps import apps as global_apps

        migration = importlib.import_module('accounts.migrations.0029_pendingsignup_one_row_per_signup')
        expires = timezone.now() + timedelta(days=1)
        older = PendingSignup.objects.create(email='twice@example.com', password='x', token_hash='h1' * 32,
                                             expires_at=expires)
        newer = PendingSignup.objects.create(email='twice@example.com', password='y', token_hash='h2' * 32,
                                             expires_at=expires)
        single = PendingSignup.objects.create(email='once@example.com', password='z', token_hash='h3' * 32,
                                              expires_at=expires)
        migration.keep_newest_signup_per_address(global_apps, None)
        self.assertEqual(set(PendingSignup.objects.values_list('pk', flat=True)), {newer.pk, single.pk})
        self.assertFalse(PendingSignup.objects.filter(pk=older.pk).exists())

    def test_a_restricted_header_without_num_proxies_is_an_error_outside_debug(self):
        restricted = dict(TRUSTED_CLIENT_IP_HEADER='CF-Connecting-IP', TRUSTED_CLIENT_IP_HEADER_FROM='cloudflare',
                          REST_FRAMEWORK={**settings.REST_FRAMEWORK, 'NUM_PROXIES': None})
        with override_settings(DEBUG=False, **restricted):
            errors = [m for m in run_checks() if m.id == 'accounts.E001']  # not deploy-only: migrate stops
        self.assertEqual(len(errors), 1)
        self.assertTrue(errors[0].is_serious())
        with override_settings(DEBUG=True, **restricted):
            self.assertFalse([m for m in run_checks() if m.id == 'accounts.E001'])
        with override_settings(DEBUG=False, TRUSTED_CLIENT_IP_HEADER='CF-Connecting-IP',
                               TRUSTED_CLIENT_IP_HEADER_FROM='cloudflare',
                               REST_FRAMEWORK={**settings.REST_FRAMEWORK, 'NUM_PROXIES': 1}):
            self.assertFalse([m for m in run_checks() if m.id == 'accounts.E001'])

    def test_a_client_ip_header_without_num_proxies_still_warns(self):
        """Verifier probe: the header alone satisfied W007, although it is never read behind the proxy."""
        for header in ('CF-Connecting-IP', 'DO-Connecting-IP'):
            found = self.ids(AUTH_PROVIDER='django', DEBUG=False, TRUSTED_CLIENT_IP_HEADER=header,
                             REST_FRAMEWORK={**settings.REST_FRAMEWORK, 'NUM_PROXIES': None})
            self.assertIn('accounts.W007', found, header)
        found = self.ids(AUTH_PROVIDER='django', DEBUG=False, TRUSTED_CLIENT_IP_HEADER='',
                         REST_FRAMEWORK={**settings.REST_FRAMEWORK, 'NUM_PROXIES': 0})
        self.assertNotIn('accounts.W007', found)  # 0 = no proxy in front: REMOTE_ADDR is the client

    def test_supabase_mode_has_no_native_warnings(self):
        found = self.ids(AUTH_PROVIDER='supabase', DEBUG=False, JWT_SIGNING_KEY='')
        self.assertFalse({'accounts.W004', 'accounts.W005', 'accounts.W006', 'accounts.W007'} & found, found)
