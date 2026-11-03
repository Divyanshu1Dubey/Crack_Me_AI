# -*- coding: utf-8 -*-
"""Import backup JSON files into Railway Postgres, skipping FK violations.

    python scripts/_import_to_railway.py --input-dir <the --output-dir of _export_tables.py>

The dumps hold user data and live outside the repository (scripts/_safe_paths.py).
"""
import argparse
import os, sys, json
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
script_dir = Path(__file__).resolve().parent
backend_dir = script_dir.parent
sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(script_dir))

from _safe_paths import external_path  # noqa: E402

_parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
_parser.add_argument('--input-dir', required=True,
                     help='Directory holding the <app>.<model>.json dumps (outside the repository).')
backup_dir = external_path(_parser.parse_args().input_dir, what='--input-dir')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')

import django  # noqa: E402
django.setup()

from django.apps import apps  # noqa: E402
from django.db import transaction  # noqa: E402

# Load order: parents before children
import_plan = [
    ('questions.examtrack', 'questions'),
    ('questions.subject', 'questions'),
    ('questions.topic', 'questions'),
    ('accounts.customuser', 'accounts'),
    ('accounts.tokenconfig', 'accounts'),
    ('accounts.tokenbalance', 'accounts'),
    ('accounts.tokentransaction', 'accounts'),
    ('accounts.subscription', 'accounts'),
    ('accounts.adminauditlog', 'accounts'),
    ('questions.question', 'questions'),
    ('questions.questionattempt', 'questions'),
    ('questions.questionimage', 'questions'),
    ('questions.questionbookmark', 'questions'),
    ('questions.questionfeedback', 'questions'),
    ('questions.discussion', 'questions'),
    ('questions.flashcard', 'questions'),
]

for fixture_name, app_label in import_plan:
    fpath = backup_dir / f'{fixture_name}.json'
    if not fpath.exists():
        print(f"SKIP: {fpath} not found", flush=True)
        continue

    with open(fpath, 'r', encoding='utf-8') as f:
        rows = json.load(f)

    if not rows:
        print(f"SKIP: {fixture_name} is empty", flush=True)
        continue

    Model = apps.get_model(app_label, fixture_name.split('.')[1])
    model_name = Model._meta.model_name
    app_label_name = Model._meta.app_label

    imported = 0
    skipped = 0
    errors = 0

    for row in rows:
        pk = row.get('pk')
        fields = row.get('fields', {})

        try:
            with transaction.atomic():
                obj, created = Model.objects.update_or_create(
                    pk=pk,
                    defaults=fields
                )
                imported += 1
        except Exception as e:
            skipped += 1
            if skipped <= 3:
                print(f"  SKIP {fixture_name} pk={pk}: {e}", flush=True)

    print(f"OK: {fixture_name} -> {imported} imported, {skipped} skipped", flush=True)

print("\nImport complete!", flush=True)
