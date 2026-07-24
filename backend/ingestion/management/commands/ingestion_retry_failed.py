"""ingestion_retry_failed — bulk-retry all failed / crashed / cancelled jobs.

Default behaviour mirrors POST /api/ingestion/jobs/<id>/retry/ for
every retryable job. Optionally filter by parent_exam.
"""
from django.core.management.base import BaseCommand

from ingestion.models import ImportJob
from ingestion.retry import can_retry, plan_retry
from ingestion.tasks import dispatch_job


class Command(BaseCommand):
    help = "Bulk-create retry jobs for every failed/crashed/cancelled ImportJob."

    def add_arguments(self, parser):
        parser.add_argument("--exam", default="", help="Filter by parent_exam (optional)")
        parser.add_argument("--limit", type=int, default=200)

    def handle(self, *args, **opts):
        qs = ImportJob.objects.filter(status__in=["failed", "crashed", "cancelled"]).order_by("-created_at")
        if opts["exam"]:
            qs = qs.filter(parent_exam=opts["exam"])
        qs = qs[: opts["limit"]]

        count = 0
        for original in qs:
            if not can_retry(original):
                continue
            try:
                retry_job = plan_retry(original)
            except Exception as e:  # pragma: no cover - defensive
                self.stderr.write(f"job {original.id}: {e}")
                continue
            dispatch_job(retry_job.id)
            count += 1
            self.stdout.write(self.style.SUCCESS(
                f"Retry {retry_job.id} <- {original.id} ({original.parent_exam})"
            ))
        if count == 0:
            self.stdout.write("Nothing to retry.")
        else:
            self.stdout.write(self.style.SUCCESS(f"Queued {count} retry jobs."))
