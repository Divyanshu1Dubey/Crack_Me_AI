"""Admin-only request diagnostics.

``GET /api/health/client-ip/`` echoes the address headers of the caller's
own request, together with the address the question-bank limiter and DRF's
throttles derive from them. Use it from the deployed site to choose
``NUM_PROXIES`` / ``TRUSTED_CLIENT_IP_HEADER`` (see the client-IP notes in
crack_cms/settings.py): the right header is the one that holds your own
public address. Only the caller's request is shown; nothing is stored.
"""
from __future__ import annotations

from django.conf import settings
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.throttling import BaseThrottle
from rest_framework.views import APIView

from accounts.permissions import IsControlTowerAdmin
from crack_cms.client_ip import get_client_ip

# (header name, request.META key)
ADDRESS_HEADERS = (
    ("X-Forwarded-For", "HTTP_X_FORWARDED_FOR"),
    ("X-Real-IP", "HTTP_X_REAL_IP"),
    ("DO-Connecting-IP", "HTTP_DO_CONNECTING_IP"),
    ("CF-Connecting-IP", "HTTP_CF_CONNECTING_IP"),
    ("True-Client-IP", "HTTP_TRUE_CLIENT_IP"),
    ("Forwarded", "HTTP_FORWARDED"),
)


class ClientIpDiagnosticsView(APIView):
    permission_classes = [IsControlTowerAdmin]

    def get(self, request):
        meta = request.META
        return Response({
            "remote_addr": meta.get("REMOTE_ADDR", ""),
            "headers": {name: meta[key] for name, key in ADDRESS_HEADERS if meta.get(key)},
            "num_proxies": api_settings.NUM_PROXIES,
            "trusted_client_ip_header": getattr(settings, "TRUSTED_CLIENT_IP_HEADER", "") or None,
            # What questions/middleware.py keys anonymous requests on.
            "rate_limit_client_ip": get_client_ip(request),
            # What DRF's anon / scoped throttles key on.
            "drf_throttle_ident": BaseThrottle().get_ident(request),
        })
