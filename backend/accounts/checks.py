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
accounts.W007  The client address is not hardened: either TRUSTED_CLIENT_IP_HEADER is
               read from any peer (TRUSTED_CLIENT_IP_HEADER_FROM unset / "any" and no
               TRUSTED_CLIENT_IP_SECRET), so a request sent to the origin directly
               can name its own address (fresh rate-limit buckets and lockout keys),
               or neither NUM_PROXIES nor the header is set, so lockouts key on the
               proxy address shared by every visitor (crack_cms/client_ip.py).
accounts.E001  (an Error, not deploy-only, outside DEBUG) TRUSTED_CLIENT_IP_HEADER_FROM
               restricts the header but NUM_PROXIES is not set: every visitor would
               share the proxy address. ``migrate`` (release.sh) refuses to run, so
               the deploy stops before that configuration serves anyone.

The Supabase checks only run in supabase mode when Supabase sign-in is
configured (SUPABASE_URL); W003 outside DEBUG; W004-W007 in django mode; E001 in
both modes. They make no network calls.
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
    header = str(getattr(settings, 'TRUSTED_CLIENT_IP_HEADER', '') or '').strip()
    restricted = _client_ip_header_restricted()
    secret = bool(str(getattr(settings, 'TRUSTED_CLIENT_IP_SECRET', '') or '').strip())
    hardening = (
        'Check GET /api/health/client-ip/ as an admin: if the right-most X-Forwarded-For entry of a request '
        'through Cloudflare is a Cloudflare address, set NUM_PROXIES=1 and TRUSTED_CLIENT_IP_HEADER_FROM='
        'cloudflare; otherwise add a Cloudflare Transform Rule header with TRUSTED_CLIENT_IP_SECRET. Removing '
        "the service's public *.up.railway.app domain closes the obvious way around Cloudflare, not every one "
        '(docs/DEPLOY_RAILWAY.md).'
    )
    if header and not restricted and not secret:
        return [checks.Warning(
            f'{header} is read from any peer: a request sent to the origin directly (around Cloudflare) can name '
            'its own client address, getting fresh sign-in rate-limit buckets and lockout keys.',
            hint='The per-email limits still cap guessing on one account, not credential stuffing across accounts. '
                 + hardening,
            id='accounts.W007',
        )]
    if num_proxies is None and not header:
        return [checks.Warning(
            'The client address is unknown (neither NUM_PROXIES nor TRUSTED_CLIENT_IP_HEADER is set): lockouts '
            'key on the proxy address and the rate limits on the raw, client-supplied X-Forwarded-For.',
            hint='Behind the platform proxy every visitor has the proxy address, so one attacker can lock an account '
                 'out for everyone. Set TRUSTED_CLIENT_IP_HEADER=CF-Connecting-IP behind Cloudflare. ' + hardening,
            id='accounts.W007',
        )]
    return []


def _client_ip_header_restricted() -> bool:
    value = str(getattr(settings, 'TRUSTED_CLIENT_IP_HEADER_FROM', '') or '').strip().lower()
    return bool(value) and value != 'any'


@checks.register(checks.Tags.security)
def client_ip_restriction_needs_proxy_depth(app_configs=None, **kwargs):
    """accounts.E001: TRUSTED_CLIENT_IP_HEADER_FROM restricted without NUM_PROXIES (outside DEBUG).

    Not a deploy-only check on purpose: ``migrate`` (release.sh) refuses to run, so the deploy stops and the
    previous version keeps serving. In that state the peer is REMOTE_ADDR, the platform proxy shared by every
    visitor: the restricted header is never read, every visitor shares one sign-in bucket and anyone can lock a
    username for everyone through django-axes.
    """
    from crack_cms.client_ip import parse_num_proxies

    if settings.DEBUG or not _client_ip_header_restricted():
        return []
    if parse_num_proxies((getattr(settings, 'REST_FRAMEWORK', {}) or {}).get('NUM_PROXIES')) is not None:
        return []
    return [checks.Error(
        'TRUSTED_CLIENT_IP_HEADER_FROM restricts the client-IP header but NUM_PROXIES is not set: every visitor '
        'would share the proxy address in the rate limits and lockouts.',
        hint='Set NUM_PROXIES (Railway: 1, after checking GET /api/health/client-ip/), or unset '
             'TRUSTED_CLIENT_IP_HEADER_FROM (docs/DEPLOY_RAILWAY.md).',
        id='accounts.E001',
    )]
