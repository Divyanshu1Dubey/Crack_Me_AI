import logging
import os

from django.conf import settings
from django.core.management import call_command
from django.db import connection


logger = logging.getLogger(__name__)

# A stable, application-specific PostgreSQL advisory-lock key.
_MIGRATION_LOCK_ID = 1122334455


def migrate_database_on_startup():
    """Apply pending production migrations before the app accepts traffic."""
    enabled = os.getenv("RUN_MIGRATIONS_ON_STARTUP", "true").lower() == "true"
    engine = settings.DATABASES["default"].get("ENGINE", "")
    if not enabled or not engine.endswith("postgresql"):
        return

    # App Platform does not run Procfile release commands. The advisory lock
    # keeps simultaneous web instances from racing while one applies migrations.
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_lock(%s)", [_MIGRATION_LOCK_ID])

    try:
        logger.info("Applying pending database migrations before startup")
        call_command("migrate", no_input=True, verbosity=1)
    finally:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s)", [_MIGRATION_LOCK_ID])
