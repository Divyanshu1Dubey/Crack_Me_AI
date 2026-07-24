"""Stage 2b — Reading-order sort.

Reads Stage 2's per-page region list and re-emits the same regions in
human reading order.  Used as a pre-stage for any LLM-assisted layout
work (Stage 7.5) so the model sees a deterministic top-to-bottom,
column-aware sequence of regions.

For the 2021 NEET-PG-2021 benchmark the entire paper is single-column
(verified: 0 pages with > 5 multi-column rows), so this stage is a
no-op.  The helper is wired so future exams with 2-column answer keys
benefit immediately.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from mce.stages import MceContext, StageResult


LOG = logging.getLogger("mce.stage_2b_reading_order")


def _group_into_columns(
    regions: list[dict[str, Any]],
    page_width_pt: float,
) -> list[list[int]]:
    """Group regions by column when a real two-column layout is present.

    Detection rule: at least 4 regions with x0 < page_w/3 AND at least
    4 regions with x0 >= 2*page_w/3.  Otherwise single-column.

    The stricter rule (vs the original biased-median approach) prevents
    false-positives from a single outlier watermark on the right side.
    """
    if not regions:
        return []
    left_thresh = page_width_pt * 0.33
    right_thresh = page_width_pt * 0.66
    left = [i for i, r in enumerate(regions) if r["bbox"][0] < left_thresh]
    right = [i for i, r in enumerate(regions) if r["bbox"][0] >= right_thresh]
    if len(left) >= 4 and len(right) >= 4:
        cols = []
        cols.append(sorted(left, key=lambda i: regions[i]["bbox"][1]))
        cols.append(sorted(right, key=lambda i: regions[i]["bbox"][1]))
        return cols
    return [list(range(len(regions)))]


def _reading_order(
    regions: list[dict[str, Any]],
    page_width_pt: float,
) -> list[dict[str, Any]]:
    """Return regions sorted in human reading order.

    For a single-column page (NEET-PG-2021 is uniformly single column),
    this is just top-to-bottom with intra-band x-ordering.

    For genuine two-column pages, emits the left column top-to-bottom
    then the right column top-to-bottom.
    """
    if not regions:
        return []
    columns = _group_into_columns(regions, page_width_pt)
    out: list[dict[str, Any]] = []
    for col in columns:
        col_regions = [regions[i] for i in col]
        col_regions.sort(key=lambda r: (float(r["bbox"][1]), float(r["bbox"][0])))
        out.extend(col_regions)
    return out


def run(ctx: MceContext, *, pages: Optional[list[int]] = None,
        force: bool = False) -> StageResult:
    """Re-emit Stage 2 pages in reading order, as a side artefact.

    The Stage 2 index is **never** reordered (other stages consume it
    in original py-pdfplumber order).  This stage writes
    ``02b_reading_order/p{NNN}.json`` for downstream consumers
    (LLM-assisted Stage 7.5) that need deterministic reading order.
    """
    res = StageResult(stage="stage_2b_reading_order")
    out_dir = ctx.stage_dir("02b_reading_order")
    layout_dir = ctx.stage_dir("02_layout")
    pages_dir = ctx.stage_dir("01_pdf_pages")

    page_iter = (
        [(p - 1, p) for p in pages]
        if pages
        else [(i, i + 1) for i in range(ctx.page_count)]
    )
    page_count = 0
    for _, page_number in page_iter:
        layout_path = layout_dir / f"p{page_number:03d}.json"
        if not layout_path.exists():
            continue
        try:
            layout = json.loads(layout_path.read_text(encoding="utf-8"))
            regions = layout.get("regions", [])
        except Exception:
            continue
        # Page width from Stage 1 metadata.
        page_width_pt = 595.3
        page_meta_path = pages_dir / "_index.json"
        if page_meta_path.exists():
            try:
                meta = json.loads(page_meta_path.read_text(encoding="utf-8"))
                page_width_pt = float(meta.get(str(page_number), {}).get("width_pt") or 595.3)
            except Exception:
                pass
        ordered = _reading_order(regions, page_width_pt)
        (out_dir / f"p{page_number:03d}.json").write_text(
            json.dumps({
                "page_number": page_number,
                "region_count": len(ordered),
                "regions": ordered,
            }, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        page_count += 1

    (out_dir / "_index.json").write_text(
        json.dumps({"page_count": page_count, "pdf_filename": ctx.pdf_filename},
                   indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    res.metrics = {"pages_processed": page_count, "regions": page_count}
    LOG.info("stage_2b_reading_order: %d pages re-ordered", page_count)
    return res


__all__ = ["run", "_reading_order"]
