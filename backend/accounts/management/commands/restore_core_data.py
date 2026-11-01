"""Restore the core catalogue from a fixture written by backup_core_data.

    python manage.py restore_core_data [--input PATH]

Matching records (same primary key) are overwritten. Refuses files that are
missing, empty, or contain models other than the core catalogue.
"""
from django.core.management.base import BaseCommand, CommandError

from accounts.core_data_backup import CoreDataBackupError, restore_core_data


class Command(BaseCommand):
    help = 'Restore core catalogue data (exam tracks, subjects, topics, jobs) from the JSON fixture'

    def add_arguments(self, parser):
        parser.add_argument('--input', default=None, help='Fixture path (default: CORE_DATA_BACKUP_PATH or BASE_DIR/core_data_seed.json)')

    def handle(self, *args, **options):
        try:
            count = restore_core_data(options.get('input'))
        except CoreDataBackupError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f'Restored {count} records'))
