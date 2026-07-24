"""ImporterOrchestrator — the heart of Phase 1.

Responsibilities:

  - Run the MCE pipeline (Stages 1 → 8 → db_writer → conservative_gate)
    for one ``ImportJob``.
  - Persist ``ImportJobStage`` and ``ImportLog`` rows so the dashboard
    has a per-stage timeline.
  - Save ``ImportCheckpoint`` rows so a crashed worker can resume.
  - Apply the conservative import gate (PR auto-import / NR stage /
    EF block) after Stage 8.
  - Update ``ImportJob.status`` and counters on every transition.

The orchestrator NEVER modifies the MCE. It calls each stage through
the stable ``run(ctx, *, pages=None)`` signature defined in
``mce/stages/__init__.py``.
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Optional

from django.conf import settings
from django.utils import timezone

from .checkpoint import latest_checkpoint, save_checkpoint
from .constants import (
    JOB_CANCELLED,
    JOB_COMPLETED,
    JOB_CRASHED,
    JOB_FAILED,
    JOB_PROCESSING,
    JOB_QUEUED,
    PIPELINE_ORDER,
    STAGE_CONSERVATIVE_GATE,
)
from .exceptions import InvalidJobTransitionError
from .models import BatchRun, ImportJob, ImportLog, MaterialAsset
from .pipeline_stages import load_summary_json, record_stage8_artifacts, run_mce_stage

LOG = logging.getLogger("ingestion.orchestrator")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _artefact_root(material: MaterialAsset) -> Path:
    """Where the orchestrator writes per-job MCE artefacts.

    Independent of the MCE's own `_artifacts_benchmark_post_fix` so
    production runs do not collide with benchmark runs.
    """
    root = Path(getattr(settings, "INGESTION_ARTEFACT_ROOT",
                       Path(settings.BASE_DIR) / "_artifacts_ingestion"))
    sha16 = material.sha256_short
    p = root / sha16
    p.mkdir(parents=True, exist_ok=True)
    return p


def _log(job: ImportJob, level: str, message: str, stage_name: str = "",
         context: Optional[dict] = None) -> ImportLog:
    return ImportLog.objects.create(
        job=job,
        level=level,
        stage_name=stage_name,
        message=message[:8000],
        context=context or {},
    )


def _transition(job: ImportJob, *, to_status: str, **fields) -> None:
    """Transition ``job.status`` enforcing the JOB_TRANSITIONS table.

    Updates optional fields atomically with the status flip.
    """
    from .constants import JOB_TRANSITIONS
    allowed = JOB_TRANSITIONS.get(job.status, set())
    if to_status not in allowed and to_status != job.status:
        raise InvalidJobTransitionError(
            f"Cannot transition job {job.id} from {job.status} -> {to_status}"
        )
    job.status = to_status
    update_fields = ["status", "updated_at"]
    for k, v in fields.items():
        setattr(job, k, v)
        update_fields.append(k)
    job.save(update_fields=update_fields)


def _build_mce_context(material: MaterialAsset, artefact_root: Path):
    """Build the MCE MceContext for one material."""
    from mce.profiles import get_profile_for_filename
    from mce.stages import MceContext

    pdf_path = Path(material.storage_path)
    full = material.sha256
    profile = get_profile_for_filename(material.original_filename)
    return MceContext(
        pdf_path=pdf_path,
        pdf_filename=material.original_filename,
        pdf_sha256=full,
        pdf_sha256_short=material.sha256_short,
        page_count=material.page_count or _infer_page_count(pdf_path),
        profile=profile,
        artefact_root=artefact_root,
        pdf_metadata=material.meta or {},
    )


def _infer_page_count(pdf_path: Path) -> int:
    """Cheap best-effort page count when MaterialAsset didn't carry it."""
    try:
        from importers.neetpg.pdf_reader import open_pdf, page_count
        doc = open_pdf(pdf_path)
        try:
            return int(page_count(doc))
        finally:
            doc.close()
    except Exception:
        return 0


def run_full_pipeline_for_job(job_id: int) -> dict:
    """Top-level entry point. Called by ``tasks.run_import_job``.

    Returns a summary dict suitable for the django-q2 result.
    """
    job = ImportJob.objects.filter(id=job_id).select_related("material_asset").first()
    if job is None:
        return {"job_id": job_id, "error": "job not found"}

    # Idempotency: if the job is already in a terminal state, no-op.
    if job.status in (JOB_COMPLETED, JOB_CANCELLED):
        return {"job_id": job_id, "status": job.status, "noop": True}

    if job.status == JOB_QUEUED:
        _transition(job, to_status=JOB_PROCESSING, started_at=timezone.now())

    material = job.material_asset
    artefact_root = _artefact_root(material)

    ctx = _build_mce_context(material, artefact_root)
    ck = latest_checkpoint(job)
    last_stage = ck.last_completed_stage if ck else ""
    resume_page = ck.last_processed_page if ck and ck.last_processed_stage == last_stage else None

    summary = {
        "job_id": job.id,
        "sha16": material.sha256_short,
        "artefact_root": str(artefact_root),
        "started_at": timezone.now().isoformat(),
    }

    try:
        for stage_name in PIPELINE_ORDER:
            # Cancellation check at every stage boundary.
            job.refresh_from_db(fields=["status"])
            if job.status == JOB_CANCELLED:
                _log(job, "WARNING", f"Job cancelled before {stage_name}", stage_name)
                return {"job_id": job.id, "status": JOB_CANCELLED, "stage": stage_name}

            # Skip stages that are already complete on resume.
            if last_stage and PIPELINE_ORDER.index(stage_name) <= PIPELINE_ORDER.index(last_stage):
                _log(job, "INFO", f"Skipping {stage_name} (resumed past it)", stage_name)
                continue

            _log(job, "INFO", f"Starting {stage_name}", stage_name)
            try:
                run_mce_stage(
                    job=job,
                    stage_name=stage_name,
                    ctx=ctx,
                    resume_from_page=resume_page if stage_name == last_stage else None,
                )
            except Exception as e:
                _log(job, "ERROR", f"Stage {stage_name} failed: {e}", stage_name)
                _transition(job, to_status=JOB_FAILED, completed_at=timezone.now(),
                            error={"stage": stage_name, "message": str(e)})
                return {"job_id": job.id, "status": JOB_FAILED, "stage": stage_name,
                        "error": str(e)}

            save_checkpoint(
                job=job,
                material=material,
                last_completed_stage=stage_name,
                last_processed_page=ctx.page_count,
                current_page=ctx.page_count,
                artifact_root=artefact_root,
                artifact_sha16=material.sha256_short,
                checkpoint_data={"stage_metrics": "ok"},
            )

            job.refresh_from_db(fields=["status", "current_stage", "current_page",
                                        "total_pages", "progress_pct"])
            job.current_stage = stage_name
            job.current_page = ctx.page_count
            job.total_pages = ctx.page_count or job.total_pages
            job.progress_pct = round(
                100.0 * (PIPELINE_ORDER.index(stage_name) + 1) / len(PIPELINE_ORDER), 1
            )
            job.save(update_fields=["current_stage", "current_page", "total_pages",
                                    "progress_pct", "updated_at"])

        # Stage 8 artefacts: record so the conservative gate can find them.
        record_stage8_artifacts(job, artefact_root)

        # Conservative gate
        from .conservative_gate import apply_qa_v2_verdict
        counts = apply_qa_v2_verdict(job=job, artefact_root=artefact_root)
        summary["verdict"] = counts
        summary["summary_json"] = load_summary_json(artefact_root)

        # Stage DB writer runs as part of the pipeline above (Stage
        # ``db_writer``). After Stage 8 the QA verdict decides what
        # actually lands in `questions.Question`. Mark complete.
        _transition(job, to_status=JOB_COMPLETED, completed_at=timezone.now())
        _log(job, "INFO",
             f"Job completed PR={counts['pr']} NR={counts['nr']} EF={counts['ef']} "
             f"imported={counts['imported']} staged={counts['staged']}",
             STAGE_CONSERVATIVE_GATE)
        summary["status"] = JOB_COMPLETED
        summary["completed_at"] = timezone.now().isoformat()
        return summary
    except Exception as e:
        LOG.exception("Unhandled error in orchestrator for job %s", job.id)
        _log(job, "ERROR", f"Orchestrator crashed: {e}", "")
        _transition(job, to_status=JOB_CRASHED, completed_at=timezone.now(),
                    error={"message": str(e)})
        return {"job_id": job.id, "status": JOB_CRASHED, "error": str(e)}


def create_job(
    *,
    material: MaterialAsset,
    parent_exam: str,
    created_by=None,
    batch: Optional[BatchRun] = None,
    config: Optional[dict] = None,
) -> ImportJob:
    """Create a new queued ``ImportJob`` for ``material``.

    Does NOT dispatch to django-q2 — the caller decides whether to
    dispatch via ``tasks.dispatch_job``.
    """
    return ImportJob.objects.create(
        material_asset=material,
        batch_run=batch,
        parent_exam=parent_exam,
        status=JOB_QUEUED,
        config=config or {"strategy": "auto-pr-only", "force": False},
        created_by=created_by,
    )


def cancel_job(job: ImportJob) -> bool:
    """Mark a job as cancelled. Returns True if the transition was valid."""
    try:
        if job.status == JOB_COMPLETED:
            return False
        _transition(job, to_status=JOB_CANCELLED, completed_at=timezone.now())
        _log(job, "WARNING", "Job cancelled by operator", "")
        return True
    except InvalidJobTransitionError:
        return False


def create_retry_job(original: ImportJob, *, created_by=None) -> ImportJob:
    """Create a retry job pointing at ``original`` via ``retry_of``."""
    return ImportJob.objects.create(
        material_asset=original.material_asset,
        batch_run=original.batch_run,
        retry_of=original,
        version=original.version + 1,
        parent_exam=original.parent_exam,
        status=JOB_QUEUED,
        config=original.config or {"strategy": "auto-pr-only", "force": True},
        created_by=created_by,
    )


__all__ = [
    "run_full_pipeline_for_job",
    "create_job",
    "cancel_job",
    "create_retry_job",
]
