"""Stage 4 — Table / algorithm / flowchart extraction.

Per page, invoke the TableEngine and persist:
    04_tables/p{NNN}_tbl{kk}.json   # {cells, bbox, confidence, method, type}
    04_tables/p{NNN}_tbl{kk}.png    # preview crop of the table region
    04_tables/p{NNN}.json           # per-page table index
    04_tables/_index.json           # stage-wide index

Each table block carries:
    type        : "table" | "algorithm" | "flowchart" | "drug_chart"
    bbox        : [x0,y0,x1,y1] in PDF points
    cells       : [[str, ...], ...]
    confidence  : 0..1
    method      : "lattice" | "stream" | "heuristic"
    asset_id    : "p{NNN}_tbl{kk}"
    source_trace: 8-field SourceTrace
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

import fitz  # type: ignore

from mce.engines.registry import get_table
from mce.engines.text_lines import extract_text_lines
from mce.stages import MceContext, StageResult
from mce.types import SourceTrace


LOG = logging.getLogger("mce.stage_4_tables")


def _crop_table_preview(
    doc: fitz.Document,
    page_number: int,
    bbox: tuple[float, ...],
    out_path: Path,
    dpi: int = 300,
) -> bool:
    """Save a PNG crop of the table region. Returns True on success."""
    try:
        page = doc[page_number - 1]
        clip = fitz.Rect(*bbox)
        pix = page.get_pixmap(dpi=dpi, alpha=False, clip=clip)
        out_path.write_bytes(pix.tobytes("png"))
        return True
    except Exception as e:
        LOG.debug("table preview crop failed: %s", e)
        return False


def _process_one_page(
    ctx: MceContext,
    page_number: int,
    page_png_path: Path,
    page_width_pt: float,
    page_height_pt: float,
    engine_name: str,
) -> tuple[list[dict[str, Any]], int]:
    """Extract tables on one page. Returns (table_blocks, line_count)."""
    table_engine = get_table()
    lines = extract_text_lines(str(ctx.pdf_path), page_number)
    raw_tables = table_engine.extract(
        page_number=page_number,
        page_png_path=page_png_path,
        page_width_pt=page_width_pt,
        page_height_pt=page_height_pt,
        lines=lines,
    )
    out: list[dict[str, Any]] = []
    for idx, t in enumerate(raw_tables):
        bbox = tuple(float(b) for b in t["bbox"])
        asset_id = f"p{page_number:03d}_tbl{idx:02d}"
        trace = SourceTrace.make(
            pdf_filename=ctx.pdf_filename,
            pdf_sha256=ctx.pdf_sha256,
            pdf_sha256_short=ctx.pdf_sha256_short,
            page_number=page_number,
            bbox=bbox,
            extraction_engine=f"{engine_name}:{t.get('method', 'unknown')}",
            pipeline_stage="stage_4_tables",
            confidence=float(t.get("confidence", 0.0)),
        )
        out.append({
            "id": asset_id,
            "page_number": page_number,
            "type": t.get("type", "table"),
            "bbox": list(bbox),
            "cells": t.get("cells", []),
            "confidence": float(t.get("confidence", 0.0)),
            "method": t.get("method", ""),
            "preview_png": t.get("preview_png"),
            "source_trace": trace.to_dict(),
        })
    return out, len(lines)


def run(ctx: MceContext, *, pages: Optional[list[int]] = None,
        force: bool = False) -> StageResult:
    res = StageResult(stage="stage_4_tables")
    out_dir: Path = ctx.stage_dir("04_tables")
    index_path = out_dir / "_index.json"

    prev_index: dict[str, dict] = {}
    if index_path.exists() and not force:
        try:
            prev_index = json.loads(index_path.read_text(encoding="utf-8"))
        except Exception:  # pragma: no cover
            prev_index = {}

    table_engine = get_table()
    engine_name = table_engine.name
    if not table_engine.is_available():
        res.warnings.append(f"table engine '{engine_name}' not available — skipping Stage 4")
        index_path.write_text(
            json.dumps(prev_index, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return res

    # Set the PDF path env so Camelot can find the source.
    os.environ["MCE_PDF_PATH"] = str(ctx.pdf_path)

    pages_render_dir = ctx.stage_dir("01_pdf_pages")
    try:
        doc = fitz.open(str(ctx.pdf_path))
    except Exception as e:  # pragma: no cover
        res.errors.append(f"fitz.open failed: {e}")
        return res

    try:
        all_tables: list[dict[str, Any]] = list(prev_index.get("tables", []))
        done_pages = {int(t["page_number"]) for t in all_tables}

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
            page_png = pages_render_dir / f"p{page_number:03d}.png"
            try:
                page_tables, _ = _process_one_page(
                    ctx, page_number, page_png,
                    float(page.rect.width), float(page.rect.height),
                    engine_name,
                )
            except Exception as e:  # pragma: no cover
                res.errors.append(f"p{page_number}: extract failed: {e}")
                continue

            # Save individual table JSON + preview crops.
            for t in page_tables:
                t_json = out_dir / f"{t['id']}.json"
                t_json.write_text(
                    json.dumps(t, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                bbox = tuple(t["bbox"])
                if any(bbox):
                    preview_path = out_dir / f"{t['id']}.png"
                    _crop_table_preview(doc, page_number, bbox, preview_path)
                    t["preview_png"] = str(preview_path)

            # Replace any prior page entries in `all_tables` (force-rerun).
            all_tables = [tt for tt in all_tables if int(tt["page_number"]) != page_number]
            all_tables.extend(page_tables)

            page_index = {
                "page_number": page_number,
                "table_count": len(page_tables),
                "table_ids": [t["id"] for t in page_tables],
            }
            (out_dir / f"p{page_number:03d}.json").write_text(
                json.dumps(page_index, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            res.artefacts_written += len(page_tables)
            res.pages_processed += 1

        all_tables.sort(key=lambda t: (int(t["page_number"]), t["id"]))
        out_index = {
            "pdf_filename": ctx.pdf_filename,
            "pdf_sha256_short": ctx.pdf_sha256_short,
            "engine_name": engine_name,
            "table_count": len(all_tables),
            "tables": all_tables,
        }
        index_path.write_text(
            json.dumps(out_index, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # Metrics.
        per_page = {}
        for t in all_tables:
            per_page[int(t["page_number"])] = per_page.get(int(t["page_number"]), 0) + 1
        type_hist: dict[str, int] = {}
        for t in all_tables:
            type_hist[t.get("type", "table")] = type_hist.get(t.get("type", "table"), 0) + 1
        res.metrics = {
            "total_tables": len(all_tables),
            "pages_with_tables": len(per_page),
            "engine_name": engine_name,
            "asset_type_histogram": type_hist,
        }
        LOG.info("stage_4_tables: %d tables across %d pages (engine=%s)",
                 res.metrics["total_tables"], res.metrics["pages_with_tables"], engine_name)
    finally:
        doc.close()

    return res


__all__ = ["run"]
