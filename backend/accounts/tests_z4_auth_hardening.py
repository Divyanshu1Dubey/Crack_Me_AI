"""Security pass (Z4 auth): token checks, session-bound devices, bare premium flags.

TOKEN   any bearer value used to make the backend call Supabase /auth/v1/user
        (8 s timeout) before DRF's throttles ran, and failures were never
        remembered. Values that cannot be live access tokens are now refused
        without a call; refused tokens are remembered for 60 s; a cached
        answer never outlives the token's exp; calls time out after 3 s, are
        shared by concurrent requests with the same token, and are capped per
        process and per client IP (429 auth_verification_busy).
DEVICE  the device cap counted only the client-sent X-Session-ID: without it
        a request was not counted, and a logged-out device kept access by
        omitting the header or sending a new one. Devices are now bound to the
        Supabase session of the verified token (session_id claim).
FLAG    is_subscribed without a Subscription row (set without payment by the
        removed /auth/subscribe/ endpoint) counted as a lifetime plan, and a
        later dated purchase turned it into a real lifetime row with unlimited
        AI. Premium now comes from rows only; migration 0026 / the
        reconcile_legacy_subscriptions command restore what payments prove.

No network: urllib.request.urlopen is patched wherever it could be reached.
"""
import base64
import importlib
import io
import json
import threading
import time
import uuid
from datetime import timedelta
from unittest import mock
from urllib.error import HTTPError

from django.apps import apps as django_apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts import supabase_rest_auth as sra
from accounts.legacy_subscriptions import FREE_ENDPOINT_NOTE, reconcile
from accounts.models import AdminAuditLog, PaymentAttempt, Subscription, TokenTransaction, UserDevice
from accounts.supabase_rest_auth import SupabaseJWTAuthentication, plausible_access_token_claims
from accounts.tests_wave1_auth import CONFIRMED, DEVICE_A, DEVICE_B, DEVICE_C, _SupabaseAuthTestCase
from accounts.utils import is_premium

User = get_user_model()

SUPABASE_ENV = {'SUPABASE_URL': 'https://example.supabase.co', 'SUPABASE_ANON_KEY': 'anon-test-key'}
PROBE = '/api/auth/tokens/history/'  # an authenticated, device-limited endpoint


def _b64(data):
    return base64.urlsafe_b64encode(json.dumps(data, separators=(',', ':')).encode()).rstrip(b'=').decode()


def _jwt(sub, session_id=None, *, exp_in=3600, header=None, **claims):
    """A Supabase-shaped access token (unsigned; GoTrue is faked)."""
    payload = {'sub': sub, 'exp': int(time.time()) + exp_in, 'aud': 'authenticated', 'role': 'authenticated', **claims}
    if session_id:
        payload['session_id'] = session_id
    return f"{_b64(header or {'alg': 'ES256', 'typ': 'JWT'})}.{_b64(payload)}.sig-{uuid.uuid4().hex}"


class _Resp(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _client(token=None, **headers):
    client = APIClient()
    if token is not None:
        headers['HTTP_AUTHORIZATION'] = f'Bearer {token}'
    client.credentials(**headers)
    return client


# ── TOKEN ─────────────────────────────────────────────────────────────────

@mock.patch.dict('os.environ', SUPABASE_ENV)
class TokenVerificationTests(TestCase):
    """The real _fetch_supabase_user against a fake GoTrue (patched urlopen)."""

    def setUp(self):
        cache.clear()
        self.calls = []
        self.answers = {}  # bearer -> identity dict | Exception (default: 401)

        def fake_urlopen(req, timeout=None):
            bearer = req.headers['Authorization'].split(' ', 1)[1]
            self.calls.append({'url': req.full_url, 'method': req.get_method(), 'timeout': timeout, 'token': bearer})
            answer = self.answers.get(bearer)
            if isinstance(answer, Exception):
                raise answer
            if answer is None:
                raise HTTPError(req.full_url, 401, 'Unauthorized', {}, io.BytesIO(b'{}'))
            return _Resp(json.dumps(answer).encode())

        patcher = mock.patch('accounts.supabase_rest_auth.request.urlopen', side_effect=fake_urlopen)
        patcher.start()
        self.addCleanup(patcher.stop)

    def live_token(self, email='tok@example.com', exp_in=3600):
        uid = str(uuid.uuid4())
        token = _jwt(uid, str(uuid.uuid4()), exp_in=exp_in)
        self.answers[token] = {'id': uid, 'email': email, 'email_confirmed_at': CONFIRMED,
                               'user_metadata': {}, 'app_metadata': {}}
        return token

    def test_values_that_cannot_be_access_tokens_never_reach_supabase(self):
        now = int(time.time())
        garbage = [
            'x', 'not-a-valid-token', uuid.uuid4().hex * 2, 'a.b.c', 'only.two',
            f"{_b64({'alg': 'none'})}.{_b64({'sub': 'u', 'exp': now + 600})}.sig",       # unsigned
            f"{_b64({'alg': 'HS256'})}.{_b64({'exp': now + 600})}.sig",                  # no subject
            f"{_b64({'alg': 'HS256'})}.{_b64({'sub': 'u', 'exp': now - 120})}.sig",      # expired
            f"{_b64({'alg': 'HS256'})}.{_b64({'sub': 'u', 'exp': str(now + 600)})}.sig",  # exp not a number
            f"{_b64({'alg': 'HS256'})}.{_b64({'sub': 'u'})}.sig",                        # no exp
            f"{_b64({'alg': 'HS256'})}.{_b64({'sub': 'u', 'exp': now + 600, 'pad': 'A' * 20000})}.sig",
        ]
        for value in garbage:
            r = _client(value).get('/api/auth/tokens/')
            self.assertEqual(r.status_code, 401, value[:40])
        self.assertEqual(self.calls, [])

        # A live-looking token is still checked with GoTrue (and refused by it here).
        self.assertEqual(_client(_jwt('someone')).get('/api/auth/tokens/').status_code, 401)
        self.assertEqual(len(self.calls), 1)

    def test_a_valid_token_still_signs_in(self):
        token = self.live_token()
        r = _client(token).get('/api/auth/tokens/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(_client(token).get('/api/auth/tokens/').status_code, 200)
        self.assertEqual(len(self.calls), 1)  # second request served from the cache
        self.assertEqual(self.calls[0]['url'], 'https://example.supabase.co/auth/v1/user')

    def test_a_refused_token_is_not_checked_again_for_a_minute(self):
        token = _jwt('revoked-user')  # GoTrue answers 401
        for _ in range(3):
            self.assertEqual(_client(token).get('/api/auth/tokens/').status_code, 401)
        self.assertEqual(len(self.calls), 1)

    def test_outages_are_not_remembered_as_refusals(self):
        token = self.live_token()
        self.answers[token] = HTTPError('https://example.supabase.co/auth/v1/user', 503, 'Unavailable', {}, io.BytesIO())
        self.assertEqual(_client(token).get('/api/auth/tokens/').status_code, 401)
        self.answers[token] = TimeoutError('slow')
        self.assertEqual(_client(token).get('/api/auth/tokens/').status_code, 401)
        self.assertEqual(len(self.calls), 2)

    def test_a_cached_answer_never_outlives_the_token(self):
        token = self.live_token(exp_in=30)
        with mock.patch.object(sra, '_cache_set', wraps=sra._cache_set) as cache_set:
            self.assertEqual(_client(token).get('/api/auth/tokens/').status_code, 200)
        (_store, key, _value, ttl), = [c.args for c in cache_set.call_args_list if c.args[1].startswith('supabase_jwt:')]
        self.assertLessEqual(ttl, 30)  # was a flat 300 s
        exp = plausible_access_token_claims(token)['exp']
        self.assertIsNotNone(plausible_access_token_claims(token, now=exp + 5))  # clock-skew leeway
        self.assertIsNone(plausible_access_token_claims(token, now=exp + 11))   # refused locally afterwards

    def test_the_supabase_call_times_out_after_three_seconds(self):
        self.assertEqual(_client(self.live_token()).get('/api/auth/tokens/').status_code, 200)
        self.assertEqual(self.calls[0]['timeout'], 3.0)  # was 8 s

    def test_over_the_process_cap_a_new_token_gets_429_without_a_call(self):
        known = self.live_token('known@example.com')
        self.assertEqual(_client(known).get('/api/auth/tokens/').status_code, 200)
        self.calls.clear()
        busy = threading.BoundedSemaphore(1)
        busy.acquire()  # every slot held (e.g. by slow calls for made-up tokens)
        with mock.patch.object(sra, '_verification_slots', return_value=busy):
            r = _client(self.live_token('new@example.com')).get('/api/auth/tokens/')
            self.assertEqual((r.status_code, r.data['code']), (429, 'auth_verification_busy'))
            self.assertEqual(r['Retry-After'], '1')
            # A token checked before keeps working.
            self.assertEqual(_client(known).get('/api/auth/tokens/').status_code, 200)
        busy.release()
        self.assertEqual(self.calls, [])

    @override_settings(SUPABASE_AUTH_VERIFY_RATE_PER_IP=2)
    @mock.patch.object(sra, '_VERIFY_RATE_WINDOW_SECONDS', 10 ** 9)  # one window for the whole test
    def test_per_ip_budget_of_supabase_calls(self):
        first, second, third = self.live_token('a@example.com'), self.live_token('b@example.com'), self.live_token('c@example.com')
        for token in (first, second):
            self.assertEqual(_client(token, REMOTE_ADDR='203.0.113.5').get('/api/auth/tokens/').status_code, 200)
        r = _client(third, REMOTE_ADDR='203.0.113.5').get('/api/auth/tokens/')
        self.assertEqual((r.status_code, r.data['code']), (429, 'auth_verification_busy'))
        self.assertEqual(len(self.calls), 2)
        # Cached tokens are not counted; another address has its own budget.
        self.assertEqual(_client(first, REMOTE_ADDR='203.0.113.5').get('/api/auth/tokens/').status_code, 200)
        self.assertEqual(_client(third, REMOTE_ADDR='198.51.100.7').get('/api/auth/tokens/').status_code, 200)
        self.assertEqual(len(self.calls), 3)

    def test_the_ip_budget_waits_for_a_trusted_client_ip(self):
        framework = {**settings.REST_FRAMEWORK, 'NUM_PROXIES': None}
        with mock.patch.dict('os.environ', {'SUPABASE_AUTH_VERIFY_RATE_PER_IP': ''}):
            with override_settings(REST_FRAMEWORK=framework, TRUSTED_CLIENT_IP_HEADER=''):
                self.assertEqual(sra._verification_rate_per_ip(), 0)  # one shared proxy address: off
            with override_settings(REST_FRAMEWORK=framework, TRUSTED_CLIENT_IP_HEADER='DO-Connecting-IP'):
                self.assertEqual(sra._verification_rate_per_ip(), 240)
            with override_settings(REST_FRAMEWORK={**framework, 'NUM_PROXIES': 1}, TRUSTED_CLIENT_IP_HEADER=''):
                self.assertEqual(sra._verification_rate_per_ip(), 240)
            with override_settings(TRUSTED_CLIENT_IP_HEADER='DO-Connecting-IP', SUPABASE_AUTH_VERIFY_RATE_PER_IP=0):
                self.assertEqual(sra._verification_rate_per_ip(), 0)

    def test_concurrent_requests_with_one_token_share_one_call(self):
        token = self.live_token()
        identity = self.answers[token]
        entered, release = threading.Event(), threading.Event()

        def slow_urlopen(req, timeout=None):
            self.calls.append({'url': req.full_url})
            entered.set()
            release.wait(5)
            return _Resp(json.dumps(identity).encode())

        results = []

        def worker():
            results.append(SupabaseJWTAuthentication()._fetch_supabase_user(token))

        with mock.patch('accounts.supabase_rest_auth.request.urlopen', side_effect=slow_urlopen):
            leader = threading.Thread(target=worker)
            leader.start()
            self.assertTrue(entered.wait(5))
            follower = threading.Thread(target=worker)
            follower.start()
            time.sleep(0.2)  # let the follower join the pending check
            release.set()
            leader.join(5)
            follower.join(5)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(results, [identity, identity])


# ── DEVICE ────────────────────────────────────────────────────────────────

UID = '66666666-6666-4666-8666-666666666666'


class SessionBoundDeviceTests(_SupabaseAuthTestCase):
    """GoTrue is faked by _SupabaseAuthTestCase; tokens carry real session_id claims."""

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(username='sess', email='sess@example.com', password=None)
        self.identity = {'id': UID, 'email': 'sess@example.com', 'email_confirmed_at': CONFIRMED,
                         'user_metadata': {}, 'app_metadata': {}}
        # backend/.env may provide SUPABASE_URL / SUPABASE_ANON_KEY (public, not
        # blanked by the hermetic test settings): never let the GoTrue /logout
        # of a logged-out session leave the machine.
        self.upstream_calls = []

        def offline_urlopen(req, timeout=None):
            self.upstream_calls.append(req.full_url)
            return _Resp(b'')

        patcher = mock.patch('accounts.supabase_rest_auth.request.urlopen', side_effect=offline_urlopen)
        patcher.start()
        self.addCleanup(patcher.stop)

    def session(self, device=None, session_id=None):
        """(client, token, session id) for one Supabase session (a fresh access token of it)."""
        sid = session_id or str(uuid.uuid4())
        token = _jwt(UID, sid)
        return self.bearer(token, self.identity, device=device), token, sid

    def active_devices(self):
        return UserDevice.objects.filter(user=self.user, is_active=True)

    def assert_code(self, response, code):
        self.assertEqual((response.status_code, response.data.get('code')), (401, code))

    def test_a_session_without_the_header_still_takes_a_slot(self):
        for device in (DEVICE_A, DEVICE_B):
            client, _, _ = self.session(device)
            self.assertEqual(client.get(PROBE).status_code, 200)
        headerless, _, sid = self.session()  # header stripped (extension, direct API use, storage blocked)
        self.assert_code(headerless.get(PROBE), 'device_limit_reached')  # used to be 200 and uncounted

        UserDevice.objects.filter(user=self.user, device_fingerprint=DEVICE_B).update(is_active=False)
        self.assertEqual(headerless.get(PROBE).status_code, 200)
        self.assertTrue(self.active_devices().filter(device_fingerprint=f'sid:{sid}', session_id=sid).exists())

    def test_a_logged_out_device_stays_out_whatever_header_it_sends(self):
        phone, phone_token, _ = self.session(DEVICE_A)
        laptop, _, _ = self.session(DEVICE_B)
        self.assertEqual(phone.get(PROBE).status_code, 200)
        self.assertEqual(laptop.get(PROBE).status_code, 200)
        device = UserDevice.objects.get(user=self.user, device_fingerprint=DEVICE_A)
        self.assertEqual(laptop.post('/api/auth/devices/logout/', {'device_id': device.id}, format='json').status_code, 200)

        for headers in ({}, {'HTTP_X_SESSION_ID': DEVICE_A}, {'HTTP_X_SESSION_ID': 'dev_brandnewdevice_9'}):
            self.assert_code(_client(phone_token, **headers).get(PROBE), 'device_inactive')
        self.assertFalse(UserDevice.objects.filter(device_fingerprint='dev_brandnewdevice_9').exists())
        # The slot is free for a new sign-in.
        new_phone, _, _ = self.session('dev_newphone000001_x')
        self.assertEqual(new_phone.get(PROBE).status_code, 200)

    def test_an_admin_force_logout_ends_the_session_too(self):
        phone, phone_token, _ = self.session(DEVICE_A)
        self.assertEqual(phone.get(PROBE).status_code, 200)
        device = UserDevice.objects.get(user=self.user, device_fingerprint=DEVICE_A)
        ops = User.objects.create_user(username='ops-z4', email='ops-z4@example.com', password=None, role='admin', is_staff=True)
        admin = APIClient()
        admin.force_authenticate(ops)
        r = admin.post(f'/api/auth/admin/users/{self.user.id}/devices/', {'device_id': device.id}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assert_code(_client(phone_token).get(PROBE), 'device_inactive')

    def test_signing_in_again_on_the_same_browser_keeps_its_one_slot(self):
        first, _, _ = self.session(DEVICE_A)
        self.assertEqual(first.get(PROBE).status_code, 200)
        second, _, sid2 = self.session(DEVICE_A)  # signed out and in again
        self.assertEqual(second.get(PROBE).status_code, 200)
        self.assertEqual(list(self.active_devices().values_list('device_fingerprint', 'session_id')), [(DEVICE_A, sid2)])
        self.assert_code(first.get(PROBE), 'device_inactive')  # the old session is retired
        self.assertEqual(self.active_devices().count(), 1)

    def test_a_refreshed_token_is_the_same_device(self):
        client, _, sid = self.session(DEVICE_A)
        self.assertEqual(client.get(PROBE).status_code, 200)
        refreshed, refreshed_token, _ = self.session(DEVICE_A, session_id=sid)
        self.assertEqual(refreshed.get(PROBE).status_code, 200)
        self.assertEqual(client.get(PROBE).status_code, 200)
        self.assertEqual(_client(refreshed_token).get(PROBE).status_code, 200)  # without the header too
        self.assertEqual(UserDevice.objects.filter(user=self.user).count(), 1)

    def test_one_device_id_shared_by_two_people_is_one_seat(self):
        owner, _, _ = self.session(DEVICE_A)
        self.assertEqual(owner.get(PROBE).status_code, 200)
        friend, _, _ = self.session(DEVICE_A)  # copied crack_device_id
        self.assertEqual(friend.get(PROBE).status_code, 200)
        self.assert_code(owner.get(PROBE), 'device_inactive')
        self.assertEqual(self.active_devices().count(), 1)

    def test_a_fresh_sign_in_on_a_logged_out_browser_is_enrolled_again(self):
        phone, _, _ = self.session(DEVICE_A)
        self.assertEqual(phone.get(PROBE).status_code, 200)
        UserDevice.objects.filter(user=self.user, device_fingerprint=DEVICE_A).update(is_active=False)
        again, _, sid2 = self.session(DEVICE_A)
        self.assertEqual(again.get(PROBE).status_code, 200)
        row = UserDevice.objects.get(user=self.user, device_fingerprint=DEVICE_A)
        self.assertEqual((row.is_active, row.session_id), (True, sid2))
        self.assert_code(phone.get(PROBE), 'device_inactive')  # the logged-out session stays out

    def test_re_enrolling_a_logged_out_browser_needs_a_free_slot(self):
        phone, _, _ = self.session(DEVICE_A)
        phone.get(PROBE)
        UserDevice.objects.filter(user=self.user, device_fingerprint=DEVICE_A).update(is_active=False)
        for device in (DEVICE_B, DEVICE_C):
            client, _, _ = self.session(device)
            self.assertEqual(client.get(PROBE).status_code, 200)
        again, _, _ = self.session(DEVICE_A)
        self.assert_code(again.get(PROBE), 'device_limit_reached')
        self.assertFalse(UserDevice.objects.get(user=self.user, device_fingerprint=DEVICE_A).is_active)

    def test_rows_from_before_the_session_binding(self):
        legacy = UserDevice.objects.create(user=self.user, device_fingerprint=DEVICE_A, is_active=True)
        client, _, sid = self.session(DEVICE_A)
        self.assertEqual(client.get(PROBE).status_code, 200)
        legacy.refresh_from_db()
        self.assertEqual(legacy.session_id, sid)
        self.assertEqual(UserDevice.objects.filter(user=self.user).count(), 1)
        # Logged out before its session was recorded: as before, sign in again with a new device id.
        UserDevice.objects.create(user=self.user, device_fingerprint=DEVICE_B, is_active=False)
        other, _, _ = self.session(DEVICE_B)
        self.assert_code(other.get(PROBE), 'device_inactive')

    def test_is_current_follows_the_session_without_the_header(self):
        a, token_a, _ = self.session(DEVICE_A)
        b, _, _ = self.session(DEVICE_B)
        a.get(PROBE)
        b.get(PROBE)
        rows = _client(token_a).get('/api/auth/devices/').data
        current = {UserDevice.objects.get(pk=row['id']).device_fingerprint: row['is_current'] for row in rows}
        self.assertEqual(current, {DEVICE_A: True, DEVICE_B: False})

    def test_an_over_limit_session_can_still_manage_devices_without_taking_a_slot(self):
        for device in (DEVICE_A, DEVICE_B):
            client, _, _ = self.session(device)
            client.get(PROBE)
        headerless, _, sid = self.session()
        r = headerless.get('/api/auth/devices/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 2)
        self.assertEqual(headerless.get('/api/auth/profile/').status_code, 200)
        self.assertFalse(UserDevice.objects.filter(session_id=sid).exists())

    def test_the_supabase_session_of_a_logged_out_device_is_ended_once(self):
        phone, phone_token, _ = self.session(DEVICE_A)
        phone.get(PROBE)
        UserDevice.objects.filter(user=self.user, device_fingerprint=DEVICE_A).update(is_active=False)
        calls = []

        def fake_urlopen(req, timeout=None):
            calls.append((req.full_url, req.get_method(), req.headers.get('Authorization')))
            return _Resp(b'')

        with mock.patch.dict('os.environ', SUPABASE_ENV), \
                mock.patch('accounts.supabase_rest_auth.request.urlopen', side_effect=fake_urlopen):
            self.assert_code(phone.get(PROBE), 'device_inactive')
            self.assert_code(phone.get(PROBE), 'device_inactive')
        self.assertEqual(calls, [
            ('https://example.supabase.co/auth/v1/logout?scope=local', 'POST', f'Bearer {phone_token}'),
        ])

    def test_a_bare_subscribed_flag_does_not_give_four_devices(self):
        User.objects.filter(pk=self.user.pk).update(is_subscribed=True)  # no Subscription row
        for device in (DEVICE_A, DEVICE_B):
            client, _, _ = self.session(device)
            self.assertEqual(client.get(PROBE).status_code, 200)
        third, _, _ = self.session(DEVICE_C)
        self.assert_code(third.get(PROBE), 'device_limit_reached')

        Subscription.objects.create(user=self.user, plan='1_month', status='active',
                                    expires_at=timezone.now() + timedelta(days=10))
        self.assertEqual(third.get(PROBE).status_code, 200)


# ── FLAG ──────────────────────────────────────────────────────────────────

def _flagged(username, **fields):
    return User.objects.create_user(username=username, email=f'{username}@example.com', password=None,
                                    is_subscribed=True, **fields)


def _ago(days):
    return timezone.now() - timedelta(days=days)


def _attempt(user, amount, *, days_ago, order, plan='legacy', payment=None):
    attempt = PaymentAttempt.objects.create(
        user=user, razorpay_order_id=order, razorpay_payment_id=payment or f'pay_{order}', amount=amount,
        plan=plan, status='successful',
    )
    PaymentAttempt.objects.filter(pk=attempt.pk).update(created_at=_ago(days_ago))
    return attempt


def _note(user, note, price, *, days_ago):
    tx = TokenTransaction.objects.create(user=user, transaction_type='purchase', amount=0, price_paid=price, note=note)
    TokenTransaction.objects.filter(pk=tx.pk).update(created_at=_ago(days_ago))
    return tx


def _run(**options):
    return reconcile(User=User, Subscription=Subscription, PaymentAttempt=PaymentAttempt,
                     TokenTransaction=TokenTransaction, AuditLog=AdminAuditLog, **options)


class BareSubscribedFlagTests(TestCase):
    def setUp(self):
        cache.clear()
        # The state the removed unpaid POST /api/auth/subscribe/ left behind.
        self.user = _flagged('freeclaim')
        _note(self.user, FREE_ENDPOINT_NOTE, 199, days_ago=120)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_a_flag_without_a_plan_grants_nothing(self):
        self.assertFalse(is_premium(self.user))
        profile = self.client.get('/api/auth/profile/').data
        self.assertEqual(
            (profile['is_premium'], profile['is_subscribed'], profile['subscription_info']), (False, False, None),
        )
        self.assertIsNotNone(profile['ai_tutor_daily_cap'])  # the free cap applies
        status = self.client.get('/api/auth/subscribe/status/').data
        self.assertEqual((status['is_subscribed'], status['subscription']), (False, None))  # no "Lifetime" stub

        from questions.models import Question, Subject
        subject = Subject.objects.create(name='Z4 Medicine', code='Z4MED')
        locked = Question.objects.create(
            question_text='Z4 stem', option_a='a', option_b='b', option_c='c', option_d='d',
            correct_answer='C', year=2024, subject=subject, explanation='C is right.',
        )
        r = self.client.post(f'/api/questions/{locked.id}/attempt/', {'selected_answer': 'A'}, format='json')
        self.assertEqual((r.status_code, r.data.get('code')), (402, 'upgrade_required'))

    def test_premium_still_comes_from_rows(self):
        Subscription.activate_from_payment(self.user, '1_year', 1999)
        profile = self.client.get('/api/auth/profile/').data
        self.assertEqual((profile['is_premium'], profile['is_subscribed']), (True, True))
        self.assertEqual(profile['subscription_info']['plan'], '1_year')


class RestorePaidLegacyPlansTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_the_early_bird_purchase_becomes_a_lifetime_row(self):
        user = _flagged('earlybird')
        _attempt(user, 199, days_ago=120, order='order_EB1')
        accounts = _run(restore=True)
        self.assertEqual([(a.user_id, a.action) for a in accounts], [(user.pk, 'restored')])
        row = Subscription.objects.get(user=user)
        self.assertEqual((row.plan, row.expires_at, row.razorpay_order_id), ('legacy', None, 'order_EB1'))
        self.assertTrue(is_premium(user))
        self.assertTrue(Subscription.get_active_subscription(user).unlimited_ai)
        self.assertTrue(AdminAuditLog.objects.filter(action='subscription_grant', resource_id=str(user.pk)).exists())

    def test_a_signed_payment_recorded_only_as_a_note_counts(self):
        user = _flagged('noteonly')
        _note(user, 'Razorpay Premium: order=order_N1, payment=pay_N1', 199, days_ago=122)
        _run(restore=True)
        row = Subscription.objects.get(user=user)
        self.assertEqual((row.plan, row.razorpay_payment_id), ('legacy', 'pay_N1'))

    def test_the_unpaid_endpoint_leaves_no_row(self):
        user = _flagged('unpaid')
        _note(user, FREE_ENDPOINT_NOTE, 199, days_ago=110)
        (account,) = _run(restore=True)
        self.assertFalse(account.proven)
        self.assertIsNotNone(account.free_claim_at)
        self.assertFalse(Subscription.objects.filter(user=user).exists())
        self.assertFalse(is_premium(user))

    def test_dated_plans_keep_the_period_they_bought(self):
        yearly = _flagged('yearly')
        _attempt(yearly, 1999, days_ago=100, order='order_Y1')  # plan column defaulted to 'legacy'
        monthly = _flagged('monthly')
        _attempt(monthly, 129, days_ago=100, order='order_M1')
        _run(restore=True)
        year_row = Subscription.objects.get(user=yearly)
        self.assertEqual(year_row.plan, '1_year')
        self.assertAlmostEqual((year_row.expires_at - timezone.now()).days, 264, delta=1)
        self.assertTrue(is_premium(yearly))
        self.assertEqual(Subscription.objects.get(user=monthly).plan, '1_month')
        self.assertFalse(is_premium(monthly))
        self.assertIsNone(Subscription.get_active_subscription(monthly))  # flips to expired
        monthly.refresh_from_db()
        self.assertFalse(monthly.is_subscribed)

    def test_one_row_per_order_and_dated_periods_stack(self):
        user = _flagged('stacker')
        _attempt(user, 129, days_ago=100, order='order_S1')
        _note(user, 'Razorpay Premium (₹129.0): order=order_S1, payment=pay_order_S1', 129, days_ago=100)
        _attempt(user, 449, days_ago=90, order='order_S2')
        _run(restore=True)
        rows = list(Subscription.objects.filter(user=user).order_by('starts_at'))
        self.assertEqual([r.plan for r in rows], ['1_month', '3_months'])
        self.assertEqual(rows[1].expires_at, rows[0].expires_at + timedelta(days=90))  # from the first's end
        self.assertTrue(is_premium(user))

    def test_accounts_with_rows_are_left_alone_and_a_second_run_changes_nothing(self):
        paid = _flagged('hasrows')
        Subscription.activate_from_payment(paid, '1_month', 129)
        _attempt(paid, 199, days_ago=120, order='order_H1')
        early = _flagged('early2')
        _attempt(early, 199, days_ago=120, order='order_E2')
        self.assertEqual([a.user_id for a in _run(restore=True)], [early.pk])
        self.assertEqual(_run(restore=True), [])
        self.assertEqual(Subscription.objects.filter(user=paid).count(), 1)
        self.assertEqual(Subscription.objects.filter(user=early).count(), 1)

    def test_the_migration_restores_paid_plans(self):
        user = _flagged('migrated')
        _attempt(user, 199, days_ago=120, order='order_MG1')
        migration = importlib.import_module('accounts.migrations.0026_restore_paid_legacy_plans')
        migration.restore_paid_plans(django_apps, None)
        self.assertEqual(Subscription.objects.get(user=user).plan, 'legacy')


class ReconcileCommandTests(TestCase):
    def setUp(self):
        cache.clear()
        self.early = _flagged('cmd-early')
        _attempt(self.early, 199, days_ago=120, order='order_C1')
        self.unpaid = _flagged('cmd-unpaid')
        _note(self.unpaid, FREE_ENDPOINT_NOTE, 199, days_ago=110)

    def run_cmd(self, *args):
        out = io.StringIO()
        call_command('reconcile_legacy_subscriptions', *args, stdout=out)
        return out.getvalue()

    def test_dry_run_reports_and_writes_nothing(self):
        out = self.run_cmd()
        self.assertIn(f'RESTORE  user={self.early.pk}', out)
        self.assertIn(f'UNPROVEN user={self.unpaid.pk}', out)
        self.assertIn('unpaid /auth/subscribe/ endpoint', out)
        self.assertIn('Dry run', out)
        self.assertFalse(Subscription.objects.exists())
        self.unpaid.refresh_from_db()
        self.assertTrue(self.unpaid.is_subscribed)

    def test_apply_restores_and_clear_unproven_clears_after_review(self):
        self.run_cmd('--apply')
        self.assertTrue(Subscription.objects.filter(user=self.early, plan='legacy').exists())
        self.unpaid.refresh_from_db()
        self.assertTrue(self.unpaid.is_subscribed)  # only with --clear-unproven

        out = self.run_cmd('--apply', '--clear-unproven')
        self.assertIn('-> cleared', out)
        self.unpaid.refresh_from_db()
        self.early.refresh_from_db()
        self.assertFalse(self.unpaid.is_subscribed)
        self.assertTrue(self.early.is_subscribed)
        log = AdminAuditLog.objects.get(action='subscription_revoke', resource_id=str(self.unpaid.pk))
        self.assertEqual(log.metadata['source'], 'reconcile_legacy_subscriptions')

    def test_clear_unproven_needs_apply(self):
        with self.assertRaises(CommandError):
            self.run_cmd('--clear-unproven')
