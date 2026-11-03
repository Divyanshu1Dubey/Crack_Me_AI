"""Client IP resolution that, once hardened, cannot be steered through ``X-Forwarded-For`` or a forged edge header.

In production the backend sits behind the platform proxy, so ``REMOTE_ADDR``
is the proxy's address and is shared by every visitor. ``X-Forwarded-For``
carries the real client address, but its left-hand entries are whatever the
client chose to send; only the entries appended by proxies we trust may be
used, which needs the proxy depth.

Settings (read from the environment in settings.py, all off by default: the
result is then ``REMOTE_ADDR``, as before):

* ``REST_FRAMEWORK['NUM_PROXIES']`` (env ``NUM_PROXIES``): the number of
  trusted proxies that append to ``X-Forwarded-For``. The **peer** is the
  entry that many places from the right -- the address that connected to the
  outermost trusted proxy (on Railway: ``NUM_PROXIES=1``, the hop Railway's
  edge appends). Without it the peer is ``REMOTE_ADDR``.
* ``TRUSTED_CLIENT_IP_HEADER`` (env): a header that an edge IN FRONT of those
  proxies sets to the client address, e.g. ``CF-Connecting-IP``. It is
  honoured only when the request came through that edge, i.e. when the peer
  is one of the edge's addresses:

  - ``TRUSTED_CLIENT_IP_HEADER_FROM`` (env): comma-separated networks and/or
    ``cloudflare`` (Cloudflare's published ranges, ``CLOUDFLARE_IP_RANGES``),
    or ``any``. Default (unset): ``any``, the behaviour before this setting
    existed. Restricting the header to Cloudflare is opt-in because it relies
    on the platform proxy appending the Cloudflare hop to X-Forwarded-For
    (NUM_PROXIES): if the hop is something else (another proxy layer in the
    platform's edge), every visitor would share that address in the rate
    limits and lockouts. Check GET /api/health/client-ip/ first (the
    right-most X-Forwarded-For entry of a request through Cloudflare must be a
    Cloudflare address), then set ``NUM_PROXIES=1`` and
    ``TRUSTED_CLIENT_IP_HEADER_FROM=cloudflare`` (docs/DEPLOY_RAILWAY.md).
  - ``TRUSTED_CLIENT_IP_SECRET`` (+ ``TRUSTED_CLIENT_IP_SECRET_HEADER``,
    default ``X-Edge-Auth``), optional: the header is additionally only
    honoured when the request carries this secret, e.g. added by a Cloudflare
    Transform Rule of our own zone.

  A request that reaches the service around the edge (for example on the
  platform's own ``*.up.railway.app`` hostname) is keyed on its peer whatever
  ``CF-Connecting-IP`` / ``X-Forwarded-For`` it sends.

django-axes (AXES_CLIENT_IP_CALLABLE), the question-bank limiter and DRF's
throttles (crack_cms/throttling.py) all key on ``get_client_ip``.

Kept free of module-level Django imports so settings.py can import
``num_proxies_from_env``.
"""
from __future__ import annotations

import functools
import hmac
import ipaddress
import logging
import re

__all__ = [
    "CLOUDFLARE_IP_RANGES",
    "client_ip_details",
    "client_ip_known",
    "edge_header_trusted",
    "get_client_ip",
    "header_to_meta_key",
    "num_proxies_from_env",
    "parse_num_proxies",
    "proxy_depth_configured",
]

logger = logging.getLogger(__name__)

# Cloudflare's edge addresses as published at https://www.cloudflare.com/ips-v4
# and https://www.cloudflare.com/ips-v6. Compare with that list when deploying;
# TRUSTED_CLIENT_IP_HEADER_FROM can list other / additional networks.
CLOUDFLARE_IP_RANGES = (
    "173.245.48.0/20", "103.21.244.0/22", "103.22.200.0/22", "103.31.4.0/22",
    "141.101.64.0/18", "108.162.192.0/18", "190.93.240.0/20", "188.114.96.0/20",
    "197.234.240.0/22", "198.41.128.0/17", "162.158.0.0/15", "104.16.0.0/13",
    "104.24.0.0/14", "172.64.0.0/13", "131.0.72.0/22",
    "2400:cb00::/32", "2606:4700::/32", "2803:f800::/32", "2405:b500::/32",
    "2405:8100::/32", "2a06:98c0::/29", "2c0f:f248::/32",
)
# Headers only Cloudflare sets: trusted from Cloudflare's ranges by default.
CLOUDFLARE_HEADERS = frozenset({"HTTP_CF_CONNECTING_IP", "HTTP_CF_CONNECTING_IPV6"})
DEFAULT_SECRET_HEADER = "X-Edge-Auth"


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


def num_proxies_from_env(environ) -> int | None:
    """NUM_PROXIES from the environment (settings.py): an explicit value only (0 = no proxy).

    There is deliberately no platform default: what the right-most
    X-Forwarded-For entry is depends on the platform's edge (Railway's answers
    on whether it appends or replaces the header, and on extra CDN layers,
    differ), so the depth is set by the operator after checking
    GET /api/health/client-ip/. Unset keeps DRF's historical keys.
    """
    return parse_num_proxies(environ.get("NUM_PROXIES"))


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


def proxy_depth_configured() -> bool:
    """True when NUM_PROXIES is set (0 included): the peer address is known."""
    return _num_proxies() is not None


@functools.lru_cache(maxsize=32)
def _header_sources(spec: str, header_key: str) -> tuple[tuple, bool]:
    """(networks allowed to set the client-IP header, any peer allowed) for TRUSTED_CLIENT_IP_HEADER_FROM."""
    tokens = [t for t in re.split(r"[\s,]+", (spec or "").strip().lower()) if t]
    if not tokens:
        # Unset: any peer, as before the setting existed (opt-in restriction, module docstring).
        return (), True
    if "any" in tokens:
        return (), True
    networks = []
    for token in tokens:
        if token == "cloudflare":
            networks.extend(ipaddress.ip_network(r) for r in CLOUDFLARE_IP_RANGES)
            continue
        try:
            networks.append(ipaddress.ip_network(token, strict=False))
        except ValueError:
            logger.warning("TRUSTED_CLIENT_IP_HEADER_FROM: %r is not a network and is ignored.", token[:64])
    return tuple(networks), False


def _sources(settings, header_key: str) -> tuple[tuple, bool]:
    return _header_sources(str(getattr(settings, "TRUSTED_CLIENT_IP_HEADER_FROM", "") or ""), header_key)


def _peer(meta) -> str:
    """The address that connected to the outermost trusted proxy (see the module docstring)."""
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


def _secret_matches(meta, settings) -> bool:
    secret = str(getattr(settings, "TRUSTED_CLIENT_IP_SECRET", "") or "")
    if not secret:
        return True
    key = header_to_meta_key(getattr(settings, "TRUSTED_CLIENT_IP_SECRET_HEADER", "") or DEFAULT_SECRET_HEADER)
    sent = str(meta.get(key) or "")
    return hmac.compare_digest(sent.encode("utf-8"), secret.encode("utf-8"))


def _peer_in(peer: str, networks) -> bool:
    ip = _clean_ip(peer)
    if not ip:
        return False
    address = ipaddress.ip_address(ip)
    if address.version == 6 and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    return any(address in network for network in networks)


def edge_header_trusted(request, peer: str | None = None) -> bool:
    """True when TRUSTED_CLIENT_IP_HEADER may be read for this request (configured, from an allowed peer, secret)."""
    from django.conf import settings

    meta = request.META
    header_key = header_to_meta_key(getattr(settings, "TRUSTED_CLIENT_IP_HEADER", ""))
    if not header_key or not _secret_matches(meta, settings):
        return False
    networks, any_peer = _sources(settings, header_key)
    if any_peer:
        return True
    return _peer_in(_peer(meta) if peer is None else peer, networks)


def client_ip_known() -> bool:
    """True when ``get_client_ip`` can tell visitors behind the platform proxy apart.

    NUM_PROXIES is set, or TRUSTED_CLIENT_IP_HEADER names a header that is
    honoured from any peer. A Cloudflare header without NUM_PROXIES is
    honoured only when Cloudflare connects to Django directly, which is not
    the case behind a platform proxy.
    """
    from django.conf import settings

    if proxy_depth_configured():
        return True
    header_key = header_to_meta_key(getattr(settings, "TRUSTED_CLIENT_IP_HEADER", ""))
    return bool(header_key) and _sources(settings, header_key)[1]


def get_client_ip(request) -> str:
    """Best-effort client address for rate limiting and lockouts.

    The configured edge header when the request came through that edge (see
    ``edge_header_trusted``), otherwise the peer: ``X-Forwarded-For`` read
    ``NUM_PROXIES`` entries from the right (DRF's rule), else ``REMOTE_ADDR``.
    A header value that is not a valid IP address is ignored.
    """
    from django.conf import settings

    meta = request.META
    peer = _peer(meta)
    header_key = header_to_meta_key(getattr(settings, "TRUSTED_CLIENT_IP_HEADER", ""))
    if header_key and edge_header_trusted(request, peer):
        ip = _clean_ip((meta.get(header_key) or "").split(",")[0])
        if ip:
            return ip
    return peer


def client_ip_details(request) -> dict:
    """What ``get_client_ip`` saw (for GET /api/health/client-ip/): the peer and whether the edge header counted."""
    peer = _peer(request.META)
    return {
        "peer": peer,
        "edge_header_honoured": edge_header_trusted(request, peer),
        "client_ip": get_client_ip(request),
    }
