"""Import Supabase Auth users, password hashes and Google identities into Django accounts.

DRY RUN BY DEFAULT: nothing is written without --apply. The rules are in
accounts/supabase_import.py (planning is a pure function, applying is one
transaction per account, idempotent: a second run changes nothing).

Source (read-only, token columns are never read):
  * --source-url postgresql://crack_super@127.0.0.1:55432/crack_restore
    (a restore that still has the ``auth`` schema). Only local hosts unless
    --allow-remote-source. The URL is never printed.
  * otherwise the default database, when it has <schema>.users.

Usage:
  DJANGO_ENV_FILE=.env.prodcheck python manage.py import_supabase_auth --source-url <url>
  ... --apply --create-missing             write (and create the accounts without a Django row)
  ... --include-newer-identities           also link CHECK_NEWER_IDENTITY rows (after review)
  ... --only-uid UID / --exclude-uid UID   restrict to / skip auth users
  ... --no-password-for EMAIL / --no-password-file PATH   never import these hashes (QA accounts)
  ... --keep-django-passwords              keep usable Django passwords of students
  ... --report PATH [--include-emails]     JSON report (emails as SHA-256 unless asked), outside the repo

Output: counts per class; with -v 2 one line per auth user (Django id, uid
prefix, email digest prefix). Never emails, names or hashes.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlparse

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from accounts import supabase_import as si

LOCAL_SOURCE_HOSTS = frozenset({'localhost', '127.0.0.1', '::1'})

CLASS_ORDER = (
    si.LINK, si.ALREADY_LINKED, si.CREATE, si.MISSING_NOT_CREATED, si.CHECK_NEWER_IDENTITY,
    si.CONFLICT_LINKED_ELSEWHERE, si.AMBIGUOUS_DJANGO_EMAIL, si.AMBIGUOUS_AUTH_EMAIL,
    si.SKIP_UNCONFIRMED, si.SKIP_NO_EMAIL, si.SKIP_DELETED, si.SKIP_ANONYMOUS, si.SKIP_SSO, si.SKIP_FILTERED,
)


def _source_is_local(url: str) -> bool:
    host = (urlparse(url).hostname or '').strip().lower()
    # No host: a Unix-domain socket on this machine.
    return host in LOCAL_SOURCE_HOSTS or host == ''


def _inside_git_work_tree(path: Path) -> bool:
    resolved = path.resolve()
    return any((parent / '.git').exists() for parent in (resolved.parent, *resolved.parent.parents))


def load_source(options):
    """(users, identities, referencing tables, description). Tests patch this."""
    schema = options['schema']
    url = (options.get('source_url') or '').strip()
    if url:
        if urlparse(url).scheme not in ('postgres', 'postgresql'):
            raise CommandError('--source-url must be a postgresql:// URL.')
        local = _source_is_local(url)
        if not local and not options.get('allow_remote_source'):
            raise CommandError(
                '--source-url points at a remote host. Restore the dump locally, or pass --allow-remote-source.'
            )
        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover - psycopg is a requirement
            raise CommandError('psycopg is required for --source-url.') from exc
        try:
            conn = psycopg.connect(
                url, connect_timeout=10,
                options='-c default_transaction_read_only=on -c statement_timeout=60000',
            )
        except psycopg.Error as exc:
            raise CommandError(f'Could not connect to the --source-url database ({exc.__class__.__name__}).') from None
        try:
            conn.read_only = True
            with conn.cursor() as cursor:
                users, identities, referencing = si.read_auth_source(cursor, schema)
        except si.SourceError as exc:
            raise CommandError(str(exc)) from None
        except psycopg.Error as exc:
            raise CommandError(f'Could not read the --source-url database ({exc.__class__.__name__}).') from None
        finally:
            conn.close()
        where = 'local host' if local else 'REMOTE host (--allow-remote-source)'
        return users, identities, referencing, f'the --source-url database ({where})'

    if connection.vendor != 'postgresql':
        raise CommandError(
            'No --source-url, and the default database is not PostgreSQL, so it has no Supabase auth schema. '
            'Pass --source-url postgresql://user@127.0.0.1:port/<restore with the auth schema>.'
        )
    with connection.cursor() as cursor:
        cursor.execute('SELECT to_regclass(%s)', [f'{schema}.users'])
        if cursor.fetchone()[0] is None:
            raise CommandError(
                f'The default database has no {schema}.users table. Pass --source-url with a restore '
                'that still has the Supabase auth schema.'
            )
        try:
            users, identities, referencing = si.read_auth_source(cursor, schema)
        except si.SourceError as exc:
            raise CommandError(str(exc)) from None
    return users, identities, referencing, 'the default database'


class Command(BaseCommand):
    help = 'Import Supabase Auth users, password hashes and Google identities (dry run unless --apply).'

    def add_arguments(self, parser):
        parser.add_argument('--source-url', default='', help='postgresql:// URL of a restore with the auth schema.')
        parser.add_argument('--schema', default='auth', help='Schema holding users / identities (default: auth).')
        parser.add_argument('--allow-remote-source', action='store_true', help='Allow a non-local --source-url host.')
        parser.add_argument('--apply', action='store_true', help='Write the changes (default: dry run).')
        parser.add_argument('--create-missing', action='store_true',
                            help='Create accounts for confirmed auth users that have no Django row.')
        parser.add_argument('--include-newer-identities', action='store_true',
                            help='Also link rows whose Supabase identity is newer than the account (review first).')
        parser.add_argument('--keep-django-passwords', action='store_true',
                            help='Keep usable Django passwords of students instead of the Supabase hash.')
        parser.add_argument('--no-password-for', action='append', default=[], metavar='EMAIL',
                            help='Never import the password hash of this address (repeatable).')
        parser.add_argument('--no-password-file', default='', metavar='PATH',
                            help='File with one address per line whose hashes are never imported.')
        parser.add_argument('--allow-privileged-password', action='append', default=[], metavar='UID',
                            help="Import the password hash of this admin/staff account's auth user id anyway "
                                 '(owner decision; repeatable). All other privileged hashes stay withheld.')
        parser.add_argument('--only-uid', action='append', default=[], metavar='UID', help='Only these auth user ids.')
        parser.add_argument('--exclude-uid', action='append', default=[], metavar='UID', help='Skip these auth user ids.')
        parser.add_argument('--report', default='', metavar='PATH',
                            help='Write a JSON report here (refused inside the git work tree).')
        parser.add_argument('--include-emails', action='store_true',
                            help='Put plain email addresses in the report (default: SHA-256 digests).')

    def _no_password_emails(self, options) -> frozenset:
        emails = {e.strip().lower() for e in options['no_password_for'] if e and e.strip()}
        path = (options['no_password_file'] or '').strip()
        if path:
            try:
                lines = Path(path).read_text(encoding='utf-8').splitlines()
            except OSError as exc:
                raise CommandError(f'Cannot read --no-password-file ({exc.__class__.__name__}).') from None
            emails.update(line.strip().lower() for line in lines if line.strip() and not line.lstrip().startswith('#'))
        return frozenset(emails)

    def _report_path(self, options):
        raw = (options['report'] or '').strip()
        if not raw:
            return None
        path = Path(raw)
        if not path.parent.exists():
            raise CommandError('The --report directory does not exist.')
        if _inside_git_work_tree(path):
            raise CommandError('Refusing to write the --report inside a git work tree (it holds account data).')
        return path

    def handle(self, *args, **options):
        User = get_user_model()
        from accounts.models import UserIdentity

        apply_changes = bool(options['apply'])
        report_path = self._report_path(options)
        no_password_emails = self._no_password_emails(options)

        users, identities, referencing, source = load_source(options)
        try:
            only_uids = si.resolve_uids(options['only_uid'], users, '--only-uid')
            exclude_uids = si.resolve_uids(options['exclude_uid'], users, '--exclude-uid')
            allow_privileged_uids = si.resolve_uids(options['allow_privileged_password'], users,
                                                    '--allow-privileged-password')
        except si.SourceError as exc:
            raise CommandError(str(exc)) from None
        import_options = si.ImportOptions(
            create_missing=bool(options['create_missing']),
            include_newer_identities=bool(options['include_newer_identities']),
            keep_django_passwords=bool(options['keep_django_passwords']),
            no_password_emails=no_password_emails,
            only_uids=only_uids,
            exclude_uids=exclude_uids,
            allow_privileged_password_uids=frozenset(allow_privileged_uids),
        )
        rows = [
            si.DjangoRow.from_user(u)
            for u in User.objects.only(
                'id', 'email', 'supabase_uid', 'date_joined', 'is_active', 'role', 'is_staff', 'is_superuser',
                'password', 'first_name', 'last_name', 'avatar_url', 'email_verified_at',
            ).order_by('pk')
        ]
        existing = dict(
            UserIdentity.objects.filter(provider=UserIdentity.PROVIDER_GOOGLE).values_list('subject', 'user_id')
        )
        plan = si.plan_import(users, identities, rows, existing, import_options)
        self._print_plan(plan, users, identities, rows, existing, referencing, source, apply_changes, options)

        if apply_changes:
            before = si.snapshot_accounts()
            result = si.apply_plan(plan)
            problems = si.check_invariants(before, plan, result)
            self._print_result(result)
            if problems:
                for problem in problems:
                    self.stderr.write(f'  INVARIANT: {problem}')
                raise CommandError('Invariant check failed after the import (see above).')
            self.stdout.write(self.style.SUCCESS(
                f'Invariants hold: accounts {before[0]} -> {before[0] + result.created} '
                f'(+{result.created} created, none removed, primary keys unchanged); '
                'supabase_uid and (provider, subject) are unique.'
            ))
        else:
            self.stdout.write('\nDry run: nothing was written. Re-run with --apply to write.')

        if report_path is not None:
            report = si.report_rows(plan, include_emails=bool(options['include_emails']))
            report['applied'] = apply_changes
            fd = os.open(str(report_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                json.dump(report, handle, indent=2, sort_keys=True)
            self.stdout.write(f'Report written ({len(report["rows"])} rows).')

    def _print_plan(self, plan, users, identities, rows, existing, referencing, source, apply_changes, options):
        out = self.stdout.write
        mode = 'APPLY' if apply_changes else 'DRY RUN (nothing is written; --apply writes)'
        out(f'Supabase Auth import -- {mode}')
        out(f'Source: {source}, schema "{options["schema"]}"')
        providers = {}
        for identity in identities:
            providers[identity.provider] = providers.get(identity.provider, 0) + 1
        other = sum(n for p, n in providers.items() if p not in ('google', 'email'))
        out(
            f'auth.users: {len(users)}   auth.identities: {len(identities)} '
            f'(google {providers.get("google", 0)}, email {providers.get("email", 0)}, other {other})'
        )
        out(f'Django accounts: {len(rows)}   Google identities already in Django: {len(existing)}')

        counts = plan.counts()
        out('\nAccounts (one decision per auth user):')
        for klass in CLASS_ORDER:
            if counts.get(klass):
                out(f'  {klass:<30}{counts[klass]:>6}')
        out(f'  {"DJANGO_ONLY (no auth user)":<30}{len(plan.django_only):>6}')
        for title, values in (
            ('Passwords (written accounts):', plan.password_counts()),
            ('Google identities:', plan.identity_counts()),
            ('Notes:', plan.note_counts()),
            ('Sign-in after the import (written accounts):', si.sign_in_summary(plan, rows)),
        ):
            if values:
                out(f'\n{title}')
                for key in sorted(values):
                    out(f'  {key:<34}{values[key]:>6}')
        if referencing:
            out('\nTables outside the auth schema that reference auth.users (storage migration): '
                + ', '.join(referencing))
        if counts.get(si.CHECK_NEWER_IDENTITY):
            out('\nCHECK_NEWER_IDENTITY: the Supabase identity was created after the Django account, so the dump '
                'cannot prove it belongs to the same person. Those accounts keep their current sign-in (their '
                'Django password, or "Forgot password"). After review, link them with '
                '--include-newer-identities [--only-uid UID].')
        if counts.get(si.MISSING_NOT_CREATED):
            out('\nMISSING_NOT_CREATED: confirmed auth users without a Django account; --create-missing creates them.')

        if int(options.get('verbosity', 1)) >= 2:
            out('\nPer auth user:')
            for d in plan.decisions:
                au = d.auth_user
                digest = si.email_digest(au.email)[:10] if au.email else '-'
                identities_text = ','.join(i.outcome.replace('IDENTITY_', '') for i in d.identities) or '-'
                out(f'  {d.klass:<26} django_id={d.row_pk or "-":<6} uid={au.id[:8]} email_sha={digest} '
                    f'password={d.password.replace("PASSWORD_", "")} google={identities_text}')

    def _print_result(self, result):
        out = self.stdout.write
        out('\nWritten:')
        out(f'  {"accounts linked":<30}{result.linked:>6}')
        out(f'  {"accounts created":<30}{result.created:>6}')
        out(f'  {"linked accounts updated":<30}{result.updated_already_linked:>6}')
        out(f'  {"accounts unchanged":<30}{result.unchanged:>6}')
        out(f'  {"password hashes written":<30}{result.passwords_written:>6}')
        out(f'  {"Google identities written":<30}{result.identities_written:>6}')
        out(f'  {"identity conflicts skipped":<30}{result.identity_conflicts:>6}')
        out(f'  {"accounts skipped (conflict)":<30}{len(result.conflicts):>6}')
        for prefix, reason in result.conflicts:
            out(f'    uid={prefix}: {reason}')
