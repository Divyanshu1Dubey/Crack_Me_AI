"""Auto-build mock tests for a batch.

Usage:
    python manage.py build_auto_tests --batch 12
"""
from __future__ import annotations

import argparse

from django.core.management.base import BaseCommand

from ...mock_test_builder import build_for_batch


class Command(BaseCommand):
    help = "Build auto-mock-tests for an import batch."

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--batch", type=int, required=True)
        parser.add_argument("--max-per-test", type=int, default=100)

    def handle(self, *args, **opts):
        n = build_for_batch(opts["batch"], max_per_test=opts["max_per_test"])
        self.stdout.write(self.style.SUCCESS(f"Built {n} auto-tests for batch {opts['batch']}"))
