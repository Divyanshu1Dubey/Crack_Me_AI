"""DRF authentication backend for Supabase Auth access tokens."""

from __future__ import annotations

import json
import os
from urllib import error, request

from django.contrib.auth import get_user_model
from rest_framework import authentication

from .models import TokenBalance


class SupabaseJWTAuthentication(authentication.BaseAuthentication):
    """
    Authenticate API requests using Supabase Auth access tokens.

    Flow:
    1) Read Authorization: Bearer <supabase_access_token>
    2) Validate token by calling Supabase `/auth/v1/user`
    3) Upsert local Django user by email and return it as request.user
    """

    def authenticate(self, request_obj):
        auth_header = authentication.get_authorization_header(request_obj).split()
        if not auth_header or auth_header[0].lower() != b"bearer":
            return None
        if len(auth_header) != 2:
            return None

        token = auth_header[1].decode("utf-8", errors="ignore").strip()
        if not token:
            return None

        supabase_user = self._fetch_supabase_user(token)
        if not supabase_user:
            return None

        user = self._upsert_local_user(supabase_user)
        return (user, None)

    def _fetch_supabase_user(self, token: str):
        supabase_url = (
            os.getenv("SUPABASE_URL", "").strip()
            or os.getenv("NEXT_PUBLIC_SUPABASE_URL", "").strip()
            or ""
        ).rstrip("/")
        verify_key = (
            os.getenv("SUPABASE_AUTH_VERIFY_KEY", "").strip()
            or os.getenv("SUPABASE_ANON_KEY", "").strip()
            or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "").strip()
            or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        )

        if not supabase_url or not verify_key:
            return None

        req = request.Request(
            url=f"{supabase_url}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {token}",
                "apikey": verify_key,
            },
            method="GET",
        )

        try:
            with request.urlopen(req, timeout=8) as resp:
                if int(getattr(resp, "status", 0) or 0) != 200:
                    return None
                payload = resp.read().decode("utf-8", errors="ignore")
                return json.loads(payload)
        except (error.HTTPError, error.URLError, TimeoutError, json.JSONDecodeError):
            return None

    def _upsert_local_user(self, supabase_user: dict):
        User = get_user_model()

        email = (supabase_user.get("email") or "").strip().lower()
        metadata = supabase_user.get("user_metadata") or {}
        app_metadata = supabase_user.get("app_metadata") or {}
        username = (metadata.get("username") or "").strip()

        if not username:
            username = (email.split("@")[0] if "@" in email else "supabase_user").strip() or "supabase_user"

        # Ensure unique username for local user table.
        base_username = username[:140]
        username_candidate = base_username
        suffix = 1
        while User.objects.filter(username=username_candidate).exclude(email=email).exists():
            suffix += 1
            username_candidate = f"{base_username[:130]}_{suffix}"

        def _is_true(value):
            return str(value).strip().lower() == "true"

        def _is_admin_from_metadata(payload: dict) -> bool:
            if not isinstance(payload, dict):
                return False
            return _is_true(payload.get("is_admin", "")) or str(payload.get("role") or "").strip().lower() == "admin"

        def _admin_email_allowlist() -> set[str]:
            raw = os.getenv("CONTROL_TOWER_ADMIN_EMAILS", "")
            configured = {
                item.strip().lower()
                for item in raw.split(",")
                if item and item.strip()
            }
            bootstrap_email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
            if bootstrap_email:
                configured.add(bootstrap_email)
            return configured

        # Privileges come from Supabase metadata. Accept both app_metadata and
        # user_metadata because some admin promotion flows store role flags in
        # user_metadata. Also support an explicit environment allowlist for
        # deterministic bootstrap behavior.
        is_admin_user = (
            _is_admin_from_metadata(app_metadata)
            or _is_admin_from_metadata(metadata)
            or email in _admin_email_allowlist()
        )

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "username": username_candidate,
                "first_name": str(metadata.get("first_name") or ""),
                "last_name": str(metadata.get("last_name") or ""),
                "target_exam": str(metadata.get("target_exam") or "UPSC CMS"),
                "is_active": True,
                "role": "admin" if is_admin_user else "student",
                "is_superuser": is_admin_user,
                "is_staff": is_admin_user,
            },
        )

        if created:
            user.set_unusable_password()
            user.save(update_fields=["password"])
        else:
            existing_admin = bool(getattr(user, "is_admin", False) or user.is_superuser or user.role == "admin")
            if existing_admin:
                is_admin_user = True

            updates = []
            desired_role = "admin" if is_admin_user else "student"
            if user.role != desired_role:
                user.role = desired_role
                updates.append("role")
            if user.is_superuser != is_admin_user:
                user.is_superuser = is_admin_user
                updates.append("is_superuser")
            if user.is_staff != is_admin_user:
                user.is_staff = is_admin_user
                updates.append("is_staff")
            if user.first_name != str(metadata.get("first_name") or ""):
                user.first_name = str(metadata.get("first_name") or "")
                updates.append("first_name")
            if user.last_name != str(metadata.get("last_name") or ""):
                user.last_name = str(metadata.get("last_name") or "")
                updates.append("last_name")
            target_exam = str(metadata.get("target_exam") or "UPSC CMS")
            if user.target_exam != target_exam:
                user.target_exam = target_exam
                updates.append("target_exam")
            avatar_url = str(metadata.get("avatar_url") or "")
            if hasattr(user, "avatar_url") and user.avatar_url != avatar_url:
                user.avatar_url = avatar_url
                updates.append("avatar_url")

            if updates:
                if "is_staff" not in updates and "is_superuser" not in updates and "role" in updates:
                    updates.extend([field for field in ["is_superuser", "is_staff"] if field not in updates])
                user.role = "admin" if is_admin_user else "student"
                user.is_superuser = is_admin_user
                user.is_staff = is_admin_user
                user.save(update_fields=sorted(set(updates)))

        TokenBalance.objects.get_or_create(user=user)
        return user
