# -*- coding: utf-8 -*-
"""Export every questions-app table (plus subscriptions) as JSON rows.

    python scripts/_export_all_tables.py --output-dir <directory outside the repository>

The rows include user data (attempts, bookmarks, notes, flashcards,
discussions, feedback, subscriptions), so the directory must be outside the
repository (scripts/_safe_paths.py). It used to be <checkout>/../../backup,
which is inside the main checkout when this runs from a git worktree.
"""
import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _safe_paths import output_dir_from_argv  # noqa: E402

backup_dir = output_dir_from_argv(description=__doc__.splitlines()[0])

import django  # noqa: E402
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
