import logging
from django.core.management.base import BaseCommand
from questions.models import Question
from django_q.tasks import async_task

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Generate videos for questions in the background'

    def add_arguments(self, parser):
        parser.add_argument(
            '--question_id',
            type=int,
            default=None,
            help='Generate video for a specific question ID',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Regenerate video even if already generated',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Limit the number of videos processed',
        )

    def handle(self, *args, **options):
        q_id = options['question_id']
        force = options['force']
        limit = options['limit']

        queryset = Question.objects.all()

        if q_id:
            queryset = queryset.filter(id=q_id)
        elif not force:
            queryset = queryset.filter(video_status='pending')

        total = queryset.count()
        if limit > 0:
            queryset = queryset[:limit]
            total = min(total, limit)

        if total == 0:
            self.stdout.write(self.style.SUCCESS("No videos to generate."))
            return

        self.stdout.write(self.style.NOTICE(f"Queueing {total} videos for generation..."))
        
        for i, question in enumerate(queryset, 1):
            self.stdout.write(f"[{i}/{total}] Queueing Q{question.id}")
            # Enqueue the background task
            async_task('video_engine.tasks.generate_video_task', question.id, force)

        self.stdout.write(self.style.SUCCESS(f"Successfully queued {total} background tasks!"))
