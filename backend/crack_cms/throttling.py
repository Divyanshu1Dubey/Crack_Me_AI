"""DRF throttles that key anonymous requests on ``crack_cms.client_ip.get_client_ip``.

DRF's own ``get_ident`` honours only NUM_PROXIES; behind Cloudflare it then
keys every visitor of one Cloudflare edge on that edge's address, and while
NUM_PROXIES is unset it keys on the raw, client-controlled X-Forwarded-For.
These subclasses use the client address django-axes and the question-bank
limiter use (the edge header when the request came through that edge, else
the peer; see crack_cms/client_ip.py):

* ``AnonRateThrottle`` / ``UserRateThrottle`` / ``ScopedRateThrottle``
  (REST_FRAMEWORK['DEFAULT_THROTTLE_CLASSES'] and the views that list a
  throttle themselves): ``get_client_ip`` once NUM_PROXIES is set. Without it
  they keep DRF's historical key, so an unconfigured deployment behaves as
  before.
* ``ClientIPScopedRateThrottle``: always ``get_client_ip`` (``REMOTE_ADDR``
  until NUM_PROXIES is set), for the sign-in endpoints, whose per-IP limits
  must never be steerable with forged headers. ``accounts.W007`` warns in
  django mode while NUM_PROXIES is unset.

Authenticated requests are keyed on the user as before (UserRateThrottle /
ScopedRateThrottle); only the anonymous ident changes.
"""
from __future__ import annotations

from rest_framework import throttling

from crack_cms.client_ip import get_client_ip, proxy_depth_configured

__all__ = [
    "AnonRateThrottle",
    "ClientIPIdentMixin",
    "ClientIPScopedRateThrottle",
    "ScopedRateThrottle",
    "StrictClientIPIdentMixin",
    "UserRateThrottle",
]


class ClientIPIdentMixin:
    """``get_ident`` from ``crack_cms.client_ip`` once NUM_PROXIES is set; DRF's rule before that."""

    def get_ident(self, request):
        if proxy_depth_configured():
            ip = get_client_ip(request)
            if ip:
                return ip
        return super().get_ident(request)


class StrictClientIPIdentMixin:
    """``get_ident`` from ``crack_cms.client_ip`` always: forged X-Forwarded-For / edge headers never count."""

    def get_ident(self, request):
        # Never DRF's fallback: without NUM_PROXIES it is the raw X-Forwarded-For.
        return get_client_ip(request) or 'unknown'


class AnonRateThrottle(ClientIPIdentMixin, throttling.AnonRateThrottle):
    pass


class UserRateThrottle(ClientIPIdentMixin, throttling.UserRateThrottle):
    pass


class ScopedRateThrottle(ClientIPIdentMixin, throttling.ScopedRateThrottle):
    pass


class ClientIPScopedRateThrottle(StrictClientIPIdentMixin, throttling.ScopedRateThrottle):
    pass
