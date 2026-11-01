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

The checks only run when Supabase sign-in is configured (SUPABASE_URL) or, for
W003, outside DEBUG. They make no network calls.
"""
from __future__ import annotations

import os

from django.conf import settings
from django.core import checks

EMAIL_CONFIRMATION_ACK_ENV = "SUPABASE_EMAIL_CONFIRMATION_ENABLED"


def _supabase_auth_configured() -> bool:
    return bool(os.getenv("SUPABASE_URL", "").strip() or os.getenv("NEXT_PUBLIC_SUPABASE_URL", "").strip())


def _truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes", "on")


@checks.register(checks.Tags.security, deploy=True)
def supabase_email_confirmation_check(app_configs=None, **kwargs):
    if not _supabase_auth_configured() or _truthy(EMAIL_CONFIRMATION_ACK_ENV):
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
    if not _supabase_auth_configured():
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
