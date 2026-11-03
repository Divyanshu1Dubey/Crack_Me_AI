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
from django.core.checks import run_checks
from django.test import TestCase, override_settings
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

        # Another tab presents the just-rotated token: an access token only.
        racing = self.refresh(first['refresh'])
        self.assertEqual(racing.status_code, 200, racing.data)
        self.assertNotIn('refresh', racing.data)

        # Later reuse of a rotated token: the whole session is revoked.
        AuthSession.objects.filter(sid=first['session_id']).update(rotated_at=timezone.now() - timedelta(minutes=5))
        self.assert_code(self.refresh(first['refresh']), 401, 'session_revoked')
        self.assertEqual(AuthSession.objects.get(sid=first['session_id']).revoked_reason, 'refresh_reuse')
        self.assert_code(self.refresh(rotated.data['refresh']), 401, 'session_revoked')
        self.assert_code(bearer(rotated.data['access'], DEVICE_A).get(PROBE), 401, 'session_revoked')

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

    def test_admins_are_exempt(self):
        make_user('boss', 'boss@example.com', role='admin', is_staff=True)
        for device_id in (DEVICE_A, DEVICE_B, DEVICE_C):
            tokens = self.login('boss@example.com').data
            self.assertEqual(bearer(tokens['access'], device_id).get(PROBE).status_code, 200)


# ── Sign-up and email verification ───────────────────────────────────────

@override_settings(**NATIVE)
class NativeRegisterTests(_NativeTestCase):
    def register(self, **data):
        body = {'email': 'newbie@example.com', 'password': PASSWORD, 'username': 'newbie_doc', **data}
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post('/api/auth/native/register/', body, format='json')

    def verify(self, **data):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post('/api/auth/native/verify-email/', data, format='json')

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

        created = self.verify(token=token)
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
        self.assert_code(self.verify(token=token), 400, 'invalid_or_expired_link')
        self.assertEqual(self.login('newbie@example.com').status_code, 200)

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
        self.assert_code(self.verify(token=token), 400, 'invalid_or_expired_link')
        self.assertFalse(User.objects.filter(email='newbie@example.com').exists())

    def test_a_weak_password_is_refused(self):
        self.assert_code(self.register(password='123'), 400, 'invalid_password')
        self.assertFalse(PendingSignup.objects.exists())

    def test_the_chosen_username_never_shows_the_email(self):
        self.register(username='newbie')  # the email's local part
        [token] = mail_links(r'/verify-email#token=(\S+)')
        self.assertEqual(self.verify(token=token).status_code, 201)
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
        self.assert_code(self.verify(token=old), 400, 'invalid_or_expired_link')
        self.assertEqual(self.verify(token=new).status_code, 201)
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
                         TRUSTED_CLIENT_IP_HEADER='DO-Connecting-IP')
        self.assertFalse({'accounts.W004', 'accounts.W005', 'accounts.W006', 'accounts.W007'} & found, found)

    def test_supabase_mode_has_no_native_warnings(self):
        found = self.ids(AUTH_PROVIDER='supabase', DEBUG=False, JWT_SIGNING_KEY='')
        self.assertFalse({'accounts.W004', 'accounts.W005', 'accounts.W006', 'accounts.W007'} & found, found)
