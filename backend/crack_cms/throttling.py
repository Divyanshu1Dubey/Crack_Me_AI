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
* ``ClientIPScopedRateThrottle``: ``get_client_ip`` as soon as the client
  address is known (NUM_PROXIES, or a trusted edge header), for the sign-in
  endpoints, whose per-IP limits must not be steerable with forged headers;
  with nothing configured it keeps DRF's key rather than REMOTE_ADDR (the
  platform proxy, one bucket for every visitor). ``accounts.W007`` warns in
  django mode while NUM_PROXIES is unset.

Authenticated requests are keyed on the user as before (UserRateThrottle /
ScopedRateThrottle); only the anonymous ident changes.
"""
from __future__ import annotations

from rest_framework import throttling

from crack_cms.client_ip import client_ip_known, get_client_ip, proxy_depth_configured

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
    """``get_ident`` from ``crack_cms.client_ip`` whenever it can tell visitors apart.

    With nothing configured (no NUM_PROXIES, no edge header, no
    TRUSTED_CLIENT_IP_HEADER_FROM), the client address would be REMOTE_ADDR,
    i.e. the platform proxy shared by every visitor: one person could then use
    up everyone's sign-in budget. DRF's own key (the raw X-Forwarded-For) is
    kept in that case, as before; accounts.W007 asks for the configuration.
    Once the operator restricts the edge header (TRUSTED_CLIENT_IP_HEADER_FROM),
    the strict address is used even before NUM_PROXIES is set.
    """

    def get_ident(self, request):
        from django.conf import settings

        restricted = bool(str(getattr(settings, 'TRUSTED_CLIENT_IP_HEADER_FROM', '') or '').strip())
        if client_ip_known() or restricted:
            return get_client_ip(request) or 'unknown'
        return super().get_ident(request)


class AnonRateThrottle(ClientIPIdentMixin, throttling.AnonRateThrottle):
    pass


class UserRateThrottle(ClientIPIdentMixin, throttling.UserRateThrottle):
    pass


class ScopedRateThrottle(ClientIPIdentMixin, throttling.ScopedRateThrottle):
    pass


class ClientIPScopedRateThrottle(StrictClientIPIdentMixin, throttling.ScopedRateThrottle):
    pass
