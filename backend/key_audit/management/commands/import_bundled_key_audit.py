"""Import the answer-key audit signals shipped with the code, once per file version, then audit every question.

``key_audit/data/`` holds the printed source keys (``source_keys_v2.jsonl``) and the AI first-pass review signals
(``pass1_reviews_hashed.jsonl``, ``pass1b_reviews_hashed.jsonl``), made on a copy of production
(``docs/ANSWER_KEY_AUDIT.md`` sections 5-6). A file is imported once per sha256 (a ``BundledSignalImport`` row records
it with the importer's report). The importers check every line against the question's current content
(``stem_hash``) and skip the others, keep a review imported before (same verdict: same timestamp) and never change a
key: these are signals for the review queue. After an import every active question is audited again
(``audit_answer_keys --apply``). A run with nothing new ends at once, so ``start_web.sh`` runs it in the background on
every start. Dry run unless ``--apply``.

  python manage.py import_bundled_key_audit            # what would be imported
  python manage.py import_bundled_key_audit --apply
"""
from __future__ import annotations

import hashlib
import io
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import IntegrityError

from key_audit.importers import import_review_signals, import_source_keys
from key_audit.models import BundledSignalImport

DATA_DIR = Path(__file__).resolve().parents[2] / 'data'
FILES = (
    ('source_keys', 'source_keys_v2.jsonl'),
    ('reviews', 'pass1_reviews_hashed.jsonl'),
    ('reviews', 'pass1b_reviews_hashed.jsonl'),
)


def file_sha256(path) -> str:
    digest = hashlib.sha256()
    with open(path, 'rb') as fh:
        for block in iter(lambda: fh.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


class Command(BaseCommand):
    help = ('Import the answer-key audit signals shipped in key_audit/data/ once per file version, then audit every '
            'question (dry run unless --apply). Never changes a key.')

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='import, record and audit (default: dry run)')
        parser.add_argument('--data-dir', default='', help='directory holding the files (default: key_audit/data)')

    def handle(self, *args, **opts):
        data_dir = Path(opts['data_dir']) if opts['data_dir'] else DATA_DIR
        apply = opts['apply']
        imported = 0
        for kind, name in FILES:
            path = data_dir / name
            if not path.is_file():
                self.stdout.write(f'{name}: not shipped')
                continue
            digest = file_sha256(path)
            if BundledSignalImport.objects.filter(name=name, sha256=digest).exists():
                self.stdout.write(f'{name}: already imported')
                continue
            if kind == 'source_keys':
                report = import_source_keys(path, apply=apply)
            else:
                report, _reviews = import_review_signals(path, apply=apply)
            data = report.as_dict()
            line = f"{name}: {data['lines']} line(s), {data['valid']} valid for {data['questions']} question(s)"
            if kind == 'source_keys':
                line += f", created {data['created']}, updated {data['updated']}, unchanged {data['unchanged']}"
            if data['skipped']:
                line += '; skipped ' + ', '.join(f'{k} {v}' for k, v in data['skipped'].items())
            self.stdout.write(line)
            if not apply:
                continue
            try:
                BundledSignalImport.objects.create(name=name, sha256=digest, kind=kind, report=data)
            except IntegrityError:
                pass  # recorded meanwhile by a concurrent run; the import itself is idempotent
            imported += 1
        if not apply:
            self.stdout.write('Dry run: nothing written. Run again with --apply to import.')
            return
        if not imported:
            self.stdout.write('Nothing new: no audit needed.')
            return
        out = io.StringIO()
        call_command('audit_answer_keys', '--apply', stdout=out)
        summary = [text for text in out.getvalue().splitlines() if text.strip()][:8]
        self.stdout.write('Audit applied:\n' + '\n'.join(summary))
