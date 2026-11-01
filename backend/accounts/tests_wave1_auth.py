"""Wave 1 regression tests: Supabase authenticator (G4-auth-accounts).

ACC-04 / AUTH-02  blocked users are rejected (code account_blocked)
ACC-05            identities are linked by CONFIRMED email only; no-email identities rejected
ACC-06 / AUTH-04  unauthenticated -> 401 + WWW-Authenticate (permission denials stay 403)
ACC-07            device cap enforced at enrolment; logged-out devices get device_inactive
ACC-09            Supabase metadata no longer overwrites profile edits
AUTH-05           the in-app role toggle and the Supabase sync never mint superusers

The Supabase HTTP call is replaced by a fake token -> user payload map, so
these tests make no network requests.
"""
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import UserDevice
from accounts.supabase_rest_auth import SupabaseJWTAuthentication

User = get_user_model()

CONFIRMED = '2026-01-01T00:00:00Z'
DEVICE_A = 'dev_aaaaaaaaaaaa_1'
DEVICE_B = 'dev_bbbbbbbbbbbb_2'
DEVICE_C = 'dev_cccccccccccc_3'


def _identity(email, *, confirmed=True, user_metadata=None, app_metadata=None, **extra):
    payload = {
        'id': f'sb-{email}',
        'email': email,
        'user_metadata': user_metadata or {},
        'app_metadata': app_metadata or {},
    }
    if confirmed:
        payload['email_confirmed_at'] = CONFIRMED
    payload.update(extra)
    return payload


class _SupabaseAuthTestCase(TestCase):
    """Routes `Authorization: Bearer <token>` through SupabaseJWTAuthentication."""

    def setUp(self):
        cache.clear()  # DRF throttle history lives in the default cache
        self.identities = {}
        patcher = mock.patch.object(
            SupabaseJWTAuthentication,
            '_fetch_supabase_user',
            autospec=True,
            side_effect=lambda _self, token: self.identities.get(token),
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def bearer(self, token, payload, device=None):
        self.identities[token] = payload
        client = APIClient()
        headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'}
        if device:
            headers['HTTP_X_SESSION_ID'] = device
        client.credentials(**headers)
        return client


class UnauthenticatedIs401Tests(_SupabaseAuthTestCase):
    def test_anonymous_request_gets_401_with_www_authenticate(self):
        r = APIClient().get('/api/auth/tokens/')
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r['WWW-Authenticate'], 'Bearer realm="api"')

    def test_invalid_token_gets_401_so_the_frontend_refreshes(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Bearer not-a-valid-token')
        self.assertEqual(client.get('/api/auth/tokens/').status_code, 401)

    def test_permission_denial_is_still_403(self):
        User.objects.create_user(username='stu', email='stu@example.com', password='x-Long-passw0rd')
        client = self.bearer('tok-stu', _identity('stu@example.com'))
        self.assertEqual(client.get('/api/auth/tokens/').status_code, 200)
        self.assertEqual(client.get('/api/auth/admin/users/').status_code, 403)


class BlockedUserTests(_SupabaseAuthTestCase):
    def test_blocked_user_is_rejected_with_account_blocked(self):
        User.objects.create_user(username='blk', email='blk@example.com', password='x-Long-passw0rd', is_active=False)
        r = self.bearer('tok-blk', _identity('blk@example.com')).get('/api/auth/profile/')
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.data['code'], 'account_blocked')

    def test_blocked_admin_is_rejected_too(self):
        User.objects.create_user(
            username='adm', email='adm@example.com', password='x-Long-passw0rd',
            role='admin', is_superuser=True, is_staff=True, is_active=False,
        )
        r = self.bearer('tok-adm', _identity('adm@example.com')).get('/api/auth/admin/users/')
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.data['code'], 'account_blocked')

    def test_admin_block_toggle_takes_effect_immediately(self):
        admin = User.objects.create_user(
            username='boss', email='boss@example.com', password='x-Long-passw0rd',
            role='admin', is_superuser=True, is_staff=True,
        )
        target = User.objects.create_user(username='tgt', email='tgt@example.com', password='x-Long-passw0rd')
        student = self.bearer('tok-tgt', _identity('tgt@example.com'))
        self.assertEqual(student.get('/api/auth/tokens/').status_code, 200)

        admin_client = APIClient()
        admin_client.force_authenticate(admin)
        r = admin_client.patch(f'/api/auth/admin/users/{target.id}/block/', {'blocked': True}, format='json')
        self.assertEqual(r.status_code, 200)

        r = student.get('/api/auth/tokens/')
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.data['code'], 'account_blocked')


class ConfirmedEmailLinkingTests(_SupabaseAuthTestCase):
    def test_unconfirmed_identity_cannot_take_over_existing_account(self):
        User.objects.create_user(
            username='admin', email='admin@cracklabs.example', password='x-Long-passw0rd',
            role='admin', is_superuser=True, is_staff=True,
        )
        r = self.bearer('tok-evil', _identity('admin@cracklabs.example', confirmed=False)).get('/api/auth/profile/')
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.data['code'], 'email_not_confirmed')

    def test_unconfirmed_identity_is_not_provisioned(self):
        r = self.bearer('tok-new', _identity('new@example.com', confirmed=False)).get('/api/auth/profile/')
        self.assertEqual(r.status_code, 401)
        self.assertFalse(User.objects.filter(email='new@example.com').exists())

    @mock.patch.dict('os.environ', {'CONTROL_TOWER_ADMIN_EMAILS': 'owner@example.com'})
    def test_allowlisted_admin_email_requires_confirmation(self):
        r = self.bearer('tok-own', _identity('owner@example.com', confirmed=False)).get('/api/auth/profile/')
        self.assertEqual(r.status_code, 401)
        self.assertFalse(User.objects.filter(email='owner@example.com').exists())

        r = self.bearer('tok-own2', _identity('owner@example.com')).get('/api/auth/profile/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data['is_admin'])

    def test_confirmed_identity_links_existing_account(self):
        user = User.objects.create_user(username='legacy', email='legacy@example.com', password='x-Long-passw0rd')
        r = self.bearer('tok-legacy', _identity('LEGACY@example.com')).get('/api/auth/profile/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['id'], user.id)

    def test_identity_without_email_is_rejected(self):
        # A local row with email='' (e.g. createsuperuser without email) must
        # never be matched by phone-only / anonymous Supabase identities.
        User.objects.create_user(username='noemail', email='', password='x-Long-passw0rd', is_superuser=True)
        r = self.bearer('tok-phone', {'id': 'sb-phone', 'phone': '+911234567890', 'phone_confirmed_at': CONFIRMED}).get('/api/auth/profile/')
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.data['code'], 'email_required')

    def test_legacy_confirmed_at_counts_only_without_phone_confirmation(self):
        auth = SupabaseJWTAuthentication()
        ok = auth._upsert_local_user({'email': 'old@example.com', 'confirmed_at': CONFIRMED})
        self.assertEqual(ok.email, 'old@example.com')
        with self.assertRaises(Exception) as ctx:
            auth._upsert_local_user({
                'email': 'phone@example.com', 'confirmed_at': CONFIRMED, 'phone_confirmed_at': CONFIRMED,
            })
        self.assertEqual(ctx.exception.detail['code'], 'email_not_confirmed')


class ProfileMetadataSyncTests(_SupabaseAuthTestCase):
    def test_profile_edits_survive_the_next_request(self):
        User.objects.create_user(
            username='doc', email='doc@example.com', password='x-Long-passw0rd',
            first_name='Edited', last_name='Name', target_exam='NEET PG',
        )
        payload = _identity('doc@example.com', user_metadata={
            'first_name': 'Signup', 'last_name': 'Value', 'avatar_url': 'https://img.example.com/a.png',
        })
        r = self.bearer('tok-doc', payload).get('/api/auth/profile/')
        self.assertEqual(r.status_code, 200)
        user = User.objects.get(email='doc@example.com')
        self.assertEqual((user.first_name, user.last_name, user.target_exam), ('Edited', 'Name', 'NEET PG'))
        # Empty local values are still filled in.
        self.assertEqual(user.avatar_url, 'https://img.example.com/a.png')

    def test_settings_edit_is_not_reverted(self):
        User.objects.create_user(username='edit', email='edit@example.com', password='x-Long-passw0rd')
        client = self.bearer('tok-edit', _identity('edit@example.com', user_metadata={'first_name': 'Signup'}))
        self.assertEqual(client.get('/api/auth/profile/').data['first_name'], 'Signup')
        r = client.patch('/api/auth/profile/', {'first_name': 'Renamed', 'target_exam': 'NEET PG'}, format='json')
        self.assertEqual(r.status_code, 200)
        again = client.get('/api/auth/profile/').data
        self.assertEqual(again['first_name'], 'Renamed')
        self.assertEqual(again['target_exam'], 'NEET PG')

    def test_new_oauth_user_gets_name_and_avatar(self):
        payload = _identity('g@example.com', user_metadata={
            'full_name': 'Asha Rao', 'picture': 'https://lh3.example.com/p.jpg',
        })
        r = self.bearer('tok-g', payload).get('/api/auth/profile/')
        self.assertEqual(r.status_code, 200)
        user = User.objects.get(email='g@example.com')
        self.assertEqual((user.first_name, user.last_name), ('Asha', 'Rao'))
        self.assertEqual(user.avatar_url, 'https://lh3.example.com/p.jpg')
        self.assertEqual(user.target_exam, 'UPSC CMS')


class SuperuserMintingTests(_SupabaseAuthTestCase):
    def test_role_toggle_grants_admin_without_superuser(self):
        boss = User.objects.create_user(
            username='boss2', email='boss2@example.com', password='x-Long-passw0rd',
            role='admin', is_superuser=True, is_staff=True,
        )
        target = User.objects.create_user(username='promo', email='promo@example.com', password='x-Long-passw0rd')
        # A student signs in (linking the row to their Supabase identity)
        # before an admin promotes them in the app.
        self.assertEqual(self.bearer('tok-promo', _identity('promo@example.com')).get('/api/auth/profile/').status_code, 200)
        client = APIClient()
        client.force_authenticate(boss)
        r = client.patch(f'/api/auth/admin/users/{target.id}/role/', {'role': 'admin'}, format='json')
        self.assertEqual(r.status_code, 200)
        target.refresh_from_db()
        self.assertEqual(target.role, 'admin')
        self.assertTrue(target.is_staff)
        self.assertFalse(target.is_superuser)

        # The next Supabase sign-in keeps them admin but does not re-mint superuser.
        r = self.bearer('tok-promo', _identity('promo@example.com')).get('/api/auth/admin/users/')
        self.assertEqual(r.status_code, 200)
        target.refresh_from_db()
        self.assertEqual(target.role, 'admin')
        self.assertFalse(target.is_superuser)

        r = client.patch(f'/api/auth/admin/users/{target.id}/role/', {'role': 'student'}, format='json')
        self.assertEqual(r.status_code, 200)
        target.refresh_from_db()
        self.assertEqual((target.role, target.is_staff, target.is_superuser), ('student', False, False))

    def test_demoting_a_superuser_removes_superuser(self):
        boss = User.objects.create_user(
            username='boss3', email='boss3@example.com', password='x-Long-passw0rd',
            role='admin', is_superuser=True, is_staff=True,
        )
        other = User.objects.create_user(
            username='su', email='su@example.com', password='x-Long-passw0rd',
            role='admin', is_superuser=True, is_staff=True,
        )
        client = APIClient()
        client.force_authenticate(boss)
        client.patch(f'/api/auth/admin/users/{other.id}/role/', {'role': 'student'}, format='json')
        other.refresh_from_db()
        self.assertFalse(other.is_admin)

    def test_trusted_app_metadata_still_promotes_to_superuser(self):
        User.objects.create_user(username='meta', email='meta@example.com', password='x-Long-passw0rd')
        self.bearer('tok-meta', _identity('meta@example.com', app_metadata={'role': 'admin'})).get('/api/auth/profile/')
        user = User.objects.get(email='meta@example.com')
        self.assertEqual((user.role, user.is_superuser, user.is_staff), ('admin', True, True))

    def test_user_metadata_never_promotes(self):
        self.bearer('tok-self', _identity('self@example.com', user_metadata={'role': 'admin', 'is_admin': True})).get('/api/auth/profile/')
        user = User.objects.get(email='self@example.com')
        self.assertEqual((user.role, user.is_superuser, user.is_staff), ('student', False, False))


class DeviceLimitTests(_SupabaseAuthTestCase):
    # A device-limited request. (GET /api/auth/tokens/ is exempt since wave 3:
    # the Header reads it on /subscription, where the over-limit device buys
    # the 4-device plan.)
    PROBE = '/api/auth/tokens/history/'

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(username='dev', email='dev@example.com', password='x-Long-passw0rd')
        self.payload = _identity('dev@example.com')

    def client_for(self, device):
        return self.bearer('tok-dev', self.payload, device=device)

    def test_third_device_is_refused_for_a_free_user(self):
        self.assertEqual(self.client_for(DEVICE_A).get('/api/auth/tokens/').status_code, 200)
        self.assertEqual(self.client_for(DEVICE_B).get('/api/auth/tokens/').status_code, 200)
        r = self.client_for(DEVICE_C).get(self.PROBE)
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.data['code'], 'device_limit_reached')
        self.assertFalse(UserDevice.objects.filter(user=self.user, device_fingerprint=DEVICE_C).exists())
        # Both enrolled devices keep working.
        self.assertEqual(self.client_for(DEVICE_A).get('/api/auth/tokens/').status_code, 200)

    def test_over_limit_device_can_reach_device_management_and_free_a_slot(self):
        self.client_for(DEVICE_A).get('/api/auth/tokens/')
        self.client_for(DEVICE_B).get('/api/auth/tokens/')
        third = self.client_for(DEVICE_C)
        devices = third.get('/api/auth/devices/')
        self.assertEqual(devices.status_code, 200)
        self.assertEqual(len(devices.data), 2)
        self.assertEqual(third.get('/api/auth/profile/').status_code, 200)

        device_a = UserDevice.objects.get(user=self.user, device_fingerprint=DEVICE_A)
        r = third.post('/api/auth/devices/logout/', {'device_id': device_a.id}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(third.get('/api/auth/tokens/').status_code, 200)

        # The logged-out device is told so (the frontend then signs out and
        # drops its device id, so a fresh sign-in enrols a new device).
        r = self.client_for(DEVICE_A).get('/api/auth/tokens/')
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.data['code'], 'device_inactive')

    def test_subscribed_user_gets_four_devices(self):
        # An active plan (Subscription row); the bare is_subscribed flag no
        # longer decides it (tests_z4_auth_hardening).
        from accounts.models import Subscription
        Subscription.objects.create(
            user=self.user, plan='1_month', status='active', expires_at=timezone.now() + timedelta(days=20),
        )
        for i in range(4):
            self.assertEqual(self.client_for(f'dev_device{i:08d}_x').get('/api/auth/tokens/').status_code, 200)
        r = self.client_for('dev_device00000004_x').get(self.PROBE)
        self.assertEqual(r.data['code'], 'device_limit_reached')

    def test_after_a_downgrade_the_least_recently_used_device_is_refused(self):
        now = timezone.now()
        for offset, fp in ((30, DEVICE_A), (20, DEVICE_B), (10, DEVICE_C)):
            device = UserDevice.objects.create(user=self.user, device_fingerprint=fp, is_active=True)
            UserDevice.objects.filter(pk=device.pk).update(last_login=now - timedelta(minutes=offset))
        r = self.client_for(DEVICE_A).get(self.PROBE)
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.data['code'], 'device_limit_reached')
        # A refused request must not refresh last_login (or it would win its slot back).
        stale = UserDevice.objects.get(user=self.user, device_fingerprint=DEVICE_A)
        self.assertLess(stale.last_login, now - timedelta(minutes=29))
        self.assertEqual(self.client_for(DEVICE_B).get('/api/auth/tokens/').status_code, 200)
        self.assertEqual(self.client_for(DEVICE_C).get('/api/auth/tokens/').status_code, 200)

    def test_devices_unseen_for_30_days_do_not_block_a_new_device(self):
        old = timezone.now() - timedelta(days=45)
        for fp in ('dev_oldoldold01_x', 'dev_oldoldold02_x', 'dev_oldoldold03_x'):
            device = UserDevice.objects.create(user=self.user, device_fingerprint=fp, is_active=True)
            UserDevice.objects.filter(pk=device.pk).update(last_login=old)
        self.assertEqual(self.client_for(DEVICE_A).get('/api/auth/tokens/').status_code, 200)
        self.assertEqual(self.client_for(DEVICE_B).get('/api/auth/tokens/').status_code, 200)
        r = self.client_for(DEVICE_C).get(self.PROBE)
        self.assertEqual(r.data['code'], 'device_limit_reached')

    def test_requests_without_or_with_spoofed_device_header_are_not_enrolled(self):
        # These fake tokens carry no Supabase session id (real access tokens
        # always do, and are then counted per session even without the
        # header: tests_z4_auth_hardening.SessionBoundDeviceTests).
        self.assertEqual(self.bearer('tok-dev', self.payload).get('/api/auth/tokens/').status_code, 200)
        self.assertEqual(self.client_for('1').get('/api/auth/tokens/').status_code, 200)
        self.assertFalse(UserDevice.objects.filter(user=self.user).exists())

    def test_admins_are_exempt(self):
        # A linked admin row (unlinked admin rows are not linked by email).
        User.objects.filter(pk=self.user.pk).update(role='admin', supabase_uid=self.payload['id'])
        for fp in (DEVICE_A, DEVICE_B, DEVICE_C):
            self.assertEqual(self.client_for(fp).get('/api/auth/tokens/').status_code, 200)
