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


def _decode_pua(text: str) -> str:
    """Decode Private-Use-Area characters emitted by a custom CMap font.

    MARROW-style recall PDFs embed an alphabet remapped onto the BMP
    PUA range (U+E000+) to defeat naive copy/paste; PyMuPDF faithfully
    returns those code points because they ARE valid Unicode, leaving
    the visible ASCII letters unrecoverable.

    Empirically (validated against MARROW ED8 subject PYQ PDFs):

    * U+E021 .. U+E03A -> "A" .. "Z"  (uppercase letters)
    * U+E041 .. U+E05A -> "a" .. "z"  (lowercase letters)
    * U+E010 .. U+E019 -> "0" .. "9"  (digits)
    * U+E008 .. U+E00B -> ".", ":", "(", ")" (option / question punctuation)

    All other PUA points are passed through unchanged so we can spot
    unrecognised ones in the log.  Non-PUA characters are untouched.
    """
    if not text:
        return text
    # Fast path: if no char in the PUA range, the string is fine as-is.
    if not any(0xE000 <= ord(c) <= 0xE0FF for c in text):
        return text
    out_chars = []
    for c in text:
        o = ord(c)
        # Digits U+E010 - U+E019
        if 0xE010 <= o <= 0xE019:
            out_chars.append(chr(ord('0') + (o - 0xE010)))
        # Uppercase A-Z
        elif 0xE021 <= o <= 0xE03A:
            out_chars.append(chr(ord('A') + (o - 0xE021)))
        # Lowercase a-z
        elif 0xE041 <= o <= 0xE05A:
            out_chars.append(chr(ord('a') + (o - 0xE041)))
        # Common punctuation U+E008-U+E00B
        elif 0xE008 <= o <= 0xE00B:
            _punc = {0xE008: '.', 0xE009: ',',
                     0xE00A: ':', 0xE00B: ';'}
            out_chars.append(_punc[o])
        else:
            out_chars.append(c)
    return "".join(out_chars)


def iter_pages(doc) -> Iterator[PageExtract]:
    """Yield a PageExtract per page.

    Text extraction happens in PyMuPDF; per-page pdfplumber fallback
    is applied by the runner (which has the path), not here.  Text is
    passed through ``_decode_pua`` so that MARROW-style PUA-encoded
    PDFs surface their underlying ASCII letters instead of garbage.
    """
    for i, page in enumerate(doc, start=1):
        text = page.get_text("text") or ""
        text = _decode_pua(text)
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
    PDF can't be opened.  Page text is decoded through ``_decode_pua``
    so PUA-encoded fonts are normalised to ASCII.
    """
    if not _HAS_PDFPLUMBER:
        return {}
    out: dict[int, str] = {}
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for idx, page in enumerate(pdf.pages, start=1):
                t = page.extract_text() or ""
                out[idx] = _decode_pua(t)
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
    "_decode_pua",
]