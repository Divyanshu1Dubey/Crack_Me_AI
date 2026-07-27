"""Print or save a QA report for a given import batch.

Usage:
    python manage.py qa_report --batch 12
    python manage.py qa_report --batch 12 --out qa_12.json
"""
from __future__ import annotations

import argparse
import json

from django.core.management.base import BaseCommand

from ...quality import build_qa_report, save_qa_report


class Command(BaseCommand):
    help = "Print or save the QA report for a material import batch."

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--batch", type=int, required=True)
        parser.add_argument("--out", default=None, help="Optional path to dump the JSON.")

    def handle(self, *args, **opts):
        report = build_qa_report(opts["batch"])
        if opts["out"]:
            save_qa_report(opts["batch"], opts["out"])
            self.stdout.write(self.style.SUCCESS(f"Wrote {opts['out']}"))
        else:
            self.stdout.write(json.dumps(report, indent=2, default=str))
