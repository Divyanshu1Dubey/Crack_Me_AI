"""Cross-Origin-Resource-Policy for images served by the API."""
import re

_IMAGE_SERVE_PATH_RE = re.compile(r"^/api/questions/images/\d+/serve/?$")


class CrossOriginResourcePolicyMiddleware:
    """Mark image responses as embeddable by other origins.

    The frontend (cracklabs.app) loads question images straight from the API
    origin (``/api/questions/images/<id>/serve/`` on api.cracklabs.app). A
    page that sends ``Cross-Origin-Embedder-Policy`` blocks any cross-origin
    ``<img>`` that lacks ``Cross-Origin-Resource-Policy: cross-origin``, so
    send it on ``image/*`` responses and on everything from the serve
    endpoint (including its redirects to public storage). A policy the view
    set itself is left alone.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response.has_header("Cross-Origin-Resource-Policy"):
            return response
        content_type = (response.get("Content-Type") or "").lower()
        if content_type.startswith("image/") or _IMAGE_SERVE_PATH_RE.match(request.path_info):
            response["Cross-Origin-Resource-Policy"] = "cross-origin"
        return response
