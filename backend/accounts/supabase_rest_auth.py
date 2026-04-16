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
        supabase_url = (os.getenv("SUPABASE_URL", "").strip() or "").rstrip("/")
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

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "username": username_candidate,
                "first_name": str(metadata.get("first_name") or ""),
                "last_name": str(metadata.get("last_name") or ""),
                "target_exam": str(metadata.get("target_exam") or "UPSC CMS"),
                "is_active": True,
            },
        )

        if created:
            user.set_unusable_password()
            user.save(update_fields=["password"])

        TokenBalance.objects.get_or_create(user=user)
        return user
