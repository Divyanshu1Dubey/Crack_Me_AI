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
(defaults to ``auto-pr-only``):

  - ``manual``     : nothing auto-imports; everything goes to staging.
  - ``auto-all``   : NOT offered any more (it was listed as "import Needs
                     Review too" but never did). Legacy jobs that still
                     carry it behave exactly like ``auto-pr-only`` and the
                     gate logs that.

Even a Production Ready question is held back (staged as Needs Review,
with the reason in ``failing_axes``) when it cannot be stored faithfully:
no single valid A–D answer, an option beyond D, a subject that cannot be
resolved, an attached Stage-3 image whose file is missing, or an answer /
explanation label in the stem or an option (the stem and the options are
public text, so the label would give the answer away; see
``questions.answer_leak``).

Questions are written with the job's exam (``ImportJob.parent_exam``),
and their ``QuestionSource.import_job_id`` is stamped ``ingestion:<job id>``
so ``ingestion_rollback`` removes exactly this job's questions.

The gate is idempotent per job: a job resumed after its worker died (same
job id) may run it a second time, so the job's staged rows nobody has acted
on are replaced, never duplicated, and a question whose staged row already
carries a review decision is not staged again. PR imports are idempotent in
``DjangoWriter``.

Nothing here mutates the QA V2 thresholds. The verdict is the
single source of truth.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from django.db import transaction

from questions.answer_leak import label_hold_reasons

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


VALID_ANSWERS = ("A", "B", "C", "D")
OPTION_LABELS = "ABCDEFGHIJ"


def source_job_ref(job: ImportJob) -> str:
    """``QuestionSource.import_job_id`` value for questions this job wrote.

    Namespaced so it can never match a legacy ``QuestionImportJob`` id.
    """
    return f"ingestion:{job.id}"


def _strategy(job: ImportJob) -> str:
    cfg = job.config or {}
    strategy = (cfg.get("strategy") or STRATEGY_AUTO_PR_ONLY).strip()
    if strategy == STRATEGY_AUTO_ALL:
        LOG.warning(
            "Job %s uses retired strategy 'auto-all'; Needs Review questions are "
            "never auto-imported — treating it as 'auto-pr-only'.", job.id,
        )
        return STRATEGY_AUTO_PR_ONLY
    return strategy


def _load_stage3_images(artefact_root: Path) -> dict[str, dict]:
    """``{image_id: Stage-3 record}`` across every ``03_images/p*.json``."""
    out: dict[str, dict] = {}
    images_dir = artefact_root / "03_images"
    if not images_dir.exists():
        return out
    for page_file in sorted(images_dir.glob("p*.json")):
        try:
            data = json.loads(page_file.read_text(encoding="utf-8"))
        except Exception as e:  # pragma: no cover - corrupt artefact
            LOG.warning("Could not load %s: %s", page_file, e)
            continue
        for rec in (data.get("images") or []):
            if isinstance(rec, dict) and rec.get("id"):
                out[rec["id"]] = rec
    return out


def _image_record(rec: dict, source_sha16: str):
    """Stage-3 image dict → the recall writer's ``ImageRecord``."""
    from importers.neetpg.models import ImageRecord
    from questions.models import QuestionImage

    modality = rec.get("modality") or "other"
    if modality not in {c[0] for c in QuestionImage.MODALITY_CHOICES}:
        modality = "other"
    return ImageRecord(
        source_sha16=rec.get("source_sha16") or source_sha16,
        page_number=int(rec.get("page_number") or 0),
        image_index_in_page=int(rec.get("image_index_in_page") or 0),
        file_path=rec.get("file_path") or "",
        mime=rec.get("mime") or "image/png",
        width=int(rec.get("width") or 0),
        height=int(rec.get("height") or 0),
        bytes=int(rec.get("bytes") or 0),
        sha256=rec.get("sha256") or "",
        sha256_short=rec.get("sha256_short") or "",
        phash=(rec.get("phash") or "")[:16],
        dhash=(rec.get("dhash") or "")[:16],
        modality=modality,
        caption=rec.get("caption") or "",
        caption_source=rec.get("caption_source") or "none",
        extraction_confidence=float(rec.get("extraction_confidence") or 0.0),
    )


def _resolve_subject_name(payload: dict, filename: str) -> Optional[str]:
    """Subject name from the payload, else the recall keyword / filename mapper."""
    name = (payload.get("subject") or "").strip()
    if name:
        return name
    from importers.neetpg import topic_mapper
    return topic_mapper.map_subject(
        payload.get("stem") or "",
        fallback=topic_mapper.fallback_subject_from_filename(filename or ""),
    )


def _load_stage7_payloads(artefact_root: Path) -> dict[str, dict]:
    """Load all Stage 7 structured outputs into ``{qid: question_payload}``.

    Walks ``<artefact_root>/07_structured/p*.json`` (one per page), each
    containing a ``questions`` array. Builds the dict keyed by the
    question id (``p<page>_q<nn>``) so the conservative gate can join it
    with the QA V2 per-question summary by id.
    """
    out: dict[str, dict] = {}
    structured_dir = artefact_root / "07_structured"
    if not structured_dir.exists():
        LOG.warning("Stage 7 structured dir missing: %s", structured_dir)
        return out
    for page_file in sorted(structured_dir.glob("p*.json")):
        try:
            import json as _json
            data = _json.loads(page_file.read_text(encoding="utf-8"))
        except Exception as e:
            LOG.warning("Could not load %s: %s", page_file, e)
            continue
        for q in (data.get("questions") or []):
            if isinstance(q, dict) and q.get("id"):
                out[q["id"]] = q
    LOG.info("Loaded %d Stage 7 payloads from %s", len(out), structured_dir)
    return out


def _authorise_writer():
    """Lazy import of DjangoWriter so we don't import the legacy
    importers package at module import time."""
    from importers.neetpg.db_writer import DjangoWriter
    return DjangoWriter


def _staged_key(page_number: int, question_number_in_pdf: int, payload: dict) -> tuple:
    return (int(page_number or 0), int(question_number_in_pdf or 0), str((payload or {}).get("id") or ""))


def _reset_undecided_staging(job: ImportJob) -> set[tuple]:
    """Clear what an earlier run of the gate staged for ``job`` (resume path).

    Rows nobody has acted on (still pending / blocked, no review note, not
    published) are deleted so this run stages them again exactly once. Rows
    with a review decision are kept; their keys are returned so the gate
    does not stage those questions a second time.
    """
    rows = StagedQuestion.objects.filter(job=job)
    rows.filter(
        review_status__in=(REVIEW_PENDING, REVIEW_BLOCKED),
        published_question__isnull=True,
        review_note="",
    ).delete()
    return {
        _staged_key(page, qno, payload)
        for page, qno, payload in rows.values_list("page_number", "question_number_in_pdf", "question_payload")
    }


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
    decided: Optional[set] = None,
) -> Optional[StagedQuestion]:
    if decided and _staged_key(page_number, question_number_in_pdf, payload) in decided:
        return None  # already staged and reviewed by an earlier run of the gate
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


def _parsed_options(payload: dict):
    """Payload options → ``ParsedOption`` list, labelling unlabeled ones by position.

    (Unlabeled options used to all become "A" and overwrite each other.)
    """
    from importers.neetpg.models import ParsedOption

    opts = []
    for idx, o in enumerate(payload.get("options") or []):
        fallback = OPTION_LABELS[idx] if idx < len(OPTION_LABELS) else "?"
        if isinstance(o, dict):
            label = (o.get("label") or "").strip()[:1].upper() or fallback
            opts.append(ParsedOption(label=label, text=o.get("text") or ""))
        else:
            opts.append(ParsedOption(label=fallback, text=str(o)))
    return opts


def _hold_reasons(payload: dict, options, subject_row, image_recs, image_ids) -> list[str]:
    """Why a Production Ready payload cannot be stored faithfully (empty = OK)."""
    reasons: list[str] = []
    labels = {
        (lbl or "").strip().upper()[:1]
        for lbl in (payload.get("answer_labels") or [])
        if (lbl or "").strip()
    }
    if len(labels) != 1 or not labels <= set(VALID_ANSWERS):
        reasons.append("answer_not_single_a_to_d")
    if any(o.label not in VALID_ANSWERS and (o.text or "").strip() for o in options):
        reasons.append("option_beyond_d")
    if subject_row is None:
        reasons.append("subject_unresolved")
    for iid in image_ids:
        rec = image_recs.get(iid)
        if not rec or not rec.get("file_path") or not Path(rec["file_path"]).is_file():
            reasons.append("image_file_missing")
            break
    # 'answer_label_in_public_text' / 'explanation_label_in_public_text':
    # every viewer sees the stem and the options, so a glued-in answer key or
    # explanation must not go live.
    reasons.extend(label_hold_reasons(payload.get("stem") or "", [o.text for o in options]))
    return reasons


def _import_production_ready(
    *,
    job: ImportJob,
    pr_payloads: list[dict],
    artefact_root: Optional[Path] = None,
    decided: Optional[set] = None,
) -> tuple[int, int, int]:
    """Write each PR payload through DjangoWriter. Returns (created, updated, held).

    The writer is exam-scoped to ``job.parent_exam`` and stamps the
    namespaced ``source_job_ref``; it never overwrites admin-corrected rows.
    Payloads that cannot be stored faithfully are staged for review
    (``held``) instead of being written.
    """
    if not pr_payloads:
        return (0, 0, 0)
    from importers.neetpg.models import ParsedQuestion
    from importers.neetpg.fingerprints import Fingerprint

    WriterCls = _authorise_writer()
    writer = WriterCls(import_job=None, exam_type=job.parent_exam,
                       source_job_ref=source_job_ref(job))
    pre_created = writer.stats.questions_created
    pre_updated = writer.stats.questions_updated
    held = 0
    asset = job.material_asset
    image_recs = _load_stage3_images(artefact_root) if artefact_root else {}
    # One RecallSource per PDF, created before the per-question savepoints
    # so a failing question cannot roll it back from under the others.
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
    recall_source = writer.upsert_recall_source(
        Path(asset.storage_path), fp,
        scan_type="recall", recall_status="recall",
    )

    for payload in pr_payloads:
        page = int(payload.get("page_number") or 0)
        qno = int(payload.get("question_number_in_pdf") or 0)
        try:
            options = _parsed_options(payload)
            subject_name = _resolve_subject_name(payload, asset.original_filename)
            subject_row = writer._subject_row_for(subject_name) if subject_name else None
            image_ids = [i for i in (payload.get("image_ids") or []) if i]
            reasons = _hold_reasons(payload, options, subject_row, image_recs, image_ids)
            if reasons:
                held += 1
                _stage_question(
                    job=job,
                    qa_status=QA_NEEDS_REVIEW,
                    review_status=REVIEW_PENDING,
                    payload=payload,
                    page_number=page,
                    question_number_in_pdf=qno,
                    failing_axes=reasons,
                    failure_reason="Production Ready but held for review: " + ", ".join(reasons),
                    decided=decided,
                )
                continue

            pq = ParsedQuestion(
                source_sha16=asset.sha256_short,
                page_number=page,
                question_number_in_pdf=qno,
                raw=payload.get("raw") or "",
                stem=payload.get("stem") or "",
                stem_raw=payload.get("stem_raw") or "",
                options=options,
                answer_labels=payload.get("answer_labels") or [],
                explanation=payload.get("explanation") or "",
                confidence_score=float(payload.get("confidence_score") or 0.0),
                subject=subject_name,
                is_image_based=bool(image_ids),
            )
            with transaction.atomic():
                question = writer.write_question(pq, recall_source, subject=subject_row)
                if question is not None:
                    for iid in image_ids:
                        writer.write_image(
                            _image_record(image_recs[iid], asset.sha256_short),
                            question, recall_source,
                        )
        except Exception as e:  # pragma: no cover - defensive
            LOG.exception("DjangoWriter failed for PR question on page %s: %s", page, e)
            held += 1
            _stage_question(
                job=job,
                qa_status=QA_NEEDS_REVIEW,
                review_status=REVIEW_PENDING,
                payload=payload,
                page_number=page,
                question_number_in_pdf=qno,
                failing_axes=["writer_error"],
                failure_reason=f"DjangoWriter raised: {e}",
                decided=decided,
            )
    created = writer.stats.questions_created - pre_created
    updated = writer.stats.questions_updated - pre_updated
    # Added up: a second run of the gate for the same job (resume) counts
    # only images it newly creates or links; a question's existing image is
    # returned by write_image without touching the stats.
    job.images_imported = (job.images_imported or 0) + writer.stats.images_created + writer.stats.images_linked
    return (created, updated, held)


@transaction.atomic
def apply_qa_v2_verdict(
    *,
    job: ImportJob,
    artefact_root: Path,
) -> dict[str, int]:
    """Apply the conservative import gate after Stage 8.

    Returns counts: ``{"pr", "nr", "ef", "staged", "imported", "held"}``.

    Behaviour:
      - PR questions are written via DjangoWriter (exam = job.parent_exam),
        except those ``held`` for review (see module docstring).
      - NR + EF create ``StagedQuestion`` rows; ``questions.Question``
        is NOT touched.
      - The ``strategy`` field on ``job.config`` selects between
        ``auto-pr-only`` (default) / ``manual`` (legacy ``auto-all`` =
        ``auto-pr-only``).
    """
    strategy = _strategy(job)
    counts = {"pr": 0, "nr": 0, "ef": 0, "staged": 0, "imported": 0, "held": 0}

    per_q = load_per_question_qa(artefact_root)
    if not per_q:
        LOG.warning("No per_question_qa.json for job %s — skipping gate.", job.id)
        return counts

    # A second run for the same job (resumed after its worker died) replaces
    # the rows the first run staged instead of adding duplicates.
    decided = _reset_undecided_staging(job)

    # Stage 7 structured payloads keyed by question id (e.g. "p001_q00").
    # The QA V2 summary is keyed the same way; we join on the id.
    stage7_payloads = _load_stage7_payloads(artefact_root)

    # Normalise: ``per_q`` may be a dict (qid → qa row) or a list of
    # (qid, qa row) tuples from json.load.  Force (qid, row) iteration.
    if isinstance(per_q, dict):
        items = list(per_q.items())
    else:
        items = []
        for row in per_q or []:
            if isinstance(row, dict):
                qid = row.get("id") or row.get("question_id")
                items.append((qid, row))

    pr_payloads: list[dict] = []
    for qid, row in items:
        status = row.get("status")
        payload = row.get("payload") or {}
        # Merge with Stage 7 payload (always has stem, options, answer).
        if qid and qid in stage7_payloads:
            payload = {**stage7_payloads[qid], **payload}
        page = int(row.get("page_number") or payload.get("page_number") or 0)
        qno = int(row.get("question_number_in_pdf") or payload.get("question_number_in_pdf") or 0)
        failing = list(row.get("failing_axes") or [])

        if status == QA_PRODUCTION_READY:
            counts["pr"] += 1
            if strategy == STRATEGY_AUTO_PR_ONLY:
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
                    decided=decided,
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
                decided=decided,
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
                decided=decided,
            )
            counts["staged"] += 1
        else:
            LOG.warning("Unknown QA status %s for job %s page %s", status, job.id, page)

    # Only run the writer for the auto strategy.
    if strategy == STRATEGY_AUTO_PR_ONLY and pr_payloads:
        created, updated, held = _import_production_ready(
            job=job, pr_payloads=pr_payloads, artefact_root=artefact_root, decided=decided,
        )
        counts["imported"] = created + updated
        counts["held"] = held
        counts["staged"] += held

    # Persist the QA percentages on the job for the dashboard.
    total = sum(v for v in (counts["pr"], counts["nr"], counts["ef"]) if v)
    if total > 0:
        job.qa_v2_production_ready_pct = round(100.0 * counts["pr"] / total, 2)
        job.qa_v2_needs_review_pct = round(100.0 * counts["nr"] / total, 2)
        job.qa_v2_extraction_failure_pct = round(100.0 * counts["ef"] / total, 2)
        job.qa_v2_total_questions = total
    job.questions_imported = counts["imported"]
    # Held-back PR questions sit in the review queue as Needs Review rows.
    job.questions_staged_nr = counts["nr"] + counts["held"]
    job.questions_staged_ef = counts["ef"]
    job.save(update_fields=[
        "qa_v2_production_ready_pct",
        "qa_v2_needs_review_pct",
        "qa_v2_extraction_failure_pct",
        "qa_v2_total_questions",
        "questions_imported",
        "questions_staged_nr",
        "questions_staged_ef",
        "images_imported",
    ])
    LOG.info(
        "Job %s gate verdict: PR=%s NR=%s EF=%s imported=%s staged=%s (strategy=%s)",
        job.id, counts["pr"], counts["nr"], counts["ef"],
        counts["imported"], counts["staged"], strategy,
    )
    return counts


__all__ = ["apply_qa_v2_verdict"]
