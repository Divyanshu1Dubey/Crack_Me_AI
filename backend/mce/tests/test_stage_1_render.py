"""Regression tests for MCE sub-stage 2.2 (Stage 1: page render).

Run: cd backend && python -m pytest mce/tests/test_stage_1_render.py -v
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import fitz  # type: ignore
import pytest

from mce.profiles import get_profile_for_filename
from mce.stages import MceContext
from mce.stages.stage_1_render import (
    BASE_DPI,
    HIGH_DPI,
    HIGH_DPI_MIN_IMAGES,
    run,
    select_dpi,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
BENCHMARK_PDF = REPO_ROOT / "material" / "neet-pg" / "NEET-PG-2021-Question-Paper-With-Solutions-PDF-1.pdf"


def _ctx(tmp_path: Path, pages_rendered: int | None = None) -> MceContext:
    pdf = BENCHMARK_PDF
    if not pdf.exists():
        pytest.skip(f"benchmark PDF not present at {pdf}")
    pdf_bytes = pdf.read_bytes()
    sha = hashlib.sha256(pdf_bytes).hexdigest()
    sha16 = sha[:16]
    doc = fitz.open(str(pdf))
    try:
        page_count = doc.page_count
    finally:
        doc.close()
    artefact_root = tmp_path / sha16
    profile = get_profile_for_filename(pdf.name)
    return MceContext(
        pdf_path=pdf,
        pdf_filename=pdf.name,
        pdf_sha256=sha,
        pdf_sha256_short=sha16,
        page_count=page_count,
        profile=profile,
        artefact_root=artefact_root,
    )


def test_select_dpi_triggers_high_dpi_for_image_heavy_page(tmp_path):
    """Pages with >= HIGH_DPI_MIN_IMAGES embedded images render at HIGH_DPI."""
    ctx = _ctx(tmp_path)
    res = run(ctx, pages=[1, 5, 38, 100])
    assert res.errors == []
    assert res.pages_processed == 4
    art = ctx.stage_dir("01_pdf_pages")
    for pno in (1, 5, 38, 100):
        meta_path = art / f"p{pno:03d}.dpi.json"
        m = json.loads(meta_path.read_text(encoding="utf-8"))
        assert m["dpi"] == HIGH_DPI, f"page {pno} should be HIGH_DPI"


def test_render_writes_png_and_meta(tmp_path):
    ctx = _ctx(tmp_path)
    res = run(ctx, pages=[38])
    assert res.errors == []
    art = ctx.stage_dir("01_pdf_pages")
    png = art / "p038.png"
    meta = art / "p038.dpi.json"
    assert png.exists() and png.stat().st_size > 50_000
    m = json.loads(meta.read_text(encoding="utf-8"))
    assert m["page_number"] == 38
    assert m["dpi"] in (BASE_DPI, HIGH_DPI)
    assert m["width_px"] > 0 and m["height_px"] > 0
    assert m["pdf_sha256_short"] == ctx.pdf_sha256_short
    assert m["png_path"] == str(png)


def test_idempotent_rerun_skips(tmp_path):
    ctx = _ctx(tmp_path)
    res1 = run(ctx, pages=[38])
    res2 = run(ctx, pages=[38])
    assert res1.pages_processed == 1
    assert res2.pages_processed == 0
    assert res2.pages_skipped == 1


def test_force_rerun_re_renders(tmp_path):
    ctx = _ctx(tmp_path)
    run(ctx, pages=[38])
    res = run(ctx, pages=[38], force=True)
    assert res.pages_processed == 1
    assert res.pages_skipped == 0


def test_index_aggregates_metrics(tmp_path):
    ctx = _ctx(tmp_path)
    run(ctx, pages=list(range(1, 11)))  # pages 1..10
    art = ctx.stage_dir("01_pdf_pages")
    index = json.loads((art / "_index.json").read_text(encoding="utf-8"))
    assert len(index) == 10
    # Sanity: most NEET-PG-2021 pages have >= 4 images and should land on HIGH_DPI.
    high = sum(1 for m in index.values() if m["dpi"] == HIGH_DPI)
    assert high >= 5
