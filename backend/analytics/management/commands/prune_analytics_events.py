"""Retention for the public analytics ingest table (AnalyticsEvent).

POST /api/analytics/events/ is open to every visitor, so the table only
grows; the admin dashboard reads the last 30 days. This command deletes the
rows older than ``--days``. It is a dry run unless ``--apply`` is given, and
it never deletes the server-written ledger rows other features read back
(analytics.views.SERVER_ONLY_EVENTS: the quest-streak freeze ledger and the
XP-ledger start marker).

    python manage.py prune_analytics_events                     # dry run, 400 days
    python manage.py prune_analytics_events --days 180 --apply  # delete

Nothing runs it automatically: deleting data is an owner decision. To keep
the table bounded, schedule the --apply form (cron / platform job, or a
django-q Schedule) once the retention period is chosen.
"""
from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

DEFAULT_DAYS = 400
# The admin dashboard (views_internal.AnalyticsDashboardDataView) reads 30 days.
MIN_DAYS = 31
DEFAULT_BATCH_SIZE = 2000


class Command(BaseCommand):
    help = 'Delete AnalyticsEvent rows older than --days (dry run unless --apply).'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=DEFAULT_DAYS,
                            help=f'Keep this many days of events (default {DEFAULT_DAYS}, minimum {MIN_DAYS}).')
        parser.add_argument('--apply', action='store_true',
                            help='Delete the rows. Without it the command only reports what it would delete.')
        parser.add_argument('--batch-size', type=int, default=DEFAULT_BATCH_SIZE,
                            help=f'Rows deleted per statement (default {DEFAULT_BATCH_SIZE}).')

    def handle(self, *args, **options):
        from analytics.models import AnalyticsEvent
        from analytics.views import SERVER_ONLY_EVENTS

        days = options['days']
        if days < MIN_DAYS:
            raise CommandError(f'--days must be at least {MIN_DAYS}: the admin dashboard shows the last 30 days.')
        batch_size = options['batch_size']
        if batch_size < 1:
            raise CommandError('--batch-size must be a positive number.')

        cutoff = timezone.now() - timedelta(days=days)
        old = AnalyticsEvent.objects.filter(created_at__lt=cutoff).exclude(event_name__in=SERVER_ONLY_EVENTS)
        total = old.count()
        if not options['apply']:
            self.stdout.write(
                f'Dry run: {total} analytics event(s) older than {days} days (before {cutoff:%Y-%m-%d}) '
                f'would be deleted. Re-run with --apply to delete them.'
            )
            return

        deleted = 0
        while True:
            # Small id batches: one huge DELETE locks SQLite / bloats the Postgres WAL.
            ids = list(old.order_by('id').values_list('id', flat=True)[:batch_size])
            if not ids:
                break
            count, _ = AnalyticsEvent.objects.filter(id__in=ids).delete()
            if not count:
                break
            deleted += count
        self.stdout.write(self.style.SUCCESS(
            f'Deleted {deleted} analytics event(s) older than {days} days (before {cutoff:%Y-%m-%d}).'
        ))
