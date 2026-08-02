"""Operational fallback for the freemium auto-seed (post_migrate signal).

Production never needs this — ``accounts.signals`` runs after every
``manage.py migrate`` and populates FreeShowcaseQuestion + auto-marks
two free preview tests. This command remains for ops who want to:

    * re-run with custom flags (``--per-year``, ``--dry-run``)
    * audit what would happen without touching the DB
    * bootstrap on a DB where the post_migrate signal was skipped

Everything is idempotent.
"""
from django.core.management.base import BaseCommand

from accounts.signals import ensure_freemium_seed


PER_YEAR_CAP = 10


class Command(BaseCommand):
    help = (
        'Operational fallback for freemium auto-seed. Production deploys run '
        'this automatically via the post_migrate signal — see accounts.signals.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--per-year',
            type=int,
            default=PER_YEAR_CAP,
            help='Target showcase count per year (default: 10).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print summary without writing (signal already runs idempotently, '
                 'so dry-run is informational only).',
        )

    def handle(self, *args, **options):
        if options['dry_run']:
            # Count what would be created without doing it.
            from accounts.models_freemium import FreeShowcaseQuestion
            from questions.models import Question
            years = list(
                Question.objects.filter(is_active=True)
                .values_list('year', flat=True).distinct().order_by('-year')
            )
            for year in years:
                cur = FreeShowcaseQuestion.objects.filter(year=year).count()
                self.stdout.write(f'  year={year}: {cur}/{options["per_year"]}')
            from tests_engine.models import Test
            preview_count = Test.objects.filter(is_free_preview=True).count()
            self.stdout.write(f'  free-preview tests: {preview_count}/2')
            return

        summary = ensure_freemium_seed()
        self.stdout.write(self.style.SUCCESS(
            f'Freemium auto-seed: {summary}'
        ))