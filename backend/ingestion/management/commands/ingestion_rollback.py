"""ingestion_rollback — soft-delete every ``Question`` produced by one ``ImportJob``.

Phase-1 safe: only soft-deletes (``is_active=False``). UPSC's
``Question`` table is never hard-deleted by the ingestion app.
"""
from django.core.management.base import BaseCommand

from ingestion.models import ImportJob


class Command(BaseCommand):
    help = "Soft-delete every Question tied to an ImportJob."

    def add_arguments(self, parser):
        parser.add_argument("job_id", type=int)

    def handle(self, *args, **opts):
        job_id = opts["job_id"]
        job = ImportJob.objects.filter(id=job_id).first()
        if not job:
            self.stderr.write(self.style.ERROR(f"job {job_id} not found"))
            return

        from importers.neetpg.db_writer import DjangoWriter
        writer = DjangoWriter(import_job=job)
        n = writer.rollback_for_job()
        self.stdout.write(self.style.SUCCESS(
            f"Soft-deleted {n} Question rows for job {job_id}."
        ))
