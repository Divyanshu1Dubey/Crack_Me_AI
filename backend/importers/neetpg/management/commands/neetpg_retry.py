"""`python manage.py neetpg_retry --job-id <id>`

Re-queue a failed or completed `QuestionImportJob` with `force=True`.
Mirrors `ImportJobRetryView` for ops use.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from questions.models import QuestionImportJob


class Command(BaseCommand):
    help = "Retry a failed/completed NEET PG recall import job."

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

        job.status = "queued"
        job.save(update_fields=["status"])
        task_id = async_task(
            "importers.neetpg.tasks.run_recall_import",
            job.id,
            job.stored_file_path,
            True,  # force
        )
        job.summary = {**(job.summary or {}), "retry_task_id": task_id}
        job.save(update_fields=["summary"])
        self.stdout.write(self.style.SUCCESS(
            f"job_id={job.id} status={job.status} task_id={task_id}"))
