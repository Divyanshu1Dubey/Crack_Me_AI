"""DB writer stage — emits the Phase-3 queue; it no longer writes live rows.

This stage used to create ``questions.Question`` rows (plus RecallSource /
QuestionSource / QuestionImage) for every question on a Stage-8 PASS page,
BEFORE the conservative QA gate ran: questions rated Needs Review or
Extraction Failure by QA V2 went live, unanswered questions went live
with answer "A", unresolved subjects got ``Subject.objects.first()``, the
exam came from the file name, and image rows had neither file nor URL.

The ingestion conservative gate (``ingestion.conservative_gate``) is now the
ONLY writer of ``questions.Question`` for this pipeline: it imports only
QA V2 "Production Ready" questions, uses the job's chosen exam, never
defaults an answer, and persists the Stage-3 image files. This stage keeps
its slot in the pipeline for the artefact below, and reports how many
questions sit on non-PASS pages (``skipped_due_to_qa``) for the dashboard.

New-table rows (Phase 3 deferred):

    QuestionAsset, QuestionPearl, QuestionReference, Concept,
    QuestionConcept, ConceptEdge

These go to ``db_new_tables_queue.jsonl`` so Phase 3 has the data ready
when the migrations land. The queue file is committed to source so the
Phase 3 writer can ingest it without re-running the pipeline.

This stage is intentionally idempotent: re-running it rewrites the same
queue file and touches no database table.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from mce.stages import MceContext, StageResult


LOG = logging.getLogger("mce.stage_db_writer")


@dataclass
class DbWriterStats:
    recall_sources_created: int = 0
    questions_created: int = 0
    questions_updated: int = 0
    images_created: int = 0
    images_deduped: int = 0
    question_sources_created: int = 0
    pending_for_phase3: int = 0
    skipped_due_to_qa: int = 0


def _normalize_text(text: str) -> str:
    """Lightweight normalisation for dedup hashes — matches the legacy
    `backend/questions/text_encoding.py.normalize_text` contract."""
    import re
    text = (text or "").lower()
    text = re.sub(r"\[(?:image|fig|figure)[^\]]*\]|\b(?:q|question|ans|answer|exp|explanation)\s*[:\-\.]?\s*", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _text_sha256(text: str) -> str:
    return hashlib.sha256(_normalize_text(text).encode("utf-8")).hexdigest()


def _pass_pages_for_pdf(artefact_root: Path) -> set[int]:
    summary = artefact_root / "08_qa" / "summary.json"
    if not summary.exists():
        return set()
    rep = (artefact_root / "08_qa" / "per_page_report.json")
    if not rep.exists():
        return set()
    try:
        per_page = json.loads(rep.read_text(encoding="utf-8"))
    except Exception:
        return set()
    return {int(pn) for pn, info in per_page.items() if info.get("status") == "PASS"}


def _load_stage3_images(stage3_dir: Path, page_number: int) -> list[dict[str, Any]]:
    p = stage3_dir / f"p{page_number:03d}.json"
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("images", [])
    except Exception:
        return []


def run(ctx: MceContext, *, pages: Optional[list[int]] = None,
        force: bool = False) -> StageResult:
    """Emit the Phase-3 queue. Never writes ``questions.Question``.

    Live rows are written only by the ingestion conservative gate, after
    QA V2 has rated each question (see module docstring).
    """
    res = StageResult(stage="stage_db_writer")
    stats = DbWriterStats()
    artefact_root = ctx.artefact_root

    pass_pages = _pass_pages_for_pdf(artefact_root)

    stage7_index = ctx.stage_dir("07_structured") / "_index.json"
    if not stage7_index.exists():
        res.errors.append("Stage 7 index missing")
        return res
    try:
        s7 = json.loads(stage7_index.read_text(encoding="utf-8"))
        questions = s7.get("questions", [])
    except Exception as e:
        res.errors.append(f"stage 7 read failed: {e}")
        return res

    if pages:
        pages_set = set(pages)
        questions = [q for q in questions if int(q["page_number"]) in pages_set]

    # ---- New-table queue file (Phase 3 deferred). ----
    queue_path = artefact_root / "00_meta" / "db_new_tables_queue.jsonl"
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    if force or not queue_path.exists():
        queue_path.write_text("", encoding="utf-8")

    with queue_path.open("a", encoding="utf-8") as qf:
        for q in questions:
            page = int(q.get("page_number", 0))
            qf.write(json.dumps({
                "kind": "phase3_assets",
                "question_id": q["id"],
                "page_number": page,
                "clinical_pearl": q.get("clinical_pearl"),
                "high_yield_points": q.get("high_yield_points", []),
                "mnemonic": q.get("mnemonic"),
                "references": q.get("references", []),
                "asset_ids": q.get("asset_ids", []),
                "captions": q.get("captions", []),
                "is_image_based": bool(q.get("image_ids")),
                "needs_review": bool(q.get("needs_review")),
                "source_trace": q.get("source_trace"),
            }, ensure_ascii=False) + "\n")
            stats.pending_for_phase3 += 1
            if page not in pass_pages:
                stats.skipped_due_to_qa += 1

    res.metrics = {**stats.__dict__, "orm_writes": False}
    LOG.info(
        "stage_db_writer: %d queued for Phase 3, %d on non-PASS pages "
        "(no ORM writes; the conservative gate is the only Question writer)",
        stats.pending_for_phase3, stats.skipped_due_to_qa,
    )
    return res


def _guess_year(filename: str) -> int:
    import re
    m = re.search(r"\b(20\d{2})\b", filename or "")
    return int(m.group(1)) if m else 0


__all__ = ["run", "DbWriterStats"]
