"""Utilities for mirroring Django users into Supabase Auth (auth.users)."""

from __future__ import annotations

import json
import logging
import os
from urllib import error, request


logger = logging.getLogger(__name__)


def _is_enabled() -> bool:
    return os.getenv("SUPABASE_AUTH_MIRROR_ENABLED", "false").lower() == "true"


def _get_supabase_url() -> str:
    return (os.getenv("SUPABASE_URL", "").strip() or "").rstrip("/")


def _get_service_role_key() -> str:
    return os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()


def sync_user_to_supabase_auth(*, email: str, password: str, username: str = "") -> bool:
    """
    Create a corresponding user in Supabase Auth using the Admin API.

    Returns True when created or already exists, False when mirroring is skipped/failed.
    """
    if not _is_enabled():
        return False

    supabase_url = _get_supabase_url()
    service_role_key = _get_service_role_key()
    if not supabase_url or not service_role_key:
        logger.warning(
            "Supabase auth mirror enabled but SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY are missing."
        )
        return False

    if not email or not password:
        logger.warning("Supabase auth mirror skipped due to missing email/password")
        return False

    payload = {
        "email": email,
        "password": password,
        "email_confirm": True,
        "user_metadata": {"username": username},
    }

    req = request.Request(
        url=f"{supabase_url}/auth/v1/admin/users",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=10) as resp:
            status = int(getattr(resp, "status", 0) or 0)
            return 200 <= status < 300
    except error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="ignore")
        except Exception:
            body = ""

        lowered = body.lower()
        if exc.code in (400, 409, 422) and (
            "already" in lowered or "exists" in lowered or "registered" in lowered
        ):
            # User exists in auth.users already; treat as success for mirroring semantics.
            return True

        logger.warning(
            "Supabase auth mirror failed: status=%s body=%s",
            exc.code,
            body[:300],
        )
        return False
    except Exception:
        logger.exception("Supabase auth mirror request failed")
        return False
