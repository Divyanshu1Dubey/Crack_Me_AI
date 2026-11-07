"""DRF authentication backend for Supabase Auth access tokens."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import threading
import time
from datetime import timedelta, timezone as dt_timezone
from http.client import HTTPException
from urllib import error, request

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import authentication, exceptions

from .auth_mode import supabase_auth_enabled
# The device cap lives in accounts.device_limits (shared with the native
# authenticator); these names are re-exported for existing imports.
from .device_limits import (  # noqa: F401
    FREE_DEVICE_LIMIT,
    SUBSCRIBED_DEVICE_LIMIT,
    _DEVICE_LIMIT_EXEMPT_READS,
    _DEVICE_MANAGEMENT_PATHS,
    _DEVICE_STALE_AFTER,
    _DEVICE_TOUCH_INTERVAL,
    _NIL_UUID,
    _SAFE_METHODS,
    _SESSION_CLAIM_PATTERN,
    _SESSION_FINGERPRINT_PREFIX,
    _SESSION_ID_PATTERN,
    DeviceLimitMixin,
    _auth_failed,
    _device_limit_for,
    _is_device_management_request,
    _is_valid_session_id,
    session_id_from_claims,
)
from .models import TokenBalance

logger = logging.getLogger(__name__)

# ── Token verification limits ────────────────────────────────────────────
# DRF authenticates before its throttles run, so every bearer value reaches
# _fetch_supabase_user, whose GoTrue call (/auth/v1/user) blocks a worker
# thread. These keep a flood of made-up tokens from tying up the workers.
# Each value can be overridden by a Django setting or environment variable
# of the same name.
_MAX_TOKEN_LENGTH = 16384
# A token counts as expired locally only this long after its ``exp`` (clock
# skew): until then GoTrue decides.
_EXP_LEEWAY_SECONDS = 10
_DEFAULT_VERIFY_TIMEOUT_SECONDS = 3.0        # SUPABASE_AUTH_TIMEOUT_SECONDS (was 8 s)
_DEFAULT_TOKEN_CACHE_SECONDS = 300           # SUPABASE_TOKEN_CACHE_SECONDS, never beyond the token's exp
_REFUSED_TOKEN_CACHE_SECONDS = 60            # a token GoTrue refused is not re-checked for this long
_DEFAULT_MAX_CONCURRENT_VERIFICATIONS = 2    # SUPABASE_AUTH_MAX_CONCURRENT_VERIFICATIONS, per process; 0 = no cap
_DEFAULT_VERIFY_RATE_PER_IP = 240            # SUPABASE_AUTH_VERIFY_RATE_PER_IP, GoTrue calls per minute; 0 = off
_VERIFY_RATE_WINDOW_SECONDS = 60
_AUTH_CACHE_ALIAS = "rate_limit"             # large LocMem cap / Redis (settings.CACHES); else 'default'
_VERIFIED_PREFIX = "supabase_jwt:"
_REFUSED_PREFIX = "supabase_jwt_refused:"
_BUDGET_PREFIX = "supabase_verify_ip:"
_SESSION_REVOKED_PREFIX = "supabase_session_revoked:"

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


def _verification_busy() -> exceptions.Throttled:
    """429 for a request whose token cannot be checked right now (limits above)."""
    exc = exceptions.Throttled(detail={
        "detail": "Too many sign-in checks right now. Please retry in a moment.",
        "code": "auth_verification_busy",
    })
    exc.wait = 1  # Retry-After
    return exc


def public_verify_key() -> str:
    """The first configured public key for token verification ('' if none)."""
    return next((v for v in (os.getenv(n, "").strip() for n in _PUBLIC_VERIFY_KEY_ENV_VARS) if v), "")


def _supabase_url() -> str:
    return (
        os.getenv("SUPABASE_URL", "").strip()
        or os.getenv("NEXT_PUBLIC_SUPABASE_URL", "").strip()
        or ""
    ).rstrip("/")


def _config_value(name: str):
    """Django setting ``name`` if defined, else the environment variable (None if neither / blank)."""
    from django.conf import settings

    value = getattr(settings, name, None)
    if value is None:
        value = os.getenv(name)
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
    return value


def _config_number(name: str, default, *, minimum=0, maximum=None, cast=int):
    value = _config_value(name)
    if value is None:
        return default
    try:
        number = cast(value)
    except (TypeError, ValueError):
        return default
    number = max(minimum, number)
    return min(maximum, number) if maximum is not None else number


def _verify_timeout() -> float:
    return _config_number(
        "SUPABASE_AUTH_TIMEOUT_SECONDS", _DEFAULT_VERIFY_TIMEOUT_SECONDS, minimum=0.5, maximum=10.0, cast=float,
    )


def _token_cache_seconds() -> int:
    return _config_number("SUPABASE_TOKEN_CACHE_SECONDS", _DEFAULT_TOKEN_CACHE_SECONDS, minimum=0, maximum=3600)


def _auth_cache():
    """Cache for token checks and their counters ('rate_limit' alias, else 'default')."""
    from django.conf import settings
    from django.core.cache import caches

    alias = _AUTH_CACHE_ALIAS if _AUTH_CACHE_ALIAS in getattr(settings, "CACHES", {}) else "default"
    return caches[alias]


def _cache_get(store, key):
    try:
        return store.get(key)
    except Exception:  # noqa: BLE001 - a cache outage must not break sign-in
        return None


def _cache_set(store, key, value, timeout):
    try:
        store.set(key, value, timeout)
    except Exception:  # noqa: BLE001
        pass


def _b64url_json_object(segment: str):
    try:
        raw = base64.urlsafe_b64decode((segment + "=" * (-len(segment) % 4)).encode("ascii"))
        value = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError):  # binascii.Error and JSONDecodeError are ValueErrors
        return None
    return value if isinstance(value, dict) else None


def unverified_jwt_parts(token: str):
    """(header, payload) of a JWT-shaped ``token``, or None. NOT verified.

    Only for values GoTrue has accepted, or to refuse values that cannot be
    access tokens at all.
    """
    if not isinstance(token, str) or not token or len(token) > _MAX_TOKEN_LENGTH:
        return None
    parts = token.split(".")
    if len(parts) != 3 or not all(parts):
        return None
    header = _b64url_json_object(parts[0])
    payload = _b64url_json_object(parts[1])
    if header is None or payload is None:
        return None
    return header, payload


def plausible_access_token_claims(token: str, now: float | None = None):
    """The payload of ``token`` if it can be a live Supabase access token, else None.

    A local, network-free check (no signature check): a JWT with an ``alg``
    other than "none", a ``sub`` and an ``exp`` that has not passed (give or
    take _EXP_LEEWAY_SECONDS). Every access token GoTrue issues passes it;
    anything that fails it would be refused by GoTrue as well.
    """
    parts = unverified_jwt_parts(token)
    if parts is None:
        return None
    header, payload = parts
    alg = header.get("alg")
    if not isinstance(alg, str) or not alg.strip() or alg.strip().lower() == "none":
        return None
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub.strip():
        return None
    exp = payload.get("exp")
    if isinstance(exp, bool) or not isinstance(exp, (int, float)):
        return None
    if exp <= (time.time() if now is None else now) - _EXP_LEEWAY_SECONDS:
        return None
    return payload


def _verification_rate_per_ip() -> int:
    """GoTrue calls allowed per client IP per minute (0 = no limit).

    Off by default while the client address is unknown: without NUM_PROXIES
    or a TRUSTED_CLIENT_IP_HEADER that can be read (crack_cms.client_ip:
    a Cloudflare header needs NUM_PROXIES behind a platform proxy) every
    request carries the proxy's address, so the budget would be one bucket
    for the whole site.
    """
    configured = _config_value("SUPABASE_AUTH_VERIFY_RATE_PER_IP")
    if configured is not None:
        try:
            return max(0, int(configured))
        except (TypeError, ValueError):
            pass
    from crack_cms.client_ip import client_ip_known

    return _DEFAULT_VERIFY_RATE_PER_IP if client_ip_known() else 0


def _within_verification_budget(ip: str, store) -> bool:
    """Count one GoTrue call for ``ip``; False once the per-minute budget is spent."""
    limit = _verification_rate_per_ip()
    if limit <= 0 or not ip:
        return True
    window = _VERIFY_RATE_WINDOW_SECONDS
    key = f"{_BUDGET_PREFIX}{ip}:{int(time.time() // window)}"
    try:
        count = 1 if store.add(key, 1, timeout=window + 5) else store.incr(key)
    except ValueError:  # expired between add() and incr()
        _cache_set(store, key, 1, window + 5)
        count = 1
    except Exception:  # noqa: BLE001 - cache outage: fail open
        return True
    return count <= limit


_SLOTS_LOCK = threading.Lock()
_SLOTS: dict[int, threading.BoundedSemaphore] = {}


def _verification_slots():
    """Per-process cap on concurrent GoTrue calls (None = no cap)."""
    size = _config_number(
        "SUPABASE_AUTH_MAX_CONCURRENT_VERIFICATIONS", _DEFAULT_MAX_CONCURRENT_VERIFICATIONS, minimum=0, maximum=64,
    )
    if size <= 0:
        return None
    with _SLOTS_LOCK:
        slots = _SLOTS.get(size)
        if slots is None:
            slots = _SLOTS[size] = threading.BoundedSemaphore(size)
        return slots


class _PendingVerification:
    """One in-flight GoTrue call that concurrent requests with the same token share."""

    __slots__ = ("done", "result", "busy")

    def __init__(self):
        self.done = threading.Event()
        self.result = None
        self.busy = False


_INFLIGHT_LOCK = threading.Lock()
_INFLIGHT: dict[str, _PendingVerification] = {}


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


class SupabaseJWTAuthentication(DeviceLimitMixin, authentication.BaseAuthentication):
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
        # AUTH_PROVIDER=django: Django issues the tokens
        # (accounts.native_auth_authentication); never call GoTrue.
        if not supabase_auth_enabled():
            return None
        auth_header = authentication.get_authorization_header(request_obj).split()
        if not auth_header or auth_header[0].lower() != b"bearer":
            return None
        if len(auth_header) != 2:
            return None

        token = auth_header[1].decode("utf-8", errors="ignore").strip()
        if not token:
            return None

        # For the per-IP budget of _fetch_supabase_user (DRF creates one
        # authenticator per request).
        self._current_request = request_obj
        supabase_user = self._fetch_supabase_user(token)
        if not supabase_user:
            return None

        # GoTrue accepted this exact token, so its claims are genuine. The
        # session id keys the device (_enforce_device_limits). Tokens that are
        # not JWTs only occur with a patched verifier (tests).
        parts = unverified_jwt_parts(token)
        claims = parts[1] if parts else None
        if claims is not None:
            token_sub = str(claims.get("sub") or "")
            verified_id = str(supabase_user.get("id") or "")
            if token_sub and verified_id and token_sub != verified_id:
                logger.error("Supabase token subject does not match the verified user; refusing the request.")
                return None
        session_id = session_id_from_claims(claims)

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

        self._enforce_device_limits(request_obj, user, session_id=session_id, token=token)
        return (user, token)

    # Device cap: accounts.device_limits.DeviceLimitMixin. A logged-out
    # device's Supabase session is signed out upstream as well.
    def _end_session(self, token, session_id):
        self._end_supabase_session(token, session_id)

    def _end_supabase_session(self, token, session_id):
        """Best effort: sign the logged-out device's Supabase session out (GoTrue /logout).

        Our refusal already stops this session on every API call; ending it
        upstream also stops its refresh token. Once per session.
        """
        if not token or not session_id:
            return
        supabase_url, verify_key = _supabase_url(), self._verify_key()
        if not supabase_url or not verify_key:
            return
        store = _auth_cache()
        try:
            if not store.add(_SESSION_REVOKED_PREFIX + session_id, 1, timeout=86400):
                return  # done already
        except Exception:  # noqa: BLE001
            return
        try:
            store.delete(_VERIFIED_PREFIX + hashlib.sha256(token.encode("utf-8")).hexdigest())
        except Exception:  # noqa: BLE001
            pass
        req = request.Request(
            url=f"{supabase_url}/auth/v1/logout?scope=local",
            data=b"",
            headers={"Authorization": f"Bearer {token}", "apikey": verify_key},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=_verify_timeout()):
                pass
        except (OSError, HTTPException, ValueError) as exc:
            logger.info("Could not end Supabase session %s upstream: %s", session_id, exc.__class__.__name__)

    @staticmethod
    def _verify_key() -> str:
        """The key sent as ``apikey`` to GoTrue ('' if none; see _fetch_supabase_user)."""
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
        return verify_key

    def _fetch_supabase_user(self, token: str):
        """GoTrue's user for ``token`` (GET /auth/v1/user, cached), or None.

        DRF runs authentication BEFORE its throttles, so every bearer value of
        every request reaches this method; it used to call Supabase (8 s
        timeout, failures never remembered) for any string at all. Now:

        * a value that cannot be a live access token (not a JWT, alg "none",
          no ``sub``, ``exp`` passed) is refused locally, without a call;
        * a token GoTrue refused (4xx) is not checked again for 60 s;
        * a valid answer is cached per SHA-256 digest of the whole token for
          SUPABASE_TOKEN_CACHE_SECONDS (300) and never beyond its ``exp``;
        * requests carrying the same token share one call (a page fires
          several at once), calls are capped per process
          (SUPABASE_AUTH_MAX_CONCURRENT_VERIFICATIONS, so unknown tokens cannot
          occupy every worker thread) and per client IP
          (SUPABASE_AUTH_VERIFY_RATE_PER_IP per minute, once the client IP is
          trusted); over a limit the request is answered 429
          ``auth_verification_busy`` without a call;
        * the call times out after SUPABASE_AUTH_TIMEOUT_SECONDS (3 s).
        """
        claims = plausible_access_token_claims(token)
        if claims is None:
            return None
        # SECURITY: key on a digest of the WHOLE token. The previous key used
        # token[:64], which for Supabase JWTs is just the (shared) header --
        # every user's token mapped to the same cache entry, so a request
        # within 5 minutes of another user's was authenticated as that user.
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        store = _auth_cache()
        cached = _cache_get(store, _VERIFIED_PREFIX + digest)
        if cached is not None:
            return cached
        if _cache_get(store, _REFUSED_PREFIX + digest):
            return None

        supabase_url = _supabase_url()
        # Token verification key resolution (_verify_key) — order matters:
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
        verify_key = self._verify_key()
        if not supabase_url or not verify_key:
            return None
        return self._verify_with_gotrue(token, digest, claims, supabase_url, verify_key, store)

    def _verify_with_gotrue(self, token, digest, claims, supabase_url, verify_key, store):
        """One GoTrue check per token at a time in this process; the others wait for it."""
        with _INFLIGHT_LOCK:
            pending = _INFLIGHT.get(digest)
            leader = pending is None
            if leader:
                pending = _INFLIGHT[digest] = _PendingVerification()
        if not leader:
            if not pending.done.wait(_verify_timeout() + 1.0) or pending.busy:
                raise _verification_busy()
            return pending.result
        try:
            pending.result = self._call_gotrue(token, digest, claims, supabase_url, verify_key, store)
            return pending.result
        except exceptions.Throttled:
            pending.busy = True
            raise
        finally:
            with _INFLIGHT_LOCK:
                if _INFLIGHT.get(digest) is pending:
                    del _INFLIGHT[digest]
            pending.done.set()

    def _client_ip_for_budget(self) -> str:
        request_obj = getattr(self, "_current_request", None)
        if request_obj is None:
            return ""
        try:
            from crack_cms.client_ip import get_client_ip

            return get_client_ip(request_obj) or ""
        except Exception:  # noqa: BLE001 - no address: no per-IP budget
            return ""

    def _call_gotrue(self, token, digest, claims, supabase_url, verify_key, store):
        if not _within_verification_budget(self._client_ip_for_budget(), store):
            raise _verification_busy()
        slots = _verification_slots()
        if slots is not None and not slots.acquire(blocking=False):
            raise _verification_busy()
        try:
            req = request.Request(
                url=f"{supabase_url}/auth/v1/user",
                headers={
                    "Authorization": f"Bearer {token}",
                    "apikey": verify_key,
                },
                method="GET",
            )
            try:
                with request.urlopen(req, timeout=_verify_timeout()) as resp:
                    if int(getattr(resp, "status", 0) or 0) != 200:
                        return None
                    result = json.loads(resp.read().decode("utf-8", errors="ignore"))
            except error.HTTPError as exc:
                # GoTrue refused the token itself (expired, revoked, signed out,
                # unknown user): do not ask again for a minute. 408 / 429 / 5xx
                # say nothing about the token.
                code = exc.code if isinstance(exc.code, int) else 0
                if 400 <= code < 500 and code not in (408, 429):
                    _cache_set(store, _REFUSED_PREFIX + digest, 1, _REFUSED_TOKEN_CACHE_SECONDS)
                try:
                    exc.close()
                except Exception:  # noqa: BLE001
                    pass
                return None
            except (OSError, HTTPException, ValueError):  # network, timeout, bad JSON
                return None
        finally:
            if slots is not None:
                slots.release()
        if not isinstance(result, dict):
            return None
        # Never serve a cached answer past the token's own expiry.
        ttl = min(_token_cache_seconds(), int(float(claims["exp"]) - time.time()))
        if ttl > 0:
            _cache_set(store, _VERIFIED_PREFIX + digest, result, ttl)
        return result

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
                # A concurrent first request may have created the row: look
                # it up again with every linking rule (never by email alone).
                relink=lambda: self._link_existing_row_by_email(
                    User, email, supabase_uid, trusted_admin, supabase_user,
                ),
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

        # The token wallet is created with the account (_create_local_user)
        # and when a row is first linked (_link_existing_row_by_email); every
        # wallet reader uses get_or_create as well. It used to cost a query on
        # every authenticated request.
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

        The email is matched case-insensitively and must match exactly one
        row. The lookup used to be case-sensitive (PostgreSQL), so a legacy
        row with a mixed-case address got a duplicate account on its first
        Supabase sign-in; with two matching rows nothing is linked.
        """
        rows = list(User.objects.filter(email__iexact=email).order_by("id")[:2])
        if not rows:
            return None
        if len(rows) > 1:
            logger.warning(
                "Refusing to link Supabase identity %s: several accounts share its email (ids %s); "
                "link one explicitly with `manage.py link_supabase_identity --email <email> --uid <id> --apply`.",
                supabase_uid or "<no id>", ", ".join(str(r.pk) for r in rows),
            )
            raise _auth_failed(
                "account_link_required",
                "This account must be verified by an administrator before it can sign in. Please contact support.",
            )
        row = rows[0]
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
            TokenBalance.objects.get_or_create(user=row)
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
    def _create_local_user(User, *, email, supabase_uid, metadata, defaults, relink=None):
        """Create the local row for a new Supabase identity. Returns (user, created).

        ``relink`` (the caller's ``_link_existing_row_by_email``) finds the
        row a concurrent first request created, with every linking rule.

        The username is public (discussions, leaderboard): the one chosen at
        sign-up (user_metadata.username) when it follows the Settings rules,
        made unique, else -- Google sign-ups have none, or it would show the
        email address, break the format rules or pass for the CrackLabs team
        ("admin", "CrackLabs_Official") -- a generated ``learner_<hex>``
        handle (accounts.handles). Only a trusted admin identity may keep a
        team name. It used to be the email's local part, which for a Gmail
        user is the address itself.
        """
        from .handles import username_for_new_account

        username_candidate = username_for_new_account(
            User, metadata.get("username"), email,
            team_member=defaults.get("role") == "admin",
        )

        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username_candidate,
                    email=email,
                    password=None,  # unusable: sign-in is Supabase only
                    supabase_uid=supabase_uid,
                    **defaults,
                )
                TokenBalance.objects.get_or_create(user=user)
            return user, True
        except IntegrityError:
            # A concurrent first request for the same identity created it.
            existing = User.objects.filter(supabase_uid=supabase_uid).first() if supabase_uid else None
            if existing is None and relink is not None:
                # Same rules as a first sign-in: one case-insensitive email
                # match, admin rows only for their original identity.
                existing = relink()
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
                f"- 2,100+ Year-wise & Subject-wise CMS PYQ Bank (2018-2026)\n"
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
