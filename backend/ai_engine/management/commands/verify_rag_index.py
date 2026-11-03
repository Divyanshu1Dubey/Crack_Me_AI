"""Read-only check of the textbook search store.

  python manage.py verify_rag_index           # print the report
  python manage.py verify_rag_index --check   # also exit non-zero when unhealthy

Exit codes with --check: 0 healthy (or RAG disabled), 2 missing/empty, 3 corrupt / LFS pointer.
Ported from branch feat/ai-production-unification (adapted to the BM25 store).
"""
import json
import sys

from django.core.management.base import BaseCommand

from ai_engine.rag_health import EXIT_CODES, rag_store_health


class Command(BaseCommand):
    help = 'Read-only health check of chroma_db/rag_store.sqlite3.'

    def add_arguments(self, parser):
        parser.add_argument('--check', action='store_true', help='Exit non-zero when the store is not healthy.')
        parser.add_argument('--path', default=None, help='Check another store file.')
        parser.add_argument('--json', action='store_true', help='Print the report as JSON.')

    def handle(self, *args, **options):
        report = rag_store_health(options['path'])
        if options['json']:
            self.stdout.write(json.dumps(report, indent=2))
        else:
            style = self.style.SUCCESS if report['status'] in ('healthy', 'disabled') else self.style.ERROR
            self.stdout.write(style(f"RAG store: {report['status'].upper()}  ({report['path']})"))
            self.stdout.write(f"  chunks={report['total_chunks']} books={report['books']} idf_terms={report['idf_terms']} "
                              f"size={report['size_bytes']} integrity={report['integrity']}")
            if report['detail']:
                self.stdout.write(f"  {report['detail']}")
        if options['check']:
            code = EXIT_CODES.get(report['status'], 3)
            if code:
                sys.exit(code)
