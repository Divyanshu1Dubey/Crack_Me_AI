"""Pipeline stages — thin bridge to MCE stages 1..10 + db_writer.

Every MCE stage has the same signature
``def run(ctx: MceContext, *, pages: list[int] | None = None) -> StageResult``.
This module wraps each one with logging, error capture and stage-row
creation. The orchestrator calls these wrappers, NOT the bare MCE
stages, so every stage invocation is observable.

Stage 7.5 (LLM) and Stages 9/10 are best-effort: a missing LLM
key or empty graph is silently downgraded to ``skipped`` rather
than aborting the job.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from mce.stages import MceContext, StageResult

from .constants import (
    ARTIFACT_QA_PER_QUESTION_JSON,
    ARTIFACT_QA_SUMMARY_JSON,
    STAGE_10_RAG,
    STAGE_1_RENDER,
    STAGE_2B_READING_ORDER,
    STAGE_2_LAYOUT,
    STAGE_3_IMAGES,
    STAGE_4_TABLES,
    STAGE_5_QUESTION_BLOCKS,
    STAGE_6_OCR,
    STAGE_7_5_LLM,
    STAGE_7_STRUCTURED,
    STAGE_8_QA,
    STAGE_9_GRAPH,
    STAGE_DB_WRITER,
)
from .models import ImportArtifact, ImportJob, ImportJobStage

LOG = logging.getLogger("ingestion.pipeline_stages")


# Mapping: stage name → (module path, callable). Lazy-loaded to avoid
# importing every MCE stage at module import time.
_STAGE_CALLABLES = {
    STAGE_1_RENDER: ("mce.stages.stage_1_render", "run"),
    STAGE_2_LAYOUT: ("mce.stages.stage_2_layout", "run"),
    STAGE_2B_READING_ORDER: ("mce.stages.stage_2b_reading_order", "run"),
    STAGE_3_IMAGES: ("mce.stages.stage_3_images", "run"),
    STAGE_4_TABLES: ("mce.stages.stage_4_tables", "run"),
    STAGE_5_QUESTION_BLOCKS: ("mce.stages.stage_5_question_blocks", "run"),
    STAGE_6_OCR: ("mce.stages.stage_6_ocr", "run"),
    STAGE_7_STRUCTURED: ("mce.stages.stage_7_structured", "run"),
    STAGE_7_5_LLM: ("mce.stages.stage_7_5_llm", "run"),
    STAGE_8_QA: ("mce.stages.stage_8_qa", "run"),
    STAGE_DB_WRITER: ("mce.stages.stage_db_writer", "run"),
    STAGE_9_GRAPH: ("mce.stages.stage_9_graph", "run"),
    STAGE_10_RAG: ("mce.stages.stage_10_rag", "run"),
}


def _import_callable(stage_name: str):
    """Lazy import so we don't pay for every stage at module load."""
    if stage_name not in _STAGE_CALLABLES:
        raise ValueError(f"Unknown stage: {stage_name}")
    module_path, attr = _STAGE_CALLABLES[stage_name]
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, attr)


def _start_stage_row(job: ImportJob, stage_name: str) -> ImportJobStage:
    return ImportJobStage.objects.create(job=job, stage_name=stage_name, status="running")


def _finish_stage_row(row: ImportJobStage, *, result: Optional[StageResult], error: Optional[str] = None) -> None:
    """Persist the stage outcome back onto the ImportJobStage row."""
    from django.utils import timezone
    row.completed_at = timezone.now()
    if error:
        row.status = "failed"
        row.errors = (row.errors or []) + [error]
    elif result is None:
        row.status = "skipped"
    else:
        row.status = "completed"
        row.pages_processed = result.pages_processed
        row.pages_skipped = result.pages_skipped
        row.artefacts_written = result.artefacts_written
        row.warnings = list(result.warnings or [])
        row.errors = list(result.errors or [])
        row.metrics = dict(result.metrics or {})
    row.save()


def run_mce_stage(
    *,
    job: ImportJob,
    stage_name: str,
    ctx: MceContext,
    resume_from_page: Optional[int] = None,
) -> Optional[StageResult]:
    """Run one MCE stage, record the outcome on ImportJobStage.

    Returns the StageResult on success, None if the stage was
    skipped (Stage 7.5 without LLM key, etc.).

    If the stage raises, the row is marked ``failed`` and the
    exception is re-raised so the orchestrator can update job.status.
    """
    # Stage 7.5 is optional — silently skip if the LLM key is absent
    if stage_name == STAGE_7_5_LLM:
        try:
            _import_callable(stage_name)
        except Exception as e:  # pragma: no cover - stage not available
            row = _start_stage_row(job, stage_name)
            _finish_stage_row(row, result=None, error=f"stage import failed: {e}")
            LOG.warning("Stage 7.5 unavailable for job %s: %s", job.id, e)
            return None

    row = _start_stage_row(job, stage_name)
    pages = [resume_from_page] if resume_from_page else None
    try:
        fn = _import_callable(stage_name)
        result = fn(ctx, pages=pages) if pages else fn(ctx)
    except Exception as e:
        LOG.exception("Stage %s failed for job %s", stage_name, job.id)
        _finish_stage_row(row, result=None, error=str(e))
        raise
    _finish_stage_row(row, result=result)
    return result


def record_stage8_artifacts(job: ImportJob, artefact_root: Path) -> None:
    """After Stage 8 we register pointers to per_question_qa.json + summary.json.

    These two files are the canonical inputs of the conservative gate.
    """
    sha16 = job.material_asset.sha256_short
    for kind, filename, sha_holder in (
        (ARTIFACT_QA_PER_QUESTION_JSON, "08_qa/per_question_qa.json", None),
        (ARTIFACT_QA_SUMMARY_JSON, "08_qa/summary.json", None),
    ):
        rel = filename
        full = artefact_root / rel
        bytes_ = full.stat().st_size if full.exists() else 0
        sha = ""
        if sha_holder is not None:
            sha = sha_holder
        ImportArtifact.objects.update_or_create(
            job=job,
            kind=kind,
            defaults={
                "sha16_short": sha16,
                "path_rel": rel,
                "bytes": bytes_,
                "sha256": sha,
            },
        )


def load_per_question_qa(artefact_root: Path) -> list[dict]:
    """Read the per-question QA JSON that Stage 8 emits."""
    p = artefact_root / "08_qa" / "per_question_qa.json"
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # pragma: no cover
        LOG.warning("Failed to read per_question_qa.json: %s", e)
        return []


def load_summary_json(artefact_root: Path) -> dict:
    """Read the Stage 8 summary.json."""
    p = artefact_root / "08_qa" / "summary.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # pragma: no cover
        return {}


__all__ = [
    "run_mce_stage",
    "record_stage8_artifacts",
    "load_per_question_qa",
    "load_summary_json",
]
