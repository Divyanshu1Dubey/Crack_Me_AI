"""Seed FreeShowcaseQuestion for every year that has Question rows.

Idempotent: skips years that already have the full 10-position set.
For each missing slot, picks the lowest-id active question not yet in
the showcase, in deterministic order, so a fresh deploy always has
something to show free users without admin intervention.

Run: `python manage.py seed_free_showcase`
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models_freemium import FreeShowcaseQuestion
from questions.models import Question


PER_YEAR_CAP = 10


class Command(BaseCommand):
    help = 'Bootstrap FreeShowcaseQuestion rows — 10 per year, deterministic.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--per-year',
            type=int,
            default=PER_YEAR_CAP,
            help='Target number of showcase questions per year (default: 10).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print what would be created without writing to the database.',
        )

    def handle(self, *args, **options):
        per_year = options['per_year']
        dry_run = options['dry_run']

        years = list(
            Question.objects.filter(is_active=True)
            .values_list('year', flat=True)
            .distinct()
            .order_by('-year')
        )
        created = 0
        skipped = 0
        for year in years:
            existing = (
                FreeShowcaseQuestion.objects
                .filter(year=year)
                .count()
            )
            if existing >= per_year:
                skipped += 1
                self.stdout.write(
                    f'  {year}: already has {existing} entries — skipping.'
                )
                continue
            needed = per_year - existing
            existing_qids = set(
                FreeShowcaseQuestion.objects
                .filter(year=year)
                .values_list('question_id', flat=True)
            )
            candidates = (
                Question.objects
                .filter(year=year, is_active=True)
                .exclude(id__in=existing_qids)
                .order_by('id')
                .values_list('id', flat=True)[:needed]
            )
            for position_offset, qid in enumerate(candidates):
                position = existing + position_offset
                if dry_run:
                    self.stdout.write(
                        f'  would create: year={year} position={position} question_id={qid}'
                    )
                    created += 1
                    continue
                with transaction.atomic():
                    FreeShowcaseQuestion.objects.create(
                        question_id=qid,
                        year=year,
                        position=position,
                    )
                    created += 1
            self.stdout.write(
                f'  {year}: added {min(needed, len(list(candidates)))} entries '
                f'(now {existing + min(needed, len(list(candidates)))}/{per_year}).'
            )

        verb = 'would create' if dry_run else 'Created'
        self.stdout.write(self.style.SUCCESS(
            f'{verb} {created} FreeShowcaseQuestion row(s) across {len(years)} year(s); '
            f'{skipped} year(s) already at cap.'
        ))