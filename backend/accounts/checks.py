"""Deployment checks for sign-in and the admin backup tools (``manage.py check --deploy``).

accounts.W001  Supabase "Confirm email" and "Secure email change" must be ON.
               Linking a local row to a Supabase identity on its first sign-in,
               and the admin email allowlist (CONTROL_TOWER_ADMIN_EMAILS /
               BOOTSTRAP_ADMIN_EMAIL), trust the email Supabase reports as
               confirmed. With "Confirm email" off GoTrue marks every sign-up
               as confirmed, and with "Secure email change" off an email change
               needs no confirmation from the old address, so anyone could claim
               an address they do not own. The setting is in the Supabase
               dashboard (Authentication -> Sign In / Providers -> Email), which
               the backend cannot read; once both are on, set
               SUPABASE_EMAIL_CONFIRMATION_ENABLED=true to acknowledge.
accounts.W002  No public key (SUPABASE_ANON_KEY / SUPABASE_PUBLISHABLE_KEY /
               SUPABASE_AUTH_VERIFY_KEY) for verifying access tokens: the
               service-role key is used as the apikey, or (without it) every
               Supabase sign-in fails.
accounts.W003  CORE_DATA_BACKUP_PATH is not set: the admin "Backup data" /
               "Restore data" tools are refused in production (the default file
               would sit on the container disk, which a redeploy wipes).

Django-native sign-in (AUTH_PROVIDER=django; W001 / W002 are then skipped):

accounts.W004  JWT_SIGNING_KEY is unset (or equals SECRET_KEY): sign-in tokens are
               signed with SECRET_KEY, so rotating one rotates the other.
accounts.W005  GOOGLE_OAUTH_CLIENT_IDS is empty: "Sign in with Google" is off, so
               accounts that only ever signed in with Google need a password reset.
accounts.W006  No real mail backend outside DEBUG (console / locmem / dummy / file):
               verification, password-reset and Google-link emails never arrive.
accounts.W007  NUM_PROXIES is not set: the sign-in rate limits and django-axes key on
               the address that connected to Django -- behind the platform proxy
               that address is the proxy's, shared by every visitor, so five failed
               sign-ins for an account lock it out for everyone. A
               TRUSTED_CLIENT_IP_HEADER alone does not help: it is only read when
               the hop the proxy appended to X-Forwarded-For (NUM_PROXIES) is the
               edge's (crack_cms/client_ip.py).

The Supabase checks only run in supabase mode when Supabase sign-in is
configured (SUPABASE_URL); W003 outside DEBUG; W004-W007 in django mode. They
make no network calls.
"""
from __future__ import annotations

import os

from django.conf import settings
from django.core import checks

from .auth_mode import django_auth_enabled, supabase_auth_enabled

EMAIL_CONFIRMATION_ACK_ENV = "SUPABASE_EMAIL_CONFIRMATION_ENABLED"


def _supabase_auth_configured() -> bool:
    return bool(os.getenv("SUPABASE_URL", "").strip() or os.getenv("NEXT_PUBLIC_SUPABASE_URL", "").strip())


def _truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes", "on")


@checks.register(checks.Tags.security, deploy=True)
def supabase_email_confirmation_check(app_configs=None, **kwargs):
    if not supabase_auth_enabled() or not _supabase_auth_configured() or _truthy(EMAIL_CONFIRMATION_ACK_ENV):
        return []
    return [checks.Warning(
        'Supabase "Confirm email" and "Secure email change" must be enabled.',
        hint=(
            "Accounts are linked on first sign-in, and admin rights are granted to "
            "CONTROL_TOWER_ADMIN_EMAILS / BOOTSTRAP_ADMIN_EMAIL, by the email Supabase reports "
            "as confirmed. With either setting off, anyone can claim an address they do not own. "
            "Turn both on in the Supabase dashboard (Authentication -> Sign In / Providers -> Email), "
            f"then set {EMAIL_CONFIRMATION_ACK_ENV}=true in the backend environment."
        ),
        id="accounts.W001",
    )]


@checks.register(checks.Tags.security, deploy=True)
def supabase_verify_key_check(app_configs=None, **kwargs):
    if not supabase_auth_enabled() or not _supabase_auth_configured():
        return []
    from .supabase_rest_auth import public_verify_key

    if public_verify_key():
        return []
    if os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip():
        message = "Supabase access tokens are verified with the service-role key."
    else:
        message = "No key is configured for verifying Supabase access tokens; every Supabase sign-in fails."
    return [checks.Warning(
        message,
        hint=(
            "Set SUPABASE_ANON_KEY (or SUPABASE_PUBLISHABLE_KEY / SUPABASE_AUTH_VERIFY_KEY) in the "
            "backend environment: the project's public anon / publishable key, the same value as the "
            "frontend's NEXT_PUBLIC_SUPABASE_ANON_KEY."
        ),
        id="accounts.W002",
    )]


@checks.register(checks.Tags.security, deploy=True)
def core_data_backup_path_check(app_configs=None, **kwargs):
    if settings.DEBUG or os.getenv("CORE_DATA_BACKUP_PATH", "").strip():
        return []
    return [checks.Warning(
        "CORE_DATA_BACKUP_PATH is not set; the admin Backup data / Restore data tools are refused.",
        hint=(
            "Point CORE_DATA_BACKUP_PATH at a file on a persistent volume. The default "
            "(<BASE_DIR>/core_data_seed.json) is on the container disk, which every redeploy wipes. "
            "`manage.py backup_core_data --output PATH` / `restore_core_data --input PATH` still work."
        ),
        id="accounts.W003",
    )]


# ── Django-native sign-in (AUTH_PROVIDER=django) ───────────────────────

_DEV_MAIL_BACKENDS = ('console.EmailBackend', 'locmem.EmailBackend', 'dummy.EmailBackend', 'filebased.EmailBackend')


@checks.register(checks.Tags.security, deploy=True)
def native_auth_signing_key_check(app_configs=None, **kwargs):
    if not django_auth_enabled():
        return []
    key = str(getattr(settings, 'JWT_SIGNING_KEY', '') or '')
    if key and key != settings.SECRET_KEY and len(key) >= 32:
        return []
    return [checks.Warning(
        'JWT_SIGNING_KEY is not set (or shorter than 32 characters): Django-native sign-in tokens are signed '
        'with SECRET_KEY or a weak key.',
        hint=(
            'Set JWT_SIGNING_KEY to a separate long random value (python -c "import secrets; '
            'print(secrets.token_urlsafe(64))"). Changing it later signs every session out.'
        ),
        id='accounts.W004',
    )]


@checks.register(checks.Tags.security, deploy=True)
def native_auth_google_client_check(app_configs=None, **kwargs):
    if not django_auth_enabled() or getattr(settings, 'GOOGLE_OAUTH_CLIENT_IDS', None):
        return []
    return [checks.Warning(
        'GOOGLE_OAUTH_CLIENT_IDS is empty: "Sign in with Google" is off.',
        hint=(
            "Set it to the OAuth web client id (comma separated, plus the Android client id for the app). "
            "Accounts that only signed in with Google can otherwise only get in with a password reset."
        ),
        id='accounts.W005',
    )]


@checks.register(checks.Tags.security, deploy=True)
def native_auth_mail_check(app_configs=None, **kwargs):
    if not django_auth_enabled() or settings.DEBUG:
        return []
    backend = str(getattr(settings, 'EMAIL_BACKEND', '') or '')
    smtp_without_host = backend.endswith('smtp.EmailBackend') and not str(getattr(settings, 'EMAIL_HOST', '') or '')
    if not backend.endswith(_DEV_MAIL_BACKENDS) and not smtp_without_host:
        return []
    return [checks.Warning(
        'No mail server is configured: sign-up verification, password reset and Google-link emails are not sent.',
        hint='Set EMAIL_HOST_PASSWORD (Gmail SMTP, settings.py) or EMAIL_BACKEND / EMAIL_HOST for your provider.',
        id='accounts.W006',
    )]


@checks.register(checks.Tags.security, deploy=True)
def native_auth_client_ip_check(app_configs=None, **kwargs):
    from crack_cms.client_ip import parse_num_proxies

    if not django_auth_enabled() or settings.DEBUG:
        return []
    num_proxies = parse_num_proxies((getattr(settings, 'REST_FRAMEWORK', {}) or {}).get('NUM_PROXIES'))
    if num_proxies is not None:
        return []
    header = str(getattr(settings, 'TRUSTED_CLIENT_IP_HEADER', '') or '').strip()
    return [checks.Warning(
        'NUM_PROXIES is not set: sign-in rate limits and lockouts key on the proxy address'
        + (f' ({header} is not read without it).' if header else '.'),
        hint=(
            'django-axes locks an account after 5 failed sign-ins per (account, client IP), and the sign-in '
            'rate limits count per client IP. Behind the platform proxy every visitor has the proxy address, '
            'so one attacker locks an account out for everyone and the limits are shared by all visitors. Set '
            'NUM_PROXIES to the number of proxies that append to X-Forwarded-For (Railway: 1), plus '
            'TRUSTED_CLIENT_IP_HEADER=CF-Connecting-IP behind Cloudflare; then check GET /api/health/client-ip/ '
            'as an admin (settings.py, client-IP notes).'
        ),
        id='accounts.W007',
    )]
