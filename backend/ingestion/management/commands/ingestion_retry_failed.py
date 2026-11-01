"""ingestion_retry_failed — bulk-retry all failed / crashed / cancelled jobs.

Default behaviour mirrors POST /api/ingestion/jobs/<id>/retry/ for
every retryable job. Optionally filter by exam: a job created without one
(the bulk-ingestion script) matches on its material's exam hint, as in the
job list API.
"""
from django.core.management.base import BaseCommand
from django.db.models import Q

from ingestion.models import ImportJob
from ingestion.orchestrator import exam_hint_spellings
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
            exam = opts["exam"]
            qs = qs.filter(
                Q(parent_exam=exam)
                | Q(parent_exam="", material_asset__exam_hint__in=exam_hint_spellings(exam))
            )
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
            task_id = dispatch_job(retry_job.id)
            retry_job.summary = {"q_task_id": task_id, "retry_of_job": original.id}
            retry_job.save(update_fields=["summary"])
            count += 1
            self.stdout.write(self.style.SUCCESS(
                f"Retry {retry_job.id} <- {original.id} ({original.parent_exam})"
            ))
        if count == 0:
            self.stdout.write("Nothing to retry.")
        else:
            self.stdout.write(self.style.SUCCESS(f"Queued {count} retry jobs."))
