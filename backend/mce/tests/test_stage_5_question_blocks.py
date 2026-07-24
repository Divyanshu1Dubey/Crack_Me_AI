"""Regression tests for MCE sub-stage 2.8 (Stages 4 + 5).

Run: cd backend && python -m pytest mce/tests/test_stage_5_question_blocks.py -v
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
from mce.stages.stage_3_images import run as run_s3
from mce.stages.stage_4_tables import run as run_s4
from mce.stages.stage_5_question_blocks import run as run_s5


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


def test_stage4_skips_when_engine_unavailable(tmp_path):
    """When the table engine is unavailable, Stage 4 writes a warning + returns."""
    from mce.engines import registry
    registry.set_override("table", type("S", (), {"name": "stub", "is_available": lambda self: False,
                                                    "extract": lambda self, **kw: []})())
    ctx = _ctx(tmp_path)
    res = run_s4(ctx, pages=[1])
    assert len(res.warnings) == 1
    registry.clear_overrides()


def test_stage5_groups_regions_into_blocks(tmp_path):
    ctx = _ctx(tmp_path)
    run_s1(ctx, pages=[38])
    run_s2(ctx, pages=[38])
    run_s3(ctx, pages=[38])
    run_s4(ctx, pages=[38])
    res = run_s5(ctx, pages=[38])
    assert res.errors == []
    art = ctx.stage_dir("05_question_blocks")
    p38 = json.loads((art / "p038.json").read_text(encoding="utf-8"))
    # Page 38 has 2 questions in the NEET-PG-2021 PDF (Q53 + Q54).
    assert p38["block_count"] == 2
    # Each block has a question number + bbox + image_ids.
    for b in p38["blocks"]:
        assert b["question_number_in_pdf"] in (53, 54)
        assert len(b["bbox"]) == 4
        # Image IDs are attached.
        assert isinstance(b["image_ids"], list)
        # Option regions captured.
        opt = b.get("option_regions", [])
        assert len(opt) == 4


def test_stage5_block_carries_source_trace(tmp_path):
    ctx = _ctx(tmp_path)
    run_s1(ctx, pages=[38])
    run_s2(ctx, pages=[38])
    run_s3(ctx, pages=[38])
    run_s5(ctx, pages=[38])
    p38 = json.loads((ctx.stage_dir("05_question_blocks") / "p038.json").read_text(encoding="utf-8"))
    for b in p38["blocks"]:
        st = b["source_trace"]
        assert st["pipeline_stage"] == "stage_5_question_blocks"
        assert st["page_number"] == 38
        assert st["extraction_engine"] == "stage_5_question_blocks"


def test_stage5_index_aggregates(tmp_path):
    ctx = _ctx(tmp_path)
    run_s1(ctx, pages=[1, 5, 38])
    run_s2(ctx, pages=[1, 5, 38])
    run_s3(ctx, pages=[1, 5, 38])
    run_s4(ctx, pages=[1, 5, 38])
    res = run_s5(ctx, pages=[1, 5, 38])
    assert res.pages_processed == 3
    art = ctx.stage_dir("05_question_blocks")
    index = json.loads((art / "_index.json").read_text(encoding="utf-8"))
    # After the Bug 2 fix (4-option cap, see test_bugfixes_2021.py),
    # fewer phantom "option" merges happen, so we no longer get the
    # previously-over-counted 6+ blocks.  Pages 1/5/38 reliably
    # contain at least 1 question each, often 2, after the fix.
    assert index["block_count"] >= 3
    assert res.metrics["total_question_blocks"] >= 3
