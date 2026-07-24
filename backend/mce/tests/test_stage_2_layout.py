"""Regression tests for MCE sub-stage 2.4 (Stage 2: layout detection).

Run: cd backend && python -m pytest mce/tests/test_stage_2_layout.py -v
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from mce.profiles import get_profile_for_filename
from mce.stages import MceContext
from mce.stages.stage_1_render import run as run_s1
from mce.stages.stage_2_layout import run as run_s2


REPO_ROOT = Path(__file__).resolve().parents[3]
BENCHMARK_PDF = REPO_ROOT / "material" / "neet-pg" / "NEET-PG-2021-Question-Paper-With-Solutions-PDF-1.pdf"


def _ctx(tmp_path: Path) -> MceContext:
    pdf = BENCHMARK_PDF
    if not pdf.exists():
        pytest.skip(f"benchmark PDF missing at {pdf}")
    sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
    sha16 = sha[:16]
    profile = get_profile_for_filename(pdf.name)
    return MceContext(
        pdf_path=pdf, pdf_filename=pdf.name,
        pdf_sha256=sha, pdf_sha256_short=sha16,
        page_count=144, profile=profile,
        artefact_root=tmp_path / sha16,
    )


def _prereq_stage1(ctx: MceContext, pages: list[int]) -> None:
    """Stage 2 depends on Stage 1 renders."""
    run_s1(ctx, pages=pages)


def test_stage2_requires_stage1(tmp_path):
    ctx = _ctx(tmp_path)
    res = run_s2(ctx, pages=[1])
    # Even without Stage 1, layout still runs (pdfplumber doesn't need
    # the rendered PNG — Stage 2 only uses it for bbox fidelity). Pages
    # should be processable.
    assert res.errors == []


def test_stage2_writes_per_page_layout_with_source_trace(tmp_path):
    ctx = _ctx(tmp_path)
    _prereq_stage1(ctx, [38])
    res = run_s2(ctx, pages=[38])
    assert res.errors == []
    assert res.pages_processed == 1
    art = ctx.stage_dir("02_layout")
    p38 = json.loads((art / "p038.json").read_text(encoding="utf-8"))
    assert p38["page_number"] == 38
    assert p38["engine_name"] == "layout_heuristic"
    assert p38["region_count"] == len(p38["regions"])
    assert p38["region_count"] > 0
    # Every region carries a SourceTrace with all 8 fields.
    for r in p38["regions"]:
        st = r["source_trace"]
        for k in ("pdf_filename", "pdf_sha256", "pdf_sha256_short",
                  "page_number", "bbox", "extraction_engine",
                  "confidence", "pipeline_stage", "extracted_at"):
            assert k in st, f"region {r['id']} missing {k}"
        assert st["pipeline_stage"] == "stage_2_layout"
        assert st["extraction_engine"] == "layout_heuristic"
        assert st["page_number"] == 38
        assert len(st["bbox"]) == 4


def test_stage2_index_aggregates(tmp_path):
    ctx = _ctx(tmp_path)
    _prereq_stage1(ctx, [1, 5, 38])
    res = run_s2(ctx, pages=[1, 5, 38])
    assert res.pages_processed == 3
    art = ctx.stage_dir("02_layout")
    index = json.loads((art / "_index.json").read_text(encoding="utf-8"))
    assert len(index) == 3
    assert res.metrics["engine_name"] == "layout_heuristic"
    hist = res.metrics["region_type_histogram"]
    # Pages 1, 5, 38 each have questions, options, answers, header.
    assert hist.get("option", 0) >= 12  # 4 options × 3 pages minimum
    assert hist.get("header", 0) >= 3   # watermark on every page
    assert hist.get("stem", 0) >= 3


def test_stage2_idempotent(tmp_path):
    ctx = _ctx(tmp_path)
    _prereq_stage1(ctx, [38])
    run_s2(ctx, pages=[38])
    res = run_s2(ctx, pages=[38])
    assert res.pages_processed == 0
    assert res.pages_skipped == 1
