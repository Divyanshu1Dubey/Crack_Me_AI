import os
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.conf import settings

class Command(BaseCommand):
    help = 'Restores core configuration data (Exams, Subjects, Topics, Jobs) from the JSON fixture'

    def handle(self, *args, **options):
        fixture_path = os.path.join(settings.BASE_DIR, 'core_data_seed.json')
        
        if not os.path.exists(fixture_path):
            self.stdout.write(self.style.ERROR(f'Fixture file not found: {fixture_path}'))
            return

        try:
            call_command('loaddata', fixture_path)
            self.stdout.write(self.style.SUCCESS(f'Successfully restored core data from {fixture_path}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to restore data: {str(e)}'))
