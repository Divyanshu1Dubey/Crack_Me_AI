"""Rate limits and lockout rules for the Django-native sign-in (AUTH_PROVIDER=django).

Per client IP: the sign-in views use ``crack_cms.throttling.ClientIPScopedRateThrottle``,
keyed on ``crack_cms.client_ip.get_client_ip`` -- the address django-axes
uses -- so forged X-Forwarded-For / CF-Connecting-IP headers never open a
new bucket.

Per email: a distributed attack on ONE account (many IPs, one email) is
limited here: the cache key is a SHA-256 of the lower-cased email, so no
address is stored in the cache. Rates live in
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] (``*_email`` scopes, settings.py).

* ``EmailRateThrottle`` subclasses are DRF view throttles reading
  ``request.data['email']``: every request counts (each one may send a mail).
* ``email_limit_reached`` / ``record_email_hit`` are the same buckets used by
  hand, for limits that must count only some outcomes (failed sign-ins) or an
  email that is not in the request body (the address of a Google token).
* ``NativeVerifyLinkThrottle``: attempts per emailed link (its digest), so
  students sharing one carrier-grade NAT address do not share a bucket.

``axes_lockout_parameters`` (settings.AXES_LOCKOUT_PARAMETERS) chooses what
django-axes locks after AXES_FAILURE_LIMIT failures.
"""
from __future__ import annotations

import hashlib

from django.core.cache import cache as default_cache
from rest_framework.throttling import SimpleRateThrottle

from crack_cms.throttling import StrictClientIPIdentMixin

# Native sign-in endpoints (accounts/urls.py): a lockout per (account, client
# IP) there, with the per-email limit above for distributed attacks.
NATIVE_AUTH_PATH_PREFIX = '/api/auth/native/'


def axes_lockout_parameters(request_or_attempt, credentials=None):
    """django-axes lockout parameters (AXES_LOCKOUT_PARAMETERS) for a request or a stored AccessAttempt.

    * The Django-native sign-in (/api/auth/native/*): one lockout per
      (username, client IP) combination, so nobody can lock a student out
      from elsewhere; the per-email limit (native_login_email) slows a
      distributed attack on one account.
    * Everything else -- Django admin (/admin/login/) and the dev-only local
      login -- keeps the separate username and client-IP lockouts it always
      had: five failures for a staff username from anywhere lock that
      username for AXES_COOLOFF_TIME.
    """
    path = str(getattr(request_or_attempt, 'path_info', '') or '')
    if path.startswith(NATIVE_AUTH_PATH_PREFIX):
        return [['username', 'ip_address']]
    return ['username', 'ip_address']


def normalized_email(value) -> str:
    """The lower-cased, trimmed address, or '' when ``value`` is not an email-like string."""
    if not isinstance(value, str):
        return ''
    email = value.strip().lower()
    if '@' not in email or len(email) > 254:
        return ''
    return email


def email_digest(email: str) -> str:
    return hashlib.sha256(normalized_email(email).encode('utf-8')).hexdigest()


class EmailRateThrottle(SimpleRateThrottle):
    """Requests per email address (``request.data[email_field]``) for ``scope``."""

    scope: str | None = None
    email_field = 'email'
    cache_format = 'throttle_email_%(scope)s_%(ident)s'

    def get_cache_key(self, request, view):
        data = getattr(request, 'data', None)
        value = data.get(self.email_field) if hasattr(data, 'get') else None
        email = normalized_email(value)
        if not email:
            return None  # nothing to key on: the view refuses the request anyway
        return self.cache_format % {'scope': self.scope, 'ident': email_digest(email)}


class NativeRegisterEmailThrottle(EmailRateThrottle):
    scope = 'native_register_email'


class NativeVerifyEmailThrottle(EmailRateThrottle):
    scope = 'native_verify_email'


class PasswordResetEmailThrottle(EmailRateThrottle):
    scope = 'password_reset_email'


class NativeVerifyLinkThrottle(SimpleRateThrottle):
    """Attempts per emailed verification link (``request.data`` token, and uid), keyed on its digest."""

    scope = 'native_verify_link'
    cache_format = 'throttle_link_%(scope)s_%(ident)s'

    def get_cache_key(self, request, view):
        data = getattr(request, 'data', None)
        token = data.get('token') if hasattr(data, 'get') else None
        if not isinstance(token, str) or not token or len(token) > 4096:
            return None  # the view refuses the request anyway
        uid = data.get('uid') if hasattr(data, 'get') else None
        value = f'{uid if isinstance(uid, str) else ""}|{token}'
        return self.cache_format % {'scope': self.scope, 'ident': hashlib.sha256(value.encode('utf-8')).hexdigest()}


class NativeRefreshThrottle(StrictClientIPIdentMixin, SimpleRateThrottle):
    """Token refreshes / sign-outs per native session (the refresh token's verified ``session_id``).

    Keyed on the session rather than the client IP, so visitors behind one
    proxy address never share a bucket; a request without a valid refresh
    token falls back to the client IP (crack_cms.client_ip).
    """

    scope = 'native_refresh'

    def get_cache_key(self, request, view):
        from .native_sessions import session_id_of_token

        data = getattr(request, 'data', None)
        raw = data.get('refresh') if hasattr(data, 'get') else None
        sid = None
        if isinstance(raw, str) and 0 < len(raw) <= 4096:
            sid, _user_id = session_id_of_token(raw, 'RefreshToken')
        ident = f'sid:{sid}' if sid else f'ip:{self.get_ident(request)}'
        return self.cache_format % {'scope': self.scope, 'ident': hashlib.sha256(ident.encode('utf-8')).hexdigest()}


class _ManualEmailBucket(SimpleRateThrottle):
    """A SimpleRateThrottle used outside DRF's view throttling (see module docstring)."""

    cache = default_cache
    cache_format = 'throttle_email_%(scope)s_%(ident)s'

    def __init__(self, scope: str):
        self.scope = scope
        super().__init__()

    def get_cache_key(self, request, view):  # pragma: no cover - not used as a view throttle
        return None

    def key_for(self, email: str) -> str:
        return self.cache_format % {'scope': self.scope, 'ident': email_digest(email)}

    def recent_hits(self, email: str) -> list:
        now = self.timer()
        return [t for t in self.cache.get(self.key_for(email), []) if t > now - self.duration]


def email_limit_reached(scope: str, email: str) -> bool:
    """True when ``email`` has used up the ``scope`` rate (nothing is recorded)."""
    email = normalized_email(email)
    if not email:
        return False
    bucket = _ManualEmailBucket(scope)
    if bucket.rate is None:
        return False
    return len(bucket.recent_hits(email)) >= bucket.num_requests


def record_email_hit(scope: str, email: str) -> None:
    """Count one event for ``email`` in the ``scope`` bucket."""
    email = normalized_email(email)
    if not email:
        return
    bucket = _ManualEmailBucket(scope)
    if bucket.rate is None:
        return
    history = bucket.recent_hits(email)
    history.insert(0, bucket.timer())
    bucket.cache.set(bucket.key_for(email), history, bucket.duration)


def consume_email_quota(scope: str, email: str) -> bool:
    """Record one event and return True, or return False (nothing recorded) when the rate is used up."""
    if email_limit_reached(scope, email):
        return False
    record_email_hit(scope, email)
    return True
