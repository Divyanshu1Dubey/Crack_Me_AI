# -*- coding: utf-8 -*-
import json
import sys
import os
from pathlib import Path
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Export questions app to JSON (handles Windows encoding issues)"

    def handle(self, *args, **options):
        sys.stdout.reconfigure(encoding='utf-8')
        import django
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')
        django.setup()

        from questions.models import Question, Bookmark, Discussion, Note, FlashCard, TestAttempt, ExamTrack, Subject, Topic
        from accounts.models import Subscription
        from django.apps import apps

        export_plan = [
            ('questions', 'Question'),
            ('questions', 'Bookmark'),
            ('questions', 'Discussion'),
            ('questions', 'Note'),
            ('questions', 'FlashCard'),
            ('questions', 'TestAttempt'),
            ('questions', 'ExamTrack'),
            ('questions', 'Subject'),
            ('questions', 'Topic'),
            ('accounts', 'Subscription'),
        ]

        backup_dir = Path(__file__).resolve().parent.parent.parent.parent / 'backup' / 'db_dumps'
        backup_dir.mkdir(parents=True, exist_ok=True)

        total_rows = 0
        for app_label, model_name in export_plan:
            Model = apps.get_model(app_label, model_name)
            qs = Model.objects.all()
            count = qs.count()
            self.stdout.write(f"Exporting {app_label}.{model_name}: {count} rows...")
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
                    except Exception as e:
                        row['fields'][fname] = None
                rows.append(row)

            out_path = backup_dir / f'{app_label}.{model_name.lower()}.json'
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(rows, f, ensure_ascii=False, default=str, indent=2)
            size_kb = out_path.stat().st_size // 1024
            self.stdout.write(f"  -> saved ({size_kb} KB)")
            total_rows += count

        self.stdout.write(f"\nDone: {total_rows} total rows exported")
