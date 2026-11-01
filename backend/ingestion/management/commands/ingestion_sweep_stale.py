"""ingestion_sweep_stale — mark processing jobs whose worker died as crashed.

A worker that dies mid-job (django-q timeout, OOM, deploy restart) leaves
its ImportJob ``processing`` for ever. This command moves every processing
job that nothing has updated for longer than the stale window (default:
the django-q task timeout + 10 min, see
``orchestrator.stale_processing_after``) to ``crashed``, so it shows up as
crashed and can be retried (Retry button, ``ingestion_retry_failed``).

``ingestion_run_pending`` runs the same sweep first, so a cron that runs the
catch-up command needs nothing else.

    python manage.py ingestion_sweep_stale --dry-run
    python manage.py ingestion_sweep_stale [--older-than-minutes 90]
"""
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError

from ingestion.orchestrator import stale_processing_after, sweep_stale_processing_jobs


class Command(BaseCommand):
    help = "Mark processing ImportJobs that stopped updating (worker lost) as crashed."

    def add_arguments(self, parser):
        parser.add_argument(
            "--older-than-minutes", type=int, default=None,
            help="Stale window in minutes (default: django-q timeout + 10 min).",
        )
        parser.add_argument("--dry-run", action="store_true", help="List the jobs without changing them.")

    def handle(self, *args, **opts):
        minutes = opts["older_than_minutes"]
        if minutes is not None and minutes <= 0:
            raise CommandError("--older-than-minutes must be positive.")
        window = timedelta(minutes=minutes) if minutes else stale_processing_after()
        ids = sweep_stale_processing_jobs(older_than=window, dry_run=opts["dry_run"])
        if not ids:
            self.stdout.write("No stale processing jobs.")
            return
        verb = "Would mark" if opts["dry_run"] else "Marked"
        self.stdout.write(self.style.WARNING(
            f"{verb} {len(ids)} job(s) crashed (no update for {int(window.total_seconds() // 60)} min): "
            + ", ".join(f"#{i}" for i in ids)
        ))
