"""Admin-only request diagnostics.

``GET /api/health/client-ip/`` echoes the address headers of the caller's
own request, together with the address the question-bank limiter, django-axes
and DRF's throttles derive from them. Use it from the deployed site to choose
``NUM_PROXIES`` / ``TRUSTED_CLIENT_IP_HEADER`` (see the client-IP notes in
crack_cms/settings.py): through the public domain ``peer`` must be the edge's
address (e.g. Cloudflare's) and ``client_ip`` your own; on the platform's own
hostname a forged ``CF-Connecting-IP`` / ``X-Forwarded-For`` must not change
``client_ip``. Only the caller's request is shown; nothing is stored.
"""
from __future__ import annotations

from django.conf import settings
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.throttling import BaseThrottle
from rest_framework.views import APIView

from accounts.permissions import IsControlTowerAdmin
from crack_cms.client_ip import client_ip_details, get_client_ip
from crack_cms.throttling import ClientIPIdentMixin, StrictClientIPIdentMixin

# (header name, request.META key)
ADDRESS_HEADERS = (
    ("X-Forwarded-For", "HTTP_X_FORWARDED_FOR"),
    ("X-Real-IP", "HTTP_X_REAL_IP"),
    ("DO-Connecting-IP", "HTTP_DO_CONNECTING_IP"),
    ("CF-Connecting-IP", "HTTP_CF_CONNECTING_IP"),
    ("True-Client-IP", "HTTP_TRUE_CLIENT_IP"),
    ("Forwarded", "HTTP_FORWARDED"),
)


class _GeneralIdent(ClientIPIdentMixin, BaseThrottle):
    pass


class _SignInIdent(StrictClientIPIdentMixin, BaseThrottle):
    pass


class ClientIpDiagnosticsView(APIView):
    permission_classes = [IsControlTowerAdmin]

    def get(self, request):
        meta = request.META
        details = client_ip_details(request)
        return Response({
            "remote_addr": meta.get("REMOTE_ADDR", ""),
            "headers": {name: meta[key] for name, key in ADDRESS_HEADERS if meta.get(key)},
            "num_proxies": api_settings.NUM_PROXIES,
            "trusted_client_ip_header": getattr(settings, "TRUSTED_CLIENT_IP_HEADER", "") or None,
            "trusted_client_ip_header_from": getattr(settings, "TRUSTED_CLIENT_IP_HEADER_FROM", "") or None,
            "trusted_client_ip_secret_set": bool(getattr(settings, "TRUSTED_CLIENT_IP_SECRET", "")),
            # The address that connected to the outermost trusted proxy (X-Forwarded-For
            # read NUM_PROXIES from the right, else REMOTE_ADDR), and whether the edge
            # header was read for this request (crack_cms/client_ip.py).
            "peer": details["peer"],
            "edge_header_honoured": details["edge_header_honoured"],
            # What questions/middleware.py and django-axes key anonymous requests on.
            "rate_limit_client_ip": get_client_ip(request),
            # What DRF's anon / scoped throttles key on (crack_cms/throttling.py).
            "drf_throttle_ident": _GeneralIdent().get_ident(request),
            # What the sign-in throttles key on (always the client address above).
            "sign_in_throttle_ident": _SignInIdent().get_ident(request),
        })
