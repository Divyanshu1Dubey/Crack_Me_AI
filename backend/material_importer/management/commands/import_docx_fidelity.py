"""Universal DOCX fidelity importer (P14 — Phase 7).

Usage:
    python manage.py import_docx_fidelity <file_or_folder> [--publish] [--report PATH]
        [--rollback [--remove-published]]

Wraps:
    1. `ingest_path(...)` — parse DOCX/PDF/PPTX/TXT, persist staging rows.
    2. `publish_batch_and_build_tests(batch_id)` — promote approved rows
       into the live `Question` bank and build auto-tests.

``--rollback`` first rolls back every earlier batch that imported the same
file(s) (matched by sha256): their staging rows and auto-tests are removed,
but the questions they already published STAY LIVE in the bank (only the
staging link is dropped). That was this command's behaviour before the
Import Center rollback learnt to remove published questions; a re-import
publishes only rows that are approved again, so removing the old questions
here would empty the bank until the replacement is reviewed.

``--remove-published`` (with ``--rollback``) also takes the old batches'
published questions out of the bank (soft delete + RemovedQuestion
tombstone, like the admin "Remove from bank" action). The tombstones make
the recall importers and ``load_exam_fixture`` skip those stems from then
on. Use it only when the old questions must disappear now.

Writes a JSON report. Backward-compatible: doesn't replace the existing
``questions/import_mocktests`` command.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from material_importer.ingest_service import ingest_path
from material_importer.mock_test_builder import (
    delete_batch,
    publish_batch,
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
        parser.add_argument(
            "--rollback", action="store_true",
            help=("Before re-importing, roll back every earlier batch that imported the same file(s) "
                  "(matched by sha256). Their published questions stay live; see --remove-published."),
        )
        parser.add_argument(
            "--remove-published", action="store_true",
            help=("With --rollback: also remove the rolled-back batches' published questions from the bank "
                  "(soft delete + tombstone). They are NOT replaced until the re-import is approved and published."),
        )
        parser.add_argument("--force", action="store_true", help="Bypass cross-batch dedup (P1 escape hatch). Use for fidelity upgrades or deliberate re-imports.")

    @staticmethod
    def _sha256(path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()

    def _rollback_previous(self, path: str, *, remove_published: bool) -> list[dict]:
        """Roll back every earlier batch that imported one of the files at ``path``."""
        from material_importer.models import ImportMaterial

        if os.path.isfile(path):
            files = [path]
        else:
            files = [os.path.join(root, fn) for root, _dirs, names in os.walk(path) for fn in names]
        batch_ids: dict[int, str] = {}
        for fp in files:
            try:
                sha = self._sha256(fp)
            except OSError:
                continue
            for batch_id in (ImportMaterial.objects.filter(file_sha256=sha)
                             .values_list("batch_id", flat=True).distinct()):
                batch_ids.setdefault(batch_id, os.path.basename(fp))

        from django.utils import timezone
        from material_importer.batch_state import set_summary_key
        from material_importer.models import ImportAuditLog, ImportBatch

        results = []
        for batch_id, fn in sorted(batch_ids.items()):
            result = delete_batch(batch_id, delete_published=remove_published)
            # Mark the old batch rolled back, as the Import Center rollback does.
            set_summary_key(batch_id, "rollback", result)
            now = timezone.now()
            ImportBatch.objects.filter(pk=batch_id).update(status="cancelled", finished_at=now, updated_at=now)
            ImportAuditLog.objects.create(
                batch_id=batch_id, level="warning", code="rollback",
                message=f"Rolled back by import_docx_fidelity --rollback: {result}",
            )
            kept = len(result.get("published_question_ids") or [])
            if remove_published:
                note = f"{result.get('published_questions_removed', 0)} published question(s) removed from the bank"
            else:
                note = f"{kept} published question(s) kept live"
            self.stdout.write(self.style.WARNING(f"Rolled back batch {batch_id} (file {fn}): {note}"))
            results.append({"batch_id": batch_id, **result})
        return results

    def handle(self, *args, **opts):
        path = os.path.abspath(opts["path"])
        if not os.path.exists(path):
            raise CommandError(f"Path not found: {path}")
        if opts["remove_published"] and not opts["rollback"]:
            raise CommandError("--remove-published only applies together with --rollback.")

        started = time.time()
        self.stdout.write(self.style.NOTICE(f"Ingesting: {path}"))

        rollbacks: list[dict] = []
        if opts["rollback"]:
            rollbacks = self._rollback_previous(path, remove_published=opts["remove_published"])

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
            "rolled_back": rollbacks,
        }

        if opts["publish"]:
            pub_started = time.time()
            if opts["no_build"]:  # publish only (the flag used to be ignored)
                res = {"published": publish_batch(batch.id), "tests_built": 0}
            else:
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