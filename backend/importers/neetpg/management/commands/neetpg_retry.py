"""`python manage.py neetpg_retry --job-id <id>`

Re-queue a failed or completed `QuestionImportJob` with `force=True`.
Mirrors `ImportJobRetryView` for ops use. The job is re-run by the importer
that created it (`summary["importer"]`; jobs without one are NEET PG's), so
an INI-CET job is never re-imported as NEET PG.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from questions.models import QuestionImportJob

TASK_BY_IMPORTER = {
    "neetpg": "importers.neetpg.tasks.run_recall_import",
    "inicet": "importers.inicet.tasks.run_recall_import",
}


class Command(BaseCommand):
    help = "Retry a failed/completed NEET PG or INI-CET recall import job."

    def add_arguments(self, parser):
        parser.add_argument("--job-id", type=int, required=True)

    def handle(self, *args, **opts):
        from django_q.tasks import async_task

        job_id = opts["job_id"]
        job = QuestionImportJob.objects.filter(id=job_id, job_type="pdf").first()
        if not job:
            raise CommandError(f"no QuestionImportJob id={job_id} (job_type='pdf')")
        if job.status not in ("failed", "completed"):
            raise CommandError(
                f"job {job_id} status is {job.status}; only 'failed' or 'completed' can be retried"
            )
        importer = (job.summary or {}).get("importer") or "neetpg"
        task_path = TASK_BY_IMPORTER.get(importer)
        if task_path is None:
            raise CommandError(f"job {job_id} was created by an unknown importer {importer!r}")

        job.status = "queued"
        job.save(update_fields=["status"])
        task_id = async_task(
            task_path,
            job.id,
            job.stored_file_path,
            True,  # force
        )
        job.summary = {**(job.summary or {}), "retry_task_id": task_id}
        job.save(update_fields=["summary"])
        self.stdout.write(self.style.SUCCESS(
            f"job_id={job.id} importer={importer} status={job.status} task_id={task_id}"))
