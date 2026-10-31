"""Authentication class for the dev-only local auth mode.

Kept in its own module (no rest_framework.views import) because DRF imports
DEFAULT_AUTHENTICATION_CLASSES while rest_framework.views is still being
initialised; importing views from here would be circular.
"""
from django.conf import settings
from rest_framework_simplejwt.authentication import JWTAuthentication


def local_auth_enabled() -> bool:
    return bool(getattr(settings, 'LOCAL_DEV_AUTH', False))


class LocalDevJWTAuthentication(JWTAuthentication):
    """SimpleJWT bearer auth, active only in local dev mode (DEBUG only)."""

    def authenticate(self, request):
        if not local_auth_enabled():
            return None
        return super().authenticate(request)
