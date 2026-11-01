"""ingestion_run_pending — dispatch queued ImportJobs that have no Q2 task.

Useful for catch-up after a worker outage. A queued job that already has a
``summary["q_task_id"]`` is still waiting in the django-q queue and is
skipped (re-dispatching it would let two tasks process the same job); pass
``--redispatch`` to dispatch those again as well, e.g. after the queue was
purged. The orchestrator also claims each job atomically, so a duplicate
task is a no-op.

Before dispatching it runs the stale-job recovery pass that the
``ingestion_recover_stale_jobs`` django-q Schedule runs every 10 minutes:
processing jobs whose worker died (no update for longer than the django-q
timeout + 10 min) are marked ``crashed`` and the recent ones re-queued to
resume from their checkpoint (see ``orchestrator.recover_stale_jobs``);
pass ``--no-sweep`` to skip that.
"""
from django.core.management.base import BaseCommand

from ingestion.models import ImportJob
from ingestion.orchestrator import recover_stale_jobs
from ingestion.tasks import dispatch_job


class Command(BaseCommand):
    help = "Dispatch any queued ImportJob that is missing a Q2 task id."

    def add_arguments(self, parser):
        parser.add_argument(
            "--redispatch", action="store_true",
            help="Also re-dispatch queued jobs that already have a task id.",
        )
        parser.add_argument(
            "--no-sweep", action="store_true",
            help="Do not recover stale processing jobs (worker lost) first.",
        )

    def handle(self, *args, **options):
        if not options["no_sweep"]:
            recovered = recover_stale_jobs()
            if recovered["swept"]:
                self.stdout.write(self.style.WARNING(
                    f"Marked {len(recovered['swept'])} stale processing job(s) crashed: "
                    + ", ".join(f"#{i}" for i in recovered["swept"])
                ))
            if recovered["resumed"]:
                self.stdout.write(self.style.SUCCESS(
                    f"Re-queued {len(recovered['resumed'])} of them to resume: "
                    + ", ".join(f"#{i}" for i in recovered["resumed"])
                ))
        pending = ImportJob.objects.filter(status="queued").order_by("created_at")[:200]
        count = skipped = 0
        for job in pending:
            summary = dict(job.summary or {})
            if summary.get("q_task_id") and not options["redispatch"]:
                skipped += 1
                continue
            task_id = dispatch_job(job.id)
            summary["q_task_id"] = task_id
            job.summary = summary
            job.save(update_fields=["summary", "updated_at"])
            count += 1
            self.stdout.write(self.style.SUCCESS(
                f"Dispatched job {job.id} ({job.material_asset.sha256_short})"
            ))
        if skipped:
            self.stdout.write(f"Skipped {skipped} queued job(s) that already have a task id.")
        if count == 0:
            self.stdout.write("No queued jobs to dispatch.")
        else:
            self.stdout.write(self.style.SUCCESS(f"Dispatched {count} jobs."))
