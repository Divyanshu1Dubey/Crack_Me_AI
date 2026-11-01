"""Export Supabase Auth users list + Django DB dump as JSON.

    python scripts/_backup_export.py --output-dir <directory outside the repository>

Writes <output-dir>/supabase_auth_users.json and <output-dir>/db_dumps/<app.model>.json.
Both hold user data, so the directory must be outside the repository
(scripts/_safe_paths.py); it used to be ../backup, inside the checkout.
"""
import json
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _safe_paths import output_dir_from_argv  # noqa: E402

OUTPUT_DIR = output_dir_from_argv(description=__doc__.splitlines()[0])

import django  # noqa: E402

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')
django.setup()

# 1. Export Supabase Auth users
try:
    from accounts.supabase_auth import list_supabase_auth_users
    users = list_supabase_auth_users()
    with open(OUTPUT_DIR / 'supabase_auth_users.json', 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=2, ensure_ascii=False, default=str)
    print(f"OK: Exported {len(users)} Supabase Auth users to {OUTPUT_DIR / 'supabase_auth_users.json'}")
except Exception as e:
    print(f"FAIL: Could not export Supabase Auth users: {e}")

# 2. Export all Django model data (table by table)
from django.apps import apps  # noqa: E402
from django.core import serializers  # noqa: E402

dump_dir = OUTPUT_DIR / 'db_dumps'
all_models = apps.get_models()
total = 0
for model in all_models:
    label = f"{model._meta.app_label}.{model._meta.model_name}"
    try:
        qs = model.objects.all()
        count = qs.count()
        if count == 0:
            continue
        data = serializers.serialize('json', qs, use_natural_foreign_keys=True, use_natural_primary_keys=True)
        dump_dir.mkdir(parents=True, exist_ok=True)
        with open(dump_dir / f"{label}.json", 'w', encoding='utf-8') as f:
            f.write(data)
        total += count
        print(f"OK: {label} -> {count} rows")
    except Exception as e:
        print(f"FAIL: {label} -> {e}")

print(f"\nDone: {total} total rows exported across all tables to {dump_dir}")
