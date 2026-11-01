import logging
from django.core.management.base import BaseCommand
from questions.models import Question
from questions.tasks import apply_explain_result
from ai_engine.services import AIService

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Generate missing AI fields for questions in bulk to populate the cache'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Regenerate AI fields even if they already exist',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Limit the number of questions processed',
        )
        parser.add_argument(
            '--subject',
            type=str,
            default=None,
            help='Filter by subject code',
        )
        parser.add_argument(
            '--year',
            type=int,
            default=None,
            help='Filter by year',
        )

    def handle(self, *args, **options):
        force = options['force']
        limit = options['limit']
        subject = options['subject']
        year = options['year']

        queryset = Question.objects.all()

        if not force:
            queryset = queryset.filter(ai_generated_at__isnull=True)
            
        if subject:
            queryset = queryset.filter(subject__code=subject)
            
        if year:
            queryset = queryset.filter(year=year)

        total = queryset.count()
        if limit > 0:
            queryset = queryset[:limit]
            total = min(total, limit)

        if total == 0:
            self.stdout.write(self.style.SUCCESS("No questions to process."))
            return

        self.stdout.write(self.style.NOTICE(f"Starting bulk AI generation for {total} questions..."))
        
        service = AIService()
        success = 0
        failed = 0

        for i, question in enumerate(queryset, 1):
            self.stdout.write(f"[{i}/{total}] Processing Q{question.id}: {question.question_text[:50]}...")
            try:
                options_dict = {
                    'A': question.option_a,
                    'B': question.option_b,
                    'C': question.option_c,
                    'D': question.option_d,
                }
                
                # Fetch detailed explanation (uses round-robin providers)
                result = service.explain_after_answer(
                    question_text=question.question_text,
                    options=options_dict,
                    correct_answer=question.correct_answer,
                    selected_answer=question.correct_answer, # Treat correct answer as selected to get proper 'why_correct' context
                    subject=question.subject.name if question.subject else '',
                    topic=question.topic.name if question.topic else ''
                )
                
                # Same rule as the AI cache task / backfill: an outage result
                # changes nothing, locks are honoured, and curated fields
                # (learning_technique, concept_keywords) are only filled
                # while empty. This used to overwrite every field with
                # whatever came back -- including the outage sentence.
                fields = apply_explain_result(question, result, service)
                if not fields:
                    failed += 1
                    self.stdout.write(self.style.WARNING("  -> No usable AI output (or fields locked); nothing saved"))
                    continue
                question.save(update_fields=fields)

                success += 1
                self.stdout.write(self.style.SUCCESS(f"  -> Success"))
            except Exception as e:
                failed += 1
                self.stdout.write(self.style.ERROR(f"  -> Failed: {e}"))
                logger.error(f"Failed to generate AI for Q{question.id}: {e}")

        self.stdout.write(self.style.SUCCESS(f"Finished! Success: {success}, Failed: {failed}"))
