"""Page images for admins: a question's own recall-PDF page (the page it was imported from, with its
printed key). Reference-store pages render through ``reference_corpus.api.render_page_png``.

Admin-only callers; the PDF path comes from ``RecallSource.pdf_path`` (written by the importer)
and is never returned in a payload.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

MIN_DPI = 50
MAX_DPI = 200


def clamp_dpi(value, default: int = 110) -> int:
    try:
        dpi = int(value)
    except (TypeError, ValueError):
        return default
    return max(MIN_DPI, min(dpi, MAX_DPI))


def render_pdf_page(path: str, page_no: int, dpi: int = 110) -> Optional[bytes]:
    """PNG of 1-based page ``page_no`` of the PDF at ``path``, or None (missing file, not a PDF,
    page out of range, PyMuPDF unavailable)."""
    if not path or not str(path).lower().endswith('.pdf') or not os.path.isfile(path):
        return None
    try:
        import fitz  # PyMuPDF
    except ImportError:  # pragma: no cover - listed in requirements.txt
        return None
    try:
        with fitz.open(path) as doc:
            if page_no < 1 or page_no > doc.page_count:
                return None
            scale = clamp_dpi(dpi) / 72.0
            pixmap = doc.load_page(page_no - 1).get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            return pixmap.tobytes('png')
    except Exception as exc:  # noqa: BLE001 - a broken PDF renders nothing
        logger.warning('evidence: recall page render failed (%s)', type(exc).__name__)
        return None
