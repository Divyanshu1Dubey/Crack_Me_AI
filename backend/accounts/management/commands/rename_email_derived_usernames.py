"""Give accounts whose public username shows their email address a generated handle.

Usernames are public: discussion threads show them (the leaderboard already
hides these ones, analytics.views._public_name). Google sign-ups and the
dev-only local register used to be named after the email's local part -- for
a Gmail user the address itself -- and some usernames hold a whole address.
New accounts get a generated handle (accounts.handles.username_for_new_account);
this command renames the existing ones to ``learner_<8 hex>``. Learners can
pick another handle in Settings (PATCH /api/auth/profile/).

Matched: the username holds an '@', or is the email's local part in any case,
optionally with a collision suffix ('_2') or cut to 140 / 130 characters
(accounts.handles.exposes_email, the rule of analytics.views._public_name).

Dry run by default; ``--apply`` renames. The output names accounts by id only
(never a username or an address). Migration accounts.0027 runs the same
rename once, in the release that made usernames writable (the "taken" answer
of PATCH /api/auth/profile/ would otherwise tell whether an account uses a
given local part); this command reports what is left, e.g. accounts created
by the previous release while it deployed, and the skipped admin/staff ids.

Renaming is safe because nothing signs in, or keys a session or a lockout, by
the username of these accounts:
  * Supabase sign-ins match CustomUser.supabase_uid, then the confirmed email;
    user_metadata.username is read only when the account is created and never
    synced back (supabase_rest_auth._upsert_local_user).
  * SimpleJWT tokens (dev-only local auth) carry the user id (USER_ID_FIELD
    'id'); the local login also looks the account up by email; no
    TokenObtainPair view is mounted; /api/auth/login/ answers 410.
  * django-axes keys lockouts by the username typed into a password form:
    Django admin (staff only) and the dev-only local login.
Admin, staff and superuser accounts are therefore skipped (reported by id):
they sign in to Django admin with their username, and ops commands look them
up by it (bootstrap_admin, mirror_user_to_supabase_auth,
sync_single_supabase_admin). Rename those by hand if wanted.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from accounts.handles import email_derived_accounts, generate_handle, rename_to_generated_handles

_MAX_IDS_SHOWN = 100


def _ids(values):
    shown = ', '.join(str(pk) for pk in values[:_MAX_IDS_SHOWN])
    more = len(values) - _MAX_IDS_SHOWN
    return f'{shown}, ... (+{more} more)' if more > 0 else shown


class Command(BaseCommand):
    help = (
        "Rename accounts whose username shows their email address (its local part, or "
        "an '@') to a generated learner_<hex> handle. Dry run unless --apply."
    )

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Rename the accounts (default: report only).')

    def handle(self, *args, **options):
        apply = bool(options.get('apply'))
        User = get_user_model()
        to_rename, team = email_derived_accounts(User)

        self.stdout.write(f'{len(to_rename)} account(s) with a username that shows their email address.')
        if team:
            self.stdout.write(self.style.WARNING(
                f'Skipped {len(team)} admin/staff account(s) (they sign in to Django admin by username; '
                f'rename by hand if wanted): id {_ids(team)}'
            ))
        if not to_rename:
            return
        if not apply:
            self.stdout.write(f'Would rename id {_ids([pk for pk, _ in to_rename])}')
            self.stdout.write('Dry run: nothing changed. Re-run with --apply to rename them.')
            return

        # Compare-and-set: a learner who picked a handle in Settings since the
        # scan keeps it.
        renamed, changed_meanwhile = rename_to_generated_handles(User, to_rename, generate=generate_handle)
        if renamed:
            self.stdout.write(self.style.SUCCESS(f'Renamed {len(renamed)} account(s): id {_ids(renamed)}'))
        if changed_meanwhile:
            self.stdout.write(f'Left {len(changed_meanwhile)} account(s) whose username changed meanwhile: '
                              f'id {_ids(changed_meanwhile)}')
