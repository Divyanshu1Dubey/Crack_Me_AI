"""Stage 2 — Layout detection.

Inputs:
    <ctx.pdf_path>                       # source PDF
    <artefact_root>/01_pdf_pages/        # Stage-1 outputs
    <artefact_root>/03_images/_index.json  # Stage-3 image anchors (forward ref)

For every page:
    1. extract TextLines via pdfplumber (with pdfminer.six fallback)
    2. load image anchors from Stage 3 (if present)
    3. invoke LayoutEngine.detect(...)
    4. attach a SourceTrace to every emitted region
    5. write per-page layout JSON
    6. update the stage-wide _index.json

Outputs:
    02_layout/p{NNN}.json   # {page_number, regions: [Region dicts]}
    02_layout/_index.json   # {page_number -> {path, region_count, ...}}

A region dict carries:
    id, type, bbox, label?, text, confidence, match_rule, line_index,
    source_trace (8-field provenance)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

import fitz  # type: ignore

from mce.engines.text_lines import extract_text_lines
from mce.engines.registry import get_layout
from mce.stages import MceContext, StageResult
from mce.types import SourceTrace


LOG = logging.getLogger("mce.stage_2_layout")


def _load_stage3_image_anchors(stage3_index_path: Path, page_number: int) -> list[tuple[str, tuple[float, ...]]]:
    """Read Stage 3's image index for this page; return [(image_id, bbox), ...].

    Stage 3 may not have run yet (this stage can run independently) — in
    that case we return [] and the layout engine just classifies text.
    """
    if not stage3_index_path.exists():
        return []
    try:
        idx = json.loads(stage3_index_path.read_text(encoding="utf-8"))
    except Exception:  # pragma: no cover - corrupt json
        return []
    out: list[tuple[str, tuple[float, ...]]] = []
    for entry in idx.get("images", []):
        if int(entry.get("page_number", -1)) == page_number:
            bbox = entry.get("bbox") or []
            if len(bbox) == 4:
                out.append((entry["id"], tuple(float(b) for b in bbox)))
    return out


def _process_one_page(
    ctx: MceContext,
    page_number: int,
    page_png_path: Path,
    page_width_pt: float,
    page_height_pt: float,
    image_anchors: list[tuple[str, tuple[float, ...]]],
    engine_name: str,
) -> tuple[list[dict[str, Any]], int]:
    """Run the LayoutEngine on one page; return (regions, line_count)."""
    lines = extract_text_lines(str(ctx.pdf_path), page_number)
    layout_engine = get_layout()
    raw_regions = layout_engine.detect(
        page_number=page_number,
        page_png_path=page_png_path,
        page_width_pt=page_width_pt,
        page_height_pt=page_height_pt,
        lines=lines,
        images=image_anchors,
    )
    regions: list[dict[str, Any]] = []
    for idx, r in enumerate(raw_regions):
        bbox = tuple(float(b) for b in r["bbox"])
        rid = f"p{page_number:03d}_r{idx:02d}"
        trace = SourceTrace.make(
            pdf_filename=ctx.pdf_filename,
            pdf_sha256=ctx.pdf_sha256,
            pdf_sha256_short=ctx.pdf_sha256_short,
            page_number=page_number,
            bbox=bbox,
            extraction_engine=engine_name,
            pipeline_stage="stage_2_layout",
            confidence=float(r.get("confidence", 0.0)),
        )
        out: dict[str, Any] = {
            "id": rid,
            "type": r["type"],
            "bbox": list(bbox),
            "label": r.get("label"),
            "text": r.get("text", ""),
            "confidence": float(r.get("confidence", 0.0)),
            "match_rule": r.get("match_rule", ""),
            "line_index": r.get("line_index"),
            "source_trace": trace.to_dict(),
        }
        regions.append(out)
    return regions, len(lines)


def run(ctx: MceContext, *, pages: Optional[list[int]] = None,
        force: bool = False) -> StageResult:
    """Detect typed regions on every page (or a subset)."""
    res = StageResult(stage="stage_2_layout")
    out_dir: Path = ctx.stage_dir("02_layout")
    index_path = out_dir / "_index.json"

    stage3_index = ctx.stage_dir("03_images") / "_index.json"  # may not exist yet
    prev_index: dict[str, dict] = {}
    if index_path.exists() and not force:
        try:
            prev_index = json.loads(index_path.read_text(encoding="utf-8"))
        except Exception:  # pragma: no cover
            prev_index = {}

    layout_engine = get_layout()
    engine_name = layout_engine.name
    if not layout_engine.is_available():
        res.errors.append(f"layout engine '{engine_name}' is not available")
        return res

    try:
        doc = fitz.open(str(ctx.pdf_path))
    except Exception as e:  # pragma: no cover
        res.errors.append(f"fitz.open failed: {e}")
        return res

    pages_render_dir = ctx.stage_dir("01_pdf_pages")
    try:
        index: dict[str, dict] = dict(prev_index)
        page_iter = (
            [(p - 1, p) for p in pages]
            if pages
            else [(i, i + 1) for i in range(ctx.page_count)]
        )
        for page_idx, page_number in page_iter:
            page = doc[page_idx]
            page_png = pages_render_dir / f"p{page_number:03d}.png"

            existing = prev_index.get(str(page_number))
            if (
                not force
                and existing
                and existing.get("engine_name") == engine_name
                and Path(existing.get("path", "")).exists()
            ):
                res.pages_skipped += 1
                index[str(page_number)] = existing
                continue

            image_anchors = _load_stage3_image_anchors(stage3_index, page_number)
            try:
                regions, line_count = _process_one_page(
                    ctx, page_number, page_png,
                    float(page.rect.width), float(page.rect.height),
                    image_anchors, engine_name,
                )
            except Exception as e:  # pragma: no cover
                res.errors.append(f"p{page_number}: layout failed: {e}")
                continue

            page_json = out_dir / f"p{page_number:03d}.json"
            payload = {
                "page_number": page_number,
                "engine_name": engine_name,
                "page_width_pt": float(page.rect.width),
                "page_height_pt": float(page.rect.height),
                "line_count": line_count,
                "region_count": len(regions),
                "regions": regions,
                "image_anchor_count": len(image_anchors),
            }
            page_json.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            index[str(page_number)] = {
                "page_number": page_number,
                "engine_name": engine_name,
                "path": str(page_json),
                "line_count": line_count,
                "region_count": len(regions),
                "image_anchor_count": len(image_anchors),
                "page_width_pt": float(page.rect.width),
                "page_height_pt": float(page.rect.height),
            }
            res.artefacts_written += 1
            res.pages_processed += 1

        index_path.write_text(
            json.dumps(index, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # Aggregate metrics.
        total_regions = sum(int(v.get("region_count", 0)) for v in index.values())
        total_lines = sum(int(v.get("line_count", 0)) for v in index.values())
        type_hist: dict[str, int] = {}
        for v in index.values():
            try:
                with open(v["path"], encoding="utf-8") as f:
                    payload = json.load(f)
                for r in payload.get("regions", []):
                    t = r.get("type", "unknown")
                    type_hist[t] = type_hist.get(t, 0) + 1
            except Exception:
                continue
        res.metrics = {
            "total_pages_laid_out": len(index),
            "total_lines": total_lines,
            "total_regions": total_regions,
            "region_type_histogram": type_hist,
            "engine_name": engine_name,
        }
        LOG.info(
            "stage_2_layout: %d pages, %d lines, %d regions, engine=%s",
            res.metrics["total_pages_laid_out"], total_lines, total_regions, engine_name,
        )
    finally:
        doc.close()

    return res


__all__ = ["run"]
