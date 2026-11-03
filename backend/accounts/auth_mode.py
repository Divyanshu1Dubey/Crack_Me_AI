"""Which sign-in provider is active (settings.AUTH_PROVIDER), read per request.

'supabase' (default): Supabase Auth issues tokens (accounts.supabase_rest_auth).
'django': Django signs people in itself (accounts.native_auth).

Kept free of DRF imports: the authenticators import it while DRF loads
DEFAULT_AUTHENTICATION_CLASSES. Read at call time so ``override_settings``
switches the mode in tests.
"""
from __future__ import annotations

from django.conf import settings

SUPABASE = 'supabase'
DJANGO = 'django'
PROVIDERS = (SUPABASE, DJANGO)


def auth_provider() -> str:
    value = str(getattr(settings, 'AUTH_PROVIDER', SUPABASE) or SUPABASE).strip().lower()
    # settings.py refuses unknown values at start-up; anything else seen at run
    # time (a bad override) keeps the historical Supabase behaviour.
    return value if value in PROVIDERS else SUPABASE


def django_auth_enabled() -> bool:
    return auth_provider() == DJANGO


def supabase_auth_enabled() -> bool:
    return auth_provider() == SUPABASE
