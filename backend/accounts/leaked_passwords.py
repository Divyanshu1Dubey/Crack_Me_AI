"""Passwords known to be public: committed to the (public) repository, printed in CI logs, shared in chats.

An imported Supabase hash of such a password, or a Django password that
still is one, lets anyone who read the repository history sign in. So:

* ``manage.py import_supabase_auth --leaked-password-file PATH`` never imports
  a Supabase hash of one of them (``PASSWORD_WITHHELD_LEAKED``), and an auth
  user without a Django row whose only password is one of them is not created
  (``MISSING_LEAKED_PASSWORD``);
* ``manage.py withhold_leaked_passwords --password-file PATH`` makes any account
  password that verifies one of them unusable (any hasher, including hashes
  imported earlier and their Argon2 re-hash after a sign-in) and ends the
  account's sessions; the owner uses "Forgot password" or Google.

The file holds the passwords, one per line, exactly as typed (blank lines are
skipped). It must live outside the git work tree, and nothing ever prints its
contents: output is counts and account ids only.
"""
from __future__ import annotations

from pathlib import Path

MAX_PASSWORDS = 200


class PasswordFileError(ValueError):
    """The password file cannot be used (the message never contains its contents)."""


def inside_git_work_tree(path) -> bool:
    resolved = Path(path).resolve()
    return any((parent / '.git').exists() for parent in (resolved.parent, *resolved.parent.parents))


def read_password_file(path) -> tuple[str, ...]:
    """The distinct passwords of ``path`` (one per line, exactly as typed), or PasswordFileError."""
    try:
        text = Path(path).read_text(encoding='utf-8')
    except (OSError, UnicodeError) as exc:
        raise PasswordFileError(f'cannot read the password file ({exc.__class__.__name__})') from None
    passwords = tuple(dict.fromkeys(line for line in text.splitlines() if line.strip()))
    if not passwords:
        raise PasswordFileError('the password file lists no password')
    if len(passwords) > MAX_PASSWORDS:
        raise PasswordFileError(f'the password file lists more than {MAX_PASSWORDS} passwords')
    return passwords


def supabase_hash_is_one_of(encrypted_password: str, passwords) -> bool:
    """True when a Supabase (GoTrue bcrypt) ``encrypted_password`` is the hash of one of ``passwords``."""
    from .hashers import SupabaseBcryptPasswordHasher, encoded_from_supabase_hash

    encoded = encoded_from_supabase_hash(encrypted_password)
    if not encoded or not passwords:
        return False
    hasher = SupabaseBcryptPasswordHasher()
    return any(hasher.verify(password, encoded) for password in passwords)


def password_is_one_of(encoded: str, passwords) -> bool:
    """True when a Django ``password`` value (any configured hasher) verifies one of ``passwords``. Never re-hashes."""
    from django.contrib.auth.hashers import check_password, is_password_usable

    if not encoded or not is_password_usable(encoded) or not passwords:
        return False
    return any(check_password(password, encoded) for password in passwords)
