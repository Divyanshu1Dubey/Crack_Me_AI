"""Password hasher for bcrypt hashes imported from Supabase Auth (GoTrue).

``manage.py import_supabase_auth`` stores a Supabase ``encrypted_password``
(``$2a$10$...``) as ``supabase_bcrypt$`` + the hash, e.g.
``supabase_bcrypt$$2a$10$<22-char salt><31-char digest>``. Django's
``BCryptPasswordHasher.decode`` / ``safe_summary`` / ``harden_runtime``
parse that form unchanged.

Why a subclass instead of Django's ``BCryptPasswordHasher``:

* bcrypt 5 raises ``ValueError`` for a password longer than 72 bytes (Django
  5.2 passes the raw password to ``bcrypt.hashpw``): a long password typed at
  the login form became an HTTP 500 instead of a failed check. GoTrue (Go's
  ``x/crypto/bcrypt``) only ever looks at the first 72 bytes, so this hasher
  does the same for verification and never raises.
* the comparison is constant time (``hmac.compare_digest`` through
  ``constant_time_compare``);
* ``must_update`` is always True: the first successful sign-in re-hashes the
  password with the preferred hasher (Argon2, first in PASSWORD_HASHERS),
  because ``AbstractBaseUser.check_password`` saves through its setter. The
  hasher is listed last so it is never used for new passwords. Accounts still
  on an imported hash: ``CustomUser.objects.filter(password__startswith='supabase_bcrypt$')``.
"""
from __future__ import annotations

import re

from django.contrib.auth.hashers import BCryptPasswordHasher
from django.utils.crypto import constant_time_compare

# GoTrue / pyca bcrypt hashes: $2a$ / $2b$ / $2y$, two-digit cost, 22-char
# salt + 31-char digest in bcrypt's base64 alphabet.
BCRYPT_HASH_RE = re.compile(r'^\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}\Z')
BCRYPT_MAX_PASSWORD_BYTES = 72
ALGORITHM = 'supabase_bcrypt'


def encoded_from_supabase_hash(encrypted_password: str) -> str:
    """The Django ``password`` value for a Supabase ``encrypted_password`` ('' if it is not a bcrypt hash)."""
    value = (encrypted_password or '').strip()
    if not BCRYPT_HASH_RE.match(value):
        return ''
    return f'{ALGORITHM}${value}'


class SupabaseBcryptPasswordHasher(BCryptPasswordHasher):
    """Verifies imported GoTrue bcrypt hashes; never the preferred hasher (see module docstring)."""

    algorithm = ALGORITHM
    digest = None  # plain bcrypt over the password bytes, as GoTrue stored it

    def encode(self, password, salt):
        bcrypt = self._load_library()
        raw = password.encode() if isinstance(password, str) else bytes(password)
        # Same bytes GoTrue hashed: bcrypt only ever uses the first 72.
        data = bcrypt.hashpw(raw[:BCRYPT_MAX_PASSWORD_BYTES], salt)
        return f'{self.algorithm}${data.decode("ascii")}'

    def verify(self, password, encoded):
        try:
            algorithm, data = encoded.split('$', 1)
        except (AttributeError, ValueError):
            return False
        if algorithm != self.algorithm or not BCRYPT_HASH_RE.match(data):
            return False
        try:
            encoded_2 = self.encode(password, data.encode('ascii'))
        except (TypeError, ValueError, UnicodeError):
            # A malformed stored hash or input: a failed check, never a 500.
            return False
        return constant_time_compare(encoded, encoded_2)

    def must_update(self, encoded):
        return True
