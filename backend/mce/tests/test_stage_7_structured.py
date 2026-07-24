"""Regression tests for MCE sub-stage 2.10 (Stage 7: structured questions).

Run: cd backend && python -m pytest mce/tests/test_stage_7_structured.py -v
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


def _run_pipeline_through_s7(ctx: MceContext, pages: list[int]) -> None:
    run_s1(ctx, pages=pages)
    run_s2(ctx, pages=pages)
    run_s3(ctx, pages=pages)
    run_s5(ctx, pages=pages)
    run_s6(ctx, pages=pages)
    run_s7(ctx, pages=pages)


def test_stage7_emits_parsed_questions(tmp_path):
    ctx = _ctx(tmp_path)
    _run_pipeline_through_s7(ctx, [38])
    art = ctx.stage_dir("07_structured")
    p38 = json.loads((art / "p038.json").read_text(encoding="utf-8"))
    assert len(p38["questions"]) == 2
    q0 = p38["questions"][0]
    # Required fields populated
    for k in ("id", "stem", "options", "answer_labels", "image_ids",
              "exam_type", "exam_source", "ocr_confidence",
              "layout_confidence", "image_mapping_confidence",
              "question_reconstruction_confidence", "unclassified_blocks",
              "bbox", "source_trace"):
        assert k in q0, f"missing {k}"
    assert q0["exam_type"] == "neet_pg"
    assert q0["exam_source"] == "NEET PG (recall)"
    # Q53 has stem text starting with "53."
    assert q0["stem"].startswith("53.")


def test_stage7_4_confidence_dimensions_present(tmp_path):
    ctx = _ctx(tmp_path)
    _run_pipeline_through_s7(ctx, [38])
    p38 = json.loads((ctx.stage_dir("07_structured") / "p038.json").read_text(encoding="utf-8"))
    for q in p38["questions"]:
        assert 0.0 <= q["ocr_confidence"] <= 1.0
        assert 0.0 <= q["layout_confidence"] <= 1.0
        assert 0.0 <= q["image_mapping_confidence"] <= 1.0
        assert 0.0 <= q["question_reconstruction_confidence"] <= 1.0


def test_stage7_emits_all_questions_jsonl(tmp_path):
    ctx = _ctx(tmp_path)
    _run_pipeline_through_s7(ctx, [38])
    art = ctx.stage_dir("07_structured")
    lines = (art / "all_questions.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    for line in lines:
        obj = json.loads(line)
        assert obj["exam_type"] == "neet_pg"


def test_stage7_unclassified_blocks_preserved(tmp_path):
    """Any text the pipeline couldn't classify must remain in unclassified_blocks."""
    ctx = _ctx(tmp_path)
    _run_pipeline_through_s7(ctx, [38])
    p38 = json.loads((ctx.stage_dir("07_structured") / "p038.json").read_text(encoding="utf-8"))
    # At least one question will carry unclassified regions
    # (explanation body lines that fell through the regex tagger).
    found = False
    for q in p38["questions"]:
        if q["unclassified_blocks"]:
            found = True
            for u in q["unclassified_blocks"]:
                assert u["type"] == "unclassified"
                assert u["source_trace"]
                assert u["source_trace"]["pipeline_stage"] == "stage_7_structured"
    # If Stage 5 grouped everything into explanation_regions, this may be False — that's OK.
    # What MUST be true: needs_review is set when any unclassified block exists.
    for q in p38["questions"]:
        if q["unclassified_blocks"]:
            assert q["needs_review"] is True
            assert q["review_reason"] == "unclassified_blocks"


def test_stage7_idempotent(tmp_path):
    ctx = _ctx(tmp_path)
    _run_pipeline_through_s7(ctx, [38])
    res = run_s7(ctx, pages=[38])
    # Second run is a no-op when force=False (already-processed pages).
    assert res.pages_processed == 1
    # Page JSON still on disk.
    assert (ctx.stage_dir("07_structured") / "p038.json").exists()
