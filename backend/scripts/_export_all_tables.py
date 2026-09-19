# -*- coding: utf-8 -*-
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')
django.setup()

from django.apps import apps

export_plan = [
    ('questions', 'Question'),
    ('questions', 'QuestionBookmark'),
    ('questions', 'QuestionFeedback'),
    ('questions', 'QuestionRevisionSnapshot'),
    ('questions', 'Discussion'),
    ('questions', 'DiscussionVote'),
    ('questions', 'Note'),
    ('questions', 'Flashcard'),
    ('questions', 'QuestionAttempt'),
    ('questions', 'QuestionImage'),
    ('questions', 'ExamTrack'),
    ('questions', 'Subject'),
    ('questions', 'Topic'),
    ('questions', 'QuestionSource'),
    ('questions', 'QuestionImportJob'),
    ('questions', 'QuestionExtractionItem'),
    ('questions', 'AdminAIPromptVersion'),
    ('questions', 'QuestionAIOperationLog'),
    ('questions', 'Announcement'),
    ('questions', 'RecallSource'),
    ('questions', 'DuplicateCluster'),
    ('questions', 'DuplicateMember'),
    ('questions', 'RemovedQuestion'),
    ('accounts', 'Subscription'),
]

backup_dir = Path(__file__).resolve().parent.parent.parent.parent / 'backup' / 'db_dumps'
backup_dir.mkdir(parents=True, exist_ok=True)

total_rows = 0
for app_label, model_name in export_plan:
    Model = apps.get_model(app_label, model_name)
    qs = Model.objects.all()
    count = qs.count()
    print(f"Exporting {app_label}.{model_name}: {count} rows...", flush=True)
    if count == 0:
        continue

    rows = []
    for obj in qs:
        row = {'model': f'{app_label}.{model_name}', 'pk': obj.pk, 'fields': {}}
        for field in Model._meta.concrete_fields:
            fname = field.name
            try:
                val = field.value_from_object(obj)
                row['fields'][fname] = val
            except Exception:
                row['fields'][fname] = None
        rows.append(row)

    out_path = backup_dir / f'{app_label}.{model_name.lower()}.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False, default=str, indent=2)
    size_kb = out_path.stat().st_size // 1024
    print(f"  -> saved ({size_kb} KB)", flush=True)
    total_rows += count

print(f"\nDone: {total_rows} total rows exported", flush=True)
