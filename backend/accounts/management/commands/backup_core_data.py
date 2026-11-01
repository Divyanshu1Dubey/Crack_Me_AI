"""Back up exam tracks, subjects, topics, job categories and jobs to a JSON fixture.

    python manage.py backup_core_data [--output PATH]

Default path: $CORE_DATA_BACKUP_PATH (a persistent volume in production). The
<BASE_DIR>/core_data_seed.json fallback is used only with DEBUG on: a container
disk is wiped on redeploy, so without the variable production needs --output.
Exits with an error (and leaves any previous backup untouched) on failure.
"""
from django.core.management.base import BaseCommand, CommandError

from accounts.core_data_backup import CoreDataBackupError, backup_core_data


class Command(BaseCommand):
    help = 'Back up core catalogue data (exam tracks, subjects, topics, jobs) to a JSON fixture'

    def add_arguments(self, parser):
        parser.add_argument('--output', default=None, help='Fixture path (default: CORE_DATA_BACKUP_PATH; BASE_DIR/core_data_seed.json only with DEBUG on)')

    def handle(self, *args, **options):
        try:
            path, count = backup_core_data(options.get('output'))
        except CoreDataBackupError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f'Backed up {count} records to {path}'))
