"""django-q2 task wrappers for the ingestion app.

These functions are referenced by name from the orchestrator and the
DRF views. Each one is a thin wrapper that translates a job_id into
an orchestrator call and persists the result onto the ImportJob row.

Q_CLUSTER is unchanged: ``orm`` broker, 4 workers (per
``crack_cms/settings.py``). Phase 7 raises workers if needed.
"""
from __future__ import annotations

import logging

LOG = logging.getLogger("ingestion.tasks")


def run_import_job(job_id: int) -> dict:
    """Entry point called by django-q2 when an ImportJob is dispatched.

    Reuses the same shape as ``importers.neetpg.tasks.run_recall_import``
    so operators see one consistent dispatch envelope.
    """
    from .orchestrator import run_full_pipeline_for_job
    result = run_full_pipeline_for_job(job_id)
    LOG.info("run_import_job(%s) -> %s", job_id, result.get("status"))
    return result


def cancel_import_job(job_id: int) -> dict:
    """Mark an ImportJob as cancelled (called by the cancel view)."""
    from .models import ImportJob
    from .orchestrator import cancel_job

    job = ImportJob.objects.filter(id=job_id).first()
    if not job:
        return {"job_id": job_id, "error": "job not found"}
    ok = cancel_job(job)
    return {"job_id": job_id, "cancelled": ok, "status": job.status}


def dispatch_job(job_id: int) -> str:
    """Dispatch a queued ImportJob to django-q2.

    Returns the Q2 task id. The caller (``views.py``) records the
    id back onto ``ImportJob.summary.q_task_id`` for traceability.
    """
    from django_q.tasks import async_task
    task_id = async_task("ingestion.tasks.run_import_job", job_id)
    return task_id


__all__ = ["run_import_job", "cancel_import_job", "dispatch_job"]
