"""
Production-incident fix (2026-07-26): re-run the AI explanation pipeline
for every Question whose `ai_explanation` is empty/blank, even if
`ai_generated_at` is already set.

Why a new command (and not just `--force` on `generate_missing_ai.py`):
    The existing `generate_missing_ai.py` filters on
    `ai_generated_at__isnull=True`. If a row was processed once but the
    AI call failed (provider quota, timeout, parse error), the field
    may stay empty while `ai_generated_at` got stamped, so the row is
    skipped forever. Students see "half-answered" questions on the
    NEET PG / INICET practice page.

    This command:
      - Filters on `ai_explanation` truly empty (not just ai_generated_at).
      - Batches in chunks of 50 + sleeps 1.5s between batches to respect
        the 11-provider rate limits.
      - Retries each row up to 2 times with exponential backoff so a
        transient provider failure doesn't break the whole run.
      - Saves in batched transactions to avoid long-running locks.
      - Reports progress + a final summary to stdout.
      - Resets `ai_generated_at` only on success — failed rows are left
        untouched so the next run can retry.

Run:
    # default: fill every empty explanation, batched
    python manage.py backfill_empty_ai

    # only NEET PG 2021
    python manage.py backfill_empty_ai --year 2021 --subject neet-pg

    # dry-run report (no AI calls, just count)
    python manage.py backfill_empty_ai --dry-run

    # cap to 200 rows for a quick smoke test
    python manage.py backfill_empty_ai --limit 200
"""
import json
import logging
import time

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from questions.models import Question
from ai_engine.services import AIService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Re-run AI explanations for every Question whose ai_explanation is empty."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true",
                            help="Re-run even when ai_explanation is non-empty.")
        parser.add_argument("--limit", type=int, default=0,
                            help="Stop after processing N rows.")
        parser.add_argument("--subject", type=str, default=None,
                            help="Filter by subject.code (e.g. neet-pg, ini-cet).")
        parser.add_argument("--year", type=int, default=None,
                            help="Filter by year.")
        parser.add_argument("--batch-size", type=int, default=50,
                            help="Rows per batch (default 50).")
        parser.add_argument("--batch-pause", type=float, default=1.5,
                            help="Seconds to sleep between batches (default 1.5).")
        parser.add_argument("--max-retries", type=int, default=2,
                            help="Retries per row on transient failure (default 2).")
        parser.add_argument("--dry-run", action="store_true",
                            help="Print what would be processed without calling AI.")

    def handle(self, *args, **options):
        force = options["force"]
        limit = options["limit"]
        subject = options["subject"]
        year = options["year"]
        batch_size = options["batch_size"]
        batch_pause = options["batch_pause"]
        max_retries = options["max_retries"]
        dry_run = options["dry_run"]

        qs = Question.objects.all()
        if not force:
            # The actual symptom: ai_explanation is empty (blank string).
            # ai_generated_at may be set or null. Catch both.
            from django.db.models import Q
            qs = qs.filter(Q(ai_explanation="") | Q(ai_explanation__isnull=True))
        if subject:
            qs = qs.filter(subject__code=subject)
        if year:
            qs = qs.filter(year=year)

        total = qs.count()
        if limit:
            qs = qs[:limit]
            total = min(total, limit)

        if total == 0:
            self.stdout.write(self.style.SUCCESS("No questions to backfill."))
            return

        self.stdout.write(self.style.NOTICE(
            f"Backfilling AI explanations for {total} question(s) "
            f"(batch_size={batch_size}, pause={batch_pause}s, retries={max_retries})..."
        ))

        if dry_run:
            for q in qs[:20]:
                self.stdout.write(f"  [dry-run] Q{q.id} ({q.year or '?'} / {q.subject or '?'}) — {q.question_text[:60]!r}")
            self.stdout.write(self.style.SUCCESS(f"[dry-run] {total} candidate(s) identified."))
            return

        service = AIService()
        success = 0
        failed = 0
        skipped = 0
        processed = 0

        # Process in batches so a slow provider can't tie up the DB.
        batch = []
        for question in qs.iterator(chunk_size=batch_size):
            batch.append(question)
            if len(batch) >= batch_size:
                s, f, k = self._process_batch(batch, service, max_retries)
                success += s
                failed += f
                skipped += k
                processed += len(batch)
                self.stdout.write(f"  progress: {processed}/{total} (ok={success}, fail={failed}, skip={skipped})")
                batch = []
                time.sleep(batch_pause)
        if batch:
            s, f, k = self._process_batch(batch, service, max_retries)
            success += s
            failed += f
            skipped += k
            processed += len(batch)

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. Processed={processed}, success={success}, failed={failed}, skipped={skipped}"
        ))
        if failed:
            self.stdout.write(self.style.WARNING(
                "Some rows failed. Re-run without --limit to retry; failed rows still have empty ai_explanation."
            ))

    def _process_batch(self, batch, service, max_retries):
        """Process a batch of questions. Returns (success, failed, skipped)."""
        success = 0
        failed = 0
        skipped = 0

        for question in batch:
            try:
                populated = self._process_one(question, service, max_retries)
                if populated:
                    success += 1
                else:
                    skipped += 1
            except Exception as e:
                failed += 1
                logger.error(f"Q{question.id} failed after retries: {e}", exc_info=True)
                self.stdout.write(self.style.ERROR(f"  Q{question.id} failed: {e}"))
        return success, failed, skipped

    def _process_one(self, question, service, max_retries):
        """Process one question with retries. Returns True on success."""
        options_dict = {
            "A": question.option_a,
            "B": question.option_b,
            "C": question.option_c,
            "D": question.option_d,
        }

        result = None
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                result = service.explain_after_answer(
                    question_text=question.question_text,
                    options=options_dict,
                    correct_answer=question.correct_answer,
                    selected_answer=question.correct_answer,
                    subject=question.subject.name if question.subject else "",
                    topic=question.topic.name if question.topic else "",
                )
                if result and (result.get("why_correct") or result.get("analysis") or result.get("core_concept")):
                    break
                # Empty result — treat as transient, retry.
                last_error = "empty result"
            except Exception as e:
                last_error = str(e)
                if attempt < max_retries:
                    time.sleep(2 ** attempt)
                    continue
            if attempt < max_retries:
                time.sleep(2 ** attempt)

        if not result or not (result.get("why_correct") or result.get("analysis") or result.get("core_concept")):
            self.stdout.write(self.style.WARNING(
                f"  Q{question.id}: empty result after {max_retries + 1} attempt(s) ({last_error})"
            ))
            return False

        # Persist in a single transaction so a partial save can't leave the
        # row half-updated.
        with transaction.atomic():
            question.ai_explanation = json.dumps(result)
            question.ai_answer = result.get("why_correct", "")
            question.ai_mnemonic = result.get("mnemonic", "")
            question.ai_clinical_pearl = result.get("clinical_pearl", "")
            question.learning_technique = result.get("exam_tip", "")
            textbook_ref = result.get("textbook_reference", {})
            if textbook_ref:
                question.ai_references = [textbook_ref]
            around_concepts = result.get("around_concepts", [])
            if around_concepts:
                question.concept_keywords = around_concepts
            question.ai_generated_at = timezone.now()
            question.ai_model = "RoundRobin-11"
            question.ai_version = "v1"
            question.save()

        self.stdout.write(self.style.SUCCESS(f"  Q{question.id}: populated"))
        return True
