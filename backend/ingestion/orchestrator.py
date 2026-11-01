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
from datetime import timedelta
from pathlib import Path
from typing import Optional

from django.conf import settings
from django.utils import timezone

from .checkpoint import latest_checkpoint, save_checkpoint
from .constants import (
    EXAM_CHOICES,
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
from .models import BatchRun, ImportJob, ImportJobStage, ImportLog, MaterialAsset
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


_EXAM_CODES = {code for code, _label in EXAM_CHOICES}
# Spellings older tooling stored in MaterialAsset.exam_hint
# (scripts/run_bulk_ingestion.py writes "inicet" / "neetpg").
_EXAM_HINT_ALIASES = {
    "inicet": "ini_cet",
    "ini-cet": "ini_cet",
    "neetpg": "neet_pg",
    "neet-pg": "neet_pg",
}


def normalize_exam_hint(hint: Optional[str]) -> str:
    """A MaterialAsset.exam_hint as an exam code (``ini_cet``…), or ''."""
    value = (hint or "").strip().lower()
    if value in _EXAM_CODES:
        return value
    return _EXAM_HINT_ALIASES.get(value, "")


def exam_hint_spellings(exam: str) -> list[str]:
    """Every exam_hint value that means ``exam`` (the code itself + aliases)."""
    return sorted({exam} | {alias for alias, code in _EXAM_HINT_ALIASES.items() if code == exam})


def effective_exam(job: ImportJob) -> str:
    """The job's exam; for a job created without one, its material's exam hint."""
    if job.parent_exam:
        return job.parent_exam
    material = getattr(job, "material_asset", None)
    return normalize_exam_hint(getattr(material, "exam_hint", "")) if material else ""


def _profile_for(material: MaterialAsset, exam: Optional[str]):
    """The MCE exam profile for this job: the exam the admin chose.

    A job created without an exam (the bulk-ingestion script) uses its
    material's exam hint. Only when neither is known do we fall back to
    guessing from the file name (which defaults to NEET PG). The chosen exam
    used to be ignored, so an "INI-CET" upload was processed — and
    imported — as whatever its file name suggested.
    """
    from mce.profiles import get_profile, get_profile_for_filename

    exam = exam or normalize_exam_hint(getattr(material, "exam_hint", ""))
    if exam:
        try:
            return get_profile(exam)
        except KeyError:
            LOG.warning("Unknown exam %r for material %s; guessing from file name",
                        exam, material.sha256_short)
    return get_profile_for_filename(material.original_filename)


def _build_mce_context(material: MaterialAsset, artefact_root: Path, exam: Optional[str] = None):
    """Build the MCE MceContext for one material."""
    from mce.stages import MceContext

    pdf_path = Path(material.storage_path)
    full = material.sha256
    profile = _profile_for(material, exam)
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


def stale_processing_after() -> timedelta:
    """How long a ``processing`` job may go without an update before it is dead.

    Longer than the django-q task timeout (``Q_CLUSTER['timeout']``, plus ten
    minutes): django-q kills a task at that timeout, so a job nothing has
    touched for longer has no live worker any more. The job row is updated
    at every stage boundary. Override with the
    ``INGESTION_STALE_PROCESSING_SECONDS`` setting.
    """
    explicit = getattr(settings, "INGESTION_STALE_PROCESSING_SECONDS", None)
    if explicit:
        return timedelta(seconds=int(explicit))
    q_timeout = int((getattr(settings, "Q_CLUSTER", None) or {}).get("timeout") or 3600)
    return timedelta(seconds=q_timeout + 600)


def run_full_pipeline_for_job(job_id: int) -> dict:
    """Top-level entry point. Called by ``tasks.run_import_job``.

    Returns a summary dict suitable for the django-q2 result.
    """
    job = ImportJob.objects.filter(id=job_id).select_related("material_asset").first()
    if job is None:
        return {"job_id": job_id, "error": "job not found"}

    # A job is claimed atomically (conditional UPDATE): two tasks for the
    # same job (a re-dispatch, a duplicate catch-up run) must never process
    # it concurrently.
    #   * queued      → claimed and run.
    #   * processing  → a no-op while its worker is alive. If nothing has
    #     touched it for longer than any live worker could run
    #     (stale_processing_after), its worker died (timeout, OOM, deploy
    #     restart) and this delivery — normally django-q re-delivering the
    #     task — takes it over and resumes from its last checkpoint.
    #   * anything else → no-op; failed / crashed jobs are re-run through a
    #     retry job instead.
    if job.status not in (JOB_QUEUED, JOB_PROCESSING):
        return {"job_id": job_id, "status": job.status, "noop": True}
    now = timezone.now()
    resumed = job.status == JOB_PROCESSING
    if resumed:
        claimed = ImportJob.objects.filter(
            id=job.id, status=JOB_PROCESSING, updated_at__lt=now - stale_processing_after(),
        ).update(updated_at=now)
    else:
        claimed = ImportJob.objects.filter(id=job.id, status=JOB_QUEUED).update(
            status=JOB_PROCESSING, started_at=now, updated_at=now,
        )
    if not claimed:
        job.refresh_from_db(fields=["status"])
        return {"job_id": job_id, "status": job.status, "noop": True}
    if resumed:
        _close_interrupted_stages(job.id, "worker lost; the job was resumed")
        _log(job, "WARNING",
             f"Resuming job: no progress since {job.updated_at.isoformat()} (its worker was lost); "
             "continuing from the last checkpoint.")
    else:
        job.status = JOB_PROCESSING
        job.started_at = now
    # A job created without an exam (the bulk-ingestion script) takes its
    # material's exam hint, so the profile and the importer agree on it.
    if not job.parent_exam:
        exam = normalize_exam_hint(job.material_asset.exam_hint)
        if exam:
            job.parent_exam = exam
            ImportJob.objects.filter(id=job.id, parent_exam="").update(parent_exam=exam)
    _refresh_batch_counters(job.batch_run_id)

    try:
        return _run_claimed_job(job)
    finally:
        _refresh_batch_counters(job.batch_run_id)


def _refresh_batch_counters(batch_id: Optional[int]) -> None:
    """Recompute a BatchRun's counters and status from its jobs.

    ``completed_jobs`` / ``failed_jobs`` were never updated, so batch pages
    read "running · 0 completed · 0 failed" whatever happened.
    """
    if not batch_id:
        return
    from .constants import BATCH_CANCELLED, BATCH_DONE, BATCH_RUNNING
    batch = BatchRun.objects.filter(id=batch_id).first()
    if batch is None:
        return
    statuses = list(batch.jobs.values_list("status", flat=True))
    completed = sum(1 for s in statuses if s == JOB_COMPLETED)
    failed = sum(1 for s in statuses if s in (JOB_FAILED, JOB_CRASHED))
    cancelled = sum(1 for s in statuses if s == JOB_CANCELLED)
    terminal = completed + failed + cancelled
    status = batch.status
    if batch.status != BATCH_CANCELLED:
        if statuses and terminal == len(statuses):
            status = BATCH_CANCELLED if cancelled == len(statuses) else BATCH_DONE
        elif statuses:
            status = BATCH_RUNNING
    BatchRun.objects.filter(id=batch_id).update(
        completed_jobs=completed, failed_jobs=failed, status=status,
        updated_at=timezone.now(),
    )


def _run_claimed_job(job: ImportJob) -> dict:
    """Run the pipeline for a job this worker has claimed (status=processing)."""
    material = job.material_asset
    artefact_root = _artefact_root(material)

    ctx = _build_mce_context(material, artefact_root, exam=job.parent_exam)
    ck = latest_checkpoint(job)
    last_stage = ck.last_completed_stage if ck else ""
    resume_page = ck.last_processed_page if ck and ck.last_completed_stage == last_stage else None

    summary = {
        "job_id": job.id,
        "sha16": material.sha256_short,
        "artefact_root": str(artefact_root),
        "started_at": timezone.now().isoformat(),
    }

    # The conservative_gate is a post-MCE gate that is NOT an MCE stage —
    # it does not appear in pipeline_stages._STAGE_CALLABLES. Run it
    # OUTSIDE the MCE loop so the orchestrator's pipeline_order stops at
    # stage_db_writer; we then invoke the gate directly.
    mce_pipeline = [s for s in PIPELINE_ORDER if s != STAGE_CONSERVATIVE_GATE]

    # Post-extraction stages (graph + RAG) are best-effort enrichment. If
    # they fail, the conservative gate can still run from the QA artefacts
    # that Stage 8 already produced. Don't fail the whole job on them.
    POST_EXTRACTION_STAGES = {"9_graph", "10_rag"}

    try:
        for stage_name in mce_pipeline:
            # Cancellation check at every stage boundary.
            job.refresh_from_db(fields=["status"])
            if job.status == JOB_CANCELLED:
                _log(job, "WARNING", f"Job cancelled before {stage_name}", stage_name)
                return {"job_id": job.id, "status": JOB_CANCELLED, "stage": stage_name}

            # Skip stages that are already complete on resume.
            if last_stage and mce_pipeline.index(stage_name) <= mce_pipeline.index(last_stage):
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
                if stage_name in POST_EXTRACTION_STAGES:
                    _log(job, "WARNING",
                         f"Post-extraction stage {stage_name} failed (non-fatal): {e}",
                         stage_name)
                    # Save a checkpoint so we know we tried.
                    save_checkpoint(
                        job=job,
                        material=material,
                        last_completed_stage=stage_name,
                        last_processed_page=ctx.page_count,
                        current_page=ctx.page_count,
                        artifact_root=artefact_root,
                        artifact_sha16=material.sha256_short,
                        checkpoint_data={"stage_metrics": "failed-non-fatal"},
                    )
                    continue
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

        # Conservative gate — record its own ImportJobStage row.
        gate_row = ImportJobStage.objects.create(
            job=job,
            stage_name=STAGE_CONSERVATIVE_GATE,
            status="running",
        )
        try:
            from .conservative_gate import apply_qa_v2_verdict
            counts = apply_qa_v2_verdict(job=job, artefact_root=artefact_root)
            gate_row.status = "completed"
            gate_row.metrics = counts
            gate_row.save(update_fields=["status", "metrics"])
        except Exception as e:
            gate_row.status = "failed"
            gate_row.errors = [str(e)]
            gate_row.save(update_fields=["status", "errors"])
            raise
        summary["verdict"] = counts
        summary["summary_json"] = load_summary_json(artefact_root)

        # The ``db_writer`` stage above only emits artefacts; the gate is the
        # only writer of `questions.Question` (QA V2 Production Ready rows,
        # with the job's exam). Mark complete.
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
        job.refresh_from_db(fields=["status"])
        try:
            _transition(job, to_status=JOB_CRASHED, completed_at=timezone.now(),
                        error={"message": str(e)})
        except InvalidJobTransitionError:
            # e.g. cancelled while the failing stage ran: keep that status.
            pass
        return {"job_id": job.id, "status": job.status, "error": str(e)}


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
        _refresh_batch_counters(job.batch_run_id)
        return True
    except InvalidJobTransitionError:
        return False


def sweep_stale_processing_jobs(*, older_than: Optional[timedelta] = None,
                                dry_run: bool = False) -> list[int]:
    """Mark ``processing`` jobs whose worker died as ``crashed``.

    A worker that died mid-job (django-q timeout, OOM, deploy restart)
    leaves its job ``processing`` for ever: only queued jobs are started,
    and a re-delivered task only resumes a job once it is stale. Jobs
    nothing has touched for ``older_than`` (default:
    ``stale_processing_after()``) are moved to ``crashed`` with a log line,
    so the dashboard shows them as crashed and the retry path (the Retry
    button, ``ingestion_retry_failed``) applies. Each move is a conditional
    UPDATE, so a job a worker resumed in the meantime is left alone.

    Returns the ids of the jobs swept (or that would be, with ``dry_run``).
    """
    window = older_than or stale_processing_after()
    cutoff = timezone.now() - window
    stale = list(
        ImportJob.objects.filter(status=JOB_PROCESSING, updated_at__lt=cutoff)
        .only("id", "batch_run_id", "current_stage", "updated_at")
    )
    if dry_run:
        return [j.id for j in stale]
    swept: list[int] = []
    for job in stale:
        now = timezone.now()
        message = (
            f"No progress since {job.updated_at.isoformat()} (more than "
            f"{int(window.total_seconds() // 60)} min): the worker was lost. Retry the job."
        )
        moved = ImportJob.objects.filter(
            id=job.id, status=JOB_PROCESSING, updated_at__lt=cutoff,
        ).update(
            status=JOB_CRASHED, completed_at=now, updated_at=now,
            error={"stage": job.current_stage or "", "message": message, "swept": True},
        )
        if not moved:
            continue
        swept.append(job.id)
        _close_interrupted_stages(job.id, "worker lost (stale-job sweeper)")
        _log(job, "ERROR", f"Marked crashed by the stale-job sweeper. {message}", job.current_stage or "")
        _refresh_batch_counters(job.batch_run_id)
    return swept


def _close_interrupted_stages(job_id: int, reason: str) -> int:
    """Mark stage rows a dead worker left ``running`` as failed (timeline only)."""
    return ImportJobStage.objects.filter(job_id=job_id, status="running").update(
        status="failed", completed_at=timezone.now(), errors=[reason],
    )


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
    "effective_exam",
    "exam_hint_spellings",
    "normalize_exam_hint",
    "stale_processing_after",
    "sweep_stale_processing_jobs",
]
