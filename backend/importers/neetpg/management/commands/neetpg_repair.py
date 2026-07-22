"""`python manage.py neetpg_repair --min-confidence 0.7`

Re-run quality checks and emit a repair queue. Future work: integrate
LLM-based repair for borderline rows.
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand

from ...config import get_config
from ... import quality as quality_mod
from ...models import ParsedQuestion, ParsedOption


class Command(BaseCommand):
    help = "Repair low-confidence rows (flag-only in v1)."

    def add_arguments(self, parser):
        parser.add_argument("--min-confidence", type=float, default=0.70)

    def handle(self, *args, **opts):
        cfg = get_config()
        threshold = float(opts["min_confidence"])
        if not cfg.parsed_dir.exists():
            self.stdout.write("No parsed JSONL yet.")
            return
        flagged = 0
        total = 0
        for path in cfg.parsed_dir.glob("*.questions.jsonl"):
            qs = []
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                qs.append(_row_to_question(row))
            kept, issues, stats = quality_mod.check_questions(qs)
            total += stats.total
            flagged += stats.flagged
            self.stdout.write(f"  {path.name}: {stats.flagged}/{stats.total} flagged")
        self.stdout.write(self.style.SUCCESS(f"Total {flagged}/{total} flagged for repair"))


def _row_to_question(row: dict):
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