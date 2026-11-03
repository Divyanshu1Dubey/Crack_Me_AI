"""manage.py import_supabase_auth: Supabase Auth users, bcrypt hashes and Google subs into Django accounts.

The source is faked (accounts.management.commands.import_supabase_auth.load_source
is patched) or read through a fake DB-API cursor; nothing connects anywhere.
"""
import io
import json
import re
import tempfile
import uuid
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from pathlib import Path
from unittest import mock

import bcrypt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts import supabase_import as si
from accounts.management.commands import import_supabase_auth as command_module
from accounts.models import AdminAuditLog, Subscription, TokenBalance, TokenTransaction, UserIdentity

User = get_user_model()

T0 = datetime(2025, 3, 1, 12, 0, tzinfo=dt_timezone.utc)
PASSWORD = 'Imported-Passw0rd!z'
FAST_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher', 'accounts.hashers.SupabaseBcryptPasswordHasher']


def gotrue_hash(password=PASSWORD):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(4, prefix=b'2a')).decode()


def auth_user(email, *, uid=None, created=T0, confirmed=T0, password='', user_meta=None, app_meta=None, **extra):
    return si.AuthUser(
        id=uid or str(uuid.uuid4()), email=email, encrypted_password=password,
        email_confirmed_at=confirmed, created_at=created, last_sign_in_at=created + timedelta(days=3),
        user_metadata=user_meta or {}, app_metadata=app_meta or {}, **extra,
    )


def google_identity(user, sub, *, email=None, data_sub=None):
    return si.AuthIdentity(
        id=str(uuid.uuid4()), user_id=user.id, provider='google', provider_id=sub,
        identity_data={'sub': sub if data_sub is None else data_sub, 'email': email or user.email,
                       'email_verified': True},
        email=email or user.email,
    )


def django_row(username, email, *, joined=T0 + timedelta(hours=1), password=None, **fields):
    user = User.objects.create_user(username=username, email=email, password=password, **fields)
    User.objects.filter(pk=user.pk).update(date_joined=joined)
    user.refresh_from_db()
    return user


@override_settings(PASSWORD_HASHERS=FAST_HASHERS)
class _ImportTestCase(TestCase):
    def run_import(self, users, identities=(), *args, referencing=()):
        out = io.StringIO()
        source = (list(users), list(identities), list(referencing), 'a test source')
        with mock.patch.object(command_module, 'load_source', return_value=source):
            with self.captureOnCommitCallbacks(execute=True):
                call_command('import_supabase_auth', *args, stdout=out, stderr=io.StringIO())
        return out.getvalue()

    def counts(self, output):
        return {m.group(1): int(m.group(2)) for m in re.finditer(r'^\s+([A-Z_]+)\s+(\d+)$', output, re.M)}


class ImportLinkTests(_ImportTestCase):
    def test_dry_run_writes_nothing_and_prints_no_personal_data(self):
        row = django_row('doc', 'doc@example.com')
        user = auth_user('doc@example.com', password=gotrue_hash())
        output = self.run_import([user], [google_identity(user, 'g-1')])
        self.assertEqual(self.counts(output)['LINK'], 1)
        self.assertIn('Dry run', output)
        row.refresh_from_db()
        self.assertIsNone(row.supabase_uid)
        self.assertIsNone(row.email_verified_at)
        self.assertFalse(UserIdentity.objects.exists())
        self.assertFalse(AdminAuditLog.objects.filter(action='identity_import').exists())
        verbose = io.StringIO()
        with mock.patch.object(command_module, 'load_source',
                               return_value=([user], [google_identity(user, 'g-1')], [], 's')):
            call_command('import_supabase_auth', verbosity=2, stdout=verbose)
        for text in (output, verbose.getvalue()):
            self.assertNotIn('@', text)
            self.assertNotIn('$2a$', text)
            self.assertNotIn(user.id, text)  # uid prefixes only

    def test_link_imports_hash_uid_verification_and_google_then_a_rerun_changes_nothing(self):
        row = django_row('doc', 'doc@example.com', first_name='')
        user = auth_user('doc@example.com', password=gotrue_hash(),
                         user_meta={'full_name': 'Asha Rao', 'avatar_url': 'https://cdn.example.com/a.png'})
        identity = google_identity(user, 'g-doc')
        output = self.run_import([user], [identity], '--apply')
        self.assertIn('Invariants hold', output)
        row.refresh_from_db()
        self.assertEqual(row.supabase_uid, user.id)
        self.assertTrue(row.password.startswith('supabase_bcrypt$$2a$'))
        self.assertEqual(row.email_verified_at, T0)
        self.assertEqual((row.first_name, row.last_name, row.avatar_url),
                         ('Asha', 'Rao', 'https://cdn.example.com/a.png'))
        imported = UserIdentity.objects.get(provider='google', subject='g-doc')
        self.assertEqual((imported.user_id, imported.source), (row.pk, 'supabase_import'))
        audit = AdminAuditLog.objects.get(action='identity_import')
        self.assertNotIn('doc@example.com', json.dumps(audit.metadata) + audit.detail)
        self.assertNotIn('$2a$', json.dumps(audit.metadata))

        logs = AdminAuditLog.objects.count()
        snapshot = User.objects.values().get(pk=row.pk)
        rerun = self.run_import([user], [identity], '--apply')
        self.assertEqual(self.counts(rerun)['ALREADY_LINKED'], 1)
        self.assertRegex(rerun, r'accounts unchanged\s+1')
        self.assertEqual(AdminAuditLog.objects.count(), logs)
        self.assertEqual(User.objects.values().get(pk=row.pk), snapshot)
        self.assertEqual(UserIdentity.objects.count(), 1)

    @override_settings(AUTH_PROVIDER='django')
    def test_the_original_password_signs_in_after_the_import(self):
        cache.clear()
        django_row('signer', 'signer@example.com')
        self.run_import([auth_user('signer@example.com', password=gotrue_hash())], (), '--apply')
        response = APIClient().post('/api/auth/native/login/', {'email': 'signer@example.com', 'password': PASSWORD},
                                    format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(User.objects.get(email='signer@example.com').password.startswith('supabase_bcrypt$'))
        # A re-run after the re-hash keeps the new hash.
        self.run_import([auth_user('signer@example.com', password=gotrue_hash(), uid=User.objects.get(
            email='signer@example.com').supabase_uid)], (), '--apply')
        self.assertFalse(User.objects.get(email='signer@example.com').password.startswith('supabase_bcrypt$'))

    def test_mixed_case_emails_match(self):
        row = django_row('mixed', 'Mixed.Case@Example.COM')
        stored = row.email  # the local part keeps its case
        user = auth_user('mixed.case@example.com')
        self.run_import([user], (), '--apply')
        row.refresh_from_db()
        self.assertEqual(row.supabase_uid, user.id)
        self.assertEqual(row.email, stored)  # never rewritten

    def test_ambiguous_and_linked_elsewhere_rows_are_skipped(self):
        django_row('dup1', 'dup@example.com')
        django_row('dup2', 'DUP@example.com')
        elsewhere = django_row('taken', 'taken@example.com')
        User.objects.filter(pk=elsewhere.pk).update(supabase_uid=str(uuid.uuid4()))
        twin_a, twin_b = auth_user('twin@example.com'), auth_user('TWIN@example.com')
        django_row('twin', 'twin@example.com')
        output = self.run_import([auth_user('dup@example.com'), auth_user('taken@example.com'), twin_a, twin_b], (),
                                 '--apply')
        counts = self.counts(output)
        self.assertEqual(counts['AMBIGUOUS_DJANGO_EMAIL'], 1)
        self.assertEqual(counts['CONFLICT_LINKED_ELSEWHERE'], 1)
        self.assertEqual(counts['AMBIGUOUS_AUTH_EMAIL'], 2)
        self.assertEqual(User.objects.exclude(supabase_uid__isnull=True).count(), 1)  # only the pre-linked row

    def test_a_newer_identity_is_checked_unless_included(self):
        old_row = django_row('veteran', 'veteran@example.com', joined=T0 - timedelta(days=200), password='Old-Django-1!')
        user = auth_user('veteran@example.com', password=gotrue_hash())
        output = self.run_import([user], [google_identity(user, 'g-vet')], '--apply')
        self.assertEqual(self.counts(output)['CHECK_NEWER_IDENTITY'], 1)
        old_row.refresh_from_db()
        self.assertIsNone(old_row.supabase_uid)
        self.assertTrue(old_row.check_password('Old-Django-1!'))
        self.assertFalse(UserIdentity.objects.exists())

        self.run_import([user], [google_identity(user, 'g-vet')], '--apply', '--include-newer-identities',
                        '--only-uid', user.id)
        old_row.refresh_from_db()
        self.assertEqual(old_row.supabase_uid, user.id)
        self.assertTrue(old_row.password.startswith('supabase_bcrypt$'))  # the usable student password is replaced
        self.assertTrue(UserIdentity.objects.filter(subject='g-vet', user=old_row).exists())


class ImportPasswordTests(_ImportTestCase):
    def test_privileged_and_listed_accounts_never_get_a_hash(self):
        admin = django_row('chief', 'chief@example.com', role='admin', is_staff=True)
        staff = django_row('staffer', 'staffer@example.com', is_staff=True)
        qa = django_row('qa', 'qa@example.com')
        users = [auth_user(r.email, password=gotrue_hash()) for r in (admin, staff, qa)]
        output = self.run_import(users, (), '--apply', '--no-password-for', 'QA@example.com')
        counts = self.counts(output)
        self.assertEqual(counts['PASSWORD_WITHHELD_PRIVILEGED'], 2)
        self.assertEqual(counts['PASSWORD_WITHHELD_LISTED'], 1)
        for row in (admin, staff, qa):
            row.refresh_from_db()
            self.assertFalse(row.has_usable_password())
            self.assertIsNotNone(row.supabase_uid)  # linked, so Google / reset still work

    def test_a_usable_student_password_is_replaced_unless_kept(self):
        replaced = django_row('rep', 'rep@example.com', password='Django-Old-1!')
        kept = django_row('keep', 'keep@example.com', password='Django-Old-2!')
        self.run_import([auth_user('rep@example.com', password=gotrue_hash())], (), '--apply')
        self.run_import([auth_user('keep@example.com', password=gotrue_hash())], (), '--apply',
                        '--keep-django-passwords')
        replaced.refresh_from_db()
        kept.refresh_from_db()
        self.assertTrue(replaced.password.startswith('supabase_bcrypt$'))
        self.assertTrue(kept.check_password('Django-Old-2!'))
        self.assertIsNotNone(kept.supabase_uid)


class ImportCreateTests(_ImportTestCase):
    def test_missing_accounts_are_created_only_with_the_flag(self):
        user = auth_user('newcomer@example.com', password=gotrue_hash(), user_meta={'username': 'newcomer'})
        output = self.run_import([user], (), '--apply')
        self.assertEqual(self.counts(output)['MISSING_NOT_CREATED'], 1)
        self.assertFalse(User.objects.filter(email='newcomer@example.com').exists())

        output = self.run_import([user], [google_identity(user, 'g-new')], '--apply', '--create-missing')
        self.assertEqual(self.counts(output)['CREATE'], 1)
        created = User.objects.get(email='newcomer@example.com')
        self.assertEqual(created.supabase_uid, user.id)
        self.assertEqual(created.role, 'student')
        self.assertTrue(created.is_active)
        self.assertEqual(created.date_joined, T0)
        self.assertEqual(created.created_at, T0)
        self.assertEqual(created.last_login, T0 + timedelta(days=3))
        self.assertEqual(created.email_verified_at, T0)
        self.assertTrue(created.password.startswith('supabase_bcrypt$'))
        self.assertTrue(TokenBalance.objects.filter(user=created).exists())
        self.assertTrue(UserIdentity.objects.filter(user=created, subject='g-new').exists())
        self.assertEqual(len(mail.outbox), 0)  # no welcome mail

    def test_created_accounts_are_students_with_a_public_handle(self):
        flagged = auth_user('boss@example.com', password=gotrue_hash(), app_meta={'role': 'admin'},
                            user_meta={'username': 'boss'})
        output = self.run_import([flagged], (), '--apply', '--create-missing')
        counts = self.counts(output)
        self.assertEqual(counts['ADMIN_FLAG_IGNORED'], 1)
        self.assertEqual(counts['PASSWORD_WITHHELD_PRIVILEGED'], 1)
        created = User.objects.get(email='boss@example.com')
        self.assertEqual(created.role, 'student')
        self.assertFalse(created.is_staff or created.is_superuser or created.has_usable_password())
        self.assertNotEqual(created.username, 'boss')  # the email's local part
        self.assertTrue(created.username.startswith('learner_'))

    def test_unusable_auth_users_are_skipped_and_banned_ones_created_inactive(self):
        users = [
            auth_user('deleted@example.com', deleted_at=T0),
            auth_user('anon@example.com', is_anonymous=True),
            auth_user('unconfirmed@example.com', confirmed=None),
            auth_user('sso@example.com', is_sso_user=True),
            auth_user('', uid=str(uuid.uuid4())),
            auth_user('banned@example.com', banned_until=timezone.now() + timedelta(days=30)),
        ]
        output = self.run_import(users, (), '--apply', '--create-missing')
        counts = self.counts(output)
        for klass in ('SKIP_DELETED', 'SKIP_ANONYMOUS', 'SKIP_UNCONFIRMED', 'SKIP_SSO', 'SKIP_NO_EMAIL'):
            self.assertEqual(counts[klass], 1, klass)
        self.assertEqual(list(User.objects.values_list('email', flat=True)), ['banned@example.com'])
        self.assertFalse(User.objects.get(email='banned@example.com').is_active)

    def test_relations_and_primary_keys_are_preserved(self):
        rows = [django_row(f'keep{i}', f'keep{i}@example.com') for i in range(3)]
        now = timezone.now()
        Subscription.objects.create(user=rows[0], plan='1_year', plan_display_name='1 Year', amount_paid=Decimal('0'),
                                    status='active', starts_at=now, expires_at=now + timedelta(days=365))
        TokenTransaction.objects.create(user=rows[1], transaction_type='purchase', amount=5, price_paid=Decimal('0'))
        pks_before = set(User.objects.values_list('pk', flat=True))
        users = [auth_user(r.email, password=gotrue_hash()) for r in rows] + [auth_user('extra@example.com')]
        self.run_import(users, (), '--apply', '--create-missing')
        self.assertEqual(User.objects.count(), len(pks_before) + 1)
        self.assertTrue(pks_before <= set(User.objects.values_list('pk', flat=True)))
        self.assertEqual(Subscription.objects.get().user_id, rows[0].pk)
        self.assertEqual(TokenTransaction.objects.get().user_id, rows[1].pk)
        for row in rows:
            self.assertEqual(User.objects.get(pk=row.pk).email, row.email)


class ImportGoogleIdentityTests(_ImportTestCase):
    def test_subjects_are_imported_mismatches_and_conflicts_skipped(self):
        a = django_row('ga', 'ga@example.com')
        b = django_row('gb', 'gb@example.com')
        c = django_row('gc', 'gc@example.com')
        other = django_row('other', 'other@example.com')
        UserIdentity.objects.create(user=other, provider='google', subject='g-taken', source='signup')
        ua, ub, uc = (auth_user(r.email) for r in (a, b, c))
        identities = [
            google_identity(ua, 'g-a'),
            google_identity(ub, 'g-b', data_sub='something-else'),
            google_identity(uc, 'g-taken'),
            google_identity(ua, 'g-a2', email='personal@gmail.com'),
        ]
        output = self.run_import([ua, ub, uc], identities, '--apply')
        counts = self.counts(output)
        self.assertEqual(counts['IDENTITY_IMPORT'], 2)
        self.assertEqual(counts['IDENTITY_SUB_MISMATCH'], 1)
        self.assertEqual(counts['IDENTITY_CONFLICT'], 1)
        self.assertEqual(counts['IDENTITY_EMAIL_DIFFERS'], 1)
        self.assertEqual(sorted(UserIdentity.objects.filter(user=a).values_list('subject', flat=True)), ['g-a', 'g-a2'])
        self.assertFalse(UserIdentity.objects.filter(user=b).exists())
        self.assertEqual(UserIdentity.objects.get(subject='g-taken').user_id, other.pk)


class ImportSafetyTests(_ImportTestCase):
    def test_the_report_is_refused_inside_the_repository(self):
        django_row('rep', 'rep@example.com')
        inside = Path(settings.BASE_DIR) / 'import_report.json'
        with self.assertRaisesMessage(CommandError, 'git work tree'):
            self.run_import([auth_user('rep@example.com')], (), '--report', str(inside))
        self.assertFalse(inside.exists())

    def test_the_report_holds_digests_not_emails_or_hashes(self):
        django_row('rep', 'rep@example.com')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'report.json'
            with mock.patch.object(command_module, '_inside_git_work_tree', return_value=False):
                self.run_import([auth_user('rep@example.com', password=gotrue_hash())], (), '--report', str(path))
            text = path.read_text(encoding='utf-8')
        report = json.loads(text)
        self.assertEqual(report['counts'], {'LINK': 1})
        self.assertNotIn('rep@example.com', text)
        self.assertNotIn('$2a$', text)
        self.assertEqual(report['rows'][0]['email_sha256'], si.email_digest('rep@example.com'))

    def test_remote_sources_need_the_flag_and_the_url_is_never_printed(self):
        url = 'postgresql://reader:s3cret-pw@db.example.com:5432/railway'  # pragma: allowlist secret
        with mock.patch('psycopg.connect') as connect:
            with self.assertRaises(CommandError) as refused:
                call_command('import_supabase_auth', '--source-url', url, stdout=io.StringIO())
            connect.assert_not_called()
        self.assertNotIn('s3cret', str(refused.exception))

        import psycopg

        with mock.patch('psycopg.connect', side_effect=psycopg.OperationalError('boom s3cret-pw')) as connect:
            with self.assertRaises(CommandError) as failed:
                call_command('import_supabase_auth', '--source-url', url, '--allow-remote-source',
                             stdout=io.StringIO())
            connect.assert_called_once()
        self.assertNotIn('s3cret', str(failed.exception))

    def test_a_local_source_url_is_read_only_and_closed(self):
        conn = mock.MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value
        with mock.patch('psycopg.connect', return_value=conn) as connect, \
                mock.patch.object(si, 'read_auth_source', return_value=([], [], [])) as reader:
            call_command('import_supabase_auth', '--source-url', 'postgresql://crack_super@127.0.0.1:55432/crack_restore',
                         stdout=io.StringIO())
        self.assertIn('default_transaction_read_only=on', connect.call_args.kwargs['options'])
        self.assertTrue(conn.read_only)
        reader.assert_called_once_with(cursor, 'auth')
        conn.close.assert_called_once()

    def test_allow_privileged_password_imports_only_the_named_admin(self):
        """--allow-privileged-password <uid>: the owner keeps one admin's Supabase password; every other
        privileged hash is still withheld."""
        keep = django_row('owner', 'owner@example.com', role='admin', is_staff=True)
        other = django_row('second', 'second@example.com', role='admin', is_staff=True)
        keep_au = auth_user(keep.email, uid='7777aaaa-0000-4000-8000-000000000001', password=gotrue_hash())
        other_au = auth_user(other.email, uid='8888bbbb-0000-4000-8000-000000000002', password=gotrue_hash())
        output = self.run_import([keep_au, other_au], (), '--apply', '--allow-privileged-password', '7777aaaa')
        counts = self.counts(output)
        self.assertEqual(counts['PASSWORD_WITHHELD_PRIVILEGED'], 1)
        keep.refresh_from_db()
        other.refresh_from_db()
        self.assertTrue(keep.has_usable_password())
        self.assertTrue(keep.password.startswith('supabase_bcrypt$'))
        self.assertTrue(keep.check_password(PASSWORD))
        self.assertFalse(other.has_usable_password())
        self.assertTrue(keep.is_staff and keep.role == 'admin')  # privileges unchanged

    def test_only_uid_accepts_a_unique_prefix(self):
        a = auth_user('pa@example.com', uid='aaaa1111-0000-4000-8000-000000000001')
        b = auth_user('pb@example.com', uid='aaaa1112-0000-4000-8000-000000000002')
        django_row('pa', 'pa@example.com')
        django_row('pb', 'pb@example.com')
        output = self.run_import([a, b], (), '--only-uid', 'aaaa1111', '--apply')
        self.assertEqual(self.counts(output)['LINK'], 1)
        self.assertEqual(User.objects.get(email='pa@example.com').supabase_uid, a.id)
        self.assertIsNone(User.objects.get(email='pb@example.com').supabase_uid)
        with self.assertRaisesMessage(CommandError, 'no single auth user'):
            self.run_import([a, b], (), '--only-uid', 'aaaa111')  # too short / ambiguous

    def test_without_a_source_url_sqlite_has_no_auth_schema(self):
        with self.assertRaisesMessage(CommandError, 'no Supabase auth schema'):
            call_command('import_supabase_auth', stdout=io.StringIO())


class _FakeCursor:
    """Answers the reader's information_schema and SELECT statements from in-memory tables."""

    def __init__(self, tables):
        self.tables = tables  # {(schema, table): (columns, rows)}
        self.statements = []
        self.description = None
        self._rows = []

    def execute(self, sql, params=None):
        self.statements.append(sql)
        if 'information_schema.columns' in sql:
            columns = self.tables.get(tuple(params), ([], []))[0]
            self._rows, self.description = [(c,) for c in columns], [('column_name',)]
            return
        if 'pg_constraint' in sql:
            self._rows, self.description = [('storage.objects',)], [('conrelid',)]
            return
        match = re.match(r'SELECT (.+) FROM "(\w+)"\."(\w+)"$', sql)
        wanted = [c.strip().strip('"') for c in match.group(1).split(',')]
        columns, rows = self.tables[(match.group(2), match.group(3))]
        self._rows = [tuple(row[columns.index(c)] for c in wanted) for row in rows]
        self.description = [(c,) for c in wanted]

    def fetchall(self):
        return list(self._rows)


class SourceReaderTests(TestCase):
    def test_reader_maps_rows_and_never_selects_token_columns(self):
        uid = str(uuid.uuid4())
        user_columns = ['id', 'email', 'encrypted_password', 'created_at', 'email_confirmed_at', 'confirmation_token',
                        'recovery_token', 'raw_user_meta_data', 'raw_app_meta_data', 'deleted_at', 'is_anonymous']
        users = [(uuid.UUID(uid), ' Doc@Example.com ', '$2a$10$' + 'a' * 53, T0, T0, 'SECRET-TOKEN', 'SECRET-TOKEN',
                  '{"full_name": "Asha Rao"}', {'provider': 'email'}, None, False)]
        # A pre-2023 identities table: the provider id lives in identities.id.
        identity_columns = ['id', 'user_id', 'provider', 'identity_data']
        identities = [('109876543210', uid, 'google', {'sub': '109876543210', 'email': 'doc@example.com'})]
        cursor = _FakeCursor({('auth', 'users'): (user_columns, users),
                              ('auth', 'identities'): (identity_columns, identities)})
        got_users, got_identities, referencing = si.read_auth_source(cursor, 'auth')
        [au] = got_users
        self.assertEqual((au.id, au.email, au.email_key), (uid, 'Doc@Example.com', 'doc@example.com'))
        self.assertEqual(au.user_metadata, {'full_name': 'Asha Rao'})
        self.assertEqual(au.email_confirmed_at, T0)
        [identity] = got_identities
        self.assertEqual((identity.provider, identity.provider_id), ('google', '109876543210'))
        self.assertEqual(referencing, ['storage.objects'])
        selects = [s for s in cursor.statements if s.startswith('SELECT "')]
        self.assertEqual(len(selects), 2)
        self.assertFalse(any('token' in s for s in selects), selects)

    def test_a_schema_without_users_is_refused(self):
        with self.assertRaises(si.SourceError):
            si.read_auth_source(_FakeCursor({}), 'auth')
        with self.assertRaises(si.SourceError):
            si.read_auth_source(_FakeCursor({}), 'auth; drop table x')
