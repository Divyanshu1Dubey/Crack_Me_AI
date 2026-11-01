"""DRF authentication backend for Supabase Auth access tokens."""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import timedelta, timezone as dt_timezone
from urllib import error, request

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import authentication, exceptions

from .models import TokenBalance

logger = logging.getLogger(__name__)

# Requests an over-the-limit device may still make, so the user can open
# Settings and free a slot (list / log out devices, load the profile) or buy
# the 4-device plan from this device (/auth/subscribe/...).
_DEVICE_MANAGEMENT_PATHS = ('/auth/profile/', '/auth/devices/', '/auth/logout/', '/auth/subscribe/')
# Read-only requests every signed-in page makes in the background (Header
# token pill, announcements). Without them the over-limit device could not
# stay on /subscription long enough to buy the 4-device plan. Exact paths
# (any /api prefix allowed), safe methods only; they never enrol the device.
_DEVICE_LIMIT_EXEMPT_READS = ('/auth/tokens/', '/analytics/announcements/')
_SAFE_METHODS = frozenset({'GET', 'HEAD', 'OPTIONS'})
# A device's last_login is refreshed at most this often (one write per
# request per user was the old behaviour).
_DEVICE_TOUCH_INTERVAL = timedelta(seconds=60)
# Devices unseen for this long no longer hold a slot for a NEW device (the
# cap was never enforced before, so many accounts carry long-dead rows, e.g.
# one per old incognito session). They stay listed in Settings.
_DEVICE_STALE_AFTER = timedelta(days=30)
# Clock skew allowed between Supabase's user ``created_at`` and our
# ``date_joined`` when deciding that a row was created from an identity.
ORIGINAL_IDENTITY_CLOCK_TOLERANCE = timedelta(minutes=5)

# Keys that may be sent as ``apikey`` when verifying an access token, in
# order. All are public (anon / publishable) keys or an explicit override.
_PUBLIC_VERIFY_KEY_ENV_VARS = (
    "SUPABASE_AUTH_VERIFY_KEY",
    "SUPABASE_ANON_KEY",
    "NEXT_PUBLIC_SUPABASE_ANON_KEY",
    "SUPABASE_PUBLISHABLE_KEY",
    "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY",
)
_service_role_fallback_logged = False


def _auth_failed(code: str, detail: str) -> exceptions.AuthenticationFailed:
    """AuthenticationFailed with a machine-readable ``code`` the frontend acts on."""
    return exceptions.AuthenticationFailed({"detail": detail, "code": code})


def public_verify_key() -> str:
    """The first configured public key for token verification ('' if none)."""
    return next((v for v in (os.getenv(n, "").strip() for n in _PUBLIC_VERIFY_KEY_ENV_VARS) if v), "")


def _is_device_management_request(request_obj) -> bool:
    """Requests an over-the-limit device may make without taking a slot."""
    path = request_obj.path
    if any(p in path for p in _DEVICE_MANAGEMENT_PATHS):
        return True
    return request_obj.method in _SAFE_METHODS and any(path.endswith(p) for p in _DEVICE_LIMIT_EXEMPT_READS)


def _supabase_email_confirmed(supabase_user: dict) -> bool:
    """True when Supabase has verified that this identity owns its email.

    ``email_confirmed_at`` is the field current GoTrue builds return. Older
    builds only expose ``confirmed_at``, which can also be set by a *phone*
    confirmation, so it only counts when no phone was confirmed.
    """
    if supabase_user.get("email_confirmed_at"):
        return True
    return bool(supabase_user.get("confirmed_at")) and not supabase_user.get("phone_confirmed_at")


def supabase_created_at(supabase_user: dict):
    """GoTrue's ``created_at`` for this identity as an aware datetime, or None."""
    raw = supabase_user.get("created_at")
    if not raw:
        return None
    try:
        value = parse_datetime(str(raw).strip())
    except (TypeError, ValueError):
        return None
    if value is not None and timezone.is_naive(value):
        value = timezone.make_aware(value, dt_timezone.utc)
    return value


def is_original_identity(supabase_user: dict, row) -> bool:
    """True when ``row`` was created from this Supabase identity.

    A row created on an identity's first sign-in is younger than the
    identity: GoTrue's ``created_at`` is not later than ``row.date_joined``
    (give or take ORIGINAL_IDENTITY_CLOCK_TOLERANCE). A sign-up made after the
    row existed -- a takeover attempt while "Confirm email" is off, or a
    deleted and re-created identity -- cannot satisfy this. The email must be
    confirmed too. Missing or unparseable dates never count.
    """
    if not _supabase_email_confirmed(supabase_user):
        return False
    created = supabase_created_at(supabase_user)
    joined = getattr(row, "date_joined", None)
    if created is None or joined is None:
        return False
    return created <= joined + ORIGINAL_IDENTITY_CLOCK_TOLERANCE


def _name_parts_from_metadata(metadata: dict) -> tuple[str, str]:
    """first/last name from Supabase user_metadata (OAuth providers only send full_name/name)."""
    first = str(metadata.get("first_name") or "").strip()
    last = str(metadata.get("last_name") or "").strip()
    if not first and not last:
        full = str(metadata.get("full_name") or metadata.get("name") or "").strip()
        if full:
            first, _, last = full.partition(" ")
    return first[:150], last.strip()[:150]


def _avatar_from_metadata(metadata: dict) -> str:
    url = str(metadata.get("avatar_url") or metadata.get("picture") or "").strip()
    # CustomUser.avatar_url is a URLField(max_length=200).
    if url.startswith(("https://", "http://")) and len(url) <= 200:
        return url
    return ""

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
    3) Find the local Django user by the Supabase user id (CustomUser.supabase_uid;
       the first sign-in links a row by its confirmed email, see
       _link_existing_row_by_email) or create one, and return it as request.user
    4) Reject blocked accounts (``is_active=False``) and enforce the device cap

    Failures that the frontend must act on raise AuthenticationFailed with a
    ``code``: ``account_blocked``, ``email_not_confirmed``, ``email_required``,
    ``account_link_required``, ``device_inactive`` and ``device_limit_reached``.

    The Supabase project must have "Confirm email" and "Secure email change"
    enabled: a confirmed email is what links a row on first sign-in and what
    the admin email allowlist trusts (system check accounts.W001).
    """

    def authenticate_header(self, request_obj):
        # DRF only answers 401 (instead of 403) for NotAuthenticated /
        # AuthenticationFailed when the FIRST authenticator returns a
        # WWW-Authenticate value. Without it, expired or unverifiable tokens
        # came back as 403 and the frontend's refresh-on-401 never ran.
        return 'Bearer realm="api"'

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

        # Admin "Block user" sets is_active=False. DRF's IsAuthenticated only
        # looks at is_authenticated (True for inactive users), so without this
        # check a blocked user kept full API access.
        if not user.is_active:
            raise _auth_failed(
                "account_blocked",
                "This account has been blocked. Contact support if you think this is a mistake.",
            )

        # Admins are exempt from device tracking and limits.
        if user.role == 'admin':
            return (user, None)

        self._enforce_device_limits(request_obj, user)
        return (user, token)

    def _enforce_device_limits(self, request_obj, user):
        """Track the X-Session-ID device and enforce the 2 (free) / 4 (subscribed) cap.

        * A device the user (or an admin) logged out raises ``device_inactive``;
          the frontend then drops its device id and signs out, so the next
          sign-in enrols a fresh device.
        * A NEW device is enrolled only while the user has fewer active devices
          (seen in the last 30 days) than the cap; otherwise
          ``device_limit_reached`` (except on the device-management paths, so
          Settings can free a slot).
        * Existing devices beyond the cap (e.g. after a 4 -> 2 downgrade): the
          ones used most recently win, judged on last_login values from BEFORE
          this request. (The old code refreshed last_login first, so the
          current device always ranked newest and the cap never triggered.)
        """
        incoming_session_id = request_obj.META.get('HTTP_X_SESSION_ID')

        # SECURITY (Fix #3): reject any X-Session-ID that doesn't match a
        # known device-token shape. Without this, an attacker can enumerate
        # X-Session-ID: 1, 2, 3, ... and spawn unlimited parallel sessions,
        # bypassing the per-user device limit. The request stays
        # authenticated; the spoofed fingerprint is simply not enrolled.
        if incoming_session_id and not _is_valid_session_id(incoming_session_id):
            incoming_session_id = None
        if not incoming_session_id:
            return

        from .models import UserDevice

        # SECURITY (Fix #3b): only trust REMOTE_ADDR for IP-based device
        # bookkeeping. X-Forwarded-For is attacker-controlled when the
        # client can reach the backend directly.
        ip = request_obj.META.get('REMOTE_ADDR', '').strip() or None
        user_agent = request_obj.META.get('HTTP_USER_AGENT', '')[:250]
        limit = 4 if getattr(user, 'is_subscribed', False) else 2
        management_request = _is_device_management_request(request_obj)

        def _limit_reached():
            return _auth_failed(
                "device_limit_reached",
                f"Maximum device limit reached ({limit} devices). Please manage devices in Settings.",
            )

        now = timezone.now()
        device = UserDevice.objects.filter(user=user, device_fingerprint=incoming_session_id).first()
        if device is None:
            slots_taken = UserDevice.objects.filter(
                user=user, is_active=True, last_login__gte=now - _DEVICE_STALE_AFTER,
            ).count()
            if slots_taken >= limit:
                if management_request:
                    return  # let it reach Settings without taking a slot
                raise _limit_reached()
            UserDevice.objects.get_or_create(
                user=user,
                device_fingerprint=incoming_session_id,
                defaults={'device_name': user_agent, 'ip_address': ip, 'is_active': True},
            )
            return

        if not device.is_active:
            raise _auth_failed("device_inactive", "This device has been logged out or blocked.")

        more_recent = (
            UserDevice.objects
            .filter(user=user, is_active=True, last_login__gt=device.last_login)
            .exclude(pk=device.pk)
            .count()
        )
        if more_recent >= limit:
            if management_request:
                return  # do not refresh last_login, or it would win its slot back
            raise _limit_reached()

        if (
            device.last_login is None
            or now - device.last_login >= _DEVICE_TOUCH_INTERVAL
            or device.device_name != user_agent
            or (device.ip_address or None) != ip
        ):
            UserDevice.objects.filter(pk=device.pk).update(
                device_name=user_agent, ip_address=ip, last_login=now,
            )

    def _fetch_supabase_user(self, token: str):
        # Cache Supabase JWT validation for the token's remaining lifetime
        # (Supabase access tokens last ~1h). Avoids a 100–300 ms outbound
        # HTTP call on every authenticated request.
        from django.core.cache import cache
        import hashlib
        # SECURITY: key on a digest of the WHOLE token. The previous key used
        # token[:64], which for Supabase JWTs is just the (shared) header --
        # every user's token mapped to the same cache entry, so a request
        # within 5 minutes of another user's was authenticated as that user.
        cache_key = "supabase_jwt:" + hashlib.sha256(token.encode("utf-8")).hexdigest()
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

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
        # It is reported by `manage.py check --deploy` (accounts.W002) and
        # logged once per process; remove it once every deployment sets
        # a public key (new-style publishable keys are as safe as anon).
        global _service_role_fallback_logged
        verify_key = public_verify_key()
        if not verify_key:
            verify_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
            if verify_key and not _service_role_fallback_logged:
                _service_role_fallback_logged = True
                logger.warning(
                    "SupabaseJWTAuthentication is verifying tokens with the "
                    "SUPABASE_SERVICE_ROLE_KEY fallback. Set SUPABASE_ANON_KEY "
                    "(or SUPABASE_PUBLISHABLE_KEY / SUPABASE_AUTH_VERIFY_KEY) in "
                    "the backend environment (principle of least privilege)."
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
                result = json.loads(payload)
                # Cache valid token for 5 minutes (well within the 1h JWT lifetime)
                try:
                    cache.set(cache_key, result, 300)
                except Exception:
                    pass
                return result
        except (error.HTTPError, error.URLError, TimeoutError, json.JSONDecodeError):
            return None

    def _upsert_local_user(self, supabase_user: dict):
        User = get_user_model()

        email = (supabase_user.get("email") or "").strip().lower()
        if not email or "@" not in email:
            # Phone-only / anonymous Supabase identities have no email. Linking
            # them "by email" would map all of them onto one local row (the
            # one with email='', e.g. a createsuperuser account).
            raise _auth_failed("email_required", "Sign in with an email address to use CrackLabs.")
        if not _supabase_email_confirmed(supabase_user):
            # SECURITY: a row is linked by email the first time. Without a
            # verified email anyone could sign up in Supabase with an address
            # that only exists locally (bootstrap admin, legacy users, an
            # allowlisted admin email) and be signed in as that account.
            raise _auth_failed("email_not_confirmed", "Please confirm your email address, then sign in again.")

        # The Supabase user id. GoTrue always returns it; once stored on a row
        # (CustomUser.supabase_uid) sign-ins are matched by it, not by email.
        supabase_uid = str(supabase_user.get("id") or "").strip()[:64] or None

        metadata = supabase_user.get("user_metadata") or {}
        app_metadata = supabase_user.get("app_metadata") or {}

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

        # ── Fix P1 (2026-09-23): admin-role loss bug ─────────────────────
        # `trusted_admin` is the privilege level for THIS login from trusted
        # sources: Supabase app_metadata (only settable with the service-role
        # key) or the env allowlist. The email is confirmed at this point
        # (checked above), so an allowlisted address can't be claimed by an
        # unverified sign-up -- provided the Supabase project has "Confirm
        # email" on (accounts.W001). user_metadata is user-editable and never
        # counts.
        admin_allowlist = _admin_email_allowlist()
        is_admin_from_metadata = _is_admin_from_metadata(app_metadata)
        is_admin_from_allowlist = email in admin_allowlist
        trusted_admin = is_admin_from_metadata or is_admin_from_allowlist

        first_name, last_name = _name_parts_from_metadata(metadata)
        avatar_url = _avatar_from_metadata(metadata)

        user = User.objects.filter(supabase_uid=supabase_uid).first() if supabase_uid else None
        linked_by_uid = user is not None
        # SECURITY (ACC-05): a linked identity whose email just changed to an
        # allowlisted admin address is not promoted, and its local email does
        # not follow. With "Confirm email" / "Secure email change" off, GoTrue
        # applies updateUser({email}) without any confirmation, so the new
        # address proves nothing. Grant admin in the admin panel (or with
        # Supabase app_metadata) instead.
        allowlist_email_change = bool(
            linked_by_uid
            and is_admin_from_allowlist
            and not is_admin_from_metadata
            and (user.email or "").strip().lower() != email
            and not (user.role == "admin" or user.is_superuser)
        )
        if allowlist_email_change:
            logger.warning(
                "Supabase identity %s changed its email to an admin-allowlisted address; "
                "account id=%s is not promoted and keeps its email.",
                supabase_uid, user.pk,
            )
            trusted_admin = False
        if user is None:
            user = self._link_existing_row_by_email(User, email, supabase_uid, trusted_admin, supabase_user)
        created = False
        if user is None:
            user, created = self._create_local_user(
                User,
                email=email,
                supabase_uid=supabase_uid,
                metadata=metadata,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "target_exam": str(metadata.get("target_exam") or "UPSC CMS")[:50],
                    "avatar_url": avatar_url,
                    "is_active": True,
                    "role": "admin" if trusted_admin else "student",
                    "is_superuser": trusted_admin,
                    "is_staff": trusted_admin,
                },
            )

        if created:
            self._send_welcome_email(user)
        else:
            if trusted_admin:
                desired = {"role": "admin", "is_superuser": True, "is_staff": True}
            elif user.role == "admin" or user.is_superuser:
                # Never demote an existing admin here (revocation is done in
                # the admin panel), but don't mint a superuser either: an admin
                # granted in the DB (in-app role toggle) keeps API admin rights
                # and is_staff, and only trusted sources grant is_superuser.
                desired = {"role": "admin", "is_staff": True}
            else:
                desired = {"role": "student", "is_superuser": False, "is_staff": False}

            # Profile fields are filled from Supabase metadata only when the
            # local value is empty. They used to be overwritten on EVERY
            # request, which reverted name / avatar edits made in Settings and
            # forced every target_exam back to "UPSC CMS" (target_exam is now
            # only set when the account is created).
            if first_name and not user.first_name:
                desired["first_name"] = first_name
            if last_name and not user.last_name:
                desired["last_name"] = last_name
            if avatar_url and not user.avatar_url:
                desired["avatar_url"] = avatar_url
            # The linked identity changed its (confirmed) email in Supabase:
            # follow it, unless another account already uses that address
            # (or it is an admin-allowlisted address, see above).
            if (
                linked_by_uid
                and not allowlist_email_change
                and (user.email or "").lower() != email
                and not User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists()
            ):
                desired["email"] = email

            updates = [field for field, value in desired.items() if getattr(user, field) != value]
            for field in updates:
                setattr(user, field, desired[field])
            if updates:
                user.save(update_fields=updates)

        TokenBalance.objects.get_or_create(user=user)
        return user

    @staticmethod
    def _is_privileged(user) -> bool:
        return user.role == "admin" or user.is_superuser or user.is_staff

    def _link_existing_row_by_email(self, User, email, supabase_uid, trusted_admin, supabase_user=None):
        """First sign-in of a Supabase identity: link the local row with its email.

        Returns the linked row, or None when no row has this email (the caller
        creates one). The email is confirmed by Supabase at this point.

        SECURITY (ACC-05): with "Confirm email" off, GoTrue marks every new
        sign-up as confirmed, so a confirmed email alone does not prove the
        person owns the local account. An admin / staff / superuser row is
        therefore linked automatically only when
          * the identity is a trusted admin (Supabase app_metadata, which needs
            the service-role key, or the env admin allowlist -- both would
            grant admin anyway), or
          * the row was created from this identity (is_original_identity: the
            identity's created_at is not later than the row's date_joined).
            That is every admin promoted in the app after signing up, whose
            row migration 0023 left without a supabase_uid.
        Any other identity is refused (code ``account_link_required``) until
        an operator links it with ``manage.py link_supabase_identity`` (or
        sets supabase_uid in Django admin). Once linked, the row is only ever
        matched by supabase_uid, so a row already linked to another identity
        is never re-linked by email.
        """
        row = User.objects.filter(email=email).order_by("id").first()
        if row is None:
            return None
        if not row.is_active:
            # Never link a blocked account.
            raise _auth_failed(
                "account_blocked",
                "This account has been blocked. Contact support if you think this is a mistake.",
            )
        privileged = self._is_privileged(row)
        original_identity = bool(privileged and supabase_user and is_original_identity(supabase_user, row))
        if row.supabase_uid and row.supabase_uid != supabase_uid:
            # Linked to another Supabase identity, which has since lost this
            # email (deleted and re-created account, email change, project
            # migration). Re-linking by email would reopen the takeover.
            reason = "linked to another Supabase identity"
        elif privileged and not trusted_admin and not original_identity:
            reason = "an admin/staff account that was not created from this Supabase identity"
        else:
            reason = ""
        if reason:
            logger.warning(
                "Refusing to link Supabase identity %s to account id=%s (%s); link it explicitly "
                "with `manage.py link_supabase_identity --email <email> --apply`.",
                supabase_uid or "<no id>", row.pk, reason,
            )
            raise _auth_failed(
                "account_link_required",
                "This account must be verified by an administrator before it can sign in. Please contact support.",
            )
        if not supabase_uid or row.supabase_uid == supabase_uid:
            return row
        try:
            with transaction.atomic():
                claimed = (
                    User.objects.filter(pk=row.pk, supabase_uid__isnull=True)
                    .update(supabase_uid=supabase_uid)
                )
        except IntegrityError:
            claimed = 0
        if claimed:
            row.supabase_uid = supabase_uid
            if privileged:
                self._log_privileged_link(row, supabase_uid, supabase_user or {}, trusted_admin)
            return row
        # A concurrent request for the same identity linked it first.
        winner = User.objects.filter(supabase_uid=supabase_uid).first()
        if winner is not None:
            return winner
        raise _auth_failed(
            "account_link_required",
            "This account must be verified by an administrator before it can sign in. Please contact support.",
        )

    @staticmethod
    def _log_privileged_link(row, supabase_uid, supabase_user, trusted_admin):
        """Log + audit-log the automatic link of an admin / staff row (best effort)."""
        basis = "trusted admin identity" if trusted_admin else "identity predates the account"
        created = supabase_created_at(supabase_user)
        logger.warning(
            "Linked Supabase identity %s to privileged account id=%s on first sign-in (%s; identity "
            "created %s, account joined %s).",
            supabase_uid, row.pk, basis, created.isoformat() if created else "unknown",
            row.date_joined.isoformat() if row.date_joined else "unknown",
        )
        from .views import create_admin_audit_log

        create_admin_audit_log(
            actor=None,
            action="user_role_update",
            resource_type="user",
            resource_id=row.pk,
            detail=f"Linked {row.username} to Supabase identity {supabase_uid} on first sign-in ({basis})",
            metadata={"supabase_uid": supabase_uid, "basis": basis, "source": "sign_in"},
        )

    @staticmethod
    def _create_local_user(User, *, email, supabase_uid, metadata, defaults):
        """Create the local row for a new Supabase identity. Returns (user, created)."""
        username = (metadata.get("username") or "").strip()
        if not username:
            username = (email.split("@")[0] if "@" in email else "supabase_user").strip() or "supabase_user"

        # Ensure unique username for local user table.
        base_username = username[:140]
        username_candidate = base_username
        suffix = 1
        while User.objects.filter(username=username_candidate).exists():
            suffix += 1
            username_candidate = f"{base_username[:130]}_{suffix}"

        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username_candidate,
                    email=email,
                    password=None,  # unusable: sign-in is Supabase only
                    supabase_uid=supabase_uid,
                    **defaults,
                )
            return user, True
        except IntegrityError:
            # A concurrent first request for the same identity created it.
            existing = User.objects.filter(supabase_uid=supabase_uid).first() if supabase_uid else None
            if existing is None:
                existing = User.objects.filter(email=email).order_by("id").first()
            if existing is None:
                raise
            return existing, False

    @staticmethod
    def _send_welcome_email(user):
        """Welcome mail for a first sign-in, sent off the request path."""
        from .emails import send_mail_in_background

        name = user.first_name or user.username
        send_mail_in_background(
            subject=f"Welcome to CrackLabs, Dr. {name}! 🩺",
            message=(
                f"Dear Dr. {name},\n\n"
                f"Welcome to CrackLabs — the premier preparation hub for MBBS, UPSC CMS, and State CMS exams.\n\n"
                f"We are excited to support you on your journey to becoming a certified medical officer or specialist. "
                f"Here is what you get access to:\n"
                f"- 1,440+ Year-wise & Subject-wise CMS PYQ Bank (2018-2025)\n"
                f"- Spaced Repetition flashcards based on SM-2\n"
                f"- An AI Tutor to break down complex medical guidelines\n"
                f"- Dynamic leaderboard to compete with medical peers across the country\n\n"
                f"Let's start your prep today! Head over to your dashboard and complete your first clinical drill.\n\n"
                f"Best regards,\n"
                f"The CrackLabs Team\n"
                f"https://www.cracklabs.app"
            ),
            recipient_list=[user.email],
        )
