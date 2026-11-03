"""Load AI review signals and official answer keys into the answer-key audit (``QuestionAudit.reviews``).

Dry run by default. Lines are normalized (``key_audit.reviews.normalize_review``) and checked against
the question's current content (``stem_hash``). ``--apply`` merges them (a review with the same
reviewer / pass / reference replaces the earlier one) and re-classifies the questions. AI output is a
review signal labelled with its reviewer (``claude-subagent (review signal)``), never evidence, and
never changes a key; human decisions are made in the review queue and cannot be imported.

  python manage.py import_review_signals pass1_reviews.jsonl            # dry run
  python manage.py import_review_signals pass1_reviews.jsonl --apply
"""
from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from key_audit.importers import import_review_signals


class Command(BaseCommand):
    help = 'Import AI review signals / official keys from a JSON-lines file (dry run unless --apply).'

    def add_arguments(self, parser):
        parser.add_argument('path', help='JSON-lines file, one review per line (question_id, stem_hash, ...)')
        parser.add_argument('--apply', action='store_true', help='merge the reviews (default: dry run)')
        parser.add_argument('--source', default='', help='label stored with the reviews (default: the file name)')
        parser.add_argument('--assume-current-content', action='store_true',
                            help='accept lines without stem_hash as made for the current content')
        parser.add_argument('--json', action='store_true', help='print the report as JSON')

    def handle(self, *args, **opts):
        path = Path(opts['path'])
        if not path.is_file():
            raise CommandError(f'no such file: {path.name}')
        report, _reviews = import_review_signals(path, apply=opts['apply'], source=opts['source'],
                                                 assume_current_content=opts['assume_current_content'])
        data = dict(report.as_dict(), mode='apply' if opts['apply'] else 'dry-run')
        if opts['json']:
            self.stdout.write(json.dumps(data, indent=2))
            return
        self.stdout.write(f"Review signals ({data['mode']}): {data['lines']} line(s), {data['valid']} valid, "
                          f"{data['questions']} question(s)")
        if data['skipped']:
            self.stdout.write('  skipped: ' + ', '.join(f'{k} {v}' for k, v in data['skipped'].items()))
        if data['notes']:
            self.stdout.write('  reviews: ' + ', '.join(f'{k} {v}' for k, v in data['notes'].items()))
        if opts['apply']:
            self.stdout.write(f"  merged into {data['questions']} audit(s) and re-classified them")
        else:
            self.stdout.write('Dry run: nothing written. Run again with --apply to import.')
