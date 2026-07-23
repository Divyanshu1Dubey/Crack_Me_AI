"""Async tasks executed by django_q.

Phase 2 keeps the runner self-contained — these wrappers just translate
a job_id + source_dir into a runner call and persist the result onto
`QuestionImportJob`.
"""
from __future__ import annotations

import logging
from pathlib import Path

LOG = logging.getLogger(__name__)


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