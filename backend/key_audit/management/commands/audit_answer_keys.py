"""Management command to audit medical answer keys across the question bank.

Evaluates every question against deterministic evidence signals:
  - Publisher PDF answer keys (Unicode PUA decoded from source compilations)
  - Explanation explicit statements vs. stored key conflicts
  - Systematic default key anomalies (NEET PG 2025 / INI-CET 2025 vote parser bias)
  - Missing or invalid keys (empty, E/F)
  - Missing image context
  - Student dispute reports

Populates QuestionAudit records with suggested_key and priority for human editorial review.
NEVER automatically modifies Question.correct_answer.

Usage:
  python manage.py audit_answer_keys [--limit N] [--exam EXAM] [--dry-run]
"""
from __future__ import annotations

import logging
from collections import Counter

from django.core.management.base import BaseCommand
from django.db.models import Q

from key_audit.models import QuestionAudit
from key_audit.services import audit_question
from questions.models import Question

logger = logging.getLogger("key_audit.command")


class Command(BaseCommand):
    help = "Audit question bank answer keys against evidence signals and populate QuestionAudit."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None, help="Limit number of questions to audit.")
        parser.add_argument("--exam", type=str, default="", help="Filter by exam_type (e.g. upsc_cms, neet_pg, ini_cet).")
        parser.add_argument("--dry-run", action="store_true", default=False, help="Preview results without saving.")

    def handle(self, *args, **options):
        limit = options["limit"]
        exam = options["exam"]
        dry_run = options["dry_run"]

        qs = Question.objects.filter(is_active=True)
        if exam:
            qs = qs.filter(exam_type=exam)
        if limit:
            qs = qs[:limit]

        total = qs.count()
        self.stdout.write(f"=== Auditing {total} active questions (exam={exam or 'all'}, dry_run={dry_run}) ===")

        status_counts = Counter()
        reason_counts = Counter()
        high_priority_samples = []

        scanned = 0
        for q in qs.iterator(chunk_size=500):
            scanned += 1
            if scanned % 1000 == 0 or scanned == total:
                self.stdout.write(f"  Processed {scanned}/{total} questions...")

            audit = audit_question(q)
            status = audit.status
            reason = audit.status_reason
            prio = audit.priority
            sugg = audit.suggested_key

            status_counts[status] += 1
            if reason:
                reason_counts[reason] += 1

            if prio >= 90.0 and len(high_priority_samples) < 10:
                high_priority_samples.append({
                    "id": q.id,
                    "exam": getattr(q, "exam_type", ""),
                    "stored_key": q.correct_answer,
                    "suggested_key": sugg,
                    "status": status,
                    "reason": reason,
                    "priority": prio,
                })

        self.stdout.write("\n=== Answer Key Audit Classification Summary ===")
        for st, count in status_counts.most_common():
            pct = (count / total * 100) if total else 0
            self.stdout.write(f"  {st:22}: {count:6} ({pct:5.1f}%)")

        self.stdout.write("\nTop Primary Risk Reasons:")
        for r, count in reason_counts.most_common(10):
            self.stdout.write(f"  {r:30}: {count:6}")

        self.stdout.write("\nSample High-Priority Review Items (Priority >= 90):")
        for s in high_priority_samples:
            self.stdout.write(
                f"  Q#{s['id']:<5} [{s['exam']}] Stored: {s['stored_key']} -> Suggested: {s['suggested_key']} "
                f"| Prio: {s['priority']} | Reason: {s['reason']}"
            )

        self.stdout.write("\n[OK] Answer key audit complete.")
