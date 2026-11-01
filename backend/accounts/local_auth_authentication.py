"""Authentication class for the dev-only local auth mode.

Kept in its own module (no rest_framework.views import) because DRF imports
DEFAULT_AUTHENTICATION_CLASSES while rest_framework.views is still being
initialised; importing views from here would be circular.
"""
from django.conf import settings
from rest_framework import exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication


def local_auth_enabled() -> bool:
    return bool(getattr(settings, 'LOCAL_DEV_AUTH', False))


class LocalDevJWTAuthentication(JWTAuthentication):
    """SimpleJWT bearer auth, active only in local dev mode (DEBUG only)."""

    def authenticate(self, request):
        if not local_auth_enabled():
            return None
        return super().authenticate(request)

    def get_user(self, validated_token):
        try:
            return super().get_user(validated_token)
        except exceptions.AuthenticationFailed as exc:
            # A blocked (is_active=False) user: answer with the same code as the
            # Supabase authenticator (accounts.supabase_rest_auth), which the
            # frontend acts on by signing this browser out. SimpleJWT's own
            # code ('user_inactive') was not handled consistently.
            if _is_inactive_user_failure(exc):
                raise exceptions.AuthenticationFailed({
                    'detail': 'This account has been blocked. Contact support if you think this is a mistake.',
                    'code': 'account_blocked',
                }) from exc
            raise


def _is_inactive_user_failure(exc: exceptions.AuthenticationFailed) -> bool:
    """SimpleJWT's "User is inactive" failure, as a detail dict or a coded string."""
    detail = exc.detail
    if isinstance(detail, dict):
        return str(detail.get('code') or '') == 'user_inactive'
    return getattr(detail, 'code', None) == 'user_inactive'
