"""Signed URLs for evidence figure crops (``GET /api/evidence/figures/<id>/?t=``).

An ``<img src>`` cannot send the Authorization header, so the figure endpoint is AllowAny and a
figure is served to a student only with a token for that figure id. Tokens are issued in the
citations payload, which is built only for viewers entitled to the question's answer. Same scheme
as ``questions.image_access`` (TimestampSigner) with its own salt, so no other signed value of the
site is accepted; the timestamp is rounded down to ``_BUCKET_SECONDS`` so a figure keeps one URL
for a few minutes, and a token is accepted for ``EVIDENCE_FIGURE_TOKEN_TTL`` seconds (default 900)
after it was issued.
"""
from __future__ import annotations

import time

from django.conf import settings
from django.core import signing

TOKEN_PARAM = 't'
DEFAULT_TTL_SECONDS = 900
_BUCKET_SECONDS = 300
_SALT = 'evidence.figure'
_MAX_TOKEN_LENGTH = 256
FIGURE_PATH = '/api/evidence/figures/{id}/'


class _BucketedTimestampSigner(signing.TimestampSigner):
    def timestamp(self):
        now = int(time.time())
        return signing.b62_encode(now - now % _BUCKET_SECONDS)


def _signer():
    return _BucketedTimestampSigner(salt=_SALT)


def token_ttl_seconds() -> int:
    try:
        return max(60, int(getattr(settings, 'EVIDENCE_FIGURE_TOKEN_TTL', DEFAULT_TTL_SECONDS)))
    except (TypeError, ValueError):
        return DEFAULT_TTL_SECONDS


def figure_token(figure_id) -> str:
    key = str(int(figure_id))
    return _signer().sign(key)[len(key) + 1:]


def figure_token_is_valid(figure_id, token) -> bool:
    if not isinstance(token, str) or not token or len(token) > _MAX_TOKEN_LENGTH:
        return False
    try:
        key = str(int(figure_id))
        value = _signer().unsign(f'{key}:{token}', max_age=token_ttl_seconds() + _BUCKET_SECONDS)
    except (signing.BadSignature, TypeError, ValueError):
        return False
    return value == key


def figure_url(figure_id, request=None, *, signed: bool = True) -> str:
    path = FIGURE_PATH.format(id=int(figure_id))
    if request is not None:
        try:
            path = request.build_absolute_uri(path)
        except Exception:  # noqa: BLE001
            pass
    if signed:
        path = f'{path}?{TOKEN_PARAM}={figure_token(figure_id)}'
    return path
