"""Restore a questions backup (Django fixture JSON, UTF-16 or UTF-8).

    python scripts/restore_backup.py <path to the backup file, outside the repository>

Questions an admin edited are left alone. The backup holds student activity
(attempts, discussions, bookmarks, feedback), so it is kept outside the
repository (scripts/_safe_paths.py); this script used to read
backend/questions_backup.json, a tracked copy of such a dump.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from _safe_paths import external_path  # noqa: E402


def _backup_path_from_argv(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('backup_path', help='Backup fixture to restore (a file outside the repository).')
    return external_path(parser.parse_args(argv).backup_path, what='the backup path')


def run(backup_path):
    import django

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')
    django.setup()

    from django.core.serializers import deserialize
    from questions.models import Question

    if not backup_path.is_file():
        print(f"Backup file not found at {backup_path}")
        return

    print("Loading backup file...")
    try:
        with open(backup_path, 'r', encoding='utf-16') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Failed to load JSON with utf-16, trying utf-8... ({e})")
        with open(backup_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

    print(f"Found {len(data)} objects in fixture.")
    restored = 0
    skipped = 0

    json_str = json.dumps(data)
    for obj in deserialize('json', json_str):
        if isinstance(obj.object, Question):
            try:
                existing = Question.objects.get(pk=obj.object.pk)
                if existing.admin_edited:
                    skipped += 1
                    continue
            except Question.DoesNotExist:
                pass
            obj.save()
            restored += 1
        else:
            # Save non-Question objects (like Subject, Topic) blindly if needed,
            # or skip them if we only want to restore Questions.
            # Assuming we want to restore everything in the fixture that isn't admin_edited
            if hasattr(obj.object, 'admin_edited'):
                try:
                    existing = obj.object.__class__.objects.get(pk=obj.object.pk)
                    if existing.admin_edited:
                        skipped += 1
                        continue
                except obj.object.__class__.DoesNotExist:
                    pass
            obj.save()

    print(f"\nRestore complete!")
    print(f"Questions restored/updated: {restored}")
    print(f"Admin-edited questions protected (skipped): {skipped}")


if __name__ == '__main__':
    run(_backup_path_from_argv())
