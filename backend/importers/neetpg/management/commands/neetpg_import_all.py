"""`python manage.py neetpg_import_all --source-dir <path>`"""
from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ...config import get_config
from ...runner import run_import


class Command(BaseCommand):
    help = "Import every NEET PG recall PDF in a directory."

    def add_arguments(self, parser):
        parser.add_argument("--source-dir", type=Path, required=True)
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        source_dir: Path = opts["source_dir"]
        if not source_dir.exists():
            raise CommandError(f"source dir not found: {source_dir}")
        cfg = get_config()
        out = run_import(source_dir, cfg=cfg)
        self.stdout.write(self.style.SUCCESS(f"Run {out['run_id']}"))
        for s in out["summaries"]:
            self.stdout.write(str(s))