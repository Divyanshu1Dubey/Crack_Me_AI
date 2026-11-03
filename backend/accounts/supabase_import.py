"""Import Supabase Auth users and Google identities into Django accounts (manage.py import_supabase_auth).

Three layers, so the rules can be tested without a database:

* reading  -- ``read_auth_source(cursor, schema)``: auth.users / auth.identities
  rows from any DB-API cursor (the default connection or a read-only psycopg
  connection). Columns are discovered through information_schema; token
  columns (confirmation / recovery / reauthentication tokens) are never read.
* planning -- ``plan_import(...)``: a pure function, one ``Decision`` per auth
  user plus the Django rows no auth user maps to (DJANGO_ONLY).
* applying -- ``apply_plan(plan)``: each decision in its own transaction,
  re-checked on the locked row (compare-and-set on ``supabase_uid``), an
  AdminAuditLog ``identity_import`` entry per written account (no email, no
  hash), then ``check_invariants``.

Rules (docs: design section 3 of the auth-recovery plan):

* Accounts are never deleted, merged or renumbered: every relation to the
  Django primary key (attempts, notes, subscriptions, payments) stays as is.
* An auth user is matched to a row by ``supabase_uid`` (ALREADY_LINKED), else by
  its email, case-insensitively, and only when exactly one row has it.
* LINK also needs the identity to be the one the row was created from
  (accounts.supabase_rest_auth.is_original_identity): a dump cannot show
  whether Supabase "Confirm email" was on, so a Supabase sign-up made after the
  row existed may belong to someone else. Those rows are CHECK_NEWER_IDENTITY
  until an operator reviews them (``--include-newer-identities``).
* Password hashes (GoTrue bcrypt) are imported as ``supabase_bcrypt$<hash>``
  (accounts.hashers), never for admin / staff / superuser rows or auth users
  flagged admin in app_metadata (there is no override), never for the
  addresses / auth user ids given with ``--no-password-for`` /
  ``--no-password-for-uid``, and never when the hash is one of the published
  passwords of ``--leaked-password-file`` (accounts.leaked_passwords). An auth
  user without a Django row whose password is such a published one is not
  created (MISSING_LEAKED_PASSWORD). A usable Django password of a student is
  replaced (``--keep-django-passwords`` keeps it); a row that is already
  linked keeps whatever usable password it has, so a re-run never undoes a
  sign-in's re-hash or a password change. A row that still holds a hash the
  plan now withholds (imported by an earlier run) is reported
  (WITHHELD_HASH_ALREADY_IMPORTED): ``manage.py withhold_leaked_passwords``
  makes it unusable.
* Google identities (auth.identities provider='google') become
  ``UserIdentity(provider='google', subject=<provider_id>)`` when
  identity_data.sub agrees; a subject already attached to another account is
  a conflict and is skipped.
* ``email_verified_at`` comes from email_confirmed_at, only when the auth email
  is the row's email.
* Created rows (CREATE, only with ``--create-missing``): original email, a
  generated or chosen public handle (never the email's local part), always a
  student, inactive when banned, date_joined / created_at / last_login from
  Supabase, a token wallet, no welcome mail.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone as dt_timezone

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .hashers import ALGORITHM as SUPABASE_BCRYPT_ALGORITHM, encoded_from_supabase_hash

logger = logging.getLogger(__name__)

# ── Decision classes (one per auth user) ────────────────────────────────
SKIP_FILTERED = 'SKIP_FILTERED'                  # --only-uid / --exclude-uid
SKIP_DELETED = 'SKIP_DELETED'
SKIP_ANONYMOUS = 'SKIP_ANONYMOUS'
SKIP_SSO = 'SKIP_SSO'
SKIP_NO_EMAIL = 'SKIP_NO_EMAIL'
SKIP_UNCONFIRMED = 'SKIP_UNCONFIRMED'
ALREADY_LINKED = 'ALREADY_LINKED'
LINK = 'LINK'
CREATE = 'CREATE'
MISSING_NOT_CREATED = 'MISSING_NOT_CREATED'      # no row; needs --create-missing
MISSING_LEAKED_PASSWORD = 'MISSING_LEAKED_PASSWORD'  # no row, and its password is a published one: not created
AMBIGUOUS_AUTH_EMAIL = 'AMBIGUOUS_AUTH_EMAIL'    # two auth users share the address
AMBIGUOUS_DJANGO_EMAIL = 'AMBIGUOUS_DJANGO_EMAIL'  # two rows share the address
CONFLICT_LINKED_ELSEWHERE = 'CONFLICT_LINKED_ELSEWHERE'
CHECK_NEWER_IDENTITY = 'CHECK_NEWER_IDENTITY'
DJANGO_ONLY = 'DJANGO_ONLY'                      # a Django row no auth user maps to

WRITING_CLASSES = (LINK, CREATE, ALREADY_LINKED)

# ── Password outcomes ───────────────────────────────────────────────────
PW_IMPORTED = 'PASSWORD_IMPORTED'                # the row had no usable password / is new
PW_REPLACED = 'PASSWORD_REPLACED'                # a usable student password is replaced
PW_KEPT_DJANGO = 'PASSWORD_KEPT_DJANGO'          # a usable Django password is kept
PW_UNCHANGED = 'PASSWORD_UNCHANGED'              # the row already holds this hash
PW_WITHHELD_PRIVILEGED = 'PASSWORD_WITHHELD_PRIVILEGED'
PW_WITHHELD_LISTED = 'PASSWORD_WITHHELD_LISTED'  # --no-password-for / --no-password-for-uid
PW_WITHHELD_LEAKED = 'PASSWORD_WITHHELD_LEAKED'  # one of the --leaked-password-file passwords
PW_NONE = 'PASSWORD_NONE'                        # no bcrypt hash in Supabase (Google-only, ...)
PW_NOT_APPLICABLE = 'PASSWORD_NOT_APPLICABLE'    # the account is not written

PASSWORD_WRITES = (PW_IMPORTED, PW_REPLACED)
PASSWORD_WITHHELD = (PW_WITHHELD_PRIVILEGED, PW_WITHHELD_LISTED, PW_WITHHELD_LEAKED)

# ── Google identity outcomes ────────────────────────────────────────────
ID_IMPORT = 'IDENTITY_IMPORT'
ID_ALREADY = 'IDENTITY_ALREADY_IMPORTED'
ID_SUB_MISMATCH = 'IDENTITY_SUB_MISMATCH'
ID_CONFLICT = 'IDENTITY_CONFLICT'                # the subject belongs to another account
ID_ACCOUNT_NOT_WRITTEN = 'IDENTITY_ACCOUNT_NOT_WRITTEN'
ID_OTHER_PROVIDER = 'IDENTITY_OTHER_PROVIDER'    # not google / email: reported only

# ── Notes ───────────────────────────────────────────────────────────────
NOTE_ADMIN_FLAG_IGNORED = 'ADMIN_FLAG_IGNORED'   # created as a student despite app_metadata
NOTE_AUTH_BANNED = 'AUTH_BANNED'
NOTE_ROW_BLOCKED = 'ROW_BLOCKED'                 # linked, stays blocked
NOTE_IDENTITY_EMAIL_DIFFERS = 'IDENTITY_EMAIL_DIFFERS'
NOTE_EMAIL_DIFFERS_FROM_ROW = 'AUTH_EMAIL_DIFFERS_FROM_ROW'  # ALREADY_LINKED with another address
# The row still holds the Supabase hash this plan withholds (an earlier import wrote it).
NOTE_WITHHELD_HASH_PRESENT = 'WITHHELD_HASH_ALREADY_IMPORTED'

BCRYPT_ONLY = re.compile(r'^\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}\Z')
_SCHEMA_RE = re.compile(r'^[a-z_][a-z0-9_]{0,62}\Z')


# ── Source records ──────────────────────────────────────────────────────

def _as_dict(value) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, (bytes, bytearray, memoryview)):
        value = bytes(value).decode('utf-8', errors='replace')
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except ValueError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _as_datetime(value):
    if value is None or value == '':
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = parse_datetime(str(value).strip())
        except (TypeError, ValueError):
            return None
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, dt_timezone.utc)
    return parsed


def _clean_email(value) -> str:
    return str(value or '').strip()


@dataclass(frozen=True)
class AuthUser:
    """One auth.users row (only the columns the import needs)."""

    id: str
    email: str = ''                      # as stored, trimmed
    encrypted_password: str = ''
    email_confirmed_at: datetime | None = None
    created_at: datetime | None = None
    last_sign_in_at: datetime | None = None
    user_metadata: dict = field(default_factory=dict)
    app_metadata: dict = field(default_factory=dict)
    banned_until: datetime | None = None
    deleted_at: datetime | None = None
    is_anonymous: bool = False
    is_sso_user: bool = False

    @property
    def email_key(self) -> str:
        return self.email.lower()

    def flagged_admin(self) -> bool:
        meta = self.app_metadata if isinstance(self.app_metadata, dict) else {}
        return str(meta.get('is_admin', '')).strip().lower() == 'true' or (
            str(meta.get('role') or '').strip().lower() == 'admin'
        )

    def banned_at(self, now) -> bool:
        return self.banned_until is not None and self.banned_until > now

    def as_supabase_user(self) -> dict:
        """The shape accounts.supabase_rest_auth.is_original_identity reads."""
        return {
            'email_confirmed_at': self.email_confirmed_at.isoformat() if self.email_confirmed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


@dataclass(frozen=True)
class AuthIdentity:
    """One auth.identities row."""

    id: str
    user_id: str
    provider: str
    provider_id: str
    identity_data: dict = field(default_factory=dict)
    email: str = ''
    created_at: datetime | None = None
    last_sign_in_at: datetime | None = None

    @property
    def data_email(self) -> str:
        data = self.identity_data if isinstance(self.identity_data, dict) else {}
        return _clean_email(data.get('email') or self.email).lower()


@dataclass(frozen=True)
class DjangoRow:
    """What the planner needs of a CustomUser row."""

    pk: int
    email: str = ''
    supabase_uid: str | None = None
    date_joined: datetime | None = None
    is_active: bool = True
    privileged: bool = False
    password: str = ''
    first_name: str = ''
    last_name: str = ''
    avatar_url: str = ''
    email_verified_at: datetime | None = None

    @property
    def email_key(self) -> str:
        return (self.email or '').strip().lower()

    @property
    def password_usable(self) -> bool:
        from django.contrib.auth.hashers import is_password_usable

        return bool(self.password) and is_password_usable(self.password)

    @classmethod
    def from_user(cls, user) -> 'DjangoRow':
        return cls(
            pk=user.pk,
            email=user.email or '',
            supabase_uid=user.supabase_uid or None,
            date_joined=user.date_joined,
            is_active=bool(user.is_active),
            privileged=bool(user.role == 'admin' or user.is_staff or user.is_superuser),
            password=user.password or '',
            first_name=user.first_name or '',
            last_name=user.last_name or '',
            avatar_url=user.avatar_url or '',
            email_verified_at=user.email_verified_at,
        )


# ── Reading the source ──────────────────────────────────────────────────

USER_REQUIRED = ('id', 'email', 'encrypted_password', 'created_at')
USER_OPTIONAL = (
    'email_confirmed_at', 'confirmed_at', 'phone_confirmed_at', 'last_sign_in_at',
    'raw_user_meta_data', 'raw_app_meta_data', 'banned_until', 'deleted_at',
    'is_anonymous', 'is_sso_user',
)
IDENTITY_REQUIRED = ('id', 'user_id', 'provider', 'identity_data')
IDENTITY_OPTIONAL = ('provider_id', 'email', 'created_at', 'last_sign_in_at')


class SourceError(Exception):
    """The source has no usable auth.users table."""


def _quote_ident(name: str) -> str:
    if not _SCHEMA_RE.match(name or ''):
        raise SourceError(f'Unsupported schema or table name {name!r}.')
    return f'"{name}"'


def _columns(cursor, schema: str, table: str) -> set[str]:
    cursor.execute(
        'SELECT column_name FROM information_schema.columns WHERE table_schema = %s AND table_name = %s',
        [schema, table],
    )
    return {str(row[0]) for row in cursor.fetchall()}


def _select(cursor, schema, table, columns):
    cursor.execute(
        f'SELECT {", ".join(_quote_ident(c) for c in columns)} FROM {_quote_ident(schema)}.{_quote_ident(table)}'
    )
    names = [c[0] if isinstance(c, (tuple, list)) else getattr(c, 'name', c) for c in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def read_auth_source(cursor, schema: str = 'auth'):
    """(users, identities, referencing_tables) from ``schema``.users / .identities.

    ``referencing_tables``: tables OUTSIDE ``schema`` with a foreign key to
    ``schema``.users (e.g. storage.objects), for the storage migration.
    """
    _quote_ident(schema)
    user_columns = _columns(cursor, schema, 'users')
    missing = [c for c in USER_REQUIRED if c not in user_columns]
    if missing:
        raise SourceError(f'{schema}.users is missing or lacks columns: {", ".join(missing)}.')
    selected = [*USER_REQUIRED, *(c for c in USER_OPTIONAL if c in user_columns)]
    users = []
    for raw in _select(cursor, schema, 'users', selected):
        confirmed = raw.get('email_confirmed_at')
        if not confirmed and raw.get('confirmed_at') and not raw.get('phone_confirmed_at'):
            confirmed = raw.get('confirmed_at')  # older GoTrue builds
        users.append(AuthUser(
            id=str(raw['id']),
            email=_clean_email(raw.get('email')),
            encrypted_password=str(raw.get('encrypted_password') or ''),
            email_confirmed_at=_as_datetime(confirmed),
            created_at=_as_datetime(raw.get('created_at')),
            last_sign_in_at=_as_datetime(raw.get('last_sign_in_at')),
            user_metadata=_as_dict(raw.get('raw_user_meta_data')),
            app_metadata=_as_dict(raw.get('raw_app_meta_data')),
            banned_until=_as_datetime(raw.get('banned_until')),
            deleted_at=_as_datetime(raw.get('deleted_at')),
            is_anonymous=bool(raw.get('is_anonymous')),
            is_sso_user=bool(raw.get('is_sso_user')),
        ))

    identities = []
    identity_columns = _columns(cursor, schema, 'identities')
    if all(c in identity_columns for c in IDENTITY_REQUIRED):
        selected = [*IDENTITY_REQUIRED, *(c for c in IDENTITY_OPTIONAL if c in identity_columns)]
        for raw in _select(cursor, schema, 'identities', selected):
            # Before 2023 GoTrue kept the provider's id in identities.id (text).
            provider_id = raw.get('provider_id') if 'provider_id' in identity_columns else raw.get('id')
            identities.append(AuthIdentity(
                id=str(raw['id']),
                user_id=str(raw['user_id']),
                provider=str(raw.get('provider') or '').strip().lower(),
                provider_id=str(provider_id or '').strip(),
                identity_data=_as_dict(raw.get('identity_data')),
                email=_clean_email(raw.get('email')),
                created_at=_as_datetime(raw.get('created_at')),
                last_sign_in_at=_as_datetime(raw.get('last_sign_in_at')),
            ))

    referencing = []
    try:
        cursor.execute(
            "SELECT DISTINCT c.conrelid::regclass::text FROM pg_constraint c "
            "WHERE c.contype = 'f' AND c.confrelid = to_regclass(%s) "
            "AND c.conrelid::regclass::text NOT LIKE %s ORDER BY 1",
            [f'{schema}.users', f'{schema}.%'],
        )
        referencing = [str(r[0]) for r in cursor.fetchall()]
    except Exception:  # noqa: BLE001 - informational only (non-PostgreSQL test cursors)
        referencing = []
    return users, identities, referencing


# ── Planning ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ImportOptions:
    create_missing: bool = False
    include_newer_identities: bool = False
    keep_django_passwords: bool = False
    no_password_emails: frozenset = frozenset()
    # Auth user ids whose hash is never imported (--no-password-for-uid).
    no_password_uids: frozenset = frozenset()
    # Published passwords (--leaked-password-file): a hash of one of them is never imported.
    leaked_passwords: tuple = ()
    only_uids: frozenset = frozenset()
    exclude_uids: frozenset = frozenset()


@dataclass
class IdentityDecision:
    identity: AuthIdentity
    outcome: str
    notes: list = field(default_factory=list)


@dataclass
class Decision:
    auth_user: AuthUser
    klass: str
    row_pk: int | None = None
    password: str = PW_NOT_APPLICABLE
    identities: list = field(default_factory=list)
    notes: list = field(default_factory=list)

    @property
    def writes(self) -> bool:
        return self.klass in WRITING_CLASSES

    @property
    def encoded_password(self) -> str:
        return encoded_from_supabase_hash(self.auth_user.encrypted_password)


@dataclass
class Plan:
    decisions: list
    django_only: list            # pks of rows no auth user maps to
    user_count: int
    other_provider_identities: int = 0

    def counts(self) -> Counter:
        return Counter(d.klass for d in self.decisions)

    def password_counts(self) -> Counter:
        return Counter(d.password for d in self.decisions if d.password != PW_NOT_APPLICABLE)

    def identity_counts(self) -> Counter:
        counts = Counter(i.outcome for d in self.decisions for i in d.identities)
        if self.other_provider_identities:
            counts[ID_OTHER_PROVIDER] += self.other_provider_identities
        return counts

    def note_counts(self) -> Counter:
        counts = Counter(n for d in self.decisions for n in d.notes)
        counts.update(n for d in self.decisions for i in d.identities for n in i.notes)
        return counts


def _password_outcome(au: AuthUser, klass: str, row: DjangoRow | None, opts: ImportOptions) -> str:
    from .leaked_passwords import supabase_hash_is_one_of

    encoded = encoded_from_supabase_hash(au.encrypted_password)
    if not encoded:
        return PW_NONE
    # Admin / staff hashes are never imported (no override): such accounts set a
    # new password ("Forgot password", manage.py changepassword) or use Google.
    if (row is not None and row.privileged) or au.flagged_admin():
        return PW_WITHHELD_PRIVILEGED
    listed = opts.no_password_emails
    if au.email_key in listed or (row is not None and row.email_key in listed) or au.id in opts.no_password_uids:
        return PW_WITHHELD_LISTED
    if supabase_hash_is_one_of(au.encrypted_password, opts.leaked_passwords):
        return PW_WITHHELD_LEAKED
    if row is None:
        return PW_IMPORTED  # CREATE
    if row.password == encoded:
        return PW_UNCHANGED
    if not row.password_usable:
        return PW_IMPORTED
    if klass == ALREADY_LINKED or opts.keep_django_passwords:
        # Linked earlier: the usable password is newer (re-hash on sign-in, a change or a reset).
        return PW_KEPT_DJANGO
    return PW_REPLACED


def _identity_decisions(au, identities, account_pk, account_email_key, existing_subjects, writes):
    out = []
    for identity in identities:
        if identity.provider != 'google':
            continue
        notes = []
        data_sub = str((identity.identity_data or {}).get('sub') or '').strip()
        if not identity.provider_id or data_sub != identity.provider_id or len(identity.provider_id) > 255:
            out.append(IdentityDecision(identity, ID_SUB_MISMATCH))
            continue
        if identity.data_email and identity.data_email != account_email_key:
            notes.append(NOTE_IDENTITY_EMAIL_DIFFERS)
        if not writes:
            out.append(IdentityDecision(identity, ID_ACCOUNT_NOT_WRITTEN, notes))
            continue
        owner = existing_subjects.get(identity.provider_id)
        if owner is None:
            outcome = ID_IMPORT
        elif account_pk is not None and owner == account_pk:
            outcome = ID_ALREADY
        else:
            outcome = ID_CONFLICT
        out.append(IdentityDecision(identity, outcome, notes))
    return out


def plan_import(auth_users, auth_identities, django_rows, existing_google_subjects, options: ImportOptions,
                *, now=None) -> Plan:
    """Decide what to do for every auth user. Pure: no database access.

    ``existing_google_subjects``: {subject: user pk} of UserIdentity(provider='google').
    """
    from .leaked_passwords import supabase_hash_is_one_of
    from .supabase_rest_auth import is_original_identity

    now = now or timezone.now()
    rows = list(django_rows)
    by_uid = {r.supabase_uid: r for r in rows if r.supabase_uid}
    by_email: dict[str, list[DjangoRow]] = {}
    for r in rows:
        if r.email_key:
            by_email.setdefault(r.email_key, []).append(r)

    identities_by_user: dict[str, list[AuthIdentity]] = {}
    other_providers = 0
    for identity in auth_identities:
        identities_by_user.setdefault(identity.user_id, []).append(identity)
        if identity.provider not in ('google', 'email'):
            other_providers += 1

    def skip_reason(au: AuthUser):
        if options.only_uids and au.id not in options.only_uids:
            return SKIP_FILTERED
        if au.id in options.exclude_uids:
            return SKIP_FILTERED
        if au.deleted_at is not None:
            return SKIP_DELETED
        if au.is_anonymous:
            return SKIP_ANONYMOUS
        if au.is_sso_user:
            return SKIP_SSO
        if not au.email or '@' not in au.email:
            return SKIP_NO_EMAIL
        if au.email_confirmed_at is None:
            return SKIP_UNCONFIRMED
        return None

    candidates = []
    decisions = []
    for au in auth_users:
        reason = skip_reason(au)
        if reason:
            decisions.append(Decision(au, reason))
        else:
            candidates.append(au)

    auth_email_counts = Counter(au.email_key for au in candidates)
    mapped_pks = set()
    for au in candidates:
        notes = []
        row = by_uid.get(au.id)
        if row is not None:
            klass = ALREADY_LINKED
            if row.email_key != au.email_key:
                notes.append(NOTE_EMAIL_DIFFERS_FROM_ROW)
        elif auth_email_counts[au.email_key] > 1:
            klass = AMBIGUOUS_AUTH_EMAIL
        else:
            matches = by_email.get(au.email_key, [])
            if not matches:
                klass = CREATE if options.create_missing else MISSING_NOT_CREATED
            elif len(matches) > 1:
                klass = AMBIGUOUS_DJANGO_EMAIL
            else:
                row = matches[0]
                if row.supabase_uid and row.supabase_uid != au.id:
                    klass = CONFLICT_LINKED_ELSEWHERE
                elif not is_original_identity(au.as_supabase_user(), row) and not options.include_newer_identities:
                    klass = CHECK_NEWER_IDENTITY
                else:
                    klass = LINK
        if row is not None and klass in (ALREADY_LINKED, LINK, CHECK_NEWER_IDENTITY, CONFLICT_LINKED_ELSEWHERE):
            mapped_pks.add(row.pk)
        if klass == AMBIGUOUS_DJANGO_EMAIL:
            mapped_pks.update(r.pk for r in by_email.get(au.email_key, []))
        account_row = row if klass in (ALREADY_LINKED, LINK) else None
        if klass in (CREATE, MISSING_NOT_CREATED) and supabase_hash_is_one_of(
            au.encrypted_password, options.leaked_passwords,
        ):
            # No Django row, and its password is a published one (a demo / test
            # account, most likely): never recreated, with or without
            # --create-missing. If it was a real person, they sign up again.
            klass = MISSING_LEAKED_PASSWORD

        if klass == CREATE and au.flagged_admin():
            notes.append(NOTE_ADMIN_FLAG_IGNORED)
        if au.banned_at(now):
            notes.append(NOTE_AUTH_BANNED)
        if account_row is not None and not account_row.is_active:
            notes.append(NOTE_ROW_BLOCKED)

        decision = Decision(au, klass, row_pk=account_row.pk if account_row else None, notes=notes)
        writes = klass in WRITING_CLASSES
        if writes:
            decision.password = _password_outcome(au, klass, account_row, options)
            if (
                account_row is not None and decision.password in PASSWORD_WITHHELD
                and account_row.password == decision.encoded_password
            ):
                notes.append(NOTE_WITHHELD_HASH_PRESENT)
        account_email_key = account_row.email_key if account_row is not None else au.email_key
        decision.identities = _identity_decisions(
            au, identities_by_user.get(au.id, []), decision.row_pk, account_email_key,
            existing_google_subjects, writes,
        )
        decisions.append(decision)

    # Rows matched to nothing. AMBIGUOUS / CHECK rows are mapped (they have a candidate).
    auth_emails = {au.email_key for au in auth_users if au.email}
    auth_ids = {au.id for au in auth_users}
    django_only = sorted(
        r.pk for r in rows
        if r.pk not in mapped_pks and r.email_key not in auth_emails and r.supabase_uid not in auth_ids
    )
    return Plan(decisions=decisions, django_only=django_only, user_count=len(rows),
                other_provider_identities=other_providers)


SIGN_IN_BOTH = 'password and Google'
SIGN_IN_PASSWORD = 'password only'
SIGN_IN_GOOGLE = 'Google only'
SIGN_IN_NEITHER = 'neither (password reset by email)'


def sign_in_summary(plan: Plan, django_rows) -> Counter:
    """How the written accounts can sign in after the import (Django-native sign-in)."""
    rows = {r.pk: r for r in django_rows}
    counts = Counter()
    for d in plan.decisions:
        if not d.writes:
            continue
        row = rows.get(d.row_pk)
        password = d.password in (PW_IMPORTED, PW_REPLACED, PW_UNCHANGED) or (
            row is not None and row.password_usable
        )
        google = any(i.outcome in (ID_IMPORT, ID_ALREADY) for i in d.identities)
        if password and google:
            counts[SIGN_IN_BOTH] += 1
        elif password:
            counts[SIGN_IN_PASSWORD] += 1
        elif google:
            counts[SIGN_IN_GOOGLE] += 1
        else:
            counts[SIGN_IN_NEITHER] += 1
    return counts


def resolve_uids(values, auth_users, flag: str) -> frozenset:
    """Full auth user ids for ``values`` (each a full id or a unique prefix of 8+ characters)."""
    ids = sorted({au.id for au in auth_users})
    resolved = set()
    for raw in values:
        value = (raw or '').strip().lower()
        if not value:
            continue
        if value in ids:
            resolved.add(value)
            continue
        matches = [i for i in ids if len(value) >= 8 and i.startswith(value)]
        if len(matches) != 1:
            raise SourceError(f'{flag} {value[:8]}: no single auth user id starts with it.')
        resolved.add(matches[0])
    return frozenset(resolved)


# ── Applying ────────────────────────────────────────────────────────────

@dataclass
class ApplyResult:
    linked: int = 0
    created: int = 0
    updated_already_linked: int = 0
    unchanged: int = 0
    passwords_written: int = 0
    identities_written: int = 0
    conflicts: list = field(default_factory=list)        # (auth uid prefix, reason)
    identity_conflicts: int = 0
    created_pks: list = field(default_factory=list)


def _fill_fields(user, au: AuthUser, decision: Decision, *, new_row: bool) -> list[str]:
    """Set the planned fields on ``user`` (blank-only, re-checked on the locked row); returns the names."""
    from .supabase_rest_auth import _avatar_from_metadata, _name_parts_from_metadata

    changed = []
    if (user.supabase_uid or None) != au.id:
        user.supabase_uid = au.id
        changed.append('supabase_uid')
    same_email = (user.email or '').strip().lower() == au.email_key
    if user.email_verified_at is None and au.email_confirmed_at is not None and same_email:
        user.email_verified_at = au.email_confirmed_at
        changed.append('email_verified_at')
    first, last = _name_parts_from_metadata(au.user_metadata or {})
    if first and not user.first_name:
        user.first_name = first
        changed.append('first_name')
    if last and not user.last_name:
        user.last_name = last
        changed.append('last_name')
    avatar = _avatar_from_metadata(au.user_metadata or {})
    if avatar and not user.avatar_url:
        user.avatar_url = avatar
        changed.append('avatar_url')
    if decision.password in PASSWORD_WRITES:
        encoded = decision.encoded_password
        current = user.password or ''
        if new_row:
            write = True
        else:
            from django.contrib.auth.hashers import is_password_usable

            usable = bool(current) and is_password_usable(current)
            # Re-checked on the locked row: never overwrite a password set
            # since the plan was made, except the planned replacement.
            write = current != encoded and (not usable or decision.password == PW_REPLACED)
        if write and encoded:
            user.password = encoded
            changed.append('password')
    return changed


def _audit(row_pk, au: AuthUser, decision: Decision, changed, identities_written):
    from .models import AdminAuditLog

    AdminAuditLog.objects.create(
        actor=None,
        action='identity_import',
        resource_type='user',
        resource_id=str(row_pk),
        detail=f'Supabase Auth import: {decision.klass}',
        metadata={
            'class': decision.klass,
            'supabase_uid': au.id,
            'fields': sorted(f for f in changed if f != 'password'),
            'password': decision.password if 'password' in changed else PW_NOT_APPLICABLE,
            'google_identities': identities_written,
            'source': 'import_supabase_auth',
        },
    )


def _write_identities(user_pk, decision: Decision, result: ApplyResult) -> int:
    from django.db import IntegrityError, transaction

    from .models import UserIdentity

    written = 0
    for item in decision.identities:
        if item.outcome != ID_IMPORT:
            continue
        identity = item.identity
        try:
            with transaction.atomic():
                obj, created = UserIdentity.objects.get_or_create(
                    provider=UserIdentity.PROVIDER_GOOGLE,
                    subject=identity.provider_id,
                    defaults={
                        'user_id': user_pk,
                        'email': identity.data_email[:254],
                        'email_verified': bool((identity.identity_data or {}).get('email_verified')),
                        'source': 'supabase_import',
                        'supabase_identity_id': identity.id[:64],
                        'last_sign_in_at': identity.last_sign_in_at,
                    },
                )
        except IntegrityError:
            result.identity_conflicts += 1
            continue
        if created:
            written += 1
        elif obj.user_id != user_pk:
            result.identity_conflicts += 1
    return written


def _create_row(au: AuthUser, decision: Decision, now):
    from django.contrib.auth import get_user_model

    from .handles import username_for_new_account
    from .models import TokenBalance

    User = get_user_model()
    if User.objects.filter(email__iexact=au.email_key).exists() or User.objects.filter(supabase_uid=au.id).exists():
        return None, 'an account with this email or uid appeared after planning'
    username = username_for_new_account(User, (au.user_metadata or {}).get('username'), au.email_key)
    user = User(
        username=username,
        email=au.email,
        role='student',
        is_staff=False,
        is_superuser=False,
        is_active=not au.banned_at(now),
        date_joined=au.created_at or now,
        last_login=au.last_sign_in_at,
    )
    user.set_unusable_password()
    _fill_fields(user, au, decision, new_row=True)
    user.save()
    if au.created_at is not None:
        User.objects.filter(pk=user.pk).update(created_at=au.created_at)  # auto_now_add
    TokenBalance.objects.get_or_create(user=user)
    return user, ''


def apply_plan(plan: Plan, *, now=None) -> ApplyResult:
    """Write every LINK / CREATE / ALREADY_LINKED decision. Idempotent."""
    from django.contrib.auth import get_user_model
    from django.db import IntegrityError, transaction

    User = get_user_model()
    now = now or timezone.now()
    result = ApplyResult()
    for decision in plan.decisions:
        if not decision.writes:
            continue
        au = decision.auth_user
        try:
            with transaction.atomic():
                if decision.klass == CREATE:
                    user, problem = _create_row(au, decision, now)
                    if user is None:
                        result.conflicts.append((au.id[:8], problem))
                        continue
                    written = _write_identities(user.pk, decision, result)
                    _audit(user.pk, au, decision, ['created'], written)
                    result.created += 1
                    result.created_pks.append(user.pk)
                    if decision.password in PASSWORD_WRITES and user.password.startswith(SUPABASE_BCRYPT_ALGORITHM + '$'):
                        result.passwords_written += 1
                    result.identities_written += written
                    continue

                user = User.objects.select_for_update().filter(pk=decision.row_pk).first()
                if user is None:
                    result.conflicts.append((au.id[:8], 'the account no longer exists'))
                    continue
                if user.supabase_uid and user.supabase_uid != au.id:
                    result.conflicts.append((au.id[:8], 'the account was linked to another identity'))
                    continue
                if decision.klass == LINK and (user.email or '').strip().lower() != au.email_key:
                    result.conflicts.append((au.id[:8], 'the account email changed after planning'))
                    continue
                changed = _fill_fields(user, au, decision, new_row=False)
                if changed:
                    user.save(update_fields=changed)
                written = _write_identities(user.pk, decision, result)
                if changed or written:
                    _audit(user.pk, au, decision, changed, written)
                if 'password' in changed:
                    result.passwords_written += 1
                result.identities_written += written
                if 'supabase_uid' in changed:
                    result.linked += 1
                elif changed or written:
                    result.updated_already_linked += 1
                else:
                    result.unchanged += 1
        except IntegrityError:
            result.conflicts.append((au.id[:8], 'a unique constraint refused the write'))
    return result


# ── Invariants and reporting ────────────────────────────────────────────

def snapshot_accounts():
    """(count, set of pks) of CustomUser, for the invariants."""
    from django.contrib.auth import get_user_model

    pks = set(get_user_model().objects.values_list('pk', flat=True))
    return len(pks), pks


def check_invariants(before, plan: Plan, result: ApplyResult) -> list[str]:
    """Problems found after an apply ([] when every invariant holds)."""
    from django.contrib.auth import get_user_model
    from django.db.models import Count

    from .models import UserIdentity

    User = get_user_model()
    problems = []
    count_before, pks_before = before
    count_after, pks_after = snapshot_accounts()
    if count_after != count_before + result.created:
        problems.append(f'account count {count_after} != {count_before} before + {result.created} created')
    if not pks_before <= pks_after:
        problems.append(f'{len(pks_before - pks_after)} account(s) disappeared')
    if set(result.created_pks) & pks_before:
        problems.append('a created account reused an existing primary key')
    dup_uids = (
        User.objects.exclude(supabase_uid__isnull=True).values('supabase_uid')
        .annotate(n=Count('pk')).filter(n__gt=1).count()
    )
    if dup_uids:
        problems.append(f'{dup_uids} supabase_uid value(s) on several accounts')
    dup_subjects = (
        UserIdentity.objects.values('provider', 'subject').annotate(n=Count('pk')).filter(n__gt=1).count()
    )
    if dup_subjects:
        problems.append(f'{dup_subjects} (provider, subject) pair(s) on several identities')
    for decision in plan.decisions:
        if decision.klass in (LINK, ALREADY_LINKED) and decision.auth_user.id[:8] not in {c[0] for c in result.conflicts}:
            if not User.objects.filter(pk=decision.row_pk, supabase_uid=decision.auth_user.id).exists():
                problems.append(f'account {decision.row_pk} is not linked to its identity')
    return problems


def email_digest(email: str) -> str:
    return hashlib.sha256((email or '').strip().lower().encode('utf-8')).hexdigest()


def report_rows(plan: Plan, *, include_emails: bool = False) -> dict:
    """JSON-serialisable report. Emails are SHA-256 digests unless ``include_emails``; never hashes."""
    rows = []
    for d in plan.decisions:
        au = d.auth_user
        rows.append({
            'class': d.klass,
            'django_id': d.row_pk,
            'supabase_uid': au.id,
            'email': au.email_key if include_emails else None,
            'email_sha256': email_digest(au.email_key) if au.email else None,
            'created_at': au.created_at.isoformat() if au.created_at else None,
            'last_sign_in_at': au.last_sign_in_at.isoformat() if au.last_sign_in_at else None,
            'password': d.password,
            'identities': [i.outcome for i in d.identities],
            'notes': list(d.notes) + [n for i in d.identities for n in i.notes],
        })
    return {
        'counts': dict(plan.counts()),
        'passwords': dict(plan.password_counts()),
        'identities': dict(plan.identity_counts()),
        'notes': dict(plan.note_counts()),
        'django_only': plan.django_only,
        'rows': rows,
    }
