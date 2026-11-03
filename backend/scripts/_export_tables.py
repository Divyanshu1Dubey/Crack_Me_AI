"""Export the key tables as JSON rows (one file per model).

    python scripts/_export_tables.py --output-dir <directory outside the repository>

The rows include user data (attempts, bookmarks, notes, flashcards,
subscriptions, audit logs), so the directory must be outside the repository
(scripts/_safe_paths.py); it used to be ../backup/db_dumps, inside the checkout.
"""
import os, sys, json
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

# Add backend to path so 'crack_cms' package is importable
script_dir = Path(__file__).resolve().parent
backend_dir = script_dir.parent
sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(script_dir))

from _safe_paths import output_dir_from_argv  # noqa: E402

backup_dir = output_dir_from_argv(description=__doc__.splitlines()[0])

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')
import django  # noqa: E402
django.setup()

from django.apps import apps  # noqa: E402

print(f"Backup dir: {backup_dir}", flush=True)

models = [
    ('questions', 'Question'), ('questions', 'QuestionBookmark'),
    ('questions', 'QuestionFeedback'), ('questions', 'Discussion'),
    ('questions', 'Note'), ('questions', 'Flashcard'),
    ('questions', 'QuestionAttempt'), ('questions', 'QuestionImage'),
    ('questions', 'ExamTrack'), ('questions', 'Subject'),
    ('questions', 'Topic'), ('accounts', 'Subscription'),
    ('accounts', 'AdminAuditLog'),
]

total = 0
for app_label, model_name in models:
    Model = apps.get_model(app_label, model_name)
    count = Model.objects.count()
    print(f'{app_label}.{model_name}: {count} rows', flush=True)
    if count == 0:
        continue
    total += count
    rows = []
    for obj in Model.objects.all():
        row = {'model': f'{app_label}.{model_name}', 'pk': obj.pk, 'fields': {}}
        for field in Model._meta.concrete_fields:
            try:
                row['fields'][field.name] = field.value_from_object(obj)
            except Exception:
                row['fields'][field.name] = None
        rows.append(row)
    out_path = backup_dir / f'{app_label}.{model_name.lower()}.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False, default=str)
    print(f'  -> {out_path.stat().st_size//1024}KB', flush=True)
print(f'\nTotal: {total} rows exported', flush=True)
