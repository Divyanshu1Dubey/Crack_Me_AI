"""DRF authentication for Django-issued access tokens (AUTH_PROVIDER=django).

Kept in its own module without rest_framework.views imports: DRF imports
DEFAULT_AUTHENTICATION_CLASSES while rest_framework.views is being
initialised, so importing views from here would be circular.

Checks, in order (each failure is a 401 with a ``code`` the frontend acts on):

1. the mode: in supabase mode this class returns None (inert);
2. SimpleJWT validation: signature, ``exp``, ``iss`` / ``aud`` and the access type
   (``token_not_valid``);
3. a ``session_id`` claim (tokens minted outside a native sign-in have none);
4. the session and its user, in ONE query: the session must exist for this user,
   be unrevoked and unexpired (``session_revoked``); a blocked user gets
   ``account_blocked``; an unverified email ``email_not_confirmed``;
5. the device cap (accounts.device_limits) for everyone but admins, exactly as
   for Supabase sessions; a logged-out device revokes its session.

A warm request costs two queries: the session with its user, and the devices.
"""
from __future__ import annotations

from django.utils import timezone
from rest_framework_simplejwt.authentication import JWTAuthentication

from .auth_mode import django_auth_enabled
from .device_limits import DeviceLimitMixin, _auth_failed, session_id_from_claims

_SESSION_REVOKED = 'This session has ended. Please sign in again.'


class NativeJWTAuthentication(DeviceLimitMixin, JWTAuthentication):
    """Bearer auth for native sessions (accounts.native_sessions); inert unless AUTH_PROVIDER=django."""

    def authenticate_header(self, request):
        return 'Bearer realm="api"'

    def authenticate(self, request):
        if not django_auth_enabled():
            return None
        header = self.get_header(request)
        if header is None:
            return None
        raw_token = self.get_raw_token(header)
        if raw_token is None:
            return None
        validated_token = self.get_validated_token(raw_token)

        sid = session_id_from_claims(validated_token.payload)
        if not sid:
            raise _auth_failed('token_not_valid', 'This sign-in token is not valid. Please sign in again.')
        user = self._session_user(sid, validated_token)

        # Admins are exempt from device tracking and limits (as in supabase mode).
        if user.role == 'admin':
            return (user, validated_token)
        self._enforce_device_limits(request, user, session_id=sid, token=None)
        return (user, validated_token)

    def _session_user(self, sid, validated_token):
        from .models import AuthSession

        session = AuthSession.objects.select_related('user').filter(sid=sid).first()
        token_user = str(validated_token.payload.get('user_id') or '')
        if session is None or str(session.user_id) != token_user:
            raise _auth_failed('session_revoked', _SESSION_REVOKED)
        user = session.user
        if not user.is_active:
            raise _auth_failed(
                'account_blocked', 'This account has been blocked. Contact support if you think this is a mistake.',
            )
        if not session.is_active_at(timezone.now()):
            if session.revoked_reason == 'device_logout':
                # Same answer as the device check gives (the device was logged out).
                raise _auth_failed('device_inactive', 'This device has been logged out or blocked.')
            raise _auth_failed('session_revoked', _SESSION_REVOKED)
        if user.email_verified_at is None:
            raise _auth_failed('email_not_confirmed', 'Please confirm your email address, then sign in again.')
        return user

    def _end_session(self, token, session_id):
        """A logged-out device's session comes back: revoke it, so its refresh token stops too."""
        from .native_sessions import revoke_session

        revoke_session(session_id, 'device_logout')
