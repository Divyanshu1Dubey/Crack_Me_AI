"""Password validator that refuses passwords published in this (public) repository's history.

An old version of manage.py bootstrap_admin shipped a default password literal. The literal was
removed (f011c1d) but stays in the git history, and on 2026-11-03 thirteen accounts still used it
(manage.py withhold_leaked_passwords clears such passwords). This validator keeps sign-up, password
change and password reset from setting it again.

Only SHA-256 digests of the normalised password (surrounding whitespace removed, casefolded) are
kept here, never the text, so this file does not re-publish it and case or spacing variants are
refused too. ``PUBLISHED_PASSWORD_SHA256`` (settings / env, comma-separated hex digests computed
the same way) adds more, e.g. for literals found later.
"""
from __future__ import annotations

import hashlib

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

# SHA-256 of the normalised default password once committed in bootstrap_admin.py.
BUILTIN_PUBLISHED_PASSWORD_SHA256 = frozenset({
    '37cab5767fedfed34a8949b6bb6780f3b90a3e42f7abfe66a2535554454695bc',
})


def normalised_password_digest(password: str) -> str:
    """The digest this module compares: sha256 of the stripped, casefolded password (UTF-8)."""
    return hashlib.sha256(str(password or '').strip().casefold().encode('utf-8')).hexdigest()


def published_password_digests() -> frozenset:
    extra = getattr(settings, 'PUBLISHED_PASSWORD_SHA256', '') or ''
    if isinstance(extra, str):
        extra = extra.split(',')
    cleaned = {str(value).strip().lower() for value in extra if str(value).strip()}
    return BUILTIN_PUBLISHED_PASSWORD_SHA256 | frozenset(cleaned)


def is_published_password(password: str) -> bool:
    return normalised_password_digest(password) in published_password_digests()


class PublishedPasswordValidator:
    """Refuses a password that was published in the repository (see the module docstring)."""

    def validate(self, password, user=None):
        if is_published_password(password):
            raise ValidationError(
                _('This password was published and is not safe to use. Please choose a different one.'),
                code='password_published',
            )

    def get_help_text(self):
        return _('Your password cannot be one that was published.')
