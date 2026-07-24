"""Stage 1 — Render every PDF page to PNG.

Inputs:
    <ctx.pdf_path>  : PDF on disk
    <ctx.artefact_root>/01_pdf_pages/

Outputs (per page):
    01_pdf_pages/p{NNN}.png          # the page render at the selected DPI
    01_pdf_pages/p{NNN}.dpi.json     # {dpi, width_px, height_px, render_reason}

Plus a stage-wide index:
    01_pdf_pages/_index.json         # {page_number → {png_path, dpi, ...}}

The DPI selector auto-decides per page:

    base_dpi  = 300                 # default; matches NEET-PG-2021 raster quality
    high_dpi  = 400                 # for image-heavy pages

Heuristic for bumping to high_dpi:

* `len(page.get_images(full=True)) >= HIGH_DPI_MIN_IMAGES` (default 4), OR
* the rendered-page area is dominated by raster (estimated by total
  embedded-image bytes / page-area).

The 2021 PDF profile (from Phase 0 audit) has 4-6 embedded images per
page; almost every page will trip the high_dpi rule — which is
deliberate. Quality wins.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import fitz  # type: ignore  # PyMuPDF

from mce.stages import MceContext, StageResult


LOG = logging.getLogger("mce.stage_1_render")


# ----------------------------------------------------------------- config

BASE_DPI = 300
HIGH_DPI = 400
HIGH_DPI_MIN_IMAGES = 4


# ----------------------------------------------------------------- DPI selector


def select_dpi(page: fitz.Page) -> tuple[int, str]:
    """Return (dpi, reason) for a given PDF page.

    The rule:
    * If the page carries >= HIGH_DPI_MIN_IMAGES embedded images, bump
      to HIGH_DPI (radiology / histology / ECG / clinical photos all
      come as multiple embedded images per page in NEET-PG-2021).
    * Else stay at BASE_DPI.
    """
    images = page.get_images(full=True) or []
    if len(images) >= HIGH_DPI_MIN_IMAGES:
        return HIGH_DPI, f"image_count={len(images)}>={HIGH_DPI_MIN_IMAGES}"
    return BASE_DPI, f"image_count={len(images)}<{HIGH_DPI_MIN_IMAGES}"


# ----------------------------------------------------------------- render


def _render_page(page: fitz.Page, dpi: int) -> bytes:
    """Render one PyMuPDF page to PNG bytes at the given DPI.

    `alpha=False` keeps the image as 24-bit RGB, which is what every
    downstream stage (Tesseract, OpenCV preprocessing, debug overlay)
    expects. `clip=None` means full page.
    """
    pix = page.get_pixmap(dpi=dpi, alpha=False)
    return pix.tobytes("png")


def _page_dims_px(page: fitz.Page, dpi: int) -> tuple[int, int]:
    """Return (width_px, height_px) for a page rendered at the given DPI."""
    w_pt, h_pt = page.rect.width, page.rect.height
    scale = dpi / 72.0
    return int(round(w_pt * scale)), int(round(h_pt * scale))


# ----------------------------------------------------------------- main entry


def run(ctx: MceContext, *, pages: Optional[list[int]] = None,
        force: bool = False) -> StageResult:
    """Render the PDF (or a subset of pages) and write the index.

    Idempotent: re-running on a page whose PNG already exists + DPI
    unchanged skips it unless `force=True`.
    """
    res = StageResult(stage="stage_1_render")
    out_dir: Path = ctx.stage_dir("01_pdf_pages")
    index_path = out_dir / "_index.json"

    # Load previous index if present (incremental / resume support).
    prev_index: dict[str, dict] = {}
    if index_path.exists() and not force:
        try:
            prev_index = json.loads(index_path.read_text(encoding="utf-8"))
        except Exception:  # pragma: no cover
            prev_index = {}

    try:
        doc = fitz.open(str(ctx.pdf_path))
    except Exception as e:  # pragma: no cover
        res.errors.append(f"fitz.open failed: {e}")
        return res

    try:
        index: dict[str, dict] = dict(prev_index)
        pages_iter = (
            [(p - 1, p) for p in pages]
            if pages
            else [(i, i + 1) for i in range(ctx.page_count)]
        )
        for page_idx, page_number in pages_iter:
            page = doc[page_idx]
            dpi, reason = select_dpi(page)
            w_px, h_px = _page_dims_px(page, dpi)
            png_path = out_dir / f"p{page_number:03d}.png"
            meta_path = out_dir / f"p{page_number:03d}.dpi.json"

            existing = prev_index.get(str(page_number))
            if (
                not force
                and existing
                and existing.get("dpi") == dpi
                and existing.get("png_path") == str(png_path)
                and png_path.exists()
            ):
                res.pages_skipped += 1
                index[str(page_number)] = existing
                continue

            try:
                png_bytes = _render_page(page, dpi)
                png_path.write_bytes(png_bytes)
            except Exception as e:  # pragma: no cover
                res.errors.append(f"p{page_number}: render failed: {e}")
                continue

            meta = {
                "page_number": page_number,
                "dpi": dpi,
                "width_px": w_px,
                "height_px": h_px,
                "width_pt": float(page.rect.width),
                "height_pt": float(page.rect.height),
                "render_reason": reason,
                "embedded_image_count": len(page.get_images(full=True) or []),
                "png_path": str(png_path),
                "png_bytes": png_path.stat().st_size,
                "pdf_filename": ctx.pdf_filename,
                "pdf_sha256_short": ctx.pdf_sha256_short,
            }
            meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
            index[str(page_number)] = meta
            res.artefacts_written += 1
            res.pages_processed += 1

        index_path.write_text(
            json.dumps(index, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # Aggregate metrics.
        dpis = [m["dpi"] for m in index.values()]
        sizes = [m["png_bytes"] for m in index.values()]
        res.metrics = {
            "total_pages_rendered": len(index),
            "pages_at_base_dpi": sum(1 for d in dpis if d == BASE_DPI),
            "pages_at_high_dpi": sum(1 for d in dpis if d == HIGH_DPI),
            "total_png_bytes": sum(sizes),
            "avg_png_bytes": (sum(sizes) // max(1, len(sizes))),
            "base_dpi": BASE_DPI,
            "high_dpi": HIGH_DPI,
        }
        LOG.info(
            "stage_1_render: %d pages, %d base / %d high dpi, %.1f MB total",
            res.metrics["total_pages_rendered"],
            res.metrics["pages_at_base_dpi"],
            res.metrics["pages_at_high_dpi"],
            res.metrics["total_png_bytes"] / (1024 * 1024),
        )
    finally:
        doc.close()

    return res


__all__ = ["run", "select_dpi", "BASE_DPI", "HIGH_DPI"]
