"""Thin wrapper over PyMuPDF for safe, lazy PDF access.

All entry points degrade gracefully if PyMuPDF is missing — they raise
`PdfBackendUnavailable` so callers can fall back to other backends.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

try:
    import fitz  # type: ignore
    _HAS_FITZ = True
except Exception:  # pragma: no cover - import-time probe
    fitz = None  # type: ignore
    _HAS_FITZ = False


class PdfBackendUnavailable(RuntimeError):
    """Raised when PyMuPDF is not installed."""


@dataclass
class PageExtract:
    page_number: int   # 1-indexed
    text: str
    image_count: int
    image_xrefs: list[int]
    width: float
    height: float


def open_pdf(pdf_path: Path):
    if not _HAS_FITZ:
        raise PdfBackendUnavailable("PyMuPDF (fitz) is not installed")
    return fitz.open(str(pdf_path))


def page_count(doc) -> int:
    return doc.page_count


def metadata(doc) -> dict:
    return dict(doc.metadata or {})


def is_encrypted(doc) -> bool:
    try:
        return bool(doc.is_encrypted)
    except Exception:
        return True


def iter_pages(doc) -> Iterator[PageExtract]:
    for i, page in enumerate(doc, start=1):
        text = page.get_text("text") or ""
        images = page.get_images(full=True) or []
        xrefs = [img[0] for img in images]
        yield PageExtract(
            page_number=i,
            text=text,
            image_count=len(images),
            image_xrefs=xrefs,
            width=float(page.rect.width),
            height=float(page.rect.height),
        )


def render_page_png(doc, page_number: int, dpi: int = 200) -> Optional[bytes]:
    if not _HAS_FITZ:
        return None
    page = doc[page_number - 1]
    pix = page.get_pixmap(dpi=dpi)
    return pix.tobytes("png")


def extract_image_bytes(doc, xref: int) -> Optional[bytes]:
    if not _HAS_FITZ:
        return None
    try:
        return doc.extract_image(xref)
    except Exception:
        return None


__all__ = [
    "PdfBackendUnavailable",
    "PageExtract",
    "open_pdf",
    "page_count",
    "metadata",
    "is_encrypted",
    "iter_pages",
    "render_page_png",
    "extract_image_bytes",
]