"""Regression tests for MCE sub-stage 2.9 (Stage 6: OCR + answer-key).

Run: cd backend && python -m pytest mce/tests/test_stage_6_ocr.py -v
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from mce.profiles import get_profile_for_filename
from mce.stages import MceContext
from mce.stages.stage_1_render import run as run_s1
from mce.stages.stage_2_layout import run as run_s2
from mce.stages.stage_3_images import run as run_s3
from mce.stages.stage_5_question_blocks import run as run_s5
from mce.stages.stage_6_ocr import run as run_s6, extract_answer_key_from_text


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


def test_stage6_runs_when_engine_unavailable(tmp_path):
    """Without Tesseract, stage 6 emits a warning and writes empty results."""
    ctx = _ctx(tmp_path)
    run_s1(ctx, pages=[38])
    run_s2(ctx, pages=[38])
    run_s3(ctx, pages=[38])
    run_s5(ctx, pages=[38])
    res = run_s6(ctx, pages=[38])
    assert res.errors == []
    # Either the engine is unavailable (warning) or it ran (results non-empty).
    if not res.metrics["engine_available"]:
        assert any("not available" in w for w in res.warnings)
        assert res.metrics["region_ocr_total"] == 0
    assert res.pages_processed == 1


def test_answer_key_extraction_basic():
    text = (
        "Q1 A\nQ2 B\nQ3 C\n"
        "ANSWER KEYS\n"
        "1. A\n2. B\n3. C\n"
    )
    offset, m = extract_answer_key_from_text(text)
    assert offset is not None and offset > 0
    assert m == {1: ["A"], 2: ["B"], 3: ["C"]}


def test_answer_key_extraction_multi_letter():
    text = (
        "ANSWER KEYS\n"
        "1. A, B\n"
        "2. C, D\n"
        "3. (B)\n"
        "4. A,B,C\n"
    )
    offset, m = extract_answer_key_from_text(text)
    assert offset is not None
    assert m[1] == ["A", "B"]
    assert m[2] == ["C", "D"]
    assert m[3] == ["B"]
    assert m[4] == ["A", "B", "C"]


def test_answer_key_extraction_missing():
    text = "Q1 A\nQ2 B\nNo key here\n"
    offset, m = extract_answer_key_from_text(text)
    assert offset is None
    assert m == {}
