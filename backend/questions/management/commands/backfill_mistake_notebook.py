"""Populate the Mistake Notebook from historical wrong answers.

Until 2026-11 nothing created MistakeNotebook rows, so every notebook was
empty. This backfills one entry per (user, question) from wrong
question-bank attempts and wrong test responses. Idempotent.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Backfill MistakeNotebook entries from historical wrong answers (idempotent).'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        from django.utils import timezone

        from questions.models import MistakeNotebook, QuestionAttempt
        from tests_engine.models import QuestionResponse

        existing = set(MistakeNotebook.objects.values_list('user_id', 'question_id'))
        to_create = {}
        for qa in QuestionAttempt.objects.filter(is_correct=False).select_related('question').iterator():
            key = (qa.user_id, qa.question_id)
            if key not in existing and key not in to_create:
                to_create[key] = (qa.selected_answer, qa.question.correct_answer, qa.pk)
        responses = (QuestionResponse.objects.filter(is_correct=False)
                     .exclude(selected_answer__isnull=True).exclude(selected_answer='')
                     .select_related('attempt', 'question'))
        for r in responses.iterator():
            key = (r.attempt.user_id, r.question_id)
            if key not in existing and key not in to_create:
                to_create[key] = (r.selected_answer, r.question.correct_answer, None)

        self.stdout.write(f'{len(to_create)} new mistake entries ({len(existing)} already present)')
        if options['dry_run'] or not to_create:
            return
        now = timezone.now()
        MistakeNotebook.objects.bulk_create([
            MistakeNotebook(
                user_id=user_id, question_id=question_id,
                selected_answer=(selected or '?').strip().upper()[:1] or '?',
                correct_answer=(correct or '?').strip().upper()[:1] or '?',
                is_correct=False, attempt_id=attempt_id, review_status='new', next_review_at=now,
            )
            for (user_id, question_id), (selected, correct, attempt_id) in to_create.items()
        ], ignore_conflicts=True, batch_size=500)
        self.stdout.write(self.style.SUCCESS('done'))
