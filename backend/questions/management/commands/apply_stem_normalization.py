"""Apply the verified stem-structure normalization to the database.

This management command reads docs/STEM_STRUCTURE_REVIEW.json and
applies ONLY the rows in the ``auto_rewrite`` bucket (confidence
≥ 0.98). Rows in any other bucket are left untouched.

Before any write, a rollback snapshot is saved to
``docs/STEM_STRUCTURE_ROLLBACK_<timestamp>.json`` containing
``(id, original_question_text, rewritten_question_text,
applied_at, migration_version)`` for every row that will be touched.

The write is wrapped in ``transaction.atomic()``. If any row fails,
the entire transaction is rolled back — no partial state.

Usage:
    python manage.py apply_stem_normalization
    python manage.py apply_stem_normalization --dry-run
    python manage.py apply_stem_normalization --rollback <snapshot.json>
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import django
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone as djtz

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')


MIGRATION_VERSION = "2026_07_30_apply_stem_normalization_v1"


class Command(BaseCommand):
    help = "Apply the verified auto_rewrite stem-normalization candidates."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Print planned changes without writing.")
        parser.add_argument("--rollback", type=str, default=None,
                            help="Path to a snapshot JSON. Reverts every "
                                 "row in the snapshot to its original "
                                 "question_text.")

    def handle(self, *args, **options):
        if options["rollback"]:
            return self._rollback(options["rollback"])

        review_path = Path("docs/STEM_STRUCTURE_REVIEW.json")
        if not review_path.exists():
            self.stderr.write(self.style.ERROR(
                f"missing {review_path} — run probe first"))
            sys.exit(1)

        review = json.loads(review_path.read_text(encoding="utf-8"))
        auto = review["buckets"].get("auto_rewrite", [])
        self.stdout.write(f"auto_rewrite candidates : {len(auto)}")

        if options["dry_run"]:
            for item in auto[:5]:
                self.stdout.write(f"  id={item['id']} score={item['score']:.3f}")
            self.stdout.write(f"\nDRY-RUN: no writes performed.")
            return

        # Phase 1: snapshot.
        snapshot_path = self._write_snapshot(auto)
        self.stdout.write(self.style.SUCCESS(
            f"snapshot written -> {snapshot_path}"))

        # Phase 2: apply in transaction.atomic().
        try:
            self._apply(auto)
        except Exception as exc:
            self.stderr.write(self.style.ERROR(
                f"apply failed, transaction rolled back: {exc}"))
            sys.exit(2)

        self.stdout.write(self.style.SUCCESS(
            f"applied {len(auto)} rewrites. rollback file: {snapshot_path}"))

    def _write_snapshot(self, items):
        from questions.models import Question
        Path("docs").mkdir(exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = Path(f"docs/STEM_STRUCTURE_ROLLBACK_{ts}.json")

        # Resolve the CURRENT question_text from the DB for every row
        # we plan to touch. This is the rollback source-of-truth.
        ids = [item["id"] for item in items]
        live = {q.id: q.question_text
                for q in Question.objects.filter(id__in=ids).only(
                    "id", "question_text")}
        snapshot = {
            "migration_version": MIGRATION_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "bucket": "auto_rewrite",
            "rows": [
                {
                    "id": item["id"],
                    "original_question_text": live[item["id"]],
                    "rewritten_question_text": item["after"],
                    "score": item["score"],
                }
                for item in items
                if item["id"] in live
            ],
        }
        path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False),
                         encoding="utf-8")
        return path

    @transaction.atomic
    def _apply(self, items):
        from questions.models import Question
        sid = transaction.savepoint()
        try:
            for item in items:
                q = Question.objects.select_for_update().get(id=item["id"])
                q.question_text = item["after"]
                q.save(update_fields=["question_text"])
            transaction.savepoint_commit(sid)
        except Exception:
            transaction.savepoint_rollback(sid)
            raise

    def _rollback(self, snapshot_path):
        from questions.models import Question
        path = Path(snapshot_path)
        if not path.exists():
            self.stderr.write(self.style.ERROR(
                f"snapshot not found: {snapshot_path}"))
            sys.exit(1)
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        rows = snapshot["rows"]
        self.stdout.write(f"rolling back {len(rows)} rows from {snapshot_path}")

        with transaction.atomic():
            sid = transaction.savepoint()
            try:
                for row in rows:
                    q = Question.objects.select_for_update().get(id=row["id"])
                    q.question_text = row["original_question_text"]
                    q.save(update_fields=["question_text"])
                transaction.savepoint_commit(sid)
            except Exception as exc:
                transaction.savepoint_rollback(sid)
                self.stderr.write(self.style.ERROR(
                    f"rollback failed: {exc}"))
                sys.exit(2)
        self.stdout.write(self.style.SUCCESS(f"rollback complete"))