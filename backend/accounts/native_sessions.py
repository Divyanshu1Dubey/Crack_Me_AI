"""Server-side sessions for Django-issued JWTs (AUTH_PROVIDER=django).

Every native sign-in creates an ``AuthSession`` and a SimpleJWT refresh token
whose ``session_id`` claim is the session's ``sid``. SimpleJWT copies the
claim into every access token made from it (``RefreshToken.access_token``),
so the device cap keys on it exactly as on a Supabase session
(accounts.device_limits, ``UserDevice.session_id``).

* ``issue_session_tokens(user, request, method)``: a new session and its first token pair.
* ``rotate(raw_refresh)``: the presented refresh token must be the session's
  current one (``refresh_jti``); it is replaced (rotation). The token rotated
  just before it (``previous_refresh_jti``) still gets an ACCESS token for
  NATIVE_AUTH_REFRESH_REUSE_SECONDS, because another tab sharing the browser
  storage may have rotated first. Any other reuse of a rotated token means
  two parties hold the session's tokens: the whole session is revoked
  (``refresh_reuse``) and both must sign in again.
* ``revoke_session`` / ``revoke_user_sessions``: logout, password reset or
  change, device logout, account block. NativeJWTAuthentication checks the
  session on every request (one query, joined with the user row), so a
  revocation applies to the next request in every worker.

Errors are ``NativeAuthError`` (a machine-readable ``code`` and an HTTP status).
"""
from __future__ import annotations

import hmac
import ipaddress
import logging
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .device_limits import session_id_from_claims

logger = logging.getLogger(__name__)

SESSION_CLAIM = 'session_id'
_DEFAULT_MAX_DAYS = 60
_DEFAULT_REUSE_SECONDS = 20

SESSION_REVOKED_DETAIL = 'This session has ended. Please sign in again.'
TOKEN_INVALID_DETAIL = 'This sign-in token is invalid or has expired. Please sign in again.'
ACCOUNT_BLOCKED_DETAIL = 'This account has been blocked. Contact support if you think this is a mistake.'
EMAIL_NOT_CONFIRMED_DETAIL = 'Please confirm your email address, then sign in again.'
DEVICE_INACTIVE_DETAIL = 'This device has been logged out or blocked.'


class NativeAuthError(Exception):
    """A refused native-auth request: ``code`` for the frontend, ``status`` for HTTP."""

    def __init__(self, code: str, detail: str, status: int = 401):
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.status = status

    def response(self):
        from rest_framework.response import Response

        return Response({'detail': self.detail, 'code': self.code}, status=self.status)


def session_max_age() -> timedelta:
    try:
        days = int(getattr(settings, 'NATIVE_AUTH_SESSION_MAX_DAYS', _DEFAULT_MAX_DAYS))
    except (TypeError, ValueError):
        days = _DEFAULT_MAX_DAYS
    return timedelta(days=max(1, days))


def refresh_reuse_window() -> timedelta:
    try:
        seconds = int(getattr(settings, 'NATIVE_AUTH_REFRESH_REUSE_SECONDS', _DEFAULT_REUSE_SECONDS))
    except (TypeError, ValueError):
        seconds = _DEFAULT_REUSE_SECONDS
    return timedelta(seconds=max(0, seconds))


def client_ip(request) -> str | None:
    """The client address for the session record (crack_cms.client_ip), or None."""
    if request is None:
        return None
    try:
        from crack_cms.client_ip import get_client_ip

        value = get_client_ip(request)
    except Exception:  # noqa: BLE001 - bookkeeping only
        value = ''
    try:
        return str(ipaddress.ip_address(value)) if value else None
    except ValueError:
        return None


def _user_agent(request) -> str:
    if request is None:
        return ''
    return str(request.META.get('HTTP_USER_AGENT', '') or '')[:255]


def _refresh_token_for(user, sid):
    from rest_framework_simplejwt.tokens import RefreshToken

    refresh = RefreshToken.for_user(user)
    refresh[SESSION_CLAIM] = sid
    return refresh


def issue_session_tokens(user, request, method: str) -> dict:
    """Create a session for ``user`` and return ``{'access', 'refresh', 'session_id'}`` (its first token pair)."""
    from .models import AuthSession

    now = timezone.now()
    sid = str(uuid.uuid4())
    refresh = _refresh_token_for(user, sid)
    AuthSession.objects.create(
        sid=sid,
        user=user,
        method=method,
        refresh_jti=str(refresh['jti']),
        expires_at=now + session_max_age(),
        last_used_at=now,
        ip_address=client_ip(request),
        user_agent=_user_agent(request),
    )
    return {'access': str(refresh.access_token), 'refresh': str(refresh), 'session_id': sid}


def session_is_active(sid, user_id) -> bool:
    """True while the session exists for this user, is not revoked and has not expired."""
    from .models import AuthSession

    if not sid:
        return False
    return AuthSession.objects.filter(
        sid=sid, user_id=user_id, revoked_at__isnull=True, expires_at__gt=timezone.now(),
    ).exists()


def revoke_session(sid, reason: str) -> int:
    """Revoke one session (no-op when it is unknown or already revoked). Returns the rows changed."""
    from .models import AuthSession

    if not sid:
        return 0
    return AuthSession.objects.filter(sid=sid, revoked_at__isnull=True).update(
        revoked_at=timezone.now(), revoked_reason=reason,
    )


def revoke_user_sessions(user_or_id, reason: str, *, except_sid=None) -> int:
    """Revoke every open session of a user, optionally keeping ``except_sid``."""
    from .models import AuthSession

    user_id = getattr(user_or_id, 'pk', user_or_id)
    rows = AuthSession.objects.filter(user_id=user_id, revoked_at__isnull=True)
    if except_sid:
        rows = rows.exclude(sid=except_sid)
    return rows.update(revoked_at=timezone.now(), revoked_reason=reason)


def session_id_of_token(raw_token, token_class_name='RefreshToken') -> tuple[str | None, str | None]:
    """(sid, user_id) of a valid refresh (or access) token, else (None, None). Verifies the signature."""
    from rest_framework_simplejwt import tokens
    from rest_framework_simplejwt.exceptions import TokenError

    if not isinstance(raw_token, str) or not raw_token or len(raw_token) > 4096:
        return None, None  # (SimpleJWT would mint a NEW token for None)
    token_class = getattr(tokens, token_class_name)
    try:
        token = token_class(raw_token)
    except (TokenError, TypeError, ValueError):
        return None, None
    return session_id_from_claims(token.payload), str(token.payload.get('user_id') or '') or None


def _equal(a: str, b: str) -> bool:
    return bool(a) and bool(b) and hmac.compare_digest(str(a), str(b))


def rotate(raw_refresh) -> dict:
    """Exchange a refresh token: ``{'access', 'refresh', 'session_id'}``, or ``{'access', 'session_id'}``
    inside the reuse window (another tab already stored the rotated refresh token).

    Raises NativeAuthError: ``token_not_valid`` (bad / expired token),
    ``session_revoked`` (revoked, expired or reused session), ``account_blocked``,
    ``email_not_confirmed`` or ``device_inactive`` (its device was logged out).
    """
    from django.contrib.auth import get_user_model
    from rest_framework_simplejwt.exceptions import TokenError
    from rest_framework_simplejwt.tokens import RefreshToken

    from .models import AuthSession, UserDevice

    if not isinstance(raw_refresh, str) or not raw_refresh or len(raw_refresh) > 4096:
        raise NativeAuthError('token_not_valid', TOKEN_INVALID_DETAIL)
    try:
        presented = RefreshToken(raw_refresh)
    except TokenError:
        raise NativeAuthError('token_not_valid', TOKEN_INVALID_DETAIL) from None
    sid = session_id_from_claims(presented.payload)
    jti = str(presented.payload.get('jti') or '')
    user_id = str(presented.payload.get('user_id') or '')
    if not sid or not jti or not user_id:
        raise NativeAuthError('token_not_valid', TOKEN_INVALID_DETAIL)

    now = timezone.now()
    refusal = None
    result = None
    with transaction.atomic():
        session = AuthSession.objects.select_for_update().filter(sid=sid).first()
        if session is None or str(session.user_id) != user_id:
            raise NativeAuthError('token_not_valid', TOKEN_INVALID_DETAIL)
        if not session.is_active_at(now):
            if session.revoked_reason == 'device_logout':
                raise NativeAuthError('device_inactive', DEVICE_INACTIVE_DETAIL)
            raise NativeAuthError('session_revoked', SESSION_REVOKED_DETAIL)
        user = get_user_model().objects.filter(pk=session.user_id).first()
        if user is None:
            raise NativeAuthError('token_not_valid', TOKEN_INVALID_DETAIL)
        if not user.is_active:
            raise NativeAuthError('account_blocked', ACCOUNT_BLOCKED_DETAIL)
        if user.email_verified_at is None:
            raise NativeAuthError('email_not_confirmed', EMAIL_NOT_CONFIRMED_DETAIL)
        if user.role != 'admin' and UserDevice.objects.filter(
            user_id=user.pk, session_id=sid, is_active=False,
        ).exists():
            # Its device was logged out (Settings / admin) or taken over by a
            # newer sign-in on that browser.
            AuthSession.objects.filter(pk=session.pk).update(revoked_at=now, revoked_reason='device_logout')
            refusal = NativeAuthError('device_inactive', DEVICE_INACTIVE_DETAIL)
        elif _equal(jti, session.refresh_jti):
            replacement = _refresh_token_for(user, sid)
            AuthSession.objects.filter(pk=session.pk).update(
                previous_refresh_jti=session.refresh_jti,
                refresh_jti=str(replacement['jti']),
                rotated_at=now,
                last_used_at=now,
            )
            result = {'access': str(replacement.access_token), 'refresh': str(replacement), 'session_id': sid}
        elif (
            _equal(jti, session.previous_refresh_jti)
            and session.rotated_at is not None
            and now - session.rotated_at <= refresh_reuse_window()
        ):
            # Another tab rotated this token a moment ago and stored the new
            # one; this request only needs an access token.
            AuthSession.objects.filter(pk=session.pk).update(last_used_at=now)
            result = {'access': str(presented.access_token), 'session_id': sid}
        else:
            AuthSession.objects.filter(pk=session.pk).update(revoked_at=now, revoked_reason='refresh_reuse')
            logger.warning(
                'Refresh token reuse on native session of account id=%s; the session is revoked.', session.user_id,
            )
            refusal = NativeAuthError('session_revoked', SESSION_REVOKED_DETAIL)
    # Raised after the block so the revocation above is committed.
    if refusal is not None:
        raise refusal
    return result
