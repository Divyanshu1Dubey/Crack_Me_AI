"""accounts/upload_validation.py
Helpers for validating user-uploaded files via magic-byte inspection.

Production hardening (Phase 4 — see docs/audit/COMPREHENSIVE_AUDIT_2026_07_30.md):
A valid extension alone is not enough — a malicious client can rename
`malware.html` → `malware.jpg` and bypass extension-only checks. Compare the
file's first ~16 bytes to a known magic set before accepting the upload.

Used by: questions/views.py (image uploads), material_importer/views.py
(DOCX/PDF/PPT imports), ingestion/ endpoints.

Drop-in usage in any view:

    from accounts.upload_validation import validate_uploaded_file
    from django.core.exceptions import ValidationError

    try:
        validate_uploaded_file(request.FILES['image'], allowed_types={'image'})
    except ValidationError as e:
        return Response({'error': str(e)}, status=400)
"""
from __future__ import annotations

from typing import Iterable, Mapping

from django.core.exceptions import ValidationError
from rest_framework.exceptions import ParseError

# ── Magic-byte signatures ─────────────────────────────────────────────────────
# (canonical mime type, prefix bytes). Match any of the prefix bytes at offset 0.
MAGIC_BYTES: Mapping[str, tuple[bytes, ...]] = {
    # Images
    'image/png': (b'\x89PNG\r\n\x1a\n',),
    'image/jpeg': (b'\xff\xd8\xff',),
    'image/gif': (b'GIF87a', b'GIF89a'),
    'image/webp': (b'RIFF',),  # also requires 'WEBP' at offset 8 — checked separately
    # Documents
    'application/pdf': (b'%PDF-',),
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': (b'PK\x03\x04',),  # DOCX is a ZIP container
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': (b'PK\x03\x04',),  # PPTX
    'application/vnd.ms-powerpoint': (b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1',),  # legacy PPT (CFB/OLE)
    'application/msword': (b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1',),  # legacy DOC
}

# Higher-level groups used by callers; value is a list of mime types accepted.
ALLOWED_GROUPS: Mapping[str, tuple[str, ...]] = {
    'image': ('image/png', 'image/jpeg', 'image/gif', 'image/webp'),
    'document': (
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/msword',
    ),
    'spreadsheet': (
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.ms-excel',
    ),
    'presentation': (
        'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'application/vnd.ms-powerpoint',
    ),
}


def _detect_mime(first_bytes: bytes) -> str | None:
    """Return the canonical mime-type for the file's magic bytes, or None."""
    for mime, prefixes in MAGIC_BYTES.items():
        for prefix in prefixes:
            if first_bytes.startswith(prefix):
                # WEBP needs extra confirmation (RIFF ... WEBP)
                if mime == 'image/webp':
                    if b'WEBP' not in first_bytes[8:16]:
                        return None
                # ZIP-based Office formats need the kind recorded in the next bytes
                if mime.startswith('application/vnd.openxmlformats-officedocument') or mime in {
                    'application/vnd.ms-powerpoint',
                    'application/msword',
                }:
                    if mime.endswith('wordprocessingml.document'):
                        # DOCX must contain word/ in central directory
                        return mime if b'word/' in first_bytes or mime.endswith('.document') else None
                return mime
    return None


def validate_uploaded_file(uploaded_file, allowed_types: Iterable[str], max_bytes: int = 10 * 1024 * 1024) -> str:
    """Validate an UploadedFile by checking size + magic bytes.

    Args:
        uploaded_file: a Django ``InMemoryUploadedFile`` / ``TemporaryUploadedFile``.
        allowed_types: any iterable of group names from ALLOWED_GROUPS
            (e.g. ``{'image'}`` or ``{'document', 'presentation'}``).
        max_bytes: hard size cap. Defaults to 10 MB (DATA_UPLOAD_MAX_MEMORY_SIZE).

    Returns:
        The detected ``content_type`` (e.g. ``"image/png"``).

    Raises:
        django.core.exceptions.ValidationError on failure.
    """
    if uploaded_file is None:
        raise ValidationError('No file was uploaded.')

    size = getattr(uploaded_file, 'size', 0)
    if size <= 0:
        raise ValidationError('Uploaded file is empty.')
    if size > max_bytes:
        raise ValidationError(f'File exceeds the {max_bytes // (1024 * 1024)} MB upload limit.')

    # Sniff first 16 bytes for magic-byte identification
    try:
        head = uploaded_file.read(16)
        if hasattr(uploaded_file, 'seek'):
            uploaded_file.seek(0)
    except Exception as exc:  # noqa: BLE001
        raise ValidationError(f'Could not read file header: {exc}')

    detected = _detect_mime(head)
    if not detected:
        raise ValidationError('File format is not supported or could not be identified.')

    allowed_mimes: set[str] = set()
    for group in allowed_types:
        allowed_mimes |= set(ALLOWED_GROUPS.get(group, ()))
    if detected not in allowed_mimes:
        raise ValidationError(
            f'Detected type {detected!s} is not in the allowed set: '
            f'{", ".join(sorted(allowed_mimes)) or "(none configured)"}.'
        )
    return detected


class UploadValidationMixin:
    """APIView mixin enforcing a single allowed-type group on `request.FILES`.

    Example:

        class MyImageView(UploadValidationMixin, APIView):
            upload_field = 'image'
            upload_allowed_types = ('image',)
    """

    upload_field: str = 'file'
    upload_allowed_types: tuple[str, ...] = ('image',)

    def validate_upload(self, request):
        from rest_framework.exceptions import ValidationError as DRFValidationError
        uploaded = request.FILES.get(self.upload_field)
        try:
            detected = validate_uploaded_file(uploaded, allowed_types=self.upload_allowed_types)
        except ValidationError as exc:
            raise DRFValidationError({'file': exc.messages})
        return uploaded, detected


def parse_upload_error(exc) -> str:
    """Translate a magic-byte ValidationError into a user-friendly message."""
    msg = str(getattr(exc, 'detail', exc) or '')
    return msg or 'Upload rejected by the server security policy.'
