"""Utilities for mirroring Django users into Supabase Auth (auth.users)."""

from __future__ import annotations

import json
import logging
import os
from typing import Any
from urllib import error, parse, request


logger = logging.getLogger(__name__)


def _is_enabled() -> bool:
    return os.getenv("SUPABASE_AUTH_MIRROR_ENABLED", "false").lower() == "true"


def _get_supabase_url() -> str:
    return (os.getenv("SUPABASE_URL", "").strip() or "").rstrip("/")


def _get_service_role_key() -> str:
    return os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()


def _is_configured() -> bool:
    return bool(_get_supabase_url() and _get_service_role_key())


def _auth_admin_headers() -> dict[str, str]:
    service_role_key = _get_service_role_key()
    return {
        "Content-Type": "application/json",
        "apikey": service_role_key,
        "Authorization": f"Bearer {service_role_key}",
    }


def _request_admin_json(*, method: str, path: str, payload: dict[str, Any] | None = None, query: dict[str, Any] | None = None):
    supabase_url = _get_supabase_url()
    if not supabase_url or not _get_service_role_key():
        return None

    url = f"{supabase_url}{path}"
    if query:
        query_string = parse.urlencode({key: value for key, value in query.items() if value not in (None, "")})
        if query_string:
            url = f"{url}?{query_string}"

    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = request.Request(url=url, data=data, headers=_auth_admin_headers(), method=method)

    try:
        with request.urlopen(req, timeout=10) as resp:
            raw_body = resp.read().decode("utf-8", errors="ignore")
            return json.loads(raw_body) if raw_body else {}
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
            return {"exists": True, "body": body}

        logger.warning(
            "Supabase admin request failed: method=%s path=%s status=%s body=%s",
            method,
            path,
            exc.code,
            body[:300],
        )
        return None
    except Exception:
        logger.exception("Supabase admin request failed: method=%s path=%s", method, path)
        return None


def list_supabase_auth_users(*, per_page: int = 200) -> list[dict[str, Any]]:
    """Return all Supabase Auth users using the admin API."""
    if not _is_configured():
        return []

    users: list[dict[str, Any]] = []
    page = 1

    while True:
        payload = _request_admin_json(
            method="GET",
            path="/auth/v1/admin/users",
            query={"page": page, "per_page": per_page},
        )
        if not payload:
            break

        page_users = payload.get("users") or []
        if not isinstance(page_users, list):
            break

        users.extend([user for user in page_users if isinstance(user, dict)])
        if len(page_users) < per_page:
            break
        page += 1

    return users


def delete_supabase_auth_user(user_id: str, *, soft_delete: bool = False) -> bool:
    """Delete one Supabase Auth user by ID."""
    if not _is_configured() or not user_id:
        return False

    payload = _request_admin_json(
        method="DELETE",
        path=f"/auth/v1/admin/users/{user_id}",
        payload={"should_soft_delete": soft_delete},
    )
    return payload is not None


def upsert_supabase_auth_user(
    *,
    email: str,
    password: str,
    username: str = "",
    user_metadata: dict[str, Any] | None = None,
    app_metadata: dict[str, Any] | None = None,
) -> bool:
    """Create or update one Supabase Auth user."""
    if not _is_configured():
        return False

    normalized_email = email.strip().lower()
    if not normalized_email or not password:
        return False

    existing_users = list_supabase_auth_users()
    matching_user = next(
        (user for user in existing_users if str(user.get("email") or "").strip().lower() == normalized_email),
        None,
    )

    base_user_metadata: dict[str, Any] = {"username": username} if username else {}
    if user_metadata:
        base_user_metadata.update(user_metadata)

    payload: dict[str, Any] = {
        "email": normalized_email,
        "password": password,
        "email_confirm": True,
        "user_metadata": base_user_metadata,
    }
    if app_metadata is not None:
        payload["app_metadata"] = app_metadata

    if matching_user and matching_user.get("id"):
        response = _request_admin_json(
            method="PUT",
            path=f"/auth/v1/admin/users/{matching_user['id']}",
            payload=payload,
        )
        return response is not None

    response = _request_admin_json(
        method="POST",
        path="/auth/v1/admin/users",
        payload=payload,
    )
    return response is not None


def sync_user_to_supabase_auth(*, email: str, password: str, username: str = "") -> bool:
    """
    Create a corresponding user in Supabase Auth using the Admin API.

    Returns True when created or already exists, False when mirroring is skipped/failed.
    """
    if not _is_enabled():
        return False

    if not _is_configured():
        logger.warning(
            "Supabase auth mirror enabled but SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY are missing."
        )
        return False

    return upsert_supabase_auth_user(
        email=email,
        password=password,
        username=username,
        user_metadata={"username": username} if username else {},
    )
