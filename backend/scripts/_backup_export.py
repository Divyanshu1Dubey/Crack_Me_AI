"""Export Supabase Auth users list + Django DB dump as JSON."""
import json
import sys
import os
import django

sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')
django.setup()

# 1. Export Supabase Auth users
try:
    from accounts.supabase_auth import list_supabase_auth_users
    users = list_supabase_auth_users()
    os.makedirs('../backup', exist_ok=True)
    with open('../backup/supabase_auth_users.json', 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=2, ensure_ascii=False, default=str)
    print(f"OK: Exported {len(users)} Supabase Auth users to backup/supabase_auth_users.json")
except Exception as e:
    print(f"FAIL: Could not export Supabase Auth users: {e}")

# 2. Export all Django model data (table by table)
from django.apps import apps
from django.core import serializers

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
        os.makedirs('../backup/db_dumps', exist_ok=True)
        fname = f"../backup/db_dumps/{label}.json"
        with open(fname, 'w', encoding='utf-8') as f:
            f.write(data)
        total += count
        print(f"OK: {label} -> {count} rows")
    except Exception as e:
        print(f"FAIL: {label} -> {e}")

print(f"\nDone: {total} total rows exported across all tables")
