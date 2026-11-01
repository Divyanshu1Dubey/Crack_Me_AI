"""Rate limit for the question bank (GET ``/api/questions/...``).

Requests are counted per identity in a fixed window (default 300 requests
per 60 s, ``QUESTION_BANK_RATE_LIMIT`` / ``QUESTION_BANK_RATE_WINDOW``):

* the authenticated user, when one is known: a session login (set by
  ``AuthenticationMiddleware``) or a bearer token that DRF authenticated on
  an earlier request;
* otherwise the client IP from ``crack_cms.client_ip.get_client_ip``, which
  is ``REMOTE_ADDR`` unless a trusted proxy depth (``NUM_PROXIES``) or a
  platform client-IP header is configured. ``X-Forwarded-For`` is never
  trusted without one of those (it is client-controlled).

The old limiter keyed every request on ``REMOTE_ADDR`` with a 60/min budget.
Behind the production proxy that address is shared by every visitor, so a
handful of students exhausted one site-wide bucket, and a single student in
rapid revision (about 12 GETs per question) exceeded it on their own.

Why tokens are learned rather than read: DRF authenticates inside the view,
after this middleware, so on the way in only the raw ``Authorization``
header is visible. Keying on that header would let a client mint a fresh
bucket per request with random tokens (an invalid token is served as
anonymous). Instead, on the way out we record which user DRF resolved the
token to (keyed by a SHA-256 digest of the token); until then a request
counts against the client IP like any anonymous request.

The image endpoint (``/api/questions/images/<id>/serve/``) is exempt: every
inline ``<img>`` would spend the budget, and ``<img>`` requests carry no
``Authorization`` header, so they would all land on the shared IP bucket.
"""
from __future__ import annotations

import hashlib
import re
import time

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.utils.cache import add_never_cache_headers

from crack_cms.client_ip import get_client_ip

DEFAULT_LIMIT = 300
DEFAULT_WINDOW_SECONDS = 60
TOKEN_USER_TTL_SECONDS = 300

_PREFIX = "/api/questions/"
_EXEMPT_PATH_RE = re.compile(r"^/api/questions/images/\d+/serve/?$")
_BUCKET_PREFIX = "rl_qs"
_TOKEN_USER_PREFIX = "rl_qs_token_user"


def _as_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _budget() -> tuple[int, int]:
    limit = _as_int(getattr(settings, "QUESTION_BANK_RATE_LIMIT", DEFAULT_LIMIT), DEFAULT_LIMIT)
    window = _as_int(
        getattr(settings, "QUESTION_BANK_RATE_WINDOW", DEFAULT_WINDOW_SECONDS),
        DEFAULT_WINDOW_SECONDS,
    )
    return limit, max(1, window)


def _bearer_digest(request) -> str:
    parts = (request.META.get("HTTP_AUTHORIZATION") or "").split()
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1]:
        return ""
    return hashlib.sha256(parts[1].encode("utf-8", "ignore")).hexdigest()


def _token_user_key(digest: str) -> str:
    return f"{_TOKEN_USER_PREFIX}:{digest}"


def _authenticated_pk(user):
    try:
        if user is not None and user.is_authenticated:
            return user.pk
    except Exception:  # noqa: BLE001 - a broken session must not 500 the API
        return None
    return None


def rate_limit_identity(request, token_digest: str = "") -> str:
    """Bucket identity for ``request`` before the view runs (``''`` if none)."""
    user_pk = _authenticated_pk(getattr(request, "user", None))
    if user_pk is not None:
        return f"u:{user_pk}"
    if token_digest:
        known_pk = cache.get(_token_user_key(token_digest))
        if known_pk is not None:
            return f"u:{known_pk}"
    ip = get_client_ip(request)
    return f"ip:{ip}" if ip else ""


def _hit(identity: str, window: int) -> tuple[int | None, int]:
    """Count one request; return (count in the current window, seconds left)."""
    now = time.time()
    bucket = int(now // window)
    retry_after = max(1, int((bucket + 1) * window - now))
    key = f"{_BUCKET_PREFIX}:{identity}:{bucket}"
    timeout = window + 5
    try:
        if cache.add(key, 1, timeout=timeout):
            return 1, retry_after
        return cache.incr(key), retry_after
    except ValueError:
        # The key expired between add() and incr().
        cache.set(key, 1, timeout=timeout)
        return 1, retry_after
    except Exception:  # noqa: BLE001 - cache outage: fail open
        return None, retry_after


class RateLimitMiddleware:
    """Per-user / per-client rate limit for question-bank GETs (see module doc)."""

    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def applies_to(request) -> bool:
        if request.method != "GET":
            return False
        path = request.path_info
        return path.startswith(_PREFIX) and not _EXEMPT_PATH_RE.match(path)

    def __call__(self, request):
        if not self.applies_to(request):
            return self.get_response(request)

        limit, window = _budget()
        token_digest = _bearer_digest(request)
        if limit > 0:
            identity = rate_limit_identity(request, token_digest)
            if identity:
                count, retry_after = _hit(identity, window)
                if count is not None and count > limit:
                    response = JsonResponse(
                        {"error": "Too many requests. Please slow down."},
                        status=429,
                    )
                    response["Retry-After"] = str(retry_after)
                    add_never_cache_headers(response)
                    return response

        response = self.get_response(request)

        if token_digest:
            # DRF copies the user it authenticated onto the Django request.
            user_pk = _authenticated_pk(getattr(request, "user", None))
            if user_pk is not None:
                try:
                    cache.set(_token_user_key(token_digest), user_pk, TOKEN_USER_TTL_SECONDS)
                except Exception:  # noqa: BLE001 - cache outage: skip
                    pass
        return response
