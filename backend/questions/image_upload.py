"""Supabase Storage upload helper for admin-uploaded question images.

This module creates a `QuestionImage` row and uploads the underlying
file to Supabase Storage. It is the only authoritative path for
admin-uploaded images — the same Django backend that serves the API
also owns the bucket.

**Bucket**: `crack-cms-question-images` (public read).
**Path**: `question_images/{question_id}/{sha256_short}.{ext}`.
**Env vars**: `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` (already in
`backend/.env.example`).

The `[[img:N]]` token scheme (used in `question_text`) refers to the
`QuestionImage.id` returned by `upload_image_to_supabase`.
"""
from __future__ import annotations

import hashlib
import io
import logging
import os
from dataclasses import dataclass
from typing import BinaryIO

logger = logging.getLogger(__name__)

BUCKET_NAME = "crack-cms-question-images"
MAX_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_MIME = {"image/png", "image/jpeg", "image/webp", "image/gif"}


@dataclass
class UploadedImage:
    id: int
    url: str
    sha256: str
    sha256_short: str
    width: int
    height: int
    bytes: int
    mime: str


def _ensure_supabase_client():
    """Return a Supabase client or raise RuntimeError with a clear message."""
    from supabase import create_client  # imported lazily so the module loads even if supabase is missing locally

    url = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError(
            "Supabase storage not configured. Set SUPABASE_URL and "
            "SUPABASE_SERVICE_ROLE_KEY in backend/.env before uploading."
        )
    return create_client(url, key)


def upload_image_to_supabase(
    *,
    file_obj: BinaryIO,
    question_id: int,
    content_type: str,
    original_filename: str,
) -> UploadedImage:
    """Upload `file_obj` to Supabase Storage and create a `QuestionImage` row.

    The `QuestionImage` row is created with `uploaded_by_admin=True` and
    the file field unset (the canonical URL is the Supabase public URL).
    The function is idempotent on `sha256` per question: re-uploading
    the same bytes updates the existing row's `updated_at` and returns
    the same id.

    Raises:
        ValueError: wrong MIME or too large.
        RuntimeError: Supabase not configured or upload failed.
    """
    from questions.models import QuestionImage  # local import to avoid AppRegistryNotReady

    if content_type not in ALLOWED_MIME:
        raise ValueError(
            f"Unsupported MIME {content_type!r}. Allowed: {sorted(ALLOWED_MIME)}"
        )

    payload = file_obj.read()
    if len(payload) > MAX_BYTES:
        raise ValueError(
            f"File too large: {len(payload)} bytes (max {MAX_BYTES})"
        )

    sha256 = hashlib.sha256(payload).hexdigest()
    sha256_short = sha256[:16]

    width = height = 0
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(payload))
        width, height = img.size
    except Exception:  # noqa: BLE001 — PIL missing or bad image; dimensions are best-effort
        logger.warning("Could not extract dimensions for uploaded image")

    existing = QuestionImage.objects.filter(
        question_id=question_id, sha256_short=sha256_short
    ).first()
    if existing:
        logger.info("Re-using existing QuestionImage #%s (sha256 short=%s)", existing.id, sha256_short)
        # No mutable bookkeeping to update — the bytes, mime, and url are
        # byte-for-byte identical (sha256 dedup), so just return the row.
        return UploadedImage(
            id=existing.id,
            url=existing.url,
            sha256=existing.sha256,
            sha256_short=existing.sha256_short,
            width=existing.width or width,
            height=existing.height or height,
            bytes=existing.bytes or len(payload),
            mime=existing.mime or content_type,
        )

    client = _ensure_supabase_client()
    ext = (original_filename.split(".")[-1] or "png").lower()[:8]
    ext = "".join(ch for ch in ext if ch.isalnum()) or "png"
    key = f"question_images/{question_id}/{sha256_short}.{ext}"

    try:
        client.storage.from_(BUCKET_NAME).upload(
            path=key,
            file=payload,
            file_options={"content-type": content_type, "upsert": "true"},
        )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Supabase upload failed: {exc}") from exc

    public_url = client.storage.from_(BUCKET_NAME).get_public_url(key)

    row = QuestionImage.objects.create(
        question_id=question_id,
        page_number=0,
        image_index_in_page=0,
        file="",  # empty — URL is the canonical location
        mime=content_type,
        width=width,
        height=height,
        bytes=len(payload),
        sha256=sha256,
        sha256_short=sha256_short,
        modality="other",
        uploaded_by_admin=True,
        url=public_url,
    )
    logger.info("Uploaded QuestionImage #%s to %s", row.id, public_url)
    return UploadedImage(
        id=row.id,
        url=public_url,
        sha256=sha256,
        sha256_short=sha256_short,
        width=width,
        height=height,
        bytes=len(payload),
        mime=content_type,
    )
