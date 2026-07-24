"""Regression tests for MCE sub-stage 2.12 (Stages 9, 10, DB writer).

Run: cd backend && python -m pytest mce/tests/test_stage_9_10_and_db.py -v
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
from mce.stages.stage_9_graph import run as run_s9
from mce.stages.stage_10_rag import run as run_s10
from mce.stages.stage_db_writer import run as run_db


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


def _pipeline_through_s8(ctx: MceContext, pages: list[int]) -> None:
    run_s1(ctx, pages=pages)
    run_s2(ctx, pages=pages)
    run_s3(ctx, pages=pages)
    run_s5(ctx, pages=pages)
    run_s6(ctx, pages=pages)
    run_s7(ctx, pages=pages)
    run_s8(ctx, pages=pages)


def test_stage9_emits_graph_nodes_edges(tmp_path):
    ctx = _ctx(tmp_path)
    _pipeline_through_s8(ctx, [38])
    res = run_s9(ctx, pages=[38])
    art = ctx.stage_dir("09_graph")
    nodes = (art / "nodes.jsonl").read_text(encoding="utf-8").strip().splitlines()
    edges = (art / "edges.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert res.metrics["nodes"] == len(nodes)
    assert res.metrics["edges"] == len(edges)
    assert len(nodes) >= 1
    for line in nodes:
        obj = json.loads(line)
        assert obj["type"]
        assert obj["name"]
    for line in edges:
        obj = json.loads(line)
        assert obj["src"] and obj["dst"]
        assert obj["weight"]


def test_stage10_emits_rag_chunks_per_question(tmp_path):
    ctx = _ctx(tmp_path)
    _pipeline_through_s8(ctx, [38])
    res = run_s10(ctx, pages=[38])
    art = ctx.stage_dir("10_rag")
    chunks = (art / "chunks.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert res.metrics["chunks"] == len(chunks)
    # Each parsed question emits at minimum: stem, options, answer, image_caption chunks.
    assert res.metrics["chunks"] >= 4
    for line in chunks:
        obj = json.loads(line)
        assert obj["chunk_id"].startswith("chk_")
        assert obj["chunk_type"]
        assert obj["body"]


def test_stage_db_writer_emits_phase3_queue(tmp_path):
    """Even when no PASS pages exist, the Phase-3 queue is emitted."""
    ctx = _ctx(tmp_path)
    _pipeline_through_s8(ctx, [38])
    res = run_db(ctx, pages=[38])
    queue = ctx.stage_dir("00_meta") / "db_new_tables_queue.jsonl"
    assert queue.exists()
    lines = queue.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == res.metrics["pending_for_phase3"]
    # Each row has the Phase-3 payload shape.
    for line in lines:
        obj = json.loads(line)
        assert obj["kind"] == "phase3_assets"
        assert obj["question_id"]
        assert "page_number" in obj
        # source_trace preserved.
        assert obj["source_trace"]


def test_stage_db_writer_gated_by_pass(tmp_path):
    """When no PASS pages exist, ORM writes are skipped but queue still emits."""
    ctx = _ctx(tmp_path)
    _pipeline_through_s8(ctx, [38])
    res = run_db(ctx, pages=[38])
    # Stage 8 on page 38 reported FAIL -> pass_pages is empty -> ORM skipped.
    if res.metrics["skipped_due_to_qa"] > 0:
        assert res.metrics["questions_created"] == 0
        assert res.metrics["images_created"] == 0
        assert res.metrics["pending_for_phase3"] >= res.metrics["skipped_due_to_qa"]
