"""
Bulk Answer Verification Command.

Iterates through questions (by year) and uses multi-model AI voting
to independently verify stored correct answers. Generates a report
of mismatches and optionally auto-corrects them.

Usage:
  python manage.py verify_answers --year 2018 --dry-run
  python manage.py verify_answers --year 2018 --fix
  python manage.py verify_answers --all-years
"""
import csv
import json
import logging
import os
import time
from collections import Counter
from django.core.management.base import BaseCommand
from django.utils import timezone

from questions.models import Question

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Verify stored correct answers using multi-model AI consensus voting."

    def add_arguments(self, parser):
        parser.add_argument(
            "--year", type=int, default=0,
            help="Specific year to verify (e.g. 2018). 0 = use --all-years.",
        )
        parser.add_argument(
            "--all-years", action="store_true",
            help="Verify ALL years in the database.",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Only generate report, do NOT modify any database records.",
        )
        parser.add_argument(
            "--fix", action="store_true",
            help="Auto-correct answers where AI consensus disagrees with stored answer.",
        )
        parser.add_argument(
            "--limit", type=int, default=0,
            help="Limit number of questions to verify (0 = no limit).",
        )
        parser.add_argument(
            "--sleep-ms", type=int, default=500,
            help="Delay in milliseconds between AI calls to avoid rate limits.",
        )
        parser.add_argument(
            "--output", type=str, default="",
            help="Path to write CSV report of mismatches.",
        )

    def handle(self, *args, **options):
        year = options["year"]
        all_years = options["all_years"]
        dry_run = options["dry_run"]
        fix = options["fix"]
        limit = options["limit"]
        sleep_ms = options["sleep_ms"]
        output_path = options["output"]

        if not year and not all_years:
            self.stderr.write(self.style.ERROR(
                "Specify --year YYYY or --all-years"
            ))
            return

        # Build queryset
        qs = Question.objects.filter(is_active=True).exclude(admin_edited=True)
        if year:
            qs = qs.filter(year=year)
        qs = qs.order_by("year", "id")

        if limit:
            qs = qs[:limit]

        questions = list(qs)
        self.stdout.write(self.style.SUCCESS(
            f"\nVerifying {len(questions)} questions"
            f" (year={'ALL' if all_years else year})"
            f" | dry_run={dry_run} | fix={fix}"
        ))

        # Initialize AI service
        from ai_engine.services import AIService
        service = AIService()

        mismatches = []
        verified = 0
        agreed = 0
        errors = 0

        for i, q in enumerate(questions):
            self.stdout.write(f"  [{i+1}/{len(questions)}] Q#{q.id} (Year {q.year})...", ending="")

            options_dict = {
                "A": q.option_a,
                "B": q.option_b,
                "C": q.option_c,
                "D": q.option_d,
            }

            try:
                consensus = service.get_consensus_answer(q.question_text, options_dict)
            except Exception as e:
                self.stdout.write(self.style.WARNING(f" ERROR: {e}"))
                errors += 1
                continue

            if not consensus:
                self.stdout.write(self.style.WARNING(" NO CONSENSUS"))
                errors += 1
                continue

            verified += 1
            stored = q.correct_answer.strip().upper()

            if consensus == stored:
                agreed += 1
                self.stdout.write(self.style.SUCCESS(f" ✅ Agrees: {stored}"))
            else:
                self.stdout.write(self.style.ERROR(
                    f" ❌ MISMATCH: DB={stored}, AI={consensus}"
                ))
                mismatches.append({
                    "question_id": q.id,
                    "year": q.year,
                    "subject": q.subject.name if q.subject else "",
                    "question_text": q.question_text[:120],
                    "stored_answer": stored,
                    "ai_consensus": consensus,
                    "option_a": q.option_a[:60],
                    "option_b": q.option_b[:60],
                    "option_c": q.option_c[:60],
                    "option_d": q.option_d[:60],
                })

                if fix and not dry_run:
                    q.correct_answer = consensus
                    q.needs_review = True
                    q.is_disputed = True
                    # Clear cached AI explanation so it regenerates with correct answer
                    q.ai_explanation = ""
                    q.ai_generated_at = None
                    q.save()
                    self.stdout.write(self.style.WARNING(
                        f"    → FIXED: Updated Q#{q.id} answer to {consensus}"
                    ))
                elif not dry_run:
                    # Just flag for review without changing
                    q.needs_review = True
                    q.is_disputed = True
                    q.save(update_fields=["needs_review", "is_disputed", "updated_at",
                                          "question_text", "option_a", "option_b",
                                          "option_c", "option_d", "explanation",
                                          "concept_explanation", "mnemonic", "reference_text"])
                    self.stdout.write(self.style.WARNING(
                        f"    → FLAGGED Q#{q.id} for admin review"
                    ))

            if sleep_ms > 0:
                time.sleep(sleep_ms / 1000.0)

        # Summary
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS(f"Verification Complete"))
        self.stdout.write(f"  Total checked: {verified}")
        self.stdout.write(f"  Agreed:        {agreed}")
        self.stdout.write(self.style.ERROR(f"  Mismatches:    {len(mismatches)}"))
        self.stdout.write(f"  Errors:        {errors}")
        if mismatches:
            accuracy = round(agreed / verified * 100, 1) if verified else 0
            self.stdout.write(f"  Answer accuracy: {accuracy}%")

        # Write CSV report
        if mismatches:
            csv_path = output_path or f"answer_mismatches_{year or 'all'}.csv"
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=mismatches[0].keys())
                writer.writeheader()
                writer.writerows(mismatches)
            self.stdout.write(self.style.SUCCESS(
                f"\n📄 Mismatch report saved to: {csv_path}"
            ))
