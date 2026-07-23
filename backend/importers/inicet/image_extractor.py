"""Image extraction — embedded + rendered, with hash + OCR + caption placeholder.

This module does NOT import imagehash at import time (it's an optional
dep). It tries lazily and falls back to sha256-only when imagehash is
missing.
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Iterable, Optional

from . import pdf_reader, ocr_engine
from .models import ImageRecord

LOG = logging.getLogger(__name__)

try:
    import imagehash  # type: ignore
    from PIL import Image  # type: ignore
    _HAS_IMAGEHASH = True
except Exception:  # pragma: no cover
    imagehash = None  # type: ignore
    Image = None  # type: ignore
    _HAS_IMAGEHASH = False


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _phash_dhash(pil_image) -> tuple[str, str]:
    if not _HAS_IMAGEHASH:
        return "", ""
    return (
        str(imagehash.phash(pil_image)),
        str(imagehash.dhash(pil_image)),
    )


def _ext_from_mime(mime: str) -> str:
    return {
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/png": "png",
        "image/tiff": "tiff",
        "image/bmp": "bmp",
    }.get(mime.lower(), "png")


def extract_embedded(
    doc,
    page_number: int,
    image_xrefs: Iterable[int],
    out_dir: Path,
    source_sha16: str,
    ocr_lang: str = "eng",
) -> list[ImageRecord]:
    """Save every embedded image on a page to disk; return ImageRecord list."""
    records: list[ImageRecord] = []
    out_dir.mkdir(parents=True, exist_ok=True)

    for idx, xref in enumerate(image_xrefs):
        try:
            info = pdf_reader.extract_image_bytes(doc, xref)
        except Exception as e:  # pragma: no cover
            LOG.warning("extract_image failed for xref=%s: %s", xref, e)
            continue
        if not info:
            continue
        # fitz.extract_image returns a dict with ext, image, ...
        ext = info.get("ext") or "png"
        data = info.get("image") or b""
        width = int(info.get("width") or 0)
        height = int(info.get("height") or 0)

        fname = f"p{page_number:04d}_i{idx:02d}.{ext}"
        path = out_dir / fname
        path.write_bytes(data)

        sha = _sha256_bytes(data)
        phash = dhash = ""
        ocr_text = ""
        ocr_conf = 0.0
        if _HAS_IMAGEHASH:
            try:
                with Image.open(path) as im:
                    phash, dhash = _phash_dhash(im)
                ocr_text, ocr_conf = ocr_engine.ocr_image(path, lang=ocr_lang)
            except Exception as e:  # pragma: no cover
                LOG.debug("imagehash/ocr failed for %s: %s", path, e)

        records.append(
            ImageRecord(
                source_sha16=source_sha16,
                page_number=page_number,
                image_index_in_page=idx,
                file_path=str(path),
                mime=f"image/{ext}" if ext != "jpg" else "image/jpeg",
                width=width,
                height=height,
                bytes=len(data),
                sha256=sha,
                sha256_short=sha[:16],
                phash=phash,
                dhash=dhash,
                ocr_text=ocr_text,
                ocr_confidence=ocr_conf,
                extraction_confidence=0.7 if phash else 0.4,
            )
        )

    return records


def render_page(
    doc,
    page_number: int,
    out_dir: Path,
    source_sha16: str,
    dpi: int = 200,
    ocr_lang: str = "eng",
) -> Optional[ImageRecord]:
    """Render a page to PNG and return it as a single image record.

    Used when a question's stem references an image but no embedded figure
    is present on the page (common with scanned PDFs that lost their
    image layers).
    """
    png = pdf_reader.render_page_png(doc, page_number, dpi=dpi)
    if not png:
        return None

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"p{page_number:04d}.png"
    path.write_bytes(png)

    sha = _sha256_bytes(png)
    phash = dhash = ""
    ocr_text = ""
    ocr_conf = 0.0
    if _HAS_IMAGEHASH:
        try:
            with Image.open(path) as im:
                phash, dhash = _phash_dhash(im)
            ocr_text, ocr_conf = ocr_engine.ocr_image(path, lang=ocr_lang)
        except Exception as e:  # pragma: no cover
            LOG.debug("render_page postprocess failed for %s: %s", path, e)

    return ImageRecord(
        source_sha16=source_sha16,
        page_number=page_number,
        image_index_in_page=0,
        file_path=str(path),
        mime="image/png",
        width=0,  # filled by caller if needed
        height=0,
        bytes=len(png),
        sha256=sha,
        sha256_short=sha[:16],
        phash=phash,
        dhash=dhash,
        ocr_text=ocr_text,
        ocr_confidence=ocr_conf,
        extraction_confidence=0.5,
        modality="unknown",
    )


__all__ = ["extract_embedded", "render_page"]