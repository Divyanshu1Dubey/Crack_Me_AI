"""`python manage.py neetpg_report`

Regenerate markdown reports from the latest run.
"""
from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand

from ...config import get_config
from ...runner import _run_id
from ... import report as report_mod


class Command(BaseCommand):
    help = "Regenerate markdown reports for the most recent run."

    def handle(self, *args, **opts):
        cfg = get_config()
        if not cfg.manifest_path.exists():
            self.stdout.write("No manifest yet.")
            return
        manifest = json.loads(cfg.manifest_path.read_text(encoding="utf-8"))
        runs = manifest.get("runs", [])
        if not runs:
            self.stdout.write("No runs yet.")
            return
        latest = runs[-1]
        run_id = latest.get("run_id") or _run_id()
        summaries = latest.get("processed", [])

        rep_dir = cfg.reports_dir / run_id
        rep_dir.mkdir(parents=True, exist_ok=True)

        report_mod.write_import_report(
            rep_dir, run_id=run_id,
            pdf_count=len(summaries),
            page_count=sum(s.get("page_count", 0) for s in summaries),
            question_count=sum(s.get("question_count", 0) for s in summaries),
            image_count=sum(s.get("image_count", 0) for s in summaries),
            sources=summaries,
        )
        self.stdout.write(self.style.SUCCESS(f"Reports regenerated at {rep_dir}"))