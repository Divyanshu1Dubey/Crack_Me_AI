"""Run the generic material-import pipeline.

Usage:
    python manage.py ingest_cms_material \
        --path ../cms_exclusive_material \
        --label "cms_exclusive_material batch 1" \
        [--use-ai] [--max-files 50] [--from-file-list list.txt]

After parsing, this command can optionally run AI enrichment on the
saved `ExtractedQuestion` rows (subject/topic via the existing
RoundRobin AI service). Enrichment runs immediately (synchronous) for
small batches; switch to the `enrich_pending_questions` management
command for background processing.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ...ingest_service import ingest_path


class Command(BaseCommand):
    help = "Ingest DOCX/PDF/PPTX files from a folder into the question/theory staging tables."

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--path", required=True, help="Folder or file to ingest.")
        parser.add_argument("--label", default="", help="Human label for the import batch.")
        parser.add_argument("--use-ai", action="store_true", help="Run AI classifier on each question.")
        parser.add_argument("--max-files", type=int, default=None, help="Limit number of files.")
        parser.add_argument("--from-file-list", default=None,
                            help="Path to a plain-text file of newline-separated paths to ingest instead of --path.")

    def handle(self, *args, **opts):
        if opts["from_file_list"]:
            file_list = Path(opts["from_file_list"]).read_text(encoding="utf-8").splitlines()
            file_list = [l.strip() for l in file_list if l.strip()]
            if not file_list:
                raise CommandError("from-file-list is empty")
            for fp in file_list:
                if not os.path.exists(fp):
                    self.stdout.write(self.style.WARNING(f"missing: {fp}"))
                    continue
                self._run_one(fp, opts)
            return
        path = opts["path"]
        if not os.path.exists(path):
            raise CommandError(f"Path does not exist: {path}")
        self._run_one(path, opts)

    def _run_one(self, path: str, opts) -> None:
        self.stdout.write(self.style.NOTICE(f"Ingesting {path} ..."))
        batch = ingest_path(
            path=path,
            source_label=opts["label"] or Path(path).name,
            use_ai=opts["use_ai"],
            max_files=opts["max_files"],
        )
        msg = (
            f"Batch#{batch.id} {batch.status}: "
            f"files={batch.files_processed}/{batch.total_files} "
            f"questions={batch.questions_extracted} "
            f"theory={batch.theory_blocks_extracted} "
            f"images={batch.images_extracted} "
            f"duplicates={batch.duplicates_skipped} "
            f"errors={len(batch.error_report or [])}"
        )
        self.stdout.write(self.style.SUCCESS(msg))
        if batch.error_report:
            for err in batch.error_report[:10]:
                self.stdout.write(self.style.WARNING(f"  - {err.get('file', '?')}: {err.get('error', '?')[:200]}"))
