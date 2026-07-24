"""Conservative import gate — apply QA V2 verdict and act.

This is the SINGLE place where ``questions.Question`` is written from
the ingestion framework. The conservative policy (Phase 1) is:

  - QA V2 "Production Ready"   → auto-import via the existing
                                 `importers.neetpg.db_writer.DjangoWriter`
                                 (already idempotent on
                                 ``recall_text_hash + exam_type``).
  - QA V2 "Needs Review"       → staged into ``StagedQuestion`` for
                                 Phase 2 admin triage. NO write to
                                 ``questions.Question``.
  - QA V2 "Extraction Failure" → staged into ``StagedQuestion`` with
                                 ``review_status='blocked'`` and
                                 ``failure_reason`` populated. NO
                                 write to ``questions.Question``.

The strategy is configurable per-job via ``ImportJob.config.strategy``
(defaults to ``auto-pr-only``). Two extra strategies exist for
forward compatibility:

  - ``auto-all``   : also auto-import Needs Review (currently
                     deactivated, but the bucket is honoured if set).
  - ``manual``     : nothing auto-imports; everything goes to staging.

Nothing here mutates the QA V2 thresholds. The verdict is the
single source of truth.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from django.db import transaction

from .constants import (
    QA_EXTRACTION_FAILURE,
    QA_NEEDS_REVIEW,
    QA_PRODUCTION_READY,
    REVIEW_BLOCKED,
    REVIEW_PENDING,
    STRATEGY_AUTO_ALL,
    STRATEGY_AUTO_PR_ONLY,
)
from .models import ImportJob, StagedQuestion
from .pipeline_stages import load_per_question_qa

LOG = logging.getLogger("ingestion.conservative_gate")


def _strategy(job: ImportJob) -> str:
    cfg = job.config or {}
    return (cfg.get("strategy") or STRATEGY_AUTO_PR_ONLY).strip()


def _authorise_writer():
    """Lazy import of DjangoWriter so we don't import the legacy
    importers package at module import time."""
    from importers.neetpg.db_writer import DjangoWriter
    return DjangoWriter


def _stage_question(
    *,
    job: ImportJob,
    qa_status: str,
    review_status: str,
    payload: dict,
    page_number: int,
    question_number_in_pdf: int,
    failing_axes: list[str],
    failure_reason: str = "",
    failure_log_paths: Optional[list[str]] = None,
) -> StagedQuestion:
    return StagedQuestion.objects.create(
        job=job,
        material_asset=job.material_asset,
        qa_status=qa_status,
        review_status=review_status,
        page_number=page_number,
        question_number_in_pdf=question_number_in_pdf,
        question_payload=payload,
        failing_axes=failing_axes,
        failure_reason=failure_reason,
        failure_log_paths=failure_log_paths or [],
    )


def _import_production_ready(
    *,
    job: ImportJob,
    pr_payloads: list[dict],
) -> tuple[int, int, list[int]]:
    """Call DjangoWriter for each PR payload. Returns (created, updated, staged_ids).

    We snapshot ``WriterStats`` counters before and after; the writer
    already maintains those counters correctly via
    ``update_or_create`` return values (see
    ``importers/neetpg/db_writer.py``).
    """
    if not pr_payloads:
        return (0, 0, [])
    WriterCls = _authorise_writer()
    writer = WriterCls(import_job=None)
    pre_created = writer.stats.questions_created
    pre_updated = writer.stats.questions_updated
    for payload in pr_payloads:
        try:
            from importers.neetpg.models import ParsedQuestion, ParsedOption
            opts = []
            for o in (payload.get("options") or []):
                if isinstance(o, dict):
                    label = (o.get("label") or "").strip()[:1].upper() or "A"
                    opts.append(ParsedOption(label=label, text=o.get("text") or ""))
                else:
                    opts.append(ParsedOption(label="A", text=str(o)))
            pq = ParsedQuestion(
                source_sha16=job.material_asset.sha256_short,
                page_number=int(payload.get("page_number") or 0),
                question_number_in_pdf=int(payload.get("question_number_in_pdf") or 0),
                raw=payload.get("raw") or "",
                stem=payload.get("stem") or "",
                stem_raw=payload.get("stem_raw") or "",
                options=opts,
                answer_labels=payload.get("answer_labels") or [],
                explanation=payload.get("explanation") or "",
                confidence_score=float(payload.get("confidence_score") or 0.0),
            )
            from importers.neetpg.fingerprints import Fingerprint
            asset = job.material_asset
            fp = Fingerprint(
                pdf_filename=asset.original_filename,
                pdf_path=asset.storage_path,
                pdf_sha256=asset.sha256,
                pdf_sha256_short=asset.sha256_short,
                size_bytes=asset.file_size,
                page_count=asset.page_count or 0,
                is_encrypted=False,
                mtime=0.0,
                metadata=asset.meta or {},
            )
            rs = writer.upsert_recall_source(
                Path(asset.storage_path),
                fp,
                scan_type="recall",
                recall_status="recall",
            )
            writer.write_question(pq, rs)
        except Exception as e:  # pragma: no cover - defensive
            LOG.exception("DjangoWriter failed for PR question on page %s: %s",
                          payload.get("page_number"), e)
            _stage_question(
                job=job,
                qa_status=QA_NEEDS_REVIEW,
                review_status=REVIEW_PENDING,
                payload=payload,
                page_number=int(payload.get("page_number") or 0),
                question_number_in_pdf=int(payload.get("question_number_in_pdf") or 0),
                failing_axes=["writer_error"],
                failure_reason=f"DjangoWriter raised: {e}",
            )
    created = writer.stats.questions_created - pre_created
    updated = writer.stats.questions_updated - pre_updated
    return (created, updated, [])


@transaction.atomic
def apply_qa_v2_verdict(
    *,
    job: ImportJob,
    artefact_root: Path,
) -> dict[str, int]:
    """Apply the conservative import gate after Stage 8.

    Returns counts: ``{"pr": int, "nr": int, "ef": int, "staged": int, "imported": int}``.

    Behaviour:
      - PR counts per ImportJob summary, written via DjangoWriter.
      - NR + EF create ``StagedQuestion`` rows; ``questions.Question``
        is NOT touched.
      - The ``strategy`` field on ``job.config`` selects between
        ``auto-pr-only`` (default) / ``auto-all`` / ``manual``.
    """
    strategy = _strategy(job)
    counts = {"pr": 0, "nr": 0, "ef": 0, "staged": 0, "imported": 0}

    per_q = load_per_question_qa(artefact_root)
    if not per_q:
        LOG.warning("No per_question_qa.json for job %s — skipping gate.", job.id)
        return counts

    pr_payloads: list[dict] = []
    for row in per_q:
        status = row.get("status")
        payload = row.get("payload") or {}
        page = int(row.get("page_number") or payload.get("page_number") or 0)
        qno = int(row.get("question_number_in_pdf") or payload.get("question_number_in_pdf") or 0)
        failing = list(row.get("failing_axes") or [])

        if status == QA_PRODUCTION_READY:
            counts["pr"] += 1
            if strategy in (STRATEGY_AUTO_PR_ONLY, STRATEGY_AUTO_ALL):
                pr_payloads.append(payload)
            else:
                _stage_question(
                    job=job,
                    qa_status=QA_PRODUCTION_READY,
                    review_status=REVIEW_PENDING,
                    payload=payload,
                    page_number=page,
                    question_number_in_pdf=qno,
                    failing_axes=[],
                )
                counts["staged"] += 1
        elif status == QA_NEEDS_REVIEW:
            counts["nr"] += 1
            _stage_question(
                job=job,
                qa_status=QA_NEEDS_REVIEW,
                review_status=REVIEW_PENDING,
                payload=payload,
                page_number=page,
                question_number_in_pdf=qno,
                failing_axes=failing,
                failure_reason="Needs Review: " + ", ".join(failing),
            )
            counts["staged"] += 1
        elif status == QA_EXTRACTION_FAILURE:
            counts["ef"] += 1
            _stage_question(
                job=job,
                qa_status=QA_EXTRACTION_FAILURE,
                review_status=REVIEW_BLOCKED,
                payload=payload,
                page_number=page,
                question_number_in_pdf=qno,
                failing_axes=failing,
                failure_reason="Extraction Failure: " + ", ".join(failing),
                failure_log_paths=[
                    str(artefact_root / "08_qa" / "overlays" / f"p{page:03d}.png"),
                ],
            )
            counts["staged"] += 1
        else:
            LOG.warning("Unknown QA status %s for job %s page %s", status, job.id, page)

    # Only run the writer for the auto strategies.
    if strategy in (STRATEGY_AUTO_PR_ONLY, STRATEGY_AUTO_ALL) and pr_payloads:
        created, updated, _ = _import_production_ready(job=job, pr_payloads=pr_payloads)
        counts["imported"] = created + updated

    # Persist the QA percentages on the job for the dashboard.
    total = sum(v for v in (counts["pr"], counts["nr"], counts["ef"]) if v)
    if total > 0:
        job.qa_v2_production_ready_pct = round(100.0 * counts["pr"] / total, 2)
        job.qa_v2_needs_review_pct = round(100.0 * counts["nr"] / total, 2)
        job.qa_v2_extraction_failure_pct = round(100.0 * counts["ef"] / total, 2)
        job.qa_v2_total_questions = total
    job.questions_imported = counts["imported"]
    job.questions_staged_nr = counts["nr"]
    job.questions_staged_ef = counts["ef"]
    job.save(update_fields=[
        "qa_v2_production_ready_pct",
        "qa_v2_needs_review_pct",
        "qa_v2_extraction_failure_pct",
        "qa_v2_total_questions",
        "questions_imported",
        "questions_staged_nr",
        "questions_staged_ef",
    ])
    LOG.info(
        "Job %s gate verdict: PR=%s NR=%s EF=%s imported=%s staged=%s (strategy=%s)",
        job.id, counts["pr"], counts["nr"], counts["ef"],
        counts["imported"], counts["staged"], strategy,
    )
    return counts


__all__ = ["apply_qa_v2_verdict"]
