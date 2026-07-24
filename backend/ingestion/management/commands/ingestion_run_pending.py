"""ingestion_run_pending — dispatch all queued ImportJobs that have no Q2 task.

Useful for cron-driven catch-up after a worker outage. Re-dispatches
anything still in queued state.
"""
from django.core.management.base import BaseCommand

from ingestion.models import ImportJob
from ingestion.tasks import dispatch_job


class Command(BaseCommand):
    help = "Dispatch any queued ImportJob that is missing a Q2 task id."

    def handle(self, *args, **options):
        pending = ImportJob.objects.filter(status="queued").order_by("created_at")[:200]
        count = 0
        for job in pending:
            dispatch_job(job.id)
            count += 1
            self.stdout.write(self.style.SUCCESS(
                f"Dispatched job {job.id} ({job.material_asset.sha256_short})"
            ))
        if count == 0:
            self.stdout.write("No queued jobs to dispatch.")
        else:
            self.stdout.write(self.style.SUCCESS(f"Dispatched {count} jobs."))
