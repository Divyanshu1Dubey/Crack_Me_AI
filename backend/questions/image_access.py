"""Signed access to explanation figures behind the public image endpoint.

``GET /api/questions/images/<id>/serve/`` (QuestionImageServeView) is
``AllowAny``: an HTML ``<img src>`` cannot send the ``Authorization`` header,
so the endpoint cannot ask who is looking. Stem figures stay public (the stem
itself is public). An *explanation* figure -- runtime role ``'explanation'``,
see ``questions.serializers.resolve_runtime_image_role`` -- belongs to the
answer, and image ids are sequential, so without a check anyone could
download the explanation figures of locked and scholarship questions by
counting up from a stem image id.

Payloads built for a viewer entitled to the question's answer (premium,
admin / staff, or a free showcase question that is not a scholarship
question; ``questions.views.user_can_view_answer``) append a signed token to
the URL of each explanation figure (``?t=<token>``). The serve view returns an
explanation figure only with a valid token for that image id, or to a caller
whose own credentials make it entitled.

A token is a ``TimestampSigner`` signature over the image id, salted for
this purpose only (no other signed value of the site is accepted). The
timestamp is rounded down to the hour, so an image keeps one URL for the
hour (the browser cache and the frontend's resolved-markup cache keep
hitting across list and detail payloads), and a token is accepted for at
least ``QUESTION_IMAGE_TOKEN_TTL`` seconds after it was issued (default
12 hours: long enough for one study session on one page of questions,
short enough that a copied URL stops working soon after).
"""
from __future__ import annotations

import re
import time

from django.conf import settings
from django.core import signing

#: Query parameter that carries the token.
TOKEN_PARAM = 't'
#: Default minimum lifetime of a token, in seconds.
DEFAULT_TOKEN_TTL_SECONDS = 12 * 60 * 60
_BUCKET_SECONDS = 60 * 60
_SALT = 'questions.image-serve.explanation-figure'
_MAX_TOKEN_LENGTH = 256
_SERVE_PATH_RE = re.compile(r'/api/questions/images/\d+/serve/?$')


class _HourlyTimestampSigner(signing.TimestampSigner):
    """Timestamps rounded down to the hour: one URL per image per hour."""

    def timestamp(self):
        now = int(time.time())
        return signing.b62_encode(now - now % _BUCKET_SECONDS)


def _signer() -> signing.TimestampSigner:
    return _HourlyTimestampSigner(salt=_SALT)


def token_ttl_seconds() -> int:
    try:
        return max(60, int(getattr(settings, 'QUESTION_IMAGE_TOKEN_TTL', DEFAULT_TOKEN_TTL_SECONDS)))
    except (TypeError, ValueError):
        return DEFAULT_TOKEN_TTL_SECONDS


def image_access_token(image_id) -> str:
    """Token for one image id: ``<timestamp>:<signature>``."""
    image_key = str(int(image_id))
    return _signer().sign(image_key)[len(image_key) + 1:]


def image_token_is_valid(image_id, token) -> bool:
    """True when ``token`` was issued for ``image_id`` and has not expired."""
    if not isinstance(token, str) or not token or len(token) > _MAX_TOKEN_LENGTH:
        return False
    try:
        image_key = str(int(image_id))
        # The hour rounding makes a token up to one bucket older than its
        # issue time: accept a full TTL after issue.
        value = _signer().unsign(f'{image_key}:{token}', max_age=token_ttl_seconds() + _BUCKET_SECONDS)
    except (signing.BadSignature, TypeError, ValueError):
        return False
    return value == image_key


def is_image_serve_url(url) -> bool:
    """True for a URL (absolute or rooted) of the image serve endpoint."""
    if not isinstance(url, str) or not url:
        return False
    path = url.split('#', 1)[0].split('?', 1)[0]
    return bool(_SERVE_PATH_RE.search(path))


def with_image_token(url: str, image_id) -> str:
    """``url`` of the serve endpoint with a fresh token for ``image_id``
    (any other URL is returned unchanged)."""
    if not is_image_serve_url(url):
        return url
    separator = '&' if '?' in url else '?'
    return f'{url}{separator}{TOKEN_PARAM}={image_access_token(image_id)}'
