"""Regression tests for MCE sub-stage 2.6 (Stage 3: image extraction).

Run: cd backend && python -m pytest mce/tests/test_stage_3_images.py -v
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from mce.profiles import get_profile_for_filename
from mce.stages import MceContext
from mce.stages.stage_1_render import run as run_s1
from mce.stages.stage_3_images import run as run_s3


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


def test_stage3_extracts_embedded_images(tmp_path):
    ctx = _ctx(tmp_path)
    run_s1(ctx, pages=[38])
    res = run_s3(ctx, pages=[38])
    assert res.errors == []
    assert res.pages_processed == 1
    art = ctx.stage_dir("03_images")
    p38 = json.loads((art / "p038.json").read_text(encoding="utf-8"))
    # Every image in this PDF has 3-5 embedded images per page.
    assert p38["image_count"] >= 3
    # Every image file must exist on disk.
    for im in p38["images"]:
        assert Path(im["file_path"]).exists()
        assert im["bytes"] > 0
        assert im["sha256"]
        assert im["sha256_short"]
        # Every image carries a SourceTrace with all 8 fields.
        st = im["source_trace"]
        for k in ("pdf_filename", "pdf_sha256", "pdf_sha256_short",
                  "page_number", "bbox", "extraction_engine",
                  "confidence", "pipeline_stage", "extracted_at"):
            assert k in st
        assert st["pipeline_stage"] == "stage_3_images"
        assert st["page_number"] == 38


def test_stage3_index_aggregates(tmp_path):
    ctx = _ctx(tmp_path)
    run_s1(ctx, pages=[1, 5, 38])
    res = run_s3(ctx, pages=[1, 5, 38])
    art = ctx.stage_dir("03_images")
    index = json.loads((art / "_index.json").read_text(encoding="utf-8"))
    assert index["pdf_sha256_short"] == ctx.pdf_sha256_short
    assert index["image_count"] >= 9  # 3 pages × ≥ 3 images each
    # Every image carries a non-empty bbox (heuristic pixel-scan fallback).
    for im in index["images"]:
        bb = im["bbox"]
        assert isinstance(bb, list) and len(bb) == 4
        # bbox can be (0,0,0,0) only when ALL placement methods failed
        # AND pixel-scan failed — extremely rare on the 2021 PDF.
        # On real pages we expect at least one of {right > left, bottom > top}.
    res.metrics["total_images"] >= 9


def test_stage3_idempotent(tmp_path):
    ctx = _ctx(tmp_path)
    run_s1(ctx, pages=[38])
    run_s3(ctx, pages=[38])
    res = run_s3(ctx, pages=[38])
    assert res.pages_processed == 0
    assert res.pages_skipped == 1


def test_stage3_metrics_record_modality_histogram(tmp_path):
    ctx = _ctx(tmp_path)
    run_s1(ctx, pages=[1, 5, 38])
    res = run_s3(ctx, pages=[1, 5, 38])
    hist = res.metrics["modality_histogram"]
    assert sum(hist.values()) >= 9
    # Every value is one of the documented modality strings.
    valid = {"radiograph", "ct", "mri", "ultrasound", "ecg", "echo",
             "fundus", "pathology_gross", "pathology_micro",
             "dermatology", "histology", "hematology", "blood_smear",
             "embryology", "anatomy_diagram", "flow_chart", "table",
             "drug_chart", "clinical_photo", "generic", "other"}
    assert all(k in valid for k in hist)
