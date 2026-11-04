"""Load printed source keys (``ai_eval.recover_source_keys`` output) into ``key_audit.SourceKey``.

Dry run by default. Every line is checked against the question's current content (``stem_hash``);
lines for other content are skipped and counted. ``--apply`` upserts the rows (never deletes) and
re-audits the questions they touch. A source key is a review signal for the answer-key audit; it
never changes a key.

  python manage.py import_source_keys source_keys.jsonl            # dry run
  python manage.py import_source_keys source_keys.jsonl --apply
  python manage.py import_source_keys old.jsonl --assume-current-content   # file without stem_hash,
        # only on the database it was made from, right after it was made
"""
from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from key_audit.importers import import_source_keys
from key_audit.services import audit_questions
from questions.models import Question


class Command(BaseCommand):
    help = 'Import printed source keys from a JSON-lines file (dry run unless --apply). Never changes a key.'

    def add_arguments(self, parser):
        parser.add_argument('path', help='JSON-lines file written by ai_eval.recover_source_keys')
        parser.add_argument('--apply', action='store_true', help='write the rows (default: dry run)')
        parser.add_argument('--assume-current-content', action='store_true',
                            help='accept lines without stem_hash as made for the current content')
        parser.add_argument('--no-audit', action='store_true', help='with --apply: do not re-audit the questions')
        parser.add_argument('--json', action='store_true', help='print the report as JSON')

    def handle(self, *args, **opts):
        path = Path(opts['path'])
        if not path.is_file():
            raise CommandError(f'no such file: {path.name}')
        report = import_source_keys(path, apply=opts['apply'], assume_current_content=opts['assume_current_content'])
        audited = 0
        if opts['apply'] and not opts['no_audit'] and report.questions:
            audited = len(audit_questions(list(Question.objects.filter(pk__in=report.questions)), save=True))
        data = dict(report.as_dict(), mode='apply' if opts['apply'] else 'dry-run', audited=audited)
        if opts['json']:
            self.stdout.write(json.dumps(data, indent=2))
            return
        verb = '' if opts['apply'] else 'would be '
        self.stdout.write(f"Source keys ({data['mode']}): {data['lines']} line(s), {data['valid']} valid, "
                          f"{data['questions']} question(s)")
        self.stdout.write(f"  {verb}created {data['created']}, {verb}updated {data['updated']}, unchanged {data['unchanged']}")
        if data['skipped']:
            self.stdout.write('  skipped: ' + ', '.join(f'{k} {v}' for k, v in data['skipped'].items()))
        if data['notes']:
            self.stdout.write('  against the current keys: ' + ', '.join(f'{k} {v}' for k, v in data['notes'].items()))
        if audited:
            self.stdout.write(f'  re-audited {audited} question(s)')
        if not opts['apply']:
            self.stdout.write('Dry run: nothing written. Run again with --apply to import.')
