import os
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.conf import settings

class Command(BaseCommand):
    help = 'Backups core configuration data (Exams, Subjects, Topics, Jobs) to a JSON fixture'

    def handle(self, *args, **options):
        fixture_path = os.path.join(settings.BASE_DIR, 'core_data_seed.json')
        models_to_backup = [
            'questions.exam',
            'questions.subject',
            'questions.topic',
            'jobs.job'
        ]
        
        try:
            with open(fixture_path, 'w', encoding='utf-8') as f:
                call_command('dumpdata', *models_to_backup, indent=2, stdout=f)
            self.stdout.write(self.style.SUCCESS(f'Successfully backed up core data to {fixture_path}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to backup data: {str(e)}'))
