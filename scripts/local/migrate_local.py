"""Apply pending Django migrations to the LOCAL development database only.

Run from anywhere with the project venv:
    python scripts/local/migrate_local.py            # migrate
    python scripts/local/migrate_local.py --check    # list unapplied migrations, change nothing

The settings are loaded from backend/.env.localdev (DJANGO_ENV_FILE). The
script refuses to touch any database that is not on this machine, so a
mis-edited env file cannot migrate a shared or production database.
"""
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / 'backend'
LOCAL_HOSTS = {'localhost', '127.0.0.1', '::1'}


def main(argv):
    os.chdir(BACKEND)
    sys.path.insert(0, str(BACKEND))
    os.environ['DJANGO_ENV_FILE'] = '.env.localdev'
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')
    import django
    from django.conf import settings
    from django.core.management import call_command

    django.setup()
    db = settings.DATABASES['default']
    engine = db.get('ENGINE', '')
    host = (db.get('HOST') or '').strip()
    if 'sqlite' in engine:
        print(f'Refusing: the local env resolves to SQLite ({db.get("NAME")}), not the restored PostgreSQL database.')
        return 2
    if host not in LOCAL_HOSTS:
        print(f'Refusing: database host {host!r} is not local.')
        return 2
    print(f'Local database: {db.get("NAME")} on {host}:{db.get("PORT")}')
    if '--check' in argv:
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor
        executor = MigrationExecutor(connection)
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        print(f'Unapplied migrations: {len(plan)}')
        for migration, _backwards in plan:
            print(f'  {migration.app_label}.{migration.name}')
        return 0
    call_command('migrate', interactive=False, verbosity=1)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
