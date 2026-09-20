# -*- coding: utf-8 -*-
"""Import backup JSON files into Railway Postgres, skipping FK violations."""
import os, sys, json
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
script_dir = Path(__file__).resolve().parent
backend_dir = script_dir.parent
sys.path.insert(0, str(backend_dir))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')

import django
django.setup()

from django.apps import apps
from django.db import transaction

backup_dir = backend_dir.parent / 'backup' / 'db_dumps'

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
