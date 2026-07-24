"""Stage 6 — Per-region OCR + image-annotation OCR + answer-key extraction.

Three jobs in one stage:

1. Image-annotation OCR — for every image extracted in Stage 3, run OCR
   on the saved file to recover labels / annotations / arrow text. The
   result is stored on the image's ``ocr_text`` field.

2. Layout-region OCR — for every Stage-2 region typed ``unclassified`` or
   flagged with low confidence, run OCR on the page-render crop. The
   result replaces the region's ``text`` if confidence is higher than
   the digital-text confidence.

3. Answer-key extraction — scan the whole PDF for the trailing
   ``ANSWER KEY`` / ``ANSWER KEYS`` section and emit a
   ``{question_number: [labels]}`` map that Stage 7 will merge into
   per-question rows.

Outputs
-------
    06_ocr/p{NNN}.json    # per-page: {region_ocr: [...], image_ocr: [...]}
    06_ocr/answer_key.json # global answer-key dict
    06_ocr/_index.json   # stage-wide index
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Optional

from mce.engines.registry import get_ocr
from mce.stages import MceContext, StageResult
from mce.types import SourceTrace


LOG = logging.getLogger("mce.stage_6_ocr")


# ----------------------------------------------------------------- answer key detection

RE_ANSWER_KEY_HEADER = re.compile(
    r"(?:answer\s*keys?|answer\s*key\s*with\s*explanations?|key\s*to\s*(?:the\s*)?questions?)",
    re.IGNORECASE,
)
RE_ANSWER_LINE_NUMBERED = re.compile(
    r"^\s*(\d{1,4})\s*[\.\)\:]\s*\(?([A-Fa-f](?:\s*[,/&+\s]\s*[A-Fa-f])*)\)?",
    re.MULTILINE,
)


def extract_answer_key_from_text(full_text: str) -> tuple[int, dict[int, list[str]]]:
    """Find the trailing answer-key section and return (start_offset, mapping).

    Returns start_offset=None when no key section is found.
    """
    m = RE_ANSWER_KEY_HEADER.search(full_text)
    if not m:
        return None, {}
    start = m.end()
    out: dict[int, list[str]] = {}
    for mm in RE_ANSWER_LINE_NUMBERED.finditer(full_text, start):
        try:
            qno = int(mm.group(1))
        except ValueError:
            continue
        labels = sorted({c.upper() for c in re.findall(r"[A-Fa-f]", mm.group(2))})
        if labels:
            out[qno] = labels
    return start, out


# ----------------------------------------------------------------- per-page OCR


def _ocr_image(
    image_path: str,
    lang: str = "eng",
) -> tuple[str, float]:
    ocr = get_ocr()
    return ocr.ocr(Path(image_path), lang=lang)


def _ocr_region(
    image_path: Path,
    bbox: tuple[float, ...],
    page_width_px: int,
    page_height_px: int,
    lang: str = "eng",
) -> tuple[str, float]:
    ocr = get_ocr()
    return ocr.ocr_region(
        image_path, bbox,
        page_width_px=page_width_px,
        page_height_px=page_height_px,
        lang=lang,
    )


def _process_page(
    ctx: MceContext,
    page_number: int,
    page_png_path: Path,
    page_width_px: int,
    page_height_px: int,
    layout_regions: list[dict[str, Any]],
    images: list[dict[str, Any]],
    lang: str = "eng",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """OCR every image + every low-confidence / unclassified region on this page."""
    ocr_engine = get_ocr()
    if not ocr_engine.is_available():
        return [], []

    region_results: list[dict[str, Any]] = []
    for r in layout_regions:
        # Only re-OCR regions whose digital text is suspect.
        if r.get("type") != "unclassified" and r.get("confidence", 1.0) >= 0.85:
            continue
        bbox = tuple(float(b) for b in r.get("bbox", []))
        if not any(bbox):
            continue
        text, conf = _ocr_region(
            page_png_path, bbox, page_width_px, page_height_px, lang=lang,
        )
        region_results.append({
            "region_id": r.get("id"),
            "bbox": list(bbox),
            "ocr_text": text,
            "ocr_confidence": conf,
            "replaces_text": (text and conf >= 50.0),
        })

    image_results: list[dict[str, Any]] = []
    for im in images:
        file_path = im.get("file_path")
        if not file_path or not Path(file_path).exists():
            continue
        text, conf = _ocr_image(file_path, lang=lang)
        image_results.append({
            "image_id": im.get("id"),
            "ocr_text": text,
            "ocr_confidence": conf,
            "page_number": int(im.get("page_number", page_number)),
        })

    return region_results, image_results


# ----------------------------------------------------------------- main entry


def run(ctx: MceContext, *, pages: Optional[list[int]] = None,
        force: bool = False) -> StageResult:
    res = StageResult(stage="stage_6_ocr")
    out_dir: Path = ctx.stage_dir("06_ocr")
    layout_dir = ctx.stage_dir("02_layout")
    stage3_dir = ctx.stage_dir("03_images")
    stage3_index = stage3_dir / "_index.json"

    pages_render_dir = ctx.stage_dir("01_pdf_pages")
    index_path = out_dir / "_index.json"

    prev_index: dict[str, dict] = {}
    if index_path.exists() and not force:
        try:
            prev_index = json.loads(index_path.read_text(encoding="utf-8"))
        except Exception:
            prev_index = {}

    # Stage 6 only adds value when the OCR engine is present.
    ocr_engine = get_ocr()
    engine_available = ocr_engine.is_available()
    if not engine_available:
        res.warnings.append(
            f"OCR engine '{ocr_engine.name}' not available — Stage 6 will write empty results. "
            "Install Tesseract + pytesseract to enable."
        )

    # Load stage 3 image index for image-annotation OCR.
    images_by_page: dict[int, list[dict[str, Any]]] = {}
    if stage3_index.exists():
        try:
            idx = json.loads(stage3_index.read_text(encoding="utf-8"))
            for im in idx.get("images", []):
                images_by_page.setdefault(int(im.get("page_number", -1)), []).append(im)
        except Exception:
            images_by_page = {}

    # Determine page sizes from Stage-1 metadata.
    stage1_index = pages_render_dir / "_index.json"
    page_meta: dict[int, dict[str, Any]] = {}
    if stage1_index.exists():
        try:
            s1 = json.loads(stage1_index.read_text(encoding="utf-8"))
            for k, v in s1.items():
                page_meta[int(k)] = v
        except Exception:
            page_meta = {}

    page_iter = (
        [(p - 1, p) for p in pages]
        if pages
        else [(i, i + 1) for i in range(ctx.page_count)]
    )
    all_pages: list[dict[str, Any]] = list(prev_index.get("pages", []))
    done_pages = {int(p["page_number"]) for p in all_pages}

    # Gather full text for answer-key detection (across all pages, when no --pages filter).
    full_text_parts: list[str] = []

    import fitz  # type: ignore
    try:
        doc = fitz.open(str(ctx.pdf_path))
    except Exception as e:  # pragma: no cover
        res.errors.append(f"fitz.open failed: {e}")
        return res

    try:
        for page_idx, page_number in page_iter:
            if not force and page_number in done_pages:
                res.pages_skipped += 1
                continue
            page_png = pages_render_dir / f"p{page_number:03d}.png"
            layout_path = layout_dir / f"p{page_number:03d}.json"
            if not layout_path.exists() or not page_png.exists():
                res.warnings.append(f"p{page_number}: prerequisites missing, skipping")
                continue
            try:
                layout_payload = json.loads(layout_path.read_text(encoding="utf-8"))
                regions = layout_payload.get("regions", [])
                pmeta = page_meta.get(page_number, {})
                page_w_px = int(pmeta.get("width_px") or 0)
                page_h_px = int(pmeta.get("height_px") or 0)
                page_text = doc[page_idx].get_text("text") or ""
                full_text_parts.append(page_text)
                region_results, image_results = _process_page(
                    ctx, page_number, page_png, page_w_px, page_h_px,
                    regions, images_by_page.get(page_number, []),
                )
            except Exception as e:  # pragma: no cover
                res.errors.append(f"p{page_number}: OCR failed: {e}")
                continue

            payload = {
                "page_number": page_number,
                "engine_name": ocr_engine.name,
                "engine_available": engine_available,
                "region_ocr": region_results,
                "image_ocr": image_results,
            }
            (out_dir / f"p{page_number:03d}.json").write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            all_pages = [pp for pp in all_pages if int(pp["page_number"]) != page_number]
            all_pages.append(payload)
            res.artefacts_written += 1
            res.pages_processed += 1

        all_pages.sort(key=lambda p: int(p["page_number"]))
        out_index = {
            "pdf_filename": ctx.pdf_filename,
            "pdf_sha256_short": ctx.pdf_sha256_short,
            "engine_name": ocr_engine.name,
            "engine_available": engine_available,
            "pages": all_pages,
        }
        index_path.write_text(
            json.dumps(out_index, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # Answer-key extraction — only meaningful when running across the
        # full PDF, not a subset of pages.
        answer_key_map: dict[str, list[str]] = {}
        key_offset = -1
        if not pages:
            full_text = "\n".join(full_text_parts)
            key_offset, answer_key_map_raw = extract_answer_key_from_text(full_text)
            answer_key_map = {str(k): v for k, v in answer_key_map_raw.items()}
        ak_path = out_dir / "answer_key.json"
        ak_payload = {
            "key_offset": key_offset,
            "question_count": len(answer_key_map),
            "answers": answer_key_map,
        }
        ak_path.write_text(json.dumps(ak_payload, indent=2, ensure_ascii=False), encoding="utf-8")

        # Image OCR results back-propagated to Stage 3 image records.
        if stage3_index.exists():
            try:
                idx = json.loads(stage3_index.read_text(encoding="utf-8"))
                for im in idx.get("images", []):
                    for p in all_pages:
                        for r in p.get("image_ocr", []):
                            if r.get("image_id") == im.get("id"):
                                im["ocr_text"] = r.get("ocr_text", "")
                                im["ocr_confidence"] = r.get("ocr_confidence", 0.0)
                                if r.get("ocr_text"):
                                    im["caption_source"] = "ocr_on_image"
                                    im["caption"] = r["ocr_text"][:200]
                stage3_index.write_text(
                    json.dumps(idx, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            except Exception:
                pass

        res.metrics = {
            "engine_name": ocr_engine.name,
            "engine_available": engine_available,
            "pages_with_results": len(all_pages),
            "region_ocr_total": sum(len(p.get("region_ocr", [])) for p in all_pages),
            "image_ocr_total": sum(len(p.get("image_ocr", [])) for p in all_pages),
            "answer_key_question_count": len(answer_key_map),
        }
        LOG.info(
            "stage_6_ocr: engine=%s available=%s pages=%d region_ocrs=%d image_ocrs=%d key_qs=%d",
            res.metrics["engine_name"], res.metrics["engine_available"],
            res.metrics["pages_with_results"],
            res.metrics["region_ocr_total"], res.metrics["image_ocr_total"],
            res.metrics["answer_key_question_count"],
        )
    finally:
        doc.close()
    return res


__all__ = ["run", "extract_answer_key_from_text"]
