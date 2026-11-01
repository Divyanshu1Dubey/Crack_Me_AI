"""Wave 3 regression tests (Z4 auth / accounts).

M1  ACC-05 deploy lockout: an unlinked admin / staff row is linked on its first
    Supabase sign-in when the identity is the one the row was created from
    (created_at <= date_joined + tolerance, confirmed email); a newer identity
    is still refused (account_link_required)
M1  manage.py link_supabase_identity --all-privileged: dry run by default,
    --apply links each unlinked admin/staff row to the single confirmed
    Supabase user with its email (admin API mocked at the HTTP level), but
    only when that is the row's original identity (the sign-in rule); a newer
    or undated identity is reported as CHECK and skipped unless
    --include-newer-identities is given; --email warns about it
M2  a linked student identity switching to an allowlisted admin email is not
    promoted and its email does not follow; deploy checks W001 / W002 / W003
L   an over-limit device may still read /auth/tokens/ and announcements (GET)
L   scholarship question set persisted per user and attempt (no cache re-roll)
L   core-data backup refuses the ephemeral default path outside DEBUG
L   FreeShowcaseQuestion refuses scholarship-challenge questions
C8  device list rows carry is_current; C12 token balance carries unlimited_ai
W5  rerun-evaluation rebuilds subject-level (topic=NULL) rows like the live writers

No network: Supabase token checks use the fake token map of
_SupabaseAuthTestCase; the admin API is a patched urllib.urlopen.
"""
import io
import json
import os
import shutil
import tempfile
from datetime import timedelta, timezone as dt_timezone
from unittest import mock
from urllib import error as urlerror

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import AdminAuditLog, Subscription, UserDevice
from accounts.supabase_rest_auth import is_original_identity, supabase_created_at
from accounts.tests_wave1_auth import CONFIRMED, DEVICE_A, DEVICE_B, DEVICE_C, _SupabaseAuthTestCase

User = get_user_model()

UID_A = '33333333-3333-4333-8333-333333333333'
UID_B = '44444444-4444-4444-8444-444444444444'
UID_C = '55555555-5555-4555-8555-555555555555'
UID_LATE = '99999999-9999-4999-8999-999999999999'


def _iso(dt):
    return dt.astimezone(dt_timezone.utc).isoformat().replace('+00:00', 'Z')


def _identity(email, uid, *, created_at=None, confirmed=True, app_metadata=None):
    payload = {'id': uid, 'email': email, 'user_metadata': {}, 'app_metadata': app_metadata or {}}
    if confirmed:
        payload['email_confirmed_at'] = CONFIRMED
    if created_at is not None:
        payload['created_at'] = created_at if isinstance(created_at, str) else _iso(created_at)
    return payload


def _privileged_row(email, *, joined_ago=timedelta(days=30), **fields):
    fields.setdefault('role', 'admin')
    fields.setdefault('is_staff', True)
    row = User.objects.create_user(username=email.split('@')[0], email=email, password=None, **fields)
    User.objects.filter(pk=row.pk).update(date_joined=timezone.now() - joined_ago)
    row.refresh_from_db()
    return row


# ── M1: automatic link of the original identity ──────────────────────────

class OriginalIdentityLinkTests(_SupabaseAuthTestCase):
    def test_promoted_admin_created_from_the_identity_keeps_access(self):
        # Migration 0023 left supabase_uid empty; the row was created on this
        # identity's first sign-in (so the identity is older than the row).
        row = _privileged_row('promoted@example.com')
        identity = _identity('promoted@example.com', UID_A, created_at=row.date_joined - timedelta(seconds=20))
        with self.assertLogs('accounts.supabase_rest_auth', level='WARNING') as logs:
            r = self.bearer('tok-promoted', identity).get('/api/auth/admin/users/')
        self.assertEqual(r.status_code, 200, r.data)
        row.refresh_from_db()
        self.assertEqual(row.supabase_uid, UID_A)
        self.assertEqual((row.role, row.is_superuser), ('admin', False))  # no superuser minted
        self.assertTrue(any('identity predates the account' in line for line in logs.output))
        self.assertTrue(AdminAuditLog.objects.filter(
            resource_type='user', resource_id=str(row.pk), metadata__supabase_uid=UID_A,
        ).exists())
        # Later sign-ins are matched by the uid.
        self.assertEqual(self.bearer('tok-promoted-2', identity).get('/api/auth/admin/users/').status_code, 200)

    def test_small_clock_skew_is_tolerated(self):
        row = _privileged_row('skew@example.com')
        identity = _identity('skew@example.com', UID_A, created_at=row.date_joined + timedelta(minutes=2))
        self.assertEqual(self.bearer('tok-skew', identity).get('/api/auth/profile/').status_code, 200)
        row.refresh_from_db()
        self.assertEqual(row.supabase_uid, UID_A)

    def test_identity_newer_than_the_admin_row_is_refused(self):
        # A sign-up made after the row existed (takeover attempt while
        # "Confirm email" is off, or a re-created identity).
        row = _privileged_row('boss@example.com', is_superuser=True)
        identity = _identity('boss@example.com', UID_B, created_at=row.date_joined + timedelta(days=1))
        r = self.bearer('tok-late', identity).get('/api/auth/admin/users/')
        self.assertEqual((r.status_code, r.data['code']), (401, 'account_link_required'))
        row.refresh_from_db()
        self.assertIsNone(row.supabase_uid)
        self.assertEqual(User.objects.count(), 1)

    def test_missing_or_garbage_created_at_is_refused(self):
        row = _privileged_row('nodate@example.com')
        for token, created in (('tok-none', None), ('tok-bad', 'yesterday')):
            r = self.bearer(token, _identity('nodate@example.com', UID_A, created_at=created)).get('/api/auth/profile/')
            self.assertEqual((r.status_code, r.data['code']), (401, 'account_link_required'), created)
        row.refresh_from_db()
        self.assertIsNone(row.supabase_uid)

    def test_unconfirmed_identity_is_never_linked(self):
        row = _privileged_row('unconf@example.com')
        identity = _identity('unconf@example.com', UID_A, created_at=row.date_joined - timedelta(days=1), confirmed=False)
        r = self.bearer('tok-unconf', identity).get('/api/auth/profile/')
        self.assertEqual((r.status_code, r.data['code']), (401, 'email_not_confirmed'))
        row.refresh_from_db()
        self.assertIsNone(row.supabase_uid)

    def test_student_rows_still_link_whatever_the_dates(self):
        row = User.objects.create_user(username='stu', email='stu@example.com', password=None)
        identity = _identity('stu@example.com', UID_A, created_at=timezone.now() + timedelta(days=3))
        self.assertEqual(self.bearer('tok-stu', identity).get('/api/auth/profile/').status_code, 200)
        row.refresh_from_db()
        self.assertEqual(row.supabase_uid, UID_A)


class OriginalIdentityHelperTests(SimpleTestCase):
    def setUp(self):
        self.row = mock.Mock(date_joined=timezone.now())

    def test_parses_gotrue_timestamps(self):
        joined = self.row.date_joined
        for raw in (_iso(joined - timedelta(hours=1)), (joined - timedelta(hours=1)).isoformat(),
                    (joined - timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%S.%f')):
            self.assertIsNotNone(supabase_created_at({'created_at': raw}), raw)
            self.assertTrue(is_original_identity({'created_at': raw, 'email_confirmed_at': CONFIRMED}, self.row), raw)

    def test_phone_only_confirmation_does_not_count(self):
        payload = {
            'created_at': _iso(self.row.date_joined - timedelta(days=1)),
            'confirmed_at': CONFIRMED, 'phone_confirmed_at': CONFIRMED,
        }
        self.assertFalse(is_original_identity(payload, self.row))
        payload.pop('phone_confirmed_at')
        self.assertTrue(is_original_identity(payload, self.row))


# ── M2: allowlist elevation never follows an unconfirmed email change ────

@mock.patch.dict('os.environ', {'CONTROL_TOWER_ADMIN_EMAILS': 'owner@example.com'})
class AllowlistEmailChangeTests(_SupabaseAuthTestCase):
    def test_student_switching_to_an_allowlisted_email_is_not_promoted(self):
        row = User.objects.create_user(username='stud', email='stud@example.com', password=None, supabase_uid=UID_A)
        client = self.bearer('tok-switch', _identity('owner@example.com', UID_A))
        with self.assertLogs('accounts.supabase_rest_auth', level='WARNING'):
            self.assertEqual(client.get('/api/auth/profile/').status_code, 200)
        self.assertEqual(client.get('/api/auth/admin/users/').status_code, 403)
        row.refresh_from_db()
        self.assertEqual((row.role, row.is_superuser, row.is_staff, row.email), ('student', False, False, 'stud@example.com'))

    def test_allowlisted_owner_with_the_same_email_is_promoted(self):
        row = User.objects.create_user(username='own', email='owner@example.com', password=None, supabase_uid=UID_A)
        r = self.bearer('tok-own', _identity('owner@example.com', UID_A)).get('/api/auth/admin/users/')
        self.assertEqual(r.status_code, 200)
        row.refresh_from_db()
        self.assertEqual(row.role, 'admin')

    def test_non_allowlisted_email_changes_still_follow(self):
        row = User.objects.create_user(username='mover', email='mover@example.com', password=None, supabase_uid=UID_A)
        self.assertEqual(self.bearer('tok-move', _identity('moved@example.com', UID_A)).get('/api/auth/profile/').status_code, 200)
        row.refresh_from_db()
        self.assertEqual(row.email, 'moved@example.com')


class DeploymentChecksTests(SimpleTestCase):
    PUBLIC_KEYS = ('SUPABASE_AUTH_VERIFY_KEY', 'SUPABASE_ANON_KEY', 'NEXT_PUBLIC_SUPABASE_ANON_KEY',
                   'SUPABASE_PUBLISHABLE_KEY', 'NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY')

    def env(self, **values):
        base = {name: '' for name in self.PUBLIC_KEYS}
        base.update({'SUPABASE_URL': '', 'NEXT_PUBLIC_SUPABASE_URL': '', 'SUPABASE_SERVICE_ROLE_KEY': '',
                     'SUPABASE_EMAIL_CONFIRMATION_ENABLED': '', 'CORE_DATA_BACKUP_PATH': ''})
        base.update(values)
        return mock.patch.dict('os.environ', base)

    @staticmethod
    def ids(results):
        return [m.id for m in results]

    def test_email_confirmation_reminder(self):
        from accounts.checks import supabase_email_confirmation_check as check
        with self.env(SUPABASE_URL='https://example.supabase.invalid'):
            self.assertEqual(self.ids(check()), ['accounts.W001'])
        with self.env(SUPABASE_URL='https://example.supabase.invalid', SUPABASE_EMAIL_CONFIRMATION_ENABLED='true'):
            self.assertEqual(check(), [])
        with self.env():
            self.assertEqual(check(), [])  # Supabase sign-in not configured

    def test_verify_key_warning(self):
        from accounts.checks import supabase_verify_key_check as check
        with self.env(SUPABASE_URL='https://example.supabase.invalid', SUPABASE_SERVICE_ROLE_KEY='test-only'):
            results = check()
            self.assertEqual(self.ids(results), ['accounts.W002'])
            self.assertIn('service-role', results[0].msg)
        with self.env(SUPABASE_URL='https://example.supabase.invalid', SUPABASE_ANON_KEY='test-anon'):
            self.assertEqual(check(), [])

    def test_backup_path_warning(self):
        from accounts.checks import core_data_backup_path_check as check
        with self.env(), override_settings(DEBUG=False):
            self.assertEqual(self.ids(check()), ['accounts.W003'])
        with self.env(CORE_DATA_BACKUP_PATH='/data/core.json'), override_settings(DEBUG=False):
            self.assertEqual(check(), [])
        with self.env(), override_settings(DEBUG=True):
            self.assertEqual(check(), [])

    def test_checks_are_deploy_only(self):
        from django.core.checks import run_checks
        with self.env(SUPABASE_URL='https://example.supabase.invalid', SUPABASE_SERVICE_ROLE_KEY='test-only'):
            self.assertNotIn('accounts.W001', self.ids(run_checks()))
            deploy_ids = self.ids(run_checks(include_deployment_checks=True))
        self.assertIn('accounts.W001', deploy_ids)
        self.assertIn('accounts.W002', deploy_ids)


# ── M1: manage.py link_supabase_identity --all-privileged ────────────────

class _FakeResponse:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode('utf-8')
        self.status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._body


@mock.patch.dict('os.environ', {'SUPABASE_URL': 'https://example.supabase.invalid', 'SUPABASE_SERVICE_ROLE_KEY': 'test-service-role'})
class LinkAllPrivilegedCommandTests(TestCase):
    def setUp(self):
        self.a1 = _privileged_row('a1@example.com')                                    # one confirmed identity
        self.a2 = _privileged_row('a2@example.com')                                    # identity unconfirmed
        self.a3 = _privileged_row('a3@example.com', role='student')                    # staff only, no identity
        self.a4 = _privileged_row('a4@example.com', is_active=False)                   # blocked
        self.a5 = _privileged_row('a5@example.com', supabase_uid=UID_B)                # already linked
        self.dup = _privileged_row('dup@example.com')                                  # two identities
        self.taken = _privileged_row('taken@example.com')                              # its identity is a5's uid
        self.student = User.objects.create_user(username='s1', email='s1@example.com', password=None)
        self.supabase_users = [
            # a1's identity is the one its row was created from (older than the row).
            {'id': UID_A, 'email': 'A1@example.com', 'email_confirmed_at': CONFIRMED,
             'created_at': _iso(self.a1.date_joined - timedelta(days=1))},
            {'id': UID_C, 'email': 'a2@example.com', 'email_confirmed_at': None},
            {'id': '66666666-6666-4666-8666-666666666666', 'email': 'dup@example.com', 'email_confirmed_at': CONFIRMED},
            {'id': '77777777-7777-4777-8777-777777777777', 'email': 'dup@example.com', 'email_confirmed_at': CONFIRMED},
            {'id': UID_B, 'email': 'taken@example.com', 'email_confirmed_at': CONFIRMED},
            {'id': '88888888-8888-4888-8888-888888888888', 'email': 's1@example.com', 'email_confirmed_at': CONFIRMED},
        ]
        self.requests = []

        def fake_urlopen(req, timeout=None):
            self.requests.append(req)
            return _FakeResponse({'users': self.supabase_users})

        patcher = mock.patch('accounts.supabase_auth.request.urlopen', side_effect=fake_urlopen)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_cmd(self, *args):
        out = io.StringIO()
        call_command('link_supabase_identity', *args, stdout=out)
        return out.getvalue()

    def uids(self):
        return {u.email: u.supabase_uid for u in User.objects.all()}

    def test_dry_run_reports_and_writes_nothing(self):
        before = self.uids()
        out = self.run_cmd('--all-privileged')
        self.assertIn(f'would link id={self.a1.pk}', out)
        self.assertIn('has not confirmed', out)
        self.assertIn('no Supabase user has this email', out)
        self.assertIn('blocked account', out)
        self.assertIn('several Supabase users', out)
        self.assertIn('already linked to account id=', out)
        self.assertIn('Dry run', out)
        self.assertEqual(self.uids(), before)
        # The admin API was called with the service-role key.
        self.assertIn('/auth/v1/admin/users', self.requests[0].full_url)
        self.assertEqual(self.requests[0].get_header('Authorization'), 'Bearer test-service-role')

    def test_apply_links_only_the_unambiguous_confirmed_rows(self):
        with self.assertLogs('accounts.link_identity', level='WARNING') as logs:
            out = self.run_cmd('--all-privileged', '--apply')
        self.assertIn('1 linked', out)
        uids = self.uids()
        self.assertEqual(uids['a1@example.com'], UID_A)
        for email in ('a2@example.com', 'a3@example.com', 'a4@example.com', 'dup@example.com',
                      'taken@example.com', 's1@example.com'):
            self.assertIsNone(uids[email], email)
        self.assertEqual(uids['a5@example.com'], UID_B)
        self.assertTrue(any(UID_A in line for line in logs.output))
        self.assertTrue(AdminAuditLog.objects.filter(resource_id=str(self.a1.pk), metadata__supabase_uid=UID_A).exists())
        # A second run has nothing left to do for a1.
        self.assertNotIn(f'id={self.a1.pk} ', self.run_cmd('--all-privileged'))

    def test_failed_admin_api_call_is_an_error_not_no_such_user(self):
        with mock.patch('accounts.supabase_auth.request.urlopen', side_effect=urlerror.URLError('down')):
            with self.assertRaisesMessage(CommandError, 'Could not list Supabase users'):
                self.run_cmd('--all-privileged', '--apply')
        self.assertIsNone(User.objects.get(pk=self.a1.pk).supabase_uid)

    def test_needs_the_service_role_configuration(self):
        with mock.patch.dict('os.environ', {'SUPABASE_SERVICE_ROLE_KEY': ''}):
            with self.assertRaises(CommandError):
                self.run_cmd('--all-privileged')

    def test_uid_and_replace_only_with_email(self):
        with self.assertRaises(CommandError):
            self.run_cmd('--all-privileged', '--uid', UID_A)
        with self.assertRaises(CommandError):
            self.run_cmd()  # neither --email nor --all-privileged

    def test_email_mode_looks_up_through_the_same_api(self):
        self.run_cmd('--email', 'a1@example.com', '--apply')
        self.assertEqual(User.objects.get(pk=self.a1.pk).supabase_uid, UID_A)
        with self.assertRaisesMessage(CommandError, 'has not confirmed'):
            self.run_cmd('--email', 'a2@example.com', '--apply')

    # An identity created after the row is what someone signing up with an
    # admin's address looks like while "Confirm email" is off; the bulk mode
    # must refuse it exactly like the sign-in path does.
    def _newer_identity_row(self, created_at='+1d'):
        # An admin row created locally whose owner never had a Supabase identity,
        # plus a later confirmed sign-up with that email.
        row = _privileged_row('late@example.com', is_superuser=True)
        if created_at == '+1d':
            created_at = row.date_joined + timedelta(days=1)
        self.supabase_users.append(_identity('late@example.com', UID_LATE, created_at=created_at))
        return row

    def test_identity_newer_than_the_account_is_flagged_and_not_linked(self):
        late = self._newer_identity_row()
        out = self.run_cmd('--all-privileged')
        self.assertIn(f'CHECK id={late.pk} ', out)
        self.assertIn('AFTER the account joined', out)
        self.assertIn('--email late@example.com', out)
        self.assertNotIn(f'would link id={late.pk} ', out)
        self.assertIn(f'would link id={self.a1.pk} ', out)  # the original identity is still planned
        self.assertIn('1 of them need an owner check', out)

        out = self.run_cmd('--all-privileged', '--apply')
        self.assertIn('1 linked', out)
        self.assertIn(f'CHECK id={late.pk} ', out)
        late.refresh_from_db()
        self.assertIsNone(late.supabase_uid)
        self.assertFalse(AdminAuditLog.objects.filter(resource_id=str(late.pk)).exists())
        self.assertEqual(User.objects.get(pk=self.a1.pk).supabase_uid, UID_A)

    def test_identity_without_a_creation_date_needs_an_owner_check_too(self):
        late = self._newer_identity_row(created_at=None)
        out = self.run_cmd('--all-privileged', '--apply')
        self.assertIn(f'CHECK id={late.pk} ', out)
        self.assertIn('no creation date', out)
        late.refresh_from_db()
        self.assertIsNone(late.supabase_uid)

    def test_small_clock_skew_still_counts_as_the_original_identity(self):
        row = _privileged_row('skewed@example.com')
        self.supabase_users.append(_identity('skewed@example.com', UID_LATE, created_at=row.date_joined + timedelta(minutes=2)))
        self.run_cmd('--all-privileged', '--apply')
        row.refresh_from_db()
        self.assertEqual(row.supabase_uid, UID_LATE)

    def test_include_newer_identities_links_them_and_records_it(self):
        late = self._newer_identity_row()
        out = self.run_cmd('--all-privileged', '--include-newer-identities')
        self.assertIn(f'would link id={late.pk} ', out)
        self.assertIn('AFTER the account joined', out)  # still flagged in the report
        late.refresh_from_db()
        self.assertIsNone(late.supabase_uid)  # dry run

        with self.assertLogs('accounts.link_identity', level='WARNING') as logs:
            out = self.run_cmd('--all-privileged', '--include-newer-identities', '--apply')
        self.assertIn('2 linked', out)
        late.refresh_from_db()
        self.assertEqual(late.supabase_uid, UID_LATE)
        self.assertTrue(any(UID_LATE in line and '--include-newer-identities' in line for line in logs.output))
        audit = AdminAuditLog.objects.get(resource_id=str(late.pk), metadata__supabase_uid=UID_LATE)
        self.assertIs(audit.metadata['original_identity'], False)
        self.assertIn('--include-newer-identities', audit.metadata['source'])
        a1_audit = AdminAuditLog.objects.get(resource_id=str(self.a1.pk), metadata__supabase_uid=UID_A)
        self.assertIs(a1_audit.metadata['original_identity'], True)

    def test_email_mode_warns_about_a_newer_identity_and_links_on_apply(self):
        # --email names one account: the operator has confirmed the owner.
        late = self._newer_identity_row()
        out = self.run_cmd('--email', 'late@example.com')
        self.assertIn('CHECK', out)
        self.assertIn('AFTER the account joined', out)
        self.assertIn('Would link', out)
        late.refresh_from_db()
        self.assertIsNone(late.supabase_uid)
        out = self.run_cmd('--email', 'late@example.com', '--apply')
        self.assertIn('AFTER the account joined', out)
        late.refresh_from_db()
        self.assertEqual(late.supabase_uid, UID_LATE)
        self.assertNotIn('CHECK', self.run_cmd('--email', 'a1@example.com'))  # original identity: no warning

    def test_include_newer_identities_only_with_all_privileged(self):
        with self.assertRaisesMessage(CommandError, '--include-newer-identities'):
            self.run_cmd('--email', 'a1@example.com', '--include-newer-identities')


# ── device limit, devices, token balance ─────────────────────────────────

class DeviceLimitBackgroundReadsTests(_SupabaseAuthTestCase):
    def setUp(self):
        super().setUp()
        User.objects.create_user(username='dev3', email='dev3@example.com', password=None)
        self.payload = _identity('dev3@example.com', UID_A)
        for device in (DEVICE_A, DEVICE_B):
            self.assertEqual(self.bearer('tok-dev3', self.payload, device=device).get('/api/auth/tokens/').status_code, 200)
        self.third = self.bearer('tok-dev3', self.payload, device=DEVICE_C)

    def test_header_reads_work_on_the_over_limit_device_without_taking_a_slot(self):
        self.assertEqual(self.third.get('/api/auth/tokens/').status_code, 200)
        self.assertEqual(self.third.get('/api/analytics/announcements/').status_code, 200)
        self.assertEqual(self.third.get('/api/auth/profile/').status_code, 200)
        self.assertFalse(UserDevice.objects.filter(device_fingerprint=DEVICE_C).exists())

    def test_everything_else_is_still_refused(self):
        for method, path in (('get', '/api/auth/tokens/history/'), ('post', '/api/auth/tokens/purchase/'),
                             ('get', '/api/analytics/dashboard/')):
            r = getattr(self.third, method)(path)
            self.assertEqual((r.status_code, r.data.get('code')), (401, 'device_limit_reached'), path)


class DeviceIsCurrentTests(_SupabaseAuthTestCase):
    def test_only_the_requesting_device_is_current(self):
        User.objects.create_user(username='cur', email='cur@example.com', password=None)
        payload = _identity('cur@example.com', UID_A)
        self.bearer('tok-cur', payload, device=DEVICE_B).get('/api/auth/profile/')
        rows = self.bearer('tok-cur', payload, device=DEVICE_A).get('/api/auth/devices/').data
        by_fingerprint = {
            UserDevice.objects.get(pk=row['id']).device_fingerprint: row['is_current'] for row in rows
        }
        self.assertEqual(by_fingerprint, {DEVICE_A: True, DEVICE_B: False})
        rows = self.bearer('tok-cur', payload).get('/api/auth/devices/').data  # no X-Session-ID
        self.assertEqual([row['is_current'] for row in rows], [False, False])


class TokenBalanceUnlimitedAiTests(TestCase):
    def balance(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client.get('/api/auth/tokens/').data

    def test_unlimited_ai_mirrors_the_metering_rule(self):
        now = timezone.now()
        user = User.objects.create_user(username='tb', email='tb@example.com', password=None)
        self.assertFalse(self.balance(user)['unlimited_ai'])
        monthly = Subscription.objects.create(user=user, plan='1_month', status='active', expires_at=now + timedelta(days=20))
        self.assertFalse(self.balance(user)['unlimited_ai'])
        monthly.delete()
        yearly = Subscription.objects.create(user=user, plan='1_year', status='active', expires_at=now + timedelta(days=200))
        self.assertTrue(self.balance(user)['unlimited_ai'])
        Subscription.objects.filter(pk=yearly.pk).update(expires_at=now - timedelta(days=1))
        self.assertFalse(self.balance(user)['unlimited_ai'])


# ── scholarship question set persistence ─────────────────────────────────

class ScholarshipSetPersistenceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from questions.models import Question, Subject

        subject = Subject.objects.create(name='Medicine W3', code='med-w3')
        cls.eligible = [
            Question.objects.create(
                question_text=f'Eligible {i}?', option_a='A', option_b='B', option_c='C', option_d='D',
                correct_answer='A', year=2024, subject=subject, is_scholarship_eligible=True,
            ).pk
            for i in range(12)
        ]

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='sch3', email='sch3@local.test', password=None)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def start(self):
        r = self.client.post('/api/auth/scholarship/start/')
        self.assertEqual(r.status_code, 200, r.data)
        return [q['id'] for q in r.data['questions']], r.data['challenge_token']

    def test_the_set_survives_cache_loss_and_token_expiry(self):
        first, _ = self.start()
        cache.clear()  # Redis flushed / down / an hour later: no re-roll
        self.assertEqual(self.start()[0], first)
        self.user.refresh_from_db()
        self.assertEqual(self.user.scholarship_challenge, {'n': 0, 'q': first})

    def test_a_token_for_another_set_is_refused(self):
        from accounts.views import _issue_scholarship_challenge

        stored, _ = self.start()
        other = sorted(set(self.eligible) - set(stored))[:5]
        token = _issue_scholarship_challenge(self.user.pk, other, 0)
        r = self.client.post('/api/auth/verify-scholarship/', {
            'answers': {str(qid): 'A' for qid in other}, 'challenge_token': token,
        }, format='json')
        self.assertEqual((r.status_code, r.data.get('code')), (400, 'scholarship_not_started'))
        self.user.refresh_from_db()
        self.assertEqual((self.user.scholarship_test_attempts, self.user.scholarship_test_passed), (0, False))

    def test_submitting_clears_the_set_and_the_next_attempt_draws_again(self):
        ids, token = self.start()
        r = self.client.post('/api/auth/verify-scholarship/', {
            'answers': {str(qid): 'B' for qid in ids}, 'challenge_token': token,
        }, format='json')
        self.assertEqual(r.data['status'], 'failed')
        self.user.refresh_from_db()
        self.assertEqual((self.user.scholarship_test_attempts, self.user.scholarship_challenge), (1, None))
        second, _ = self.start()
        self.user.refresh_from_db()
        self.assertEqual(self.user.scholarship_challenge, {'n': 1, 'q': second})

    def test_a_question_that_is_no_longer_eligible_is_replaced_alone(self):
        from questions.models import Question

        first, _ = self.start()
        Question.objects.filter(pk=first[0]).update(is_scholarship_eligible=False)
        second, _ = self.start()
        self.assertEqual(len(second), 5)
        self.assertNotIn(first[0], second)
        self.assertEqual(set(second) & set(first), set(first[1:]))


# ── core data backup path ────────────────────────────────────────────────

@mock.patch.dict('os.environ', {'CORE_DATA_BACKUP_PATH': ''})
class CoreDataBackupPathTests(TestCase):
    def setUp(self):
        cache.clear()
        admin = User.objects.create_user(username='bkops', email='bkops@local.test', password=None,
                                         role='admin', is_superuser=True, is_staff=True)
        self.client = APIClient()
        self.client.force_authenticate(admin)

    @override_settings(DEBUG=False)
    def test_production_refuses_the_ephemeral_default(self):
        from accounts.core_data_backup import CoreDataBackupNotConfigured, core_data_backup_path

        with self.assertRaises(CoreDataBackupNotConfigured):
            core_data_backup_path()
        for path in ('backup-data', 'restore-data'):
            r = self.client.post(f'/api/auth/admin/system/{path}/')
            self.assertEqual((r.status_code, r.data.get('code')), (503, 'backup_not_configured'), path)
            self.assertIn('CORE_DATA_BACKUP_PATH', r.data['error'])
        with self.assertRaisesMessage(CommandError, 'CORE_DATA_BACKUP_PATH'):
            call_command('backup_core_data', stdout=io.StringIO())

    @override_settings(DEBUG=False)
    def test_an_explicit_path_still_works_in_production(self):
        tmpdir = tempfile.mkdtemp(prefix='z4-backup-')
        self.addCleanup(shutil.rmtree, tmpdir, ignore_errors=True)
        target = os.path.join(tmpdir, 'core.json')
        call_command('backup_core_data', output=target, stdout=io.StringIO())
        self.assertTrue(os.path.isfile(target))

    @override_settings(DEBUG=True)
    def test_local_development_keeps_the_default(self):
        from accounts.core_data_backup import core_data_backup_path

        self.assertTrue(core_data_backup_path().endswith('core_data_seed.json'))


# ── free showcase curation ───────────────────────────────────────────────

class FreeShowcaseCurationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from questions.models import Question, Subject

        subject = Subject.objects.create(name='Showcase W3', code='shw-w3')
        common = dict(option_a='A', option_b='B', option_c='C', option_d='D', correct_answer='A', year=2024, subject=subject)
        cls.normal = Question.objects.create(question_text='Free?', **common)
        cls.scholarship = Question.objects.create(question_text='Challenge?', is_scholarship_eligible=True, **common)

    def test_model_validation_refuses_scholarship_questions(self):
        from accounts.models_freemium import FreeShowcaseQuestion

        with self.assertRaises(ValidationError) as ctx:
            FreeShowcaseQuestion(question=self.scholarship, year=2024, position=0).full_clean()
        self.assertIn('question', ctx.exception.message_dict)
        FreeShowcaseQuestion(question=self.normal, year=2024, position=1).full_clean()

    def test_django_admin_form_refuses_them(self):
        # The admin change form (not rendered: tests have no collected static manifest).
        from django.contrib import admin as django_admin
        from django.test import RequestFactory

        from accounts.models_freemium import FreeShowcaseQuestion

        request = RequestFactory().post('/admin/accounts/freeshowcasequestion/add/')
        request.user = User.objects.create_user(username='dj', email='dj@local.test', password=None,
                                                role='admin', is_superuser=True, is_staff=True)
        form_class = django_admin.site._registry[FreeShowcaseQuestion].get_form(request)
        form = form_class(data={'question': self.scholarship.pk, 'year': 2024, 'position': 0})
        self.assertFalse(form.is_valid())
        self.assertIn('scholarship-challenge', str(form.errors['question']))
        form = form_class(data={'question': self.normal.pk, 'year': 2024, 'position': 0})
        self.assertTrue(form.is_valid(), form.errors)


# ── rerun evaluation ─────────────────────────────────────────────────────

class RerunEvaluationSubjectRowsTests(TestCase):
    def setUp(self):
        from questions.models import Question, QuestionAttempt, Subject, Topic
        from tests_engine.models import QuestionResponse, Test, TestAttempt

        cache.clear()
        admin = User.objects.create_user(username='evops', email='evops@local.test', password=None,
                                         role='admin', is_superuser=True, is_staff=True)
        self.client = APIClient()
        self.client.force_authenticate(admin)
        self.student = User.objects.create_user(username='evstu', email='evstu@local.test', password=None)
        self.subject = Subject.objects.create(name='Rerun W3', code='rr-w3')
        self.topic = Topic.objects.create(name='Rerun topic', subject=self.subject)
        common = dict(option_a='A', option_b='B', option_c='C', option_d='D', correct_answer='A', year=2024, subject=self.subject)
        q1, q2, q4, q5 = (Question.objects.create(question_text=f'T{i}?', topic=self.topic, **common) for i in (1, 2, 4, 5))
        q3 = Question.objects.create(question_text='No topic?', **common)
        test = Test.objects.create(title='Mock', test_type='mixed', num_questions=4, time_limit_minutes=10,
                                   created_by=admin, is_published=True)
        attempt = TestAttempt.objects.create(user=self.student, test=test, is_completed=True)
        for question, selected, correct, seconds in ((q1, 'A', True, 30), (q2, 'B', False, 20),
                                                     (q3, 'A', True, 10), (q4, None, None, 5)):
            QuestionResponse.objects.create(attempt=attempt, question=question, selected_answer=selected,
                                            is_correct=correct, time_taken_seconds=seconds)
        QuestionAttempt.objects.create(user=self.student, question=q5, selected_answer='A', is_correct=True)
        QuestionAttempt.objects.create(user=self.student, question=q3, selected_answer='C', is_correct=False)

    def rerun(self):
        r = self.client.post('/api/auth/admin/system/rerun-evaluation/',
                             {'scope': 'user', 'user_id': self.student.pk}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        return r.data['results']

    def rows(self):
        from analytics.models import UserTopicPerformance

        return {
            row.topic_id: (row.total_attempts, row.correct_answers, row.incorrect_answers, row.total_time_seconds)
            for row in UserTopicPerformance.objects.filter(user=self.student, subject=self.subject)
        }

    def test_subject_and_topic_rows_match_the_live_writers(self):
        results = self.rerun()
        # Subject row: 3 answered test questions (q4 unanswered is skipped) + 2 QBank answers.
        # Topic row: q1, q2 + QBank q5. q3 (no topic) counts in the subject row only.
        self.assertEqual(self.rows(), {None: (5, 3, 2, 60), self.topic.pk: (3, 2, 1, 50)})
        self.assertEqual((results['processed_responses'], results['processed_qbank_answers']), (3, 2))
        self.assertEqual(results['subject_rows_created'], 1)

        from analytics.views import subject_totals
        totals = subject_totals(self.student)
        self.assertEqual([(t['total'], t['correct']) for t in totals], [(5, 3)])

    def test_rerun_is_repeatable(self):
        self.rerun()
        self.rerun()  # no duplicate subject-level row (uniq_subject_level_topic_performance)
        self.assertEqual(self.rows(), {None: (5, 3, 2, 60), self.topic.pk: (3, 2, 1, 50)})


class FreemiumSeedOncePerMigrateTests(SimpleTestCase):
    def test_seed_runs_for_the_accounts_sender_only(self):
        from django.apps import apps

        from accounts import signals

        with mock.patch.object(signals, 'ensure_freemium_seed') as seed:
            signals.freemium_post_migrate(sender=apps.get_app_config('questions'))
            seed.assert_not_called()
            signals.freemium_post_migrate(sender=apps.get_app_config('accounts'))
            seed.assert_called_once_with()


class AccountsMigrationsTests(TestCase):
    def test_models_and_migrations_agree(self):
        out = io.StringIO()
        try:
            call_command('makemigrations', 'accounts', '--check', '--dry-run', stdout=out, stderr=io.StringIO())
        except SystemExit:
            self.fail(f'accounts has model changes without a migration:\n{out.getvalue()}')
