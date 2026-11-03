"""Make account passwords that are publicly known unusable, and end those accounts' sessions.

DRY RUN BY DEFAULT: nothing is written without --apply.

Which accounts (at least one of):
  --password-file PATH   published passwords, one per line exactly as typed (a file OUTSIDE the git
                         work tree; accounts.leaked_passwords). An account matches when its current
                         password verifies one of them -- any hasher: a Supabase hash imported earlier,
                         its Argon2 re-hash after a sign-in, or a Django password.
  --user-id N            (repeatable) only these accounts. Without --password-file they match when
                         their password is still an imported Supabase hash (``supabase_bcrypt$``),
                         i.e. never changed since the import; any other usable password is reported,
                         not touched (check it with --password-file).

--apply, per matching account, inside a transaction on the locked row (re-checked there):
set_unusable_password(), end every Django-native session, and an AdminAuditLog
``session_revoke`` entry (no password, no email). The owners then sign in with
"Forgot password" or Google. Staff / admin accounts are treated like any other.

Usage:
  DJANGO_ENV_FILE=.env.prodcheck python manage.py withhold_leaked_passwords --password-file PATH
  ... --apply                    write
  ... -v 2                       list the account ids

Output: counts, and account ids with -v 2. Never passwords, hashes or emails.
"""
from __future__ import annotations

from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.hashers import ALGORITHM as SUPABASE_BCRYPT_ALGORITHM
from accounts.leaked_passwords import PasswordFileError, inside_git_work_tree, password_is_one_of, read_password_file

IMPORTED_PREFIX = SUPABASE_BCRYPT_ALGORITHM + '$'


def _matches(password: str, leaked: tuple) -> bool:
    if leaked:
        return password_is_one_of(password, leaked)
    return (password or '').startswith(IMPORTED_PREFIX)


class Command(BaseCommand):
    help = 'Make publicly known account passwords unusable and end those sessions (dry run unless --apply).'

    def add_arguments(self, parser):
        parser.add_argument('--password-file', default='', metavar='PATH',
                            help='Published passwords, one per line (a file outside the git work tree).')
        parser.add_argument('--user-id', action='append', default=[], type=int, metavar='N',
                            help='Only this account (repeatable). Without --password-file: its imported '
                                 'Supabase hash, if it still has one.')
        parser.add_argument('--apply', action='store_true', help='Write the changes (default: dry run).')

    def _leaked(self, options) -> tuple:
        raw = (options['password_file'] or '').strip()
        if not raw:
            return ()
        path = Path(raw)
        if inside_git_work_tree(path):
            raise CommandError('Refusing to read --password-file inside a git work tree '
                               '(keep the published passwords out of the repository).')
        try:
            return read_password_file(path)
        except PasswordFileError as exc:
            raise CommandError(f'--password-file: {exc}.') from None

    def handle(self, *args, **options):
        User = get_user_model()
        leaked = self._leaked(options)
        user_ids = sorted({int(i) for i in options['user_id']})
        if not leaked and not user_ids:
            raise CommandError('Give --password-file PATH and/or --user-id N.')
        apply_changes = bool(options['apply'])
        verbose = int(options.get('verbosity', 1)) >= 2

        rows = User.objects.exclude(password='').exclude(password__startswith='!').order_by('pk')
        if user_ids:
            rows = rows.filter(pk__in=user_ids)
            missing = sorted(set(user_ids) - set(User.objects.filter(pk__in=user_ids).values_list('pk', flat=True)))
            if missing:
                self.stdout.write(f'No account with id {", ".join(map(str, missing))}.')
        checked, hits, other_usable = 0, [], []
        for user in rows.only('id', 'password', 'role', 'is_staff', 'is_superuser').iterator():
            checked += 1
            if _matches(user.password, leaked):
                hits.append(user)
            elif not leaked:
                other_usable.append(user.pk)

        privileged = [u.pk for u in hits if u.role == 'admin' or u.is_staff or u.is_superuser]
        mode = 'APPLY' if apply_changes else 'DRY RUN (nothing is written; --apply writes)'
        self.stdout.write(f'Publicly known passwords -- {mode}')
        if leaked:
            self.stdout.write(f'Published passwords checked: {len(leaked)}')
        self.stdout.write(f'Accounts with a usable password checked: {checked}')
        self.stdout.write(f'Accounts whose password is publicly known: {len(hits)} (staff / admin: {len(privileged)})')
        if verbose and hits:
            self.stdout.write(f'  ids: {", ".join(str(u.pk) for u in hits)}')
        if other_usable:
            self.stdout.write(
                f'Listed accounts with another usable password (not an imported hash; not touched, check them '
                f'with --password-file): {len(other_usable)}'
                + (f' (ids {", ".join(map(str, other_usable))})' if verbose else '')
            )
        if not apply_changes:
            self.stdout.write('\nDry run: nothing was written. Re-run with --apply to make these passwords unusable.')
            return

        from accounts.native_sessions import revoke_user_sessions
        from accounts.views import create_admin_audit_log

        changed, sessions = [], 0
        for hit in hits:
            with transaction.atomic():
                user = User.objects.select_for_update().filter(pk=hit.pk).first()
                if user is None or not _matches(user.password, leaked):
                    continue  # changed since the check (a reset, a new password): keep it
                user.set_unusable_password()
                user.save(update_fields=['password'])
                ended = revoke_user_sessions(user, 'admin')
                sessions += ended
                create_admin_audit_log(
                    actor=None,
                    action='session_revoke',
                    resource_type='user',
                    resource_id=user.pk,
                    detail='Password made unusable: it is publicly known (withhold_leaked_passwords)',
                    metadata={'reason': 'leaked_password', 'sessions_revoked': ended,
                              'source': 'withhold_leaked_passwords'},
                )
                changed.append(user.pk)
        self.stdout.write(self.style.SUCCESS(
            f'Passwords made unusable: {len(changed)}; native sessions ended: {sessions}.'
            + (f' ids: {", ".join(map(str, changed))}' if verbose and changed else '')
        ))
        self.stdout.write('The owners sign in again with "Forgot password" (or Google, when linked).')
