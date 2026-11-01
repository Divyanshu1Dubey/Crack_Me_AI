"""Public usernames ("handles"): the name other learners see.

``CustomUser.username`` is public: discussion threads show it, and so does the
leaderboard (``analytics.views._public_name``). It must never come from the
email address. Google sign-ups carry no username, and their accounts used to
be named after the address's local part (for a Gmail user, the address
itself); the dev-only local register did the same.

* ``exposes_email``             the username shows the person's email address:
  it holds an ``@``, or it is the address's local part (any case), optionally
  with a collision suffix (``_2``, ``_3``, ...) or cut to 140 / 130 characters.
  Same rule as ``analytics.views._public_name``.
* ``generate_handle``           a non-identifying ``learner_<8 hex>`` handle
  that no account uses.
* ``username_for_new_account``  the username of a new account (Supabase first
  sign-in, dev-only local register): the name chosen at sign-up when it
  follows the Settings rules, else a generated handle.
* ``handle_error``              why a handle a learner picked in Settings is
  refused (``PATCH /api/auth/profile/``), or None.
* ``email_derived_accounts`` / ``rename_to_generated_handles``  the backfill
  of usernames that show the email (migration 0027 and
  ``manage.py rename_email_derived_usernames``).
"""
from __future__ import annotations

import re
import secrets

HANDLE_MIN_LENGTH = 3
HANDLE_MAX_LENGTH = 30
GENERATED_HANDLE_PREFIX = 'learner_'
HANDLE_TAKEN_MESSAGE = 'This username is taken. Please choose another.'
# A chosen sign-up name that is taken gets '_2', '_3', ...; after about a
# hundred taken variants, a generated handle (bounded queries per sign-in).
_MAX_SUFFIX = 100

_HANDLE_CHARS_RE = re.compile(r'[A-Za-z0-9_.]+')
_HAS_LETTER_OR_DIGIT_RE = re.compile(r'[A-Za-z0-9]')
# Names that pass for the CrackLabs team, compared without '_' / '.' and
# trailing digits ("Admin", "ad.min", "support_1"). Admins and staff may use them.
_RESERVED_HANDLES = frozenset({
    'admin', 'administrator', 'root', 'staff', 'support', 'help', 'helpdesk',
    'moderator', 'mod', 'system', 'official', 'team', 'cracklabs', 'crackcms',
    'null', 'none', 'undefined',
})
_RESERVED_PREFIXES = ('cracklabs', 'crackcms')


def _email_local_part(email) -> str:
    if not isinstance(email, str):
        return ''
    return email.strip().lower().split('@', 1)[0].strip()


def exposes_email(username, email) -> bool:
    """True when ``username`` shows (part of) ``email`` (see the module docstring)."""
    name = username.strip().lower() if isinstance(username, str) else ''
    if not name:
        return False
    if '@' in name:
        return True
    local = _email_local_part(email)
    if not local:
        return False
    stems = {name}
    head, sep, tail = name.rpartition('_')
    if sep and tail.isdigit():
        stems.add(head)  # a collision suffix
    # Derived names were cut to 140 (130 before a suffix) characters.
    return bool(stems & {local, local[:140], local[:130]})


def generate_handle(User, *, attempts: int = 8) -> str:
    """A fresh ``learner_<8 hex>`` handle that no account uses (any case)."""
    for _ in range(attempts):
        candidate = f'{GENERATED_HANDLE_PREFIX}{secrets.token_hex(4)}'
        if not User.objects.filter(username__iexact=candidate).exists():
            return candidate
    # 4 billion values: repeated collisions mean a broken RNG; 16 hex digits cannot collide.
    return f'{GENERATED_HANDLE_PREFIX}{secrets.token_hex(8)}'


def _format_error(name: str):
    """Why ``name`` (already trimmed) is not a well-formed handle, or None."""
    if '@' in name:
        return "Your username can't be an email address."
    if not HANDLE_MIN_LENGTH <= len(name) <= HANDLE_MAX_LENGTH:
        return f'Choose a username of {HANDLE_MIN_LENGTH} to {HANDLE_MAX_LENGTH} characters.'
    if not _HANDLE_CHARS_RE.fullmatch(name):
        return 'Use only letters, numbers, underscores (_) and dots (.).'
    if not _HAS_LETTER_OR_DIGIT_RE.search(name):
        return 'Include at least one letter or number.'
    return None


def _is_reserved(name: str) -> bool:
    key = re.sub(r'[._]+', '', name.lower()).rstrip('0123456789')
    return key in _RESERVED_HANDLES or key.startswith(_RESERVED_PREFIXES)


def _is_team_member(user) -> bool:
    return bool(
        getattr(user, 'role', '') == 'admin'
        or getattr(user, 'is_staff', False)
        or getattr(user, 'is_superuser', False)
    )


def username_for_new_account(User, requested, email, *, team_member: bool = False) -> str:
    """The username of a new account.

    The name the person chose at sign-up (``user_metadata.username`` / the
    local register's ``username``) when it follows the Settings rules
    (``handle_error`` except uniqueness: 3-30 letters, digits, ``_`` and
    ``.``, not part of the email, not a name reserved for the team -- which
    ``team_member``, a trusted admin account, may use), made unique with
    ``_2``, ``_3``, ... within 30 characters. Otherwise a generated
    ``learner_<hex>`` handle: no name given (Google sign-ups), or one that
    would show the email address, break the format rules or pass for the
    CrackLabs team. The learner can pick another one in Settings.
    """
    requested = requested.strip() if isinstance(requested, str) else ''
    if (
        _format_error(requested)
        or exposes_email(requested, email)
        or (_is_reserved(requested) and not team_member)
    ):
        return generate_handle(User)
    candidate = requested
    for suffix in range(2, _MAX_SUFFIX + 1):
        if not User.objects.filter(username__iexact=candidate).exists():
            return candidate
        tail = f'_{suffix}'
        candidate = f'{requested[:HANDLE_MAX_LENGTH - len(tail)]}{tail}'
        if exposes_email(candidate, email) or (_is_reserved(candidate) and not team_member):
            break
    return generate_handle(User)


def handle_error(value, *, user, User):
    """Why ``value`` cannot become ``user``'s public username, or None when it can.

    3-30 letters, digits, ``_`` and ``.``; no email address or part of the
    user's own; not a name that passes for the CrackLabs team (admins and
    staff excepted); not used by another account (any case).
    """
    name = value.strip() if isinstance(value, str) else ''
    problem = _format_error(name)
    if problem:
        return problem
    if exposes_email(name, getattr(user, 'email', '')):
        return "Choose a username that isn't part of your email address."
    if _is_reserved(name) and not _is_team_member(user):
        return 'This username is reserved. Please choose another.'
    taken = User.objects.filter(username__iexact=name)
    if getattr(user, 'pk', None) is not None:
        taken = taken.exclude(pk=user.pk)
    if taken.exists():
        return HANDLE_TAKEN_MESSAGE
    return None


def email_derived_accounts(User):
    """Accounts whose username shows their email address: ``(students, team)``.

    ``students`` lists ``(id, username)`` pairs; ``team`` the ids of admin,
    staff and superuser accounts, which are never renamed automatically (they
    sign in to Django admin by username, and ops commands look them up by
    it). Works with the historical model of a migration.
    """
    students, team = [], []
    rows = (
        User.objects.only('id', 'username', 'email', 'role', 'is_staff', 'is_superuser')
        .order_by('id')
        .iterator(chunk_size=500)
    )
    for user in rows:
        if not exposes_email(user.username, user.email):
            continue
        if _is_team_member(user):
            team.append(user.pk)
        else:
            students.append((user.pk, user.username))
    return students, team


def rename_to_generated_handles(User, accounts, *, generate=None):
    """Give each ``(id, username)`` in ``accounts`` a generated handle.

    Compare-and-set: an account whose username changed since it was listed
    (a learner who picked a handle in Settings meanwhile) keeps it. Returns
    ``(renamed ids, ids left alone)``.
    """
    generate = generate or generate_handle
    renamed, changed_meanwhile = [], []
    for pk, old in accounts:
        updated = User.objects.filter(pk=pk, username=old).update(username=generate(User))
        (renamed if updated else changed_meanwhile).append(pk)
    return renamed, changed_meanwhile
