"""Thin wrapper over PyMuPDF for safe, lazy PDF access.

All entry points degrade gracefully if PyMuPDF is missing — they raise
`PdfBackendUnavailable` so callers can fall back to other backends.

A pdfplumber-based text-extraction helper is exposed as
`extract_text_via_pdfplumber()` for scanned PDFs where PyMuPDF's
text layer is empty (some scanned-but-OCR'd PDFs store the recognised
text in a way that pdfplumber can recover but PyMuPDF cannot).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

try:
    import fitz  # type: ignore
    _HAS_FITZ = True
except Exception:  # pragma: no cover - import-time probe
    fitz = None  # type: ignore
    _HAS_FITZ = False

try:
    import pdfplumber  # type: ignore
    _HAS_PDFPLUMBER = True
except Exception:  # pragma: no cover
    pdfplumber = None  # type: ignore
    _HAS_PDFPLUMBER = False


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
    """Yield a PageExtract per page.

    Text extraction happens in PyMuPDF; per-page pdfplumber fallback
    is applied by the runner (which has the path), not here.
    """
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


def extract_text_via_pdfplumber_pages(pdf_path: Path) -> dict[int, str]:
    """Open `pdf_path` with pdfplumber and return {1-indexed_page: text}.

    Used as a fallback when PyMuPDF's text layer is empty (some scanned
    PDFs). Returns an empty dict when pdfplumber is unavailable or the
    PDF can't be opened.
    """
    if not _HAS_PDFPLUMBER:
        return {}
    out: dict[int, str] = {}
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for idx, page in enumerate(pdf.pages, start=1):
                t = page.extract_text() or ""
                out[idx] = t
    except Exception:
        return {}
    return out


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
    "extract_text_via_pdfplumber_pages",
    "render_page_png",
    "extract_image_bytes",
]