# -*- coding: utf-8 -*-
import json
import sys
from pathlib import Path

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError


# (app_label, model_name). The command used to import ``Bookmark``,
# ``FlashCard`` and ``TestAttempt`` from questions.models -- none of which
# exist there -- so it died with ImportError before exporting anything.
EXPORT_PLAN = [
    ('questions', 'Question'),
    ('questions', 'QuestionBookmark'),
    ('questions', 'Discussion'),
    ('questions', 'Note'),
    ('questions', 'Flashcard'),
    ('tests_engine', 'TestAttempt'),
    ('questions', 'ExamTrack'),
    ('questions', 'Subject'),
    ('questions', 'Topic'),
    ('accounts', 'Subscription'),
]


def _inside_a_checkout(path: Path) -> bool:
    """True when ``path`` is inside this project or any git working tree.

    The dumps hold student data (bookmarks, notes, flashcards, test attempts,
    subscriptions); written inside a checkout they are one ``git add`` away
    from being published.
    """
    from django.conf import settings

    project_root = Path(settings.BASE_DIR).resolve().parent
    try:
        path.relative_to(project_root)
        return True
    except ValueError:
        pass
    return any((parent / '.git').exists() for parent in (path, *path.parents))


class Command(BaseCommand):
    help = "Export questions app to JSON (handles Windows encoding issues)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir', required=True,
            help=('Directory for the JSON dumps. Required, and it must be outside the repository: '
                  'the dumps contain user data (bookmarks, notes, flashcards, test attempts, subscriptions).'),
        )

    def handle(self, *args, **options):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except (AttributeError, ValueError):  # pragma: no cover - non-reconfigurable stream
            pass

        raw_dir = str(options.get('output_dir') or '').strip()
        if not raw_dir:
            raise CommandError('--output-dir is required (a directory outside the repository).')
        backup_dir = Path(raw_dir).expanduser().resolve()
        if _inside_a_checkout(backup_dir):
            raise CommandError(
                f'Refusing to write user data inside a source checkout: {backup_dir}. '
                'Choose a directory outside the repository.'
            )
        backup_dir.mkdir(parents=True, exist_ok=True)

        total_rows = 0
        for app_label, model_name in EXPORT_PLAN:
            Model = apps.get_model(app_label, model_name)
            qs = Model.objects.all().order_by('pk')
            count = qs.count()
            self.stdout.write(f"Exporting {app_label}.{model_name}: {count} rows...")
            if count == 0:
                continue

            out_path = backup_dir / f'{app_label}.{model_name.lower()}.json'
            fields = list(Model._meta.concrete_fields)
            # Stream rows to disk (the question bank is ~10k rows with long
            # text fields; building one big list held it all in memory).
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write('[\n')
                for index, obj in enumerate(qs.iterator(chunk_size=500)):
                    row = {'model': f'{app_label}.{model_name.lower()}', 'pk': obj.pk, 'fields': {}}
                    for field in fields:
                        if field.primary_key:
                            continue
                        try:
                            row['fields'][field.name] = field.value_from_object(obj)
                        except Exception:
                            row['fields'][field.name] = None
                    if index:
                        f.write(',\n')
                    f.write(json.dumps(row, ensure_ascii=False, default=str, indent=2))
                f.write('\n]\n')
            size_kb = out_path.stat().st_size // 1024
            self.stdout.write(f"  -> saved ({size_kb} KB)")
            total_rows += count

        self.stdout.write(f"\nDone: {total_rows} total rows exported")
