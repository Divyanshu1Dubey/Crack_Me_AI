"""`python manage.py neetpg_status [--job-id <id>] [--limit 20] [--failed-only]`

Lists recent `QuestionImportJob` rows of `job_type='pdf'` so an operator
can audit what the recall importer is doing without the admin shell.

Examples:
    python manage.py neetpg_status
    python manage.py neetpg_status --failed-only
    python manage.py neetpg_status --job-id 42
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from questions.models import QuestionImportJob


class Command(BaseCommand):
    help = "Show status of NEET PG recall import jobs."

    def add_arguments(self, parser):
        parser.add_argument("--job-id", type=int, default=None)
        parser.add_argument("--limit", type=int, default=20)
        parser.add_argument("--failed-only", action="store_true")

    def handle(self, *args, **opts):
        job_id = opts.get("job_id")
        if job_id is not None:
            job = QuestionImportJob.objects.filter(id=job_id, job_type="pdf").first()
            if not job:
                raise CommandError(f"no QuestionImportJob with id={job_id} and job_type='pdf'")
            self._print_job(job, verbose=True)
            return

        qs = QuestionImportJob.objects.filter(job_type="pdf").order_by("-created_at")
        if opts.get("failed_only"):
            qs = qs.filter(status="failed")
        qs = qs[: opts.get("limit", 20)]

        if not qs:
            self.stdout.write("No jobs match the filter.")
            return
        self.stdout.write(self.style.SUCCESS(
            f"{'id':>5}  {'status':<12}  {'source':<40}  {'pdfs':>5}  {'qs':>5}  {'imgs':>5}  created_at"))
        for j in qs:
            totals = (j.summary or {}).get("totals") or {}
            self.stdout.write(
                f"{j.id:>5}  {j.status:<12}  "
                f"{(j.source_filename or '')[:40]:<40}  "
                f"{totals.get('pdfs', 0):>5}  {totals.get('questions', 0):>5}  "
                f"{totals.get('images', 0):>5}  "
                f"{j.created_at:%Y-%m-%d %H:%M:%S}"
            )

    def _print_job(self, job, verbose: bool = False) -> None:
        self.stdout.write(self.style.SUCCESS(
            f"job_id={job.id} status={job.status} source={job.source_filename}"))
        self.stdout.write(f"  stored_file_path: {job.stored_file_path}")
        self.stdout.write(f"  created_at:       {job.created_at}")
        self.stdout.write(f"  updated_at:       {job.updated_at}")
        if verbose:
            self.stdout.write("  summary: " + str(job.summary))
            self.stdout.write("  error_report: " + str(job.error_report))
