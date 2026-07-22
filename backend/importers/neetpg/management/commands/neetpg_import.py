"""`python manage.py neetpg_import --pdf <file>`"""
from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ...config import get_config
from ...runner import process_one_pdf


class Command(BaseCommand):
    help = "Import a single NEET PG recall PDF."

    def add_arguments(self, parser):
        parser.add_argument("--pdf", type=Path, required=True)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        pdf: Path = opts["pdf"]
        if not pdf.exists():
            raise CommandError(f"pdf not found: {pdf}")
        cfg = get_config()
        summary = process_one_pdf(pdf, cfg)
        self.stdout.write(self.style.SUCCESS(str(summary)))