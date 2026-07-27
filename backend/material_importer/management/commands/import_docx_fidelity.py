"""Universal DOCX fidelity importer (P14 — Phase 7).

Usage:
    python manage.py import_docx_fidelity <file_or_folder> [--publish] [--report PATH]

Wraps:
    1. `ingest_path(...)` — parse DOCX/PDF/PPTX/TXT, persist staging rows.
    2. `publish_batch_and_build_tests(batch_id)` — promote approved rows
       into the live `Question` bank and build auto-tests.

Writes a JSON report. Backward-compatible: doesn't replace the existing
``questions/import_mocktests`` command.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from material_importer.ingest_service import ingest_path
from material_importer.mock_test_builder import (
    delete_batch,
    publish_batch_and_build_tests,
)


class Command(BaseCommand):
    help = "Import a single DOCX (or a folder) with full fidelity and publish as a mock test."

    def add_arguments(self, parser):
        parser.add_argument("path", help="Single file or folder to import.")
        parser.add_argument("--label", default="", help="Optional batch source label.")
        parser.add_argument("--publish", action="store_true", help="Promote approved rows to the Question bank and build tests.")
        parser.add_argument("--no-build", action="store_true", help="Skip the auto-test builder (still publishes).")
        parser.add_argument("--use-ai", action="store_true", help="Run AI classification per question.")
        parser.add_argument("--max-files", type=int, default=None, help="Cap on number of files to ingest.")
        parser.add_argument("--report", default="import_docx_fidelity_report.json", help="Path to write the JSON report.")
        parser.add_argument("--rollback", action="store_true", help="If a previous batch exists for this path (by sha256), delete it before re-importing.")
        parser.add_argument("--force", action="store_true", help="Bypass cross-batch dedup (P1 escape hatch). Use for fidelity upgrades or deliberate re-imports.")

    def handle(self, *args, **opts):
        path = os.path.abspath(opts["path"])
        if not os.path.exists(path):
            raise CommandError(f"Path not found: {path}")

        started = time.time()
        self.stdout.write(self.style.NOTICE(f"Ingesting: {path}"))

        if opts["rollback"]:
            from material_importer.models import ImportBatch, ImportMaterial
            import hashlib as _hl
            if os.path.isfile(path):
                fp = path
                sha = _hl.sha256(open(fp, "rb").read()).hexdigest()
                mat = ImportMaterial.objects.filter(file_sha256=sha).first()
                if mat:
                    self.stdout.write(self.style.WARNING(f"Rolling back batch {mat.batch_id} (matched by file_sha256)"))
                    delete_batch(mat.batch_id, delete_published=True)
            elif os.path.isdir(path):
                for root, _dirs, files in os.walk(path):
                    for fn in files:
                        fp = os.path.join(root, fn)
                        try:
                            sha = _hl.sha256(open(fp, "rb").read()).hexdigest()
                        except OSError:
                            continue
                        mat = ImportMaterial.objects.filter(file_sha256=sha).first()
                        if mat:
                            self.stdout.write(self.style.WARNING(f"Rolling back batch {mat.batch_id} (file {fn})"))
                            delete_batch(mat.batch_id, delete_published=True)

        batch = ingest_path(
            path,
            source_label=opts["label"] or Path(path).name,
            use_ai=opts["use_ai"],
            max_files=opts["max_files"],
            force=opts["force"],
        )

        report = {
            "source_file": Path(path).name,
            "batch_id": batch.id,
            "status": batch.status,
            "questions_found": batch.questions_found,
            "questions_extracted": batch.questions_extracted,
            "questions_rejected": batch.questions_rejected,
            "duplicates_skipped": batch.duplicates_skipped,
            "theory_blocks_extracted": batch.theory_blocks_extracted,
            "images_extracted": batch.images_extracted,
            "tests_built": 0,
            "files_processed": batch.files_processed,
            "total_files": batch.total_files,
            "duration_ms": int((time.time() - started) * 1000),
            "warnings": [],
            "errors": batch.error_report or [],
        }

        if opts["publish"]:
            pub_started = time.time()
            res = publish_batch_and_build_tests(batch.id)
            report["tests_built"] = res.get("tests_built", 0)
            report["published"] = res.get("published", 0)
            report["publish_duration_ms"] = int((time.time() - pub_started) * 1000)

        for m in batch.materials.all():
            if m.parse_warnings:
                for w in m.parse_warnings[:50]:
                    report["warnings"].append({"file": m.original_filename, "warning": w})

        report_path = os.path.abspath(opts["report"])
        if os.path.dirname(report_path):
            os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)

        self.stdout.write(self.style.SUCCESS(
            f"Imported {report['questions_found']} questions ({report['questions_extracted']} accepted, "
            f"{report['questions_rejected']} rejected, {report['duplicates_skipped']} duplicate). "
            f"Tests built: {report['tests_built']}. "
            f"Report: {report_path}"
        ))