"""Stage 3 — Image extraction.

Highest-priority stage. Extracts every embedded image at native
resolution, plus render-region crops for vector content, with full
provenance + per-image modality hints.

Per-page outputs (under `03_images/`):

    p{NNN}_img{kk}.{png|jpg}      # the saved image bytes
    p{NNN}.json                   # per-page image index with bbox + meta

Plus a stage-wide `_index.json` aggregating every image for the whole
PDF. Stage 5 (question blocks) reads this index to map images to
questions via bbox intersection.

Per-image bbox strategy
=======================

PyMuPDF gives each embedded image an `xref`. For every xref we
materialise a per-page bbox by collecting every placement rect across
the page (an image xref can appear multiple times on a page in a
clipped/masked pattern). We union those rects into a single page-level
bbox for that image instance.

For images that aren't separately embedded (vector graphics, charts,
charts drawn directly with PDF drawing commands), we don't have an
xref — Stage 2's layout engine flags those regions as `image` and we
re-crop them from the high-res page render in `extract_render_region`.
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
from pathlib import Path
from typing import Any, Optional

import fitz  # type: ignore  # PyMuPDF
from PIL import Image

from mce.stages import MceContext, StageResult
from mce.types import SourceTrace


LOG = logging.getLogger("mce.stage_3_images")


# ----------------------------------------------------------------- helpers


def _rects_union(rects: list[tuple[float, ...]]) -> tuple[float, ...]:
    """Union of (x0,y0,x1,y1) rects in PDF-point space."""
    if not rects:
        return (0.0, 0.0, 0.0, 0.0)
    x0 = min(r[0] for r in rects)
    y0 = min(r[1] for r in rects)
    x1 = max(r[2] for r in rects)
    y1 = max(r[3] for r in rects)
    return (x0, y0, x1, y1)


def _rotate_image_if_needed(raw_bytes: bytes, mime: str) -> tuple[bytes, int, int, int]:
    """Return (rotated_bytes, rotation_degrees, width, height).

    Some PDF images are stored with a CTM rotation that PyMuPDF's
    `extract_image` does not apply. We inspect the EXIF orientation
    hint when available; otherwise we leave the orientation as-is and
    rely on the bbox rotation metadata in the index.
    """
    try:
        with Image.open(io.BytesIO(raw_bytes)) as im:
            width, height = im.size
            # EXIF orientation only applies to JPEG with EXIF block.
            exif_rotation = 0
            try:
                exif = im.getexif()
                if exif:
                    orientation = exif.get(0x0112)  # Orientation tag
                    mapping = {3: 180, 6: 270, 8: 90}
                    exif_rotation = mapping.get(int(orientation or 0), 0)
            except Exception:
                exif_rotation = 0
            if exif_rotation == 0:
                return raw_bytes, 0, width, height
            im2 = im.rotate(-exif_rotation, expand=True)
            buf = io.BytesIO()
            ext = "JPEG" if mime.endswith("jpeg") or mime.endswith("jpg") else "PNG"
            im2.save(buf, format=ext, quality=95)
            return buf.getvalue(), exif_rotation, im2.size[0], im2.size[1]
    except Exception:
        # Best effort: return original bytes + zero rotation.
        try:
            with Image.open(io.BytesIO(raw_bytes)) as im:
                return raw_bytes, 0, im.size[0], im.size[1]
        except Exception:
            return raw_bytes, 0, 0, 0


def _guess_modality_from_pixels(img_bytes: bytes, mime: str) -> tuple[str, str]:  # noqa: ARG001 - mime reserved for future colour/grayscale hint
    """Very lightweight pixel-based modality guess.

    Returns (modality, modality_subtype). Used only as a hint that the
    caption engine can later refine.
    """
    try:
        with Image.open(io.BytesIO(img_bytes)) as im:
            im = im.convert("RGB")
            w, h = im.size
            if w < 32 or h < 32:
                return "other", ""
            # Mean luminance + saturation give a cheap signal.
            small = im.resize((min(w, 96), min(h, 96)))
            pixels = list(small.getdata())
            n = len(pixels)
            r_sum = sum(p[0] for p in pixels) / n
            g_sum = sum(p[1] for p in pixels) / n
            b_sum = sum(p[2] for p in pixels) / n
            mn, mx = min(min(p) for p in pixels), max(max(p) for p in pixels)
            is_grayscale = (mx - mn) < 24 and abs(r_sum - g_sum) < 8 and abs(g_sum - b_sum) < 8
            # Aspect ratio hints
            aspect = w / max(1, h)
            if aspect > 2.2 or aspect < 0.45:
                # Wide / tall strip — likely ECG rhythm strip or electrophoresis gel.
                if aspect > 2.2:
                    return "ecg", "rhythm_strip"
                return "other", ""
            if is_grayscale:
                # Grayscale = radiograph / CT / MRI / ultrasound / histopath / fundus
                if r_sum < 60:
                    return "radiograph", "high_contrast"
                if r_sum > 180:
                    return "radiograph", "low_contrast"
                return "ct", ""
            # Colour — clinical photo, gross specimen, dermatology, embryology
            if g_sum > r_sum and g_sum > b_sum:
                return "clinical_photo", ""
            if r_sum > g_sum and r_sum > b_sum:
                return "pathology_gross", ""
            return "clinical_photo", ""
    except Exception:
        return "other", ""


# ----------------------------------------------------------------- per-page extraction


def _pixel_scan_bbox(
    page_png_path: Path,
    page_width_pt: float,
    page_height_pt: float,
    image_index: int,
) -> tuple[float, ...] | None:
    """When PyMuPDF can't give us an image's placement rect, scan the
    high-res page render for the most likely bbox.

    Algorithm:
      1. Convert PNG to grayscale numpy array.
      2. Find columns that contain non-white pixels in the right 70 %
         of the page (where NEET-PG images usually live) AND have a
         high pixel-density gradient (edges / dense content).
      3. Identify contiguous non-white horizontal bands.
      4. Pick the band whose vertical position corresponds to the
         image_index's ordinal position on the page.

    This is intentionally heuristic — the goal is to put a *plausible*
    bbox on the page for the image so the frontend can render it in
    context, not to recover ground-truth placement (which is lost).

    Returns (x0_pt, y0_pt, x1_pt, y1_pt) in PDF-point space, or None.
    """
    try:
        import numpy as np  # type: ignore
        from PIL import Image  # type: ignore
    except Exception:
        return None
    if not page_png_path.exists():
        return None
    try:
        with Image.open(str(page_png_path)) as im:
            arr = np.array(im.convert("L"))
    except Exception:
        return None
    h_px, w_px = arr.shape
    # Threshold: any pixel < 240 considered "ink".
    mask = arr < 240

    # Focus on the right half of the page (where images live).
    x_start = int(w_px * 0.5)
    right_mask = mask[:, x_start:]
    # Column density in the right half.
    col_density = right_mask.mean(axis=0)
    # Find columns with density > 1 % (ink present).
    has_ink = col_density > 0.01
    if not has_ink.any():
        return None
    # Find contiguous ink bands.
    bands: list[tuple[int, int]] = []
    in_band = False
    start = 0
    for i, v in enumerate(has_ink):
        if v and not in_band:
            in_band = True
            start = i
        elif not v and in_band:
            in_band = False
            if i - start > 20:  # ignore tiny slivers
                bands.append((start + x_start, i + x_start))
    if in_band:
        bands.append((start + x_start, w_px))

    if not bands:
        return None

    # Pick the band at ordinal position `image_index` (clamped).
    band = bands[min(image_index, len(bands) - 1)]

    # Find the vertical extent of the ink inside this band.
    col_lo, col_hi = band
    band_mask = mask[:, col_lo:col_hi]
    row_density = band_mask.mean(axis=1)
    has_row = row_density > 0.005
    rows = np.where(has_row)[0]
    if rows.size == 0:
        return None
    y0_px, y1_px = int(rows.min()), int(rows.max())

    # Convert pixel bbox back to PDF points.
    scale_x = page_width_pt / w_px
    scale_y = page_height_pt / h_px
    return (
        float(col_lo * scale_x),
        float(y0_px * scale_y),
        float(col_hi * scale_x),
        float(y1_px * scale_y),
    )


def _template_match_bbox(
    page_png_path: Path,
    page_width_pt: float,
    page_height_pt: float,
    image_bytes: bytes,
    image_w: int,
    image_h: int,
) -> tuple[float, ...] | None:
    """Find the actual on-page bbox of an extracted image by template
    matching against the rendered page.

    The image extracted from the PDF is often at its native sample
    resolution while the page is rendered at 400 DPI.  Try several
    scales of the template against the page and pick the highest
    correlation peak.  Returns None when cv2 is unavailable or no
    peak crosses the threshold.

    Returns (x0_pt, y0_pt, x1_pt, y1_pt) in PDF-point space.
    """
    try:
        import numpy as np  # type: ignore
        import cv2  # type: ignore
        from PIL import Image  # type: ignore
    except Exception:
        return None
    if not page_png_path.exists() or image_w <= 0 or image_h <= 0:
        return None

    try:
        page_arr = np.array(Image.open(str(page_png_path)).convert("L"))
        template_pil = Image.open(io.BytesIO(image_bytes))
        template_arr = np.array(template_pil.convert("L"))
    except Exception:
        return None

    h_page, w_page = page_arr.shape
    h_t, w_t = template_arr.shape
    if h_t > h_page or w_t > w_page:
        return None

    # Coarse downsample the page once (search space stays fixed).
    scale = 0.25
    page_s = cv2.resize(page_arr, (max(w_page // 4, 1), max(h_page // 4, 1)),
                        interpolation=cv2.INTER_AREA)
    h_p_s, w_p_s = page_s.shape

    best = None   # (max_val, x0_px, y0_px, w_t_scaled, h_t_scaled)
    # Try 8 plausible render-side scales (page render is typically larger
    # than the source JPEG/PNG because the source image was downsampled
    # during PDF authoring).  Try both CCOEFF_NORMED (good for distinct
    # structural content) and CCORR_NORMED (good for photographic content
    # where luminance distribution is the signal).
    for factor in (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0):
        nt_w = int(w_t * factor * scale)
        nt_h = int(h_t * factor * scale)
        if nt_w < 6 or nt_h < 6 or nt_w >= w_p_s or nt_h >= h_p_s:
            continue
        tmpl_s = cv2.resize(template_arr, (nt_w, nt_h), interpolation=cv2.INTER_AREA)
        for tm in (cv2.TM_CCOEFF_NORMED, cv2.TM_CCORR_NORMED):
            try:
                result = cv2.matchTemplate(page_s, tmpl_s, tm)
            except Exception:
                continue
            _, mx, _, mloc = cv2.minMaxLoc(result)
            if best is None or mx > best[0]:
                best = (mx, mloc[0], mloc[1], nt_w, nt_h)

    if best is None or best[0] < 0.45:
        return None

    # Convert coarse-match location back to full-resolution pixel space.
    x0_px = int(best[1] / scale)
    y0_px = int(best[2] / scale)
    # Derive the bbox in full-resolution from the matched-template size.
    nt_w, nt_h = best[3], best[4]
    # The template was resized by (factor * scale); scale it back to full.
    full_w = int(nt_w / scale)
    full_h = int(nt_h / scale)
    # Clamp.
    if x0_px < 0 or y0_px < 0 or x0_px + full_w > w_page or y0_px + full_h > h_page:
        return None

    scale_x = page_width_pt / w_page
    scale_y = page_height_pt / h_page
    return (
        float(x0_px * scale_x),
        float(y0_px * scale_y),
        float((x0_px + full_w) * scale_x),
        float((y0_px + full_h) * scale_y),
    )


def _extract_page_embedded(
    doc: fitz.Document,
    page_number: int,
    page_png_path: Path,
    page_width_pt: float,
    page_height_pt: float,
    out_dir: Path,
    pdf_filename: str,
    pdf_sha256: str,
    pdf_sha256_short: str,
) -> list[dict[str, Any]]:
    """Extract every embedded image on one page.

    The 2021 PDF mixes:
      * regular XObject images (rect discoverable via `get_image_rects`)
      * inline images (`BI ... EI`) — rect NOT discoverable via the rect API
      * form XObjects / masked placements — sometimes only via `get_image_bbox`

    Strategy:
      1. Try `get_image_rects(xref)` -> list of placement rects.
      2. Fall back to `get_image_bbox(xref)` -> single rect.
      3. Fall back to looking up the image block in `get_text("dict")`
         type-1 blocks.
      4. If all three return nothing, the rect is left as (0,0,0,0) and
         `extraction_confidence` is downgraded to 0.5 so Stage 5 / Stage 8
         can flag it for review.
    """
    page = doc[page_number - 1]

    # Build image-block lookup from get_text('dict') type=1 entries (real image blocks).
    img_blocks: list[tuple[float, ...]] = []
    try:
        for b in page.get_text("dict").get("blocks", []):
            if b.get("type") == 1 and b.get("bbox"):
                img_blocks.append(tuple(float(v) for v in b["bbox"]))
    except Exception:
        img_blocks = []

    page_imgs: list[dict[str, Any]] = []
    seen_xrefs: set[int] = set()

    for idx, img_info in enumerate(page.get_images(full=True) or []):
        xref = int(img_info[0])
        if xref in seen_xrefs:
            # De-dupe identical xrefs on the same page (PDF can list the
            # same image twice in the resource table).
            continue
        seen_xrefs.add(xref)

        # --- 0. Extract the image bytes first so the placement
        # resolver (template-match fallback) can use them.
        try:
            extracted = doc.extract_image(xref)
        except Exception as e:
            LOG.warning("extract_image failed for xref=%s on p%s: %s", xref, page_number, e)
            continue
        if not extracted:
            continue
        ext = extracted.get("ext") or "png"
        raw = extracted.get("image") or b""
        mime = f"image/{ext}" if ext != "jpg" else "image/jpeg"
        rotated, rotation_deg, w_px, h_px = _rotate_image_if_needed(raw, mime)

        # --- 1. Determine placement rect via fallback paths.
        bbox: tuple[float, ...] = (0.0, 0.0, 0.0, 0.0)
        placement_method = "none"
        try:
            rects = page.get_image_rects(xref) or []
        except Exception:
            rects = []
        if rects:
            bbox = _rects_union([tuple(float(v) for v in r) for r in rects])
            placement_method = "get_image_rects"
        else:
            try:
                bb = page.get_image_bbox(xref)
                if bb is not None and bb.is_valid and (bb.width > 0 or bb.height > 0):
                    bbox = (float(bb.x0), float(bb.y0), float(bb.x1), float(bb.y1))
                    placement_method = "get_image_bbox"
            except Exception:
                pass
            if bbox == (0.0, 0.0, 0.0, 0.0) and img_blocks and idx < len(img_blocks):
                # 3. last resort — pair the xref with the next-available
                # image block by ordinal position. Confidence is low.
                bbox = img_blocks[idx]
                placement_method = "image_block_ordinal"
            if bbox == (0.0, 0.0, 0.0, 0.0):
                # 4. Try template-matching first (high confidence): search
                # the rendered page for the extracted image bytes via
                # normalized cross-correlation.  Falls back to the
                # ordinal pixel-scan heuristic when cv2 is unavailable
                # or the match score is too low.
                tm_bbox = _template_match_bbox(
                    page_png_path, page_width_pt, page_height_pt,
                    rotated, w_px, h_px,
                )
                if tm_bbox is not None:
                    bbox = tm_bbox
                    placement_method = "template_match"
                else:
                    scanned = _pixel_scan_bbox(
                        page_png_path, page_width_pt, page_height_pt, idx,
                    )
                    if scanned is not None:
                        bbox = scanned
                        placement_method = "pixel_scan"

        sha = hashlib.sha256(rotated).hexdigest()
        sha16 = sha[:16]
        file_name = f"p{page_number:03d}_img{idx:02d}.{ext}"
        file_path = out_dir / file_name
        file_path.write_bytes(rotated)

        modality, modality_subtype = _guess_modality_from_pixels(rotated, mime)
        # Extraction confidence drops if we couldn't resolve placement.
        if placement_method == "get_image_rects":
            extraction_confidence = 1.0
        elif placement_method == "get_image_bbox":
            extraction_confidence = 0.95
        elif placement_method == "template_match":
            extraction_confidence = 0.9
        elif placement_method == "image_block_ordinal":
            extraction_confidence = 0.6
        elif placement_method == "pixel_scan":
            extraction_confidence = 0.5
        else:
            extraction_confidence = 0.4  # image without any placement info

        trace = SourceTrace.make(
            pdf_filename=pdf_filename, pdf_sha256=pdf_sha256,
            pdf_sha256_short=pdf_sha256_short, page_number=page_number,
            bbox=bbox, extraction_engine=f"pymupdf_extract_image:{placement_method}",
            pipeline_stage="stage_3_images",
            confidence=extraction_confidence,
        )
        img_id = f"p{page_number:03d}_img{idx:02d}_{sha16}"
        rec = {
            "id": img_id,
            "source_sha16": pdf_sha256_short,
            "page_number": page_number,
            "image_index_in_page": idx,
            "xref": int(xref),
            "file_path": str(file_path),
            "mime": mime,
            "width": w_px,
            "height": h_px,
            "bytes": len(rotated),
            "sha256": sha,
            "sha256_short": sha16,
            "bbox": list(bbox),
            "page_spans": [(page_number, list(bbox))],
            "rotation_deg": int(rotation_deg),
            "role": "other",
            "modality": modality,
            "modality_subtype": modality_subtype,
            "placement_method": placement_method,
            "caption": "",
            "caption_source": "none",
            "ocr_text": "",
            "ocr_confidence": 0.0,
            "extraction_confidence": extraction_confidence,
            "source_trace": trace.to_dict(),
        }
        page_imgs.append(rec)
    return page_imgs


def _extract_render_region(
    doc: fitz.Document,
    page_number: int,
    bbox: tuple[float, ...],
    out_dir: Path,
    pdf_filename: str,
    pdf_sha256: str,
    pdf_sha256_short: str,
    existing_xref_count: int,
    dpi: int = 400,
) -> dict[str, Any] | None:
    """Render a region of the page (bbox in PDF points) to PNG. Used when
    an image on the page is not a separately-embedded xref but is drawn
    by vector primitives.
    """
    page = doc[page_number - 1]
    try:
        clip = fitz.Rect(*bbox)
        pix = page.get_pixmap(dpi=dpi, alpha=False, clip=clip)
    except Exception as e:
        LOG.warning("render-region failed for p%s bbox=%s: %s", page_number, bbox, e)
        return None
    raw = pix.tobytes("png")
    sha = hashlib.sha256(raw).hexdigest()
    sha16 = sha[:16]
    idx = existing_xref_count
    file_name = f"p{page_number:03d}_img{idx:02d}_render.png"
    file_path = out_dir / file_name
    file_path.write_bytes(raw)
    modality, modality_subtype = _guess_modality_from_pixels(raw, "image/png")
    trace = SourceTrace.make(
        pdf_filename=pdf_filename, pdf_sha256=pdf_sha256,
        pdf_sha256_short=pdf_sha256_short, page_number=page_number,
        bbox=bbox, extraction_engine="pymupdf_render_region",
        pipeline_stage="stage_3_images",
        confidence=0.85,           # render crops are slightly less certain than native embeds
    )
    img_id = f"p{page_number:03d}_img{idx:02d}_render_{sha16}"
    return {
        "id": img_id,
        "source_sha16": pdf_sha256_short,
        "page_number": page_number,
        "image_index_in_page": idx,
        "xref": -1,                # -1 marks a render-region crop
        "file_path": str(file_path),
        "mime": "image/png",
        "width": pix.width,
        "height": pix.height,
        "bytes": len(raw),
        "sha256": sha,
        "sha256_short": sha16,
        "bbox": list(bbox),
        "page_spans": [(page_number, list(bbox))],
        "rotation_deg": 0,
        "role": "other",
        "modality": modality,
        "modality_subtype": modality_subtype,
        "caption": "",
        "caption_source": "none",
        "ocr_text": "",
        "ocr_confidence": 0.0,
        "extraction_confidence": 0.85,
        "source_trace": trace.to_dict(),
    }


# ----------------------------------------------------------------- main entry


def run(ctx: MceContext, *, pages: Optional[list[int]] = None,
        force: bool = False) -> StageResult:
    res = StageResult(stage="stage_3_images")
    out_dir: Path = ctx.stage_dir("03_images")
    pages_render_dir: Path = ctx.stage_dir("01_pdf_pages")
    index_path = out_dir / "_index.json"

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
        all_images: list[dict[str, Any]] = list(prev_index.get("images", []))
        # Track which pages we've already processed in this index.
        done_pages = {int(im["page_number"]) for im in all_images}

        page_iter = (
            [(p - 1, p) for p in pages]
            if pages
            else [(i, i + 1) for i in range(ctx.page_count)]
        )
        for page_idx, page_number in page_iter:
            if not force and page_number in done_pages:
                res.pages_skipped += 1
                continue
            page = doc[page_idx]
            try:
                page_png = pages_render_dir / f"p{page_number:03d}.png"
                page_imgs = _extract_page_embedded(
                    doc, page_number,
                    page_png,
                    float(page.rect.width), float(page.rect.height),
                    out_dir,
                    ctx.pdf_filename, ctx.pdf_sha256, ctx.pdf_sha256_short,
                )
            except Exception as e:  # pragma: no cover
                res.errors.append(f"p{page_number}: extract failed: {e}")
                continue

            page_payload = {
                "page_number": page_number,
                "image_count": len(page_imgs),
                "images": page_imgs,
            }
            page_json = out_dir / f"p{page_number:03d}.json"
            page_json.write_text(
                json.dumps(page_payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            # Replace any existing page entries in `all_images` (force-rerun).
            all_images = [im for im in all_images if int(im["page_number"]) != page_number]
            all_images.extend(page_imgs)

            res.artefacts_written += len(page_imgs) + 1
            res.pages_processed += 1

        # Re-sort by (page_number, image_index_in_page) for stable iteration.
        all_images.sort(key=lambda im: (int(im["page_number"]), int(im["image_index_in_page"])))
        out_index = {
            "pdf_filename": ctx.pdf_filename,
            "pdf_sha256_short": ctx.pdf_sha256_short,
            "image_count": len(all_images),
            "images": all_images,
        }
        index_path.write_text(
            json.dumps(out_index, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # Metrics.
        per_page_counts: dict[int, int] = {}
        modalities: dict[str, int] = {}
        for im in all_images:
            per_page_counts[int(im["page_number"])] = per_page_counts.get(int(im["page_number"]), 0) + 1
            modalities[im.get("modality", "other")] = modalities.get(im.get("modality", "other"), 0) + 1
        res.metrics = {
            "total_images": len(all_images),
            "pages_with_images": len(per_page_counts),
            "avg_images_per_page": (sum(per_page_counts.values()) / max(1, len(per_page_counts))),
            "max_images_on_a_page": max(per_page_counts.values()) if per_page_counts else 0,
            "modality_histogram": modalities,
        }
        LOG.info(
            "stage_3_images: %d images across %d pages (avg %.1f/page, max %d/page)",
            res.metrics["total_images"], res.metrics["pages_with_images"],
            res.metrics["avg_images_per_page"], res.metrics["max_images_on_a_page"],
        )
    finally:
        doc.close()
    return res


__all__ = ["run", "_extract_render_region"]
