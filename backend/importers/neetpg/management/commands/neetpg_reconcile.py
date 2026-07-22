"""`python manage.py neetpg_reconcile [--source-dir <path>] [--dry-run]`

Reads Phase-1 parser output (`*.questions.jsonl`) and re-links it to the
Question rows already in the database. Useful when:

* a previous import ran but didn't write QuestionSource bridge rows,
* the JSONL was generated separately (e.g. a different machine) and
  you only have the JSONL artefact on hand.

Idempotent: re-running skips QuestionSource rows that already exist
(their `(question, recall_source, page_number, question_number_in_pdf)`
unique constraint prevents duplicates).
"""
from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from questions.models import Question, QuestionExtractionItem, QuestionSource, RecallSource


class Command(BaseCommand):
    help = "Re-link Phase-1 parsed JSONL into existing Question rows."

    def add_arguments(self, parser):
        parser.add_argument("--source-dir", type=Path, default=None,
                            help="Override parsed_dir; defaults to config.parsed_dir.")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--emit-extraction-items", action="store_true",
                            help="Emit unmatched JSONL rows as QuestionExtractionItem for admin review.")

    def handle(self, *args, **opts):
        from importers.neetpg.config import get_config

        cfg = get_config()
        parsed_dir: Path = opts.get("source_dir") or cfg.parsed_dir
        dry_run = bool(opts.get("dry_run"))
        emit_items = bool(opts.get("emit_extraction_items"))

        if not parsed_dir.exists():
            raise CommandError(f"parsed_dir not found: {parsed_dir}")
        jsonl_files = sorted(parsed_dir.glob("*.questions.jsonl"))
        if not jsonl_files:
            self.stdout.write("No *.questions.jsonl files in parsed_dir.")
            return

        total_lines = 0
        matched = 0
        unmatched = 0
        sources_created = 0
        items_emitted = 0
        rs_created = 0

        for path in jsonl_files:
            sha16_candidate = path.stem.split(".")[0]
            self.stdout.write(f"  … reconciling {path.name}")
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                total_lines += 1

                stem = row.get("stem") or row.get("stem_raw") or ""
                if not stem.strip():
                    unmatched += 1
                    if emit_items and not dry_run:
                        QuestionExtractionItem.objects.create(
                            status="pending",
                            raw_text=row.get("raw", ""),
                            question_text=stem,
                            review_note="reconcile: empty stem",
                        )
                        items_emitted += 1
                    continue

                # Naive reconciliation: match by first 50 chars of stem.
                head = stem.strip()[:50]
                q = (Question.objects
                     .filter(exam_type="neet_pg",
                             question_text__startswith=head)
                     .first())
                if not q:
                    unmatched += 1
                    if emit_items and not dry_run:
                        QuestionExtractionItem.objects.create(
                            status="pending",
                            raw_text=row.get("raw", ""),
                            question_text=stem,
                            page_number=str(row.get("page_number", "")),
                            review_note="reconcile: no DB match",
                        )
                        items_emitted += 1
                    continue

                recall_source = (
                    RecallSource.objects.filter(pdf_sha256_short=sha16_candidate).first()
                )
                if not recall_source and not dry_run:
                    self.stdout.write(self.style.WARNING(
                        f"      no RecallSource for sha16={sha16_candidate}; "
                        "creating stub."))
                    recall_source, rs_was_created = RecallSource.objects.get_or_create(
                        pdf_sha256_short=sha16_candidate,
                        defaults={
                            "pdf_filename": row.get("source_sha16", sha16_candidate),
                            "pdf_path": str(path),
                            "pdf_sha256": "",
                            "pdf_sha256_short": sha16_candidate,
                            "recall_status": "recall",
                            "scan_type": "unknown",
                        },
                    )
                    if rs_was_created:
                        rs_created += 1

                matched += 1
                if not dry_run and recall_source:
                    _, created = QuestionSource.objects.get_or_create(
                        question=q,
                        recall_source=recall_source,
                        page_number=row.get("page_number", 0) or 0,
                        question_number_in_pdf=row.get("question_number_in_pdf"),
                        defaults={
                            "original_text": row.get("raw", ""),
                            "extracted_text": stem,
                        },
                    )
                    if created:
                        sources_created += 1

        self.stdout.write(self.style.SUCCESS(
            f"Reconciled {total_lines} row(s): matched={matched} unmatched={unmatched} "
            f"QuestionSource rows created={sources_created} "
            f"RecallSource stubs created={rs_created} "
            f"items_emitted={items_emitted} dry_run={dry_run}"))

