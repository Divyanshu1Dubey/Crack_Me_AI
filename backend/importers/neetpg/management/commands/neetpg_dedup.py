"""`python manage.py neetpg_dedup`

Re-run dedup over already-parsed JSONL files in the parsed directory.
"""
from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand

from ...config import get_config
from ... import deduplicator


class Command(BaseCommand):
    help = "Re-run deduplication over previously parsed JSONL."

    def handle(self, *args, **opts):
        cfg = get_config()
        if not cfg.parsed_dir.exists():
            self.stdout.write("No parsed JSONL yet.")
            return
        total_report = deduplicator.DedupReport()
        for path in cfg.parsed_dir.glob("*.questions.jsonl"):
            questions = []
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                questions.append(_row_to_question(row))
            r = deduplicator.dedup_batch(questions, [])
            total_report.new_canonical += r.new_canonical
            total_report.exact_sha_duplicates += r.exact_sha_duplicates
            total_report.fuzzy_duplicates += r.fuzzy_duplicates
            total_report.embedding_duplicates += r.embedding_duplicates
            self.stdout.write(
                f"  {path.name}: +{r.new_canonical} canonical, "
                f"{r.exact_sha_duplicates} sha-dup, {r.fuzzy_duplicates} fuzzy-dup"
            )
        self.stdout.write(self.style.SUCCESS(str(total_report)))


def _row_to_question(row: dict):
    from ...models import ParsedOption, ParsedQuestion
    opts = [ParsedOption(**{k: o.get(k) for k in ("label", "text", "is_correct", "image_refs")})
            for o in row.get("options", [])]
    return ParsedQuestion(
        source_sha16=row.get("source_sha16", ""),
        page_number=row.get("page_number", 0),
        question_number_in_pdf=row.get("question_number_in_pdf"),
        stem=row.get("stem", ""),
        stem_raw=row.get("stem_raw", ""),
        options=opts,
        answer_labels=row.get("answer_labels", []),
        answer_text=row.get("answer_text"),
        explanation=row.get("explanation"),
        question_type=row.get("question_type", "single_best"),
        is_image_based=row.get("is_image_based", False),
        raw=row.get("raw", ""),
        extraction_confidence=row.get("extraction_confidence", 0.0),
        confidence_score=row.get("confidence_score", 0.0),
        ocr_confidence=row.get("ocr_confidence", 0.0),
    )