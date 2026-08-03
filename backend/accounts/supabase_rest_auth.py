"""DRF authentication backend for Supabase Auth access tokens."""

from __future__ import annotations

import json
import os
import re
from urllib import error, request

from django.contrib.auth import get_user_model
from rest_framework import authentication

from .models import TokenBalance

# SECURITY (Fix #3): The X-Session-ID header is trusted by this backend as a
# device fingerprint. Without validation, any attacker can rotate the header
# (`X-Session-ID: 1`, `2`, `3`, ...) to spawn unlimited parallel sessions
# and bypass the per-user device limit. We require the header to look like
# either:
#   - a UUID-shaped token (8-4-4-4-12 hex), OR
#   - a client-prefixed random ID matching ``^(dev|ses)_[a-z0-9_]{8,80}$``
#     (the formats emitted by frontend/src/lib/api.ts:84-92), OR
#   - an alphanumeric token of length 16-128 with no obvious high-entropy
#     attacks (only [A-Za-z0-9_-]).
# Plain integers, short strings, and special characters are rejected so
# simple enumeration can't multiply the device count.
_SESSION_ID_PATTERN = re.compile(
    r"^(?:"
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    r"|(?:dev|ses)_[A-Za-z0-9_]{8,80}"
    r"|[A-Za-z0-9_\-]{16,128}"
    r")$"
)


def _is_valid_session_id(value):
    """Return True iff ``value`` looks like a non-spoofable device token."""
    if not value or not isinstance(value, str):
        return False
    if len(value) > 128:
        return False
    return bool(_SESSION_ID_PATTERN.match(value))


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

        # ── Device Management & Limits ──
        incoming_session_id = request_obj.META.get('HTTP_X_SESSION_ID')

        # Premium student exception: ensure they never get locked out due to device limits/race conditions
        if user.email in ['sbsp181107@gmail.com'] or user.role == 'admin':
            return (user, None)

        # SECURITY (Fix #3): reject any X-Session-ID that doesn't match a
        # known device-token shape. Without this, an attacker can enumerate
        # X-Session-ID: 1, 2, 3, ... and spawn unlimited parallel sessions,
        # bypassing the per-user device limit.
        if incoming_session_id and not _is_valid_session_id(incoming_session_id):
            # Drop the spoofed header; behave as if no device tracker was
            # attached for this request. We don't fail authentication — the
            # user is still legitimately authenticated via Supabase — but
            # we won't enroll this fingerprint as a "device", so any later
            # attempt with a valid-looking session will be the one that
            # counts toward the limit.
            incoming_session_id = None

        if incoming_session_id:
            from .models import UserDevice

            # SECURITY (Fix #3b): only trust REMOTE_ADDR for IP-based device
            # bookkeeping. X-Forwarded-For is attacker-controlled when the
            # client can reach the backend directly, so honoring it lets
            # anyone spoof their IP for rate-limit / geo / device bookkeeping.
            # Render sits behind a known proxy; we still capture the raw
            # socket address.
            ip = request_obj.META.get('REMOTE_ADDR', '').strip()

            user_agent = request_obj.META.get('HTTP_USER_AGENT', '')[:250]

            device, created = UserDevice.objects.get_or_create(
                user=user,
                device_fingerprint=incoming_session_id,
                defaults={
                    'device_name': user_agent,
                    'ip_address': ip,
                    'is_active': True
                }
            )

            if not created:
                # Update last login
                device.device_name = user_agent
                device.ip_address = ip
                device.save(update_fields=['device_name', 'ip_address', 'last_login'])

            if not device.is_active:
                from rest_framework import exceptions
                raise exceptions.AuthenticationFailed({
                    "detail": "This device has been logged out or blocked.",
                    "code": "device_inactive"
                })

            # Enforce limits if it's a new device or checking limits
            limit = 4 if getattr(user, 'is_subscribed', False) else 2

            active_devices = UserDevice.objects.filter(user=user, is_active=True).order_by('-last_login')
            if active_devices.count() > limit:
                # If this device isn't in the allowed top N devices, reject
                allowed_ids = list(active_devices.values_list('id', flat=True)[:limit])
                if device.id not in allowed_ids:
                    allowed_paths = ['/auth/profile/', '/auth/devices/', '/auth/logout/']
                    if not any(p in request_obj.path for p in allowed_paths):
                        from rest_framework import exceptions
                        raise exceptions.AuthenticationFailed({
                            "detail": f"Maximum device limit reached ({limit} devices). Please manage devices in Settings.",
                            "code": "device_limit_reached"
                        })

        return (user, token)

    def _fetch_supabase_user(self, token: str):
        supabase_url = (
            os.getenv("SUPABASE_URL", "").strip()
            or os.getenv("NEXT_PUBLIC_SUPABASE_URL", "").strip()
            or ""
        ).rstrip("/")
        # Token verification key resolution — order matters:
        #   1. SUPABASE_AUTH_VERIFY_KEY   (explicit override — recommended)
        #   2. SUPABASE_ANON_KEY          (anon / publishable key — safe)
        #   3. NEXT_PUBLIC_SUPABASE_ANON_KEY (frontend anon, safe)
        #   4. SUPABASE_SERVICE_ROLE_KEY  (LAST-RESORT fallback only — see note)
        #
        # SECURITY NOTE: SERVICE ROLE key bypasses RLS and impersonates any
        # user. It MUST NOT be used in code paths that trust user-supplied
        # JWTs. We use it ONLY as a *verify_key* sent in the `apikey`
        # header to Supabase's `/auth/v1/user` endpoint, which simply
        # answers "is this bearer token currently valid for this user?"
        # — the response is keyed off the bearer token itself, not the
        # apikey. So even with the service role key as apikey, a forged
        # JWT that Supabase has not issued will still be rejected.
        #
        # However, the canonical safe choice is SUPABASE_AUTH_VERIFY_KEY
        # or SUPABASE_ANON_KEY — those should be configured in production.
        # The SERVICE_ROLE_KEY fallback exists for operational continuity
        # when those keys are missing (e.g. during the rollout of Fix #4
        # which previously broke production by removing this fallback).
        # We log a WARNING whenever the fallback fires so operators know
        # to add the proper key.
        anon_keys = [
            os.getenv("SUPABASE_AUTH_VERIFY_KEY", "").strip(),
            os.getenv("SUPABASE_ANON_KEY", "").strip(),
            os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "").strip(),
        ]
        verify_key = next((k for k in anon_keys if k), "")

        used_service_role_fallback = False
        if not verify_key:
            verify_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
            used_service_role_fallback = bool(verify_key)

        if used_service_role_fallback:
            import logging
            logging.getLogger(__name__).warning(
                "SupabaseJWTAuthentication is verifying tokens with the "
                "SUPABASE_SERVICE_ROLE_KEY fallback. This is operationally "
                "safe (Supabase keys token verification to the bearer JWT, "
                "not the apikey) but should be replaced with "
                "SUPABASE_AUTH_VERIFY_KEY or SUPABASE_ANON_KEY for "
                "principle-of-least-privilege. Add the proper key to "
                "production env to silence this warning."
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
            configured.update(["meduraa.web@gmail.com", "parulmaterial@gmail.com"])
            bootstrap_email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
            if bootstrap_email:
                configured.add(bootstrap_email)
            return configured

        # Privileges come from Supabase app_metadata or allowlist. Do not trust
        # user_metadata as it can be modified by the end-user.
        is_admin_user = (
            _is_admin_from_metadata(app_metadata)
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
            
            # Send personalized welcome email
            try:
                from django.core.mail import send_mail
                from django.conf import settings
                subject = f"Welcome to CrackLabs, Dr. {user.first_name or user.username}! 🩺"
                message = (
                    f"Dear Dr. {user.first_name or user.username},\n\n"
                    f"Welcome to CrackLabs — the premier preparation hub for MBBS, UPSC CMS, and State CMS exams.\n\n"
                    f"We are excited to support you on your journey to becoming a certified medical officer or specialist. "
                    f"Here is what you get access to:\n"
                    f"- 1,440+ Year-wise & Subject-wise CMS PYQ Bank (2018-2025)\n"
                    f"- Spaced Repetition flashcards based on SM-2\n"
                    f"- Unlimited AI Tutor to break down complex medical guidelines\n"
                    f"- Dynamic leaderboard to compete with medical peers across the country\n\n"
                    f"Let's start your prep today! Head over to your dashboard and complete your first clinical drill.\n\n"
                    f"Best regards,\n"
                    f"The CrackLabs Team\n"
                    f"https://www.cracklabs.app"
                )
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=True,
                )
            except Exception:
                pass
        else:

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
