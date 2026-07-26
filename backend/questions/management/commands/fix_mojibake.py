"""
fix_mojibake.py — One-shot cleanup of UTF-8-as-Latin-1 mojibake.

Walks every Question row and runs fix_mojibake() + NFC-normalize over its
text fields. Writes the cleaned text back to the DB and, when run with
--fixture, also rewrites backend/fixtures/cms_fixture.json so the production
deploy stays consistent.

Usage:
    python manage.py fix_mojibake                          # dry-run, prints counts
    python manage.py fix_mojibake --apply                  # write to DB
    python manage.py fix_mojibake --apply --fixture        # rewrite fixtures/cms_fixture.json (legacy path still accepted)
    python manage.py fix_mojibake --apply --fixture fixtures/cms_fixture.json
    python manage.py fix_mojibake --apply --fixture fixtures/neet_pg_fixture.json
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from questions.models import Question
from questions.text_encoding import fix_mojibake, normalize_text

logger = logging.getLogger(__name__)

TEXT_FIELDS = (
    "question_text",
    "option_a",
    "option_b",
    "option_c",
    "option_d",
    "explanation",
    "concept_explanation",
    "mnemonic",
    "ai_explanation",
    "ai_mnemonic",
    "ai_clinical_pearl",
    "concept_keywords_text",  # safe even if the model doesn't have it
)


class Command(BaseCommand):
    help = "Repair UTF-8-as-Latin-1 mojibake in Question text fields."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true",
                            help="Persist changes (default is dry-run).")
        parser.add_argument("--fixture", type=str, default="",
                            help="Path to questions_fixture.json to rewrite.")
        parser.add_argument("--batch-size", type=int, default=500)

    def handle(self, *args, **options):
        apply = options["apply"]
        fixture = options["fixture"]
        batch_size = options["batch_size"]

        affected = 0
        scanned = 0
        updated_fields: dict[str, int] = {f: 0 for f in TEXT_FIELDS}

        qs = Question.objects.all().only(*[f for f in TEXT_FIELDS if hasattr(Question, f)])
        self.stdout.write(f"Scanning {qs.count()} questions...")

        pending = []
        for q in qs.iterator(chunk_size=batch_size):
            scanned += 1
            dirty = False
            for field in updated_fields:
                if not hasattr(q, field):
                    continue
                original = getattr(q, field) or ""
                if not original:
                    continue
                fixed = normalize_text(original)
                if fixed != original:
                    dirty = True
                    setattr(q, field, fixed)
                    updated_fields[field] += 1
            if dirty:
                affected += 1
                if apply:
                    pending.append(q)
                    if len(pending) >= batch_size:
                        with transaction.atomic():
                            for item in pending:
                                item.save(update_fields=list(updated_fields.keys()))
                        pending.clear()

        if apply and pending:
            with transaction.atomic():
                for item in pending:
                    item.save(update_fields=list(updated_fields.keys()))

        self.stdout.write(self.style.SUCCESS(
            f"\n{'APPLIED' if apply else 'DRY-RUN'} "
            f"scanned={scanned} rows_updated={affected}"
        ))
        for field, count in updated_fields.items():
            if count:
                self.stdout.write(f"  {field}: {count} rows changed")

        if fixture and apply:
            self._rewrite_fixture(Path(fixture), updated_fields)
        elif fixture and not apply:
            self.stdout.write(self.style.WARNING(
                "Fixture path provided but --apply not set — fixture untouched."
            ))
        elif apply and not fixture:
            # If --apply is set without --fixture, default to fixtures/cms_fixture.json
            default_fixture = Path(__file__).resolve().parents[4] / 'fixtures' / 'cms_fixture.json'
            if default_fixture.exists():
                self.stdout.write(f"No --fixture given; defaulting to {default_fixture.relative_to(Path.cwd())}")
                self._rewrite_fixture(default_fixture, updated_fields)

    def _rewrite_fixture(self, fixture_path: Path, fields_changed: dict[str, int]) -> None:
        """Rewrite the fixture so the next deploy ships clean text.

        For each entry whose model == 'questions.question', re-emit any
        changed text field through normalize_text() and write the file back
        atomically.
        """
        if not fixture_path.exists():
            self.stdout.write(self.style.ERROR(f"Fixture not found: {fixture_path}"))
            return

        text_keys = {f for f, n in fields_changed.items() if n > 0}
        text_keys &= {"question_text", "option_a", "option_b", "option_c",
                      "option_d", "explanation", "concept_explanation", "mnemonic"}
        if not text_keys:
            self.stdout.write("No text fields changed — fixture left as-is.")
            return

        with fixture_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        rewritten = 0
        for entry in data:
            if entry.get("model") != "questions.question":
                continue
            fields = entry.setdefault("fields", {})
            for k in list(text_keys):
                if k in fields and isinstance(fields[k], str):
                    new = normalize_text(fields[k])
                    if new != fields[k]:
                        fields[k] = new
                        rewritten += 1

        tmp = fixture_path.with_suffix(fixture_path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        tmp.replace(fixture_path)
        self.stdout.write(self.style.SUCCESS(
            f"Fixture rewritten: {fixture_path} ({rewritten} fields touched)"
        ))