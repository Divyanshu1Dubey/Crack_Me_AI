"""Client IP resolution that cannot be steered through ``X-Forwarded-For``.

In production the backend sits behind the platform edge, so ``REMOTE_ADDR``
is the proxy's address and is shared by every visitor. ``X-Forwarded-For``
carries the real client address, but its left-hand entries are whatever the
client chose to send; only the entries appended by proxies we trust may be
used, which needs the proxy depth.

Two settings control this, both read from the environment in settings.py and
both off by default (the result is then ``REMOTE_ADDR``, as before):

* ``REST_FRAMEWORK['NUM_PROXIES']`` (env ``NUM_PROXIES``): the number of
  trusted proxies that append to ``X-Forwarded-For``. DRF's anon/user/scoped
  throttles read the same value, so they and the question-bank limiter agree
  on who the client is.
* ``TRUSTED_CLIENT_IP_HEADER`` (env): a header that the platform edge sets to
  the client address, e.g. ``CF-Connecting-IP`` or ``DO-Connecting-IP``. Only
  set it when every request reaches Django through that edge; otherwise a
  client can send the header itself.

Kept free of module-level Django imports so settings.py can import
``parse_num_proxies``.
"""
from __future__ import annotations

import ipaddress

__all__ = ["get_client_ip", "header_to_meta_key", "parse_num_proxies"]


def parse_num_proxies(raw) -> int | None:
    """Parse a ``NUM_PROXIES`` value: a non-negative int, otherwise None."""
    if raw is None:
        return None
    value = str(raw).strip()
    if not value:
        return None
    try:
        num = int(value)
    except ValueError:
        return None
    return num if num >= 0 else None


def header_to_meta_key(header: str | None) -> str:
    """``'CF-Connecting-IP'`` -> ``'HTTP_CF_CONNECTING_IP'`` (``''`` if unset)."""
    name = (header or "").strip().upper().replace("-", "_")
    if not name:
        return ""
    return name if name.startswith("HTTP_") else f"HTTP_{name}"


def _clean_ip(value: str | None) -> str:
    """Return a normalised IP address, or ``''`` for anything that is not one."""
    candidate = (value or "").strip().strip('"')
    if not candidate:
        return ""
    if candidate.startswith("[") and "]" in candidate:
        # "[2001:db8::1]:443" -> "2001:db8::1"
        candidate = candidate[1:candidate.index("]")]
    elif candidate.count(":") == 1:
        # "203.0.113.7:51234" -> "203.0.113.7"
        candidate = candidate.split(":", 1)[0]
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return ""


def _num_proxies() -> int | None:
    from rest_framework.settings import api_settings

    return parse_num_proxies(api_settings.NUM_PROXIES)


def get_client_ip(request) -> str:
    """Best-effort client address for rate limiting.

    Order: the configured platform header, then ``X-Forwarded-For`` read
    ``NUM_PROXIES`` entries from the right (DRF's rule), then ``REMOTE_ADDR``.
    A header value that is not a valid IP address is ignored.
    """
    from django.conf import settings

    meta = request.META
    header_key = header_to_meta_key(getattr(settings, "TRUSTED_CLIENT_IP_HEADER", ""))
    if header_key:
        ip = _clean_ip((meta.get(header_key) or "").split(",")[0])
        if ip:
            return ip

    remote_addr = (meta.get("REMOTE_ADDR") or "").strip()
    num_proxies = _num_proxies()
    xff = meta.get("HTTP_X_FORWARDED_FOR")
    if num_proxies and xff:
        addrs = [part.strip() for part in xff.split(",") if part.strip()]
        if addrs:
            ip = _clean_ip(addrs[-min(num_proxies, len(addrs))])
            if ip:
                return ip
    return remote_addr
