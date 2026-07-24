"""Regression tests for MCE sub-stage 2.11 (Stage 8: QA + overlays).

Run: cd backend && python -m pytest mce/tests/test_stage_8_qa.py -v
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
from mce.stages.stage_5_question_blocks import run as run_s5
from mce.stages.stage_6_ocr import run as run_s6
from mce.stages.stage_7_structured import run as run_s7
from mce.stages.stage_8_qa import run as run_s8


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


def _pipeline_through_s7(ctx: MceContext, pages: list[int]) -> None:
    run_s1(ctx, pages=pages)
    run_s2(ctx, pages=pages)
    run_s3(ctx, pages=pages)
    run_s5(ctx, pages=pages)
    run_s6(ctx, pages=pages)
    run_s7(ctx, pages=pages)


def test_stage8_writes_per_page_report(tmp_path):
    ctx = _ctx(tmp_path)
    _pipeline_through_s7(ctx, [38])
    res = run_s8(ctx, pages=[38])
    art = ctx.stage_dir("08_qa")
    rep = json.loads((art / "per_page_report.json").read_text(encoding="utf-8"))
    assert "38" in rep
    pr = rep["38"]
    assert pr["status"] in ("PASS", "FAIL")
    assert pr["question_count"] >= 1
    assert pr["image_count"] >= 1


def test_stage8_writes_overlay_png(tmp_path):
    ctx = _ctx(tmp_path)
    _pipeline_through_s7(ctx, [38])
    run_s8(ctx, pages=[38])
    overlay = ctx.stage_dir("08_qa") / "overlays" / "p038.png"
    assert overlay.exists()
    assert overlay.stat().st_size > 10_000  # not a 0-byte file


def test_stage8_summary_aggregates(tmp_path):
    ctx = _ctx(tmp_path)
    _pipeline_through_s7(ctx, [38])
    res = run_s8(ctx, pages=[38])
    summary = json.loads((ctx.stage_dir("08_qa") / "summary.json").read_text(encoding="utf-8"))
    assert summary["total_pages_evaluated"] == 1
    assert summary["pass_count"] + summary["fail_count"] == 1
    assert "failure_modes" in summary


def test_stage8_metrics_contains_thresholds(tmp_path):
    ctx = _ctx(tmp_path)
    _pipeline_through_s7(ctx, [38])
    res = run_s8(ctx, pages=[38])
    assert res.metrics["pass_threshold"] == 0.85
    assert res.metrics["max_unclassified_blocks"] == 2
