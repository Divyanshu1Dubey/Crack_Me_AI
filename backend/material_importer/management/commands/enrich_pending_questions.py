"""Run AI enrichment on staged ExtractedQuestion rows.

Usage:
    python manage.py enrich_pending_questions --batch 12
    python manage.py enrich_pending_questions --limit 50
    python manage.py enrich_pending_questions --batch 12 --since 2026-07-01
"""
from __future__ import annotations

import argparse
from datetime import datetime

from django.core.management.base import BaseCommand

from ...enrichment import enrich_batch


class Command(BaseCommand):
    help = "Run AI enrichment on staged ExtractedQuestion rows."

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--batch", type=int, required=True, help="ImportBatch id")
        parser.add_argument("--limit", type=int, default=None, help="Limit rows per run")
        parser.add_argument("--since", default=None, help="Only rows created after this ISO date")

    def handle(self, *args, **opts):
        limit = opts["limit"]
        n = enrich_batch(opts["batch"], limit=limit)
        self.stdout.write(self.style.SUCCESS(f"Enriched {n} questions in batch {opts['batch']}"))
