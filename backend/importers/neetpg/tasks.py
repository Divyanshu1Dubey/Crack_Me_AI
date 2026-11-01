"""Async tasks executed by django_q.

Phase 2 keeps the runner self-contained — these wrappers just translate
a job_id + source_dir into a runner call and persist the result onto
`QuestionImportJob`.
"""
from __future__ import annotations

import logging
from pathlib import Path

LOG = logging.getLogger(__name__)

INTERRUPTED_MESSAGE = (
    "The import stopped before it finished (the worker hit its time limit or was "
    "restarted). Retry the job; split a very large folder into smaller ones."
)


def refuse_redelivery(job) -> dict | None:
    """Why this delivery must not run ``job`` (a result dict), or None to run it.

    Only a queued job is run: the API, the CLI and retry all queue a job
    before dispatching its task. A job still ``processing`` means an earlier
    delivery started the run and its worker was killed (django-q timeout,
    restart): django-q re-presents an unacknowledged task every
    ``Q_CLUSTER['retry']`` seconds, so running it again would restart a run
    that cannot finish, every hour, for ever. Such a job is marked failed
    (Retry re-queues it); any other state is a late duplicate (no-op).
    """
    if job.status == "queued":
        return None
    if job.status == "processing":
        job.status = "failed"
        job.error_report = (job.error_report or []) + [{"stage": "runner", "message": INTERRUPTED_MESSAGE}]
        job.save(update_fields=["status", "error_report", "updated_at"])
        LOG.warning("run_recall_import: job %s was interrupted by a lost worker; marked failed", job.id)
        return {"job_id": job.id, "status": "failed", "interrupted": True}
    return {"job_id": job.id, "status": job.status, "noop": True}


def run_recall_import(job_id: int, source_dir: str, force: bool = False) -> dict:
    """Run the recall importer and persist results onto a QuestionImportJob row.

    This is the entrypoint used by both the CLI runner and the
    `/api/imports/neetpg/jobs/` POST endpoint.
    """
    from questions.models import QuestionImportJob
    from .config import get_config
    from .runner import run_import

    job = QuestionImportJob.objects.filter(id=job_id).first()
    if not job:
        LOG.error("run_recall_import: job_id=%s not found", job_id)
        return {"job_id": job_id, "error": "job not found"}
    refused = refuse_redelivery(job)
    if refused is not None:
        return refused

    job.status = "processing"
    job.save(update_fields=["status"])

    try:
        cfg = get_config()
        result = run_import(Path(source_dir), cfg=cfg, force=force, import_job_id=job.id)
        job.status = "completed"
        job.summary = {
            **(job.summary or {}),
            "run_id": result.get("run_id"),
            "summaries": result.get("summaries", []),
            "totals": {
                "pdfs": len(result.get("summaries", [])),
                "questions": sum(s.get("question_count", 0) for s in result.get("summaries", [])),
                "images": sum(s.get("image_count", 0) for s in result.get("summaries", [])),
            },
        }
        job.save(update_fields=["status", "summary", "updated_at"])
        return job.summary
    except Exception as e:  # pragma: no cover - defensive
        LOG.exception("run_recall_import failed: job_id=%s", job_id)
        job.status = "failed"
        job.error_report = (job.error_report or []) + [{
            "stage": "runner",
            "message": str(e),
        }]
        job.save(update_fields=["status", "error_report", "updated_at"])
        return {"job_id": job_id, "error": str(e)}