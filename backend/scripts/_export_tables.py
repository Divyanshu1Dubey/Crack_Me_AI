import os, sys, json
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

# Add backend to path so 'crack_cms' package is importable
script_dir = Path(__file__).resolve().parent
backend_dir = script_dir.parent
sys.path.insert(0, str(backend_dir))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')
import django
django.setup()

from django.apps import apps

backup_dir = backend_dir.parent / 'backup' / 'db_dumps'
backup_dir.mkdir(parents=True, exist_ok=True)
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
