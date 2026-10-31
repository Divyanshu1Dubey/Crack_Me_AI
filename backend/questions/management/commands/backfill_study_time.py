"""Populate StudyTimeBreakdown from historical activity.

Until 2026-11 nothing recorded study time, so the Study Time page was
always empty. This rebuilds per-(user, subject, day) rows from completed
test attempts (per-question timings, same rules as live recording) and
counts first question-bank attempts (no timing data, so 0 seconds).
Days that already have a row are left untouched, so it is safe to re-run.
"""
from collections import defaultdict

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Backfill StudyTimeBreakdown from historical tests and question-bank attempts (idempotent).'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        from django.utils import timezone

        from questions.models import QuestionAttempt, StudyTimeBreakdown
        from questions.study_time import rows_for_test_submission
        from tests_engine.models import QuestionResponse, TestAttempt

        existing = set(StudyTimeBreakdown.objects.values_list('user_id', 'subject_id', 'date'))
        totals = defaultdict(lambda: [0, 0])

        per_attempt = defaultdict(list)
        responses = QuestionResponse.objects.filter(attempt__is_completed=True).values_list(
            'attempt_id', 'question__subject_id', 'time_taken_seconds', 'selected_answer')
        for attempt_id, subject_id, seconds, selected in responses.iterator():
            per_attempt[attempt_id].append((subject_id, seconds, bool(selected)))

        attempts = TestAttempt.objects.filter(is_completed=True).select_related('test')
        for attempt in attempts.iterator():
            when = attempt.completed_at or attempt.started_at
            if not when or attempt.pk not in per_attempt:
                continue
            day = timezone.localdate(when)
            rows = rows_for_test_submission(per_attempt[attempt.pk], attempt.time_taken_seconds,
                                            attempt.test.time_limit_minutes if attempt.test else None)
            for subject_id, seconds, count in rows:
                key = (attempt.user_id, subject_id, day)
                if key not in existing:
                    totals[key][0] += seconds
                    totals[key][1] += count

        qbank = QuestionAttempt.objects.exclude(question__subject_id__isnull=True).values_list(
            'user_id', 'question__subject_id', 'attempted_at')
        for user_id, subject_id, attempted_at in qbank.iterator():
            key = (user_id, subject_id, timezone.localdate(attempted_at))
            if key not in existing:
                totals[key][1] += 1

        hours = sum(v[0] for v in totals.values()) / 3600
        self.stdout.write(f'{len(totals)} new study-time rows, {hours:.1f} h total ({len(existing)} rows already present)')
        if options['dry_run'] or not totals:
            return
        StudyTimeBreakdown.objects.bulk_create([
            StudyTimeBreakdown(user_id=u, subject_id=s, date=d, seconds=secs, question_count=count)
            for (u, s, d), (secs, count) in totals.items()
        ], ignore_conflicts=True, batch_size=500)
        self.stdout.write(self.style.SUCCESS('done'))
