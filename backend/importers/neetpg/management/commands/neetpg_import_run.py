"""`python manage.py neetpg_import_run --source-dir <path> [--force]`

Production wrapper around `importers.neetpg.runner.run_import` that:

1. Creates a `QuestionImportJob` row with `job_type='pdf'`.
2. Streams progress to stdout.
3. Re-uses the same code path as the `/api/imports/neetpg/jobs/` POST
   endpoint, so behaviour is identical.

This command writes **into** the database; never destructive, never
hard-deletes. Re-runs are idempotent: `Question.update_or_create` is
keyed on `recall_text_hash` + `exam_type='neet_pg'`.
"""
from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from questions.models import QuestionImportJob


class Command(BaseCommand):
    help = "Run a NEET PG recall import and persist into the database (queues django_q task)."

    def add_arguments(self, parser):
        parser.add_argument("--source-dir", type=Path, required=True)
        parser.add_argument("--force", action="store_true",
                            help="Re-process sources that are already in the manifest.")

    def handle(self, *args, **opts):
        source_dir: Path = opts["source_dir"]
        if not source_dir.exists():
            raise CommandError(f"source dir not found: {source_dir}")
        force = bool(opts.get("force"))

        from django_q.tasks import async_task

        job = QuestionImportJob.objects.create(
            job_type="pdf",
            status="queued",
            source_filename=source_dir.name,
            stored_file_path=str(source_dir),
            summary={"source_dir": str(source_dir), "force": force,
                     "triggered_via": "manage.py neetpg_import_run"},
        )
        self.stdout.write(self.style.SUCCESS(
            f"Created QuestionImportJob id={job.id} status={job.status}"))

        task_id = async_task(
            "importers.neetpg.tasks.run_recall_import",
            job.id,
            str(source_dir),
            force,
        )
        job.summary["q_task_id"] = task_id
        job.save(update_fields=["summary"])

        self.stdout.write(self.style.SUCCESS(
            f"Queued django_q task {task_id}; track via "
            f"`python manage.py neetpg_status --job-id {job.id}` or "
            f"`/api/imports/neetpg/jobs/{job.id}/`"))
