"""Blog images: admin uploads stored under MEDIA_ROOT/blog, served publicly.

    POST /api/blog/images/                       admin (role 'admin', superuser or staff), multipart ``file``
    GET  /api/blog/images/<yyyy>/<mm>/<hash>.<ext>   public

Production serves no /media/ URL (Django serves MEDIA_ROOT only with DEBUG),
so blog images go through this view, like question images go through
questions.views.QuestionImageServeView, whose hardening this copies: only
real raster bytes (PNG, JPEG, GIF, WebP, typed from the content, never from
the client's name or Content-Type) are accepted and served, and every response
carries ``X-Content-Type-Options: nosniff`` and
``Content-Security-Policy: default-src 'none'; sandbox``. On Railway
MEDIA_ROOT is /data/media on the volume (docs/DEPLOY_RAILWAY.md), so uploads
survive deploys. Supabase Storage (retired) is not used.

A file is named after the SHA-256 of its bytes, so the same image uploaded
twice in a month is stored once and a URL never changes content (it is cached
for a year). The editor inserts the returned ``src`` (a path on the API
origin) into the post body as a markdown image; the public renderer
(frontend/src/lib/blogMarkdown.ts) points it at the API origin.
"""
from __future__ import annotations

import hashlib
import io
import logging
import os
import re
import uuid
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .views import BlogAdminPermission, BlogReadThrottle

logger = logging.getLogger(__name__)

#: Largest accepted upload (bytes); BLOG_IMAGE_MAX_BYTES overrides it.
DEFAULT_MAX_BYTES = 5 * 1024 * 1024
#: Largest accepted side and area, in pixels (decompression bombs, absurd scans).
MAX_SIDE = 8000
MAX_PIXELS = 40_000_000
#: The folder under MEDIA_ROOT.
SUBDIR = "blog"
#: Public URL prefix of a stored image (the API is mounted at /api/).
URL_PREFIX = "/api/blog/images/"
#: <yyyy>/<mm>/<32 hex>.<ext>: the only names the serve view opens.
STORED_NAME = re.compile(r"\d{4}/\d{2}/[0-9a-f]{32}\.(?:png|jpg|gif|webp)")

#: Raster formats (magic bytes -> MIME), as questions.views._RASTER_SIGNATURES.
_RASTER_SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)
_EXTENSION = {"image/png": "png", "image/jpeg": "jpg", "image/gif": "gif", "image/webp": "webp"}
_PIL_FORMAT = {"image/png": "PNG", "image/jpeg": "JPEG", "image/gif": "GIF", "image/webp": "WEBP"}
IMAGE_RESPONSE_CSP = "default-src 'none'; sandbox"


class ImageRejected(ValueError):
    """The upload is not an image this endpoint stores (the message is shown to the admin)."""


def max_upload_bytes() -> int:
    return int(getattr(settings, "BLOG_IMAGE_MAX_BYTES", DEFAULT_MAX_BYTES))


def _too_large_message(limit: int) -> str:
    size = f"{limit // (1024 * 1024)} MB" if limit >= 1024 * 1024 else f"{max(1, limit // 1024)} KB"
    return f"The image is larger than {size}; resize or compress it first."


def sniff_raster_mime(head: bytes) -> str | None:
    """'image/png' / 'image/jpeg' / 'image/gif' / 'image/webp' from the first bytes, or None."""
    head = head or b""
    for signature, mime in _RASTER_SIGNATURES:
        if head.startswith(signature):
            return mime
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    return None


def harden(response):
    """Image responses are inert documents even when opened directly."""
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = IMAGE_RESPONSE_CSP
    return response


def inspect_image(data: bytes) -> tuple[str, int, int]:
    """(mime, width, height) of an upload, or ImageRejected."""
    limit = max_upload_bytes()
    if not data:
        raise ImageRejected("The file is empty.")
    if len(data) > limit:
        raise ImageRejected(_too_large_message(limit))
    mime = sniff_raster_mime(data[:16])
    if not mime:
        raise ImageRejected("Upload a PNG, JPEG, GIF or WebP image (SVG and other formats are not accepted).")
    try:
        from PIL import Image
    except ImportError as exc:  # Pillow is in requirements.txt; fail closed without it
        raise ImageRejected("Image checks are unavailable on this server.") from exc
    try:
        with Image.open(io.BytesIO(data)) as img:
            fmt, (width, height) = img.format, img.size
            img.verify()
    except Image.DecompressionBombError as exc:
        raise ImageRejected("The image has too many pixels.") from exc
    except Exception as exc:  # noqa: BLE001 - any decoder error means "not a readable image"
        raise ImageRejected("The file is not a readable image.") from exc
    if fmt != _PIL_FORMAT[mime]:
        raise ImageRejected("The file's content does not match an image format.")
    if width < 1 or height < 1 or width > MAX_SIDE or height > MAX_SIDE or width * height > MAX_PIXELS:
        raise ImageRejected(f"Images may be at most {MAX_SIDE} pixels on a side.")
    return mime, width, height


def images_root() -> Path:
    return Path(settings.MEDIA_ROOT) / SUBDIR


def store_image(data: bytes, mime: str) -> str:
    """Write the bytes (once) and return the stored name <yyyy>/<mm>/<hash>.<ext>."""
    now = timezone.now()
    name = f"{now:%Y}/{now:%m}/{hashlib.sha256(data).hexdigest()[:32]}.{_EXTENSION[mime]}"
    target = images_root() / name
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(f".{target.name}.{uuid.uuid4().hex}.part")
        partial.write_bytes(data)
        os.replace(partial, target)
    return name


def stored_image_path(name: str) -> Path | None:
    """The file of a stored name, or None (bad name, outside the folder, missing)."""
    if not STORED_NAME.fullmatch(name or ""):
        return None
    root = os.path.realpath(images_root())
    candidate = os.path.realpath(os.path.join(root, name))
    if not candidate.startswith(root + os.sep) or not os.path.isfile(candidate):
        return None
    return Path(candidate)


class BlogImageUploadView(APIView):
    """POST a multipart ``file``; answers 201 ``{src, width, height, bytes, mime}``."""

    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [BlogAdminPermission]

    def post(self, request):
        upload = request.FILES.get("file")
        if upload is None:
            return Response({"file": ["Choose an image file to upload."]}, status=status.HTTP_400_BAD_REQUEST)
        limit = max_upload_bytes()
        if upload.size is not None and upload.size > limit:
            return Response({"file": [_too_large_message(limit)]}, status=status.HTTP_400_BAD_REQUEST)
        data = upload.read(limit + 1)
        try:
            mime, width, height = inspect_image(data)
        except ImageRejected as exc:
            return Response({"file": [str(exc)]}, status=status.HTTP_400_BAD_REQUEST)
        name = store_image(data, mime)
        logger.info("Blog image stored: %s (%s, %sx%s, %s bytes) by user %s",
                    name, mime, width, height, len(data), getattr(request.user, "pk", None))
        return Response(
            {"src": f"{URL_PREFIX}{name}", "width": width, "height": height, "bytes": len(data), "mime": mime},
            status=status.HTTP_201_CREATED,
        )


class BlogImageServeView(APIView):
    """GET a stored blog image (public, cached for a year: names never change content)."""

    authentication_classes: list = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [BlogReadThrottle]

    def get(self, request, name: str):
        path = stored_image_path(name)
        if path is None:
            raise Http404("Blog image not found")
        handle = open(path, "rb")
        head = handle.read(16)
        handle.seek(0)
        mime = sniff_raster_mime(head)
        if not mime:
            # Only this module writes here and it stores raster bytes only; anything
            # else in the folder was not written by it and is never served.
            handle.close()
            raise Http404("Blog image not found")
        response = FileResponse(handle, content_type=mime)
        response["Cache-Control"] = "public, max-age=31536000, immutable"
        response["Cross-Origin-Resource-Policy"] = "cross-origin"
        return harden(response)
