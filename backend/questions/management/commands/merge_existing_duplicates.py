"""Bulk soft-drop non-canonical duplicates across every DuplicateCluster.

Background
----------
The dedup pipeline (`find_and_merge_duplicates.py`) has already detected
2,858 clusters containing 6,478 DuplicateMember rows. Every cluster has a
`canonical_question_id` chosen by the canonical-selection algorithm
(prefer admin-edited -> most images -> oldest created_at -> lowest id).

This command consumes that pre-computed canonical choice and soft-drops
every non-canonical member (`is_dropped=True, is_active=False`). It is
idempotent: rows already dropped are skipped.

Mirrors the per-row semantics of `QuestionViewSet.merge_duplicates`
(backend/questions/views.py:538). Skips a row if:
  * it IS the canonical
  * it is already `is_dropped=True`

Usage
-----
    # DRY RUN — show plan, no writes
    cd backend
    python manage.py merge_existing_duplicates

    # LIVE — actually soft-drop
    python manage.py merge_existing_duplicates --apply

    # Optional limit for spot-checking
    python manage.py merge_existing_duplicates --limit 50
"""
from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import F

from questions.models import (
    DuplicateMember,
    Question,
)


class Command(BaseCommand):
    help = (
        "Bulk soft-drop non-canonical duplicates in every DuplicateCluster. "
        "Uses canonical_question_id already stored on each cluster. "
        "Mirrors POST /questions/<id>/merge-duplicates/."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply the soft-drops. Without this, command is a dry-run.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Process at most N rows (for spot-checking). 0 = unlimited.",
        )
        parser.add_argument(
            "--report",
            type=str,
            default="docs/MERGE_DUPLICATES_REPORT.json",
            help="Path to write the JSON plan/report.",
        )

    def handle(self, *args, **options):
        apply = options["apply"]
        limit = options["limit"] or None
        report_path = Path(options["report"])

        # Build the plan: one row per (cluster, non-canonical member).
        # F("cluster__canonical_question_id") compares two columns in
        # the WHERE clause.
        plan_qs = (
            DuplicateMember.objects
            .filter(cluster__canonical_question__isnull=False)
            .exclude(question_id__isnull=True)
            .exclude(question_id=F("cluster__canonical_question_id"))
            .select_related("cluster", "question")
            .order_by("cluster_id", "question_id")
        )
        if limit:
            plan_qs = plan_qs[:limit]

        rows = list(plan_qs)

        plan = []
        for m in rows:
            plan.append({
                "cluster_id": m.cluster_id,
                "canonical_id": m.cluster.canonical_question_id,
                "duplicate_id": m.question_id,
                "already_dropped": bool(m.question.is_dropped),
                "already_inactive": m.question.is_active is False,
            })

        total = len(plan)
        already_dropped = sum(1 for p in plan if p["already_dropped"])
        to_drop = total - already_dropped
        cluster_ids = sorted({p["cluster_id"] for p in plan})

        self.stdout.write(self.style.NOTICE(
            f"Plan: {total} non-canonical member rows across "
            f"{len(cluster_ids)} clusters."
        ))
        self.stdout.write(
            f"  will soft-drop : {to_drop}\n"
            f"  already dropped: {already_dropped}"
        )
        if limit:
            self.stdout.write(self.style.WARNING(
                f"  --limit {limit} in effect (sliced first {limit} rows)."
            ))

        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps({
            "total_rows": total,
            "will_soft_drop": to_drop,
            "already_dropped": already_dropped,
            "clusters_touched": len(cluster_ids),
            "plan": plan,
        }, indent=2, ensure_ascii=False))
        self.stdout.write(self.style.SUCCESS(
            f"  plan written -> {report_path}"
        ))

        if not apply:
            self.stdout.write(self.style.WARNING(
                "DRY RUN. Re-run with --apply to commit."
            ))
            return

        if to_drop == 0:
            self.stdout.write(self.style.SUCCESS(
                "Nothing to do (all targeted rows already dropped)."
            ))
            return

        to_apply = [p for p in plan if not p["already_dropped"]]
        dup_ids = [p["duplicate_id"] for p in to_apply]

        with transaction.atomic():
            # Ensure every soft-dropped row is registered as a member
            # of its cluster (parity with merge_duplicates view).
            existing_members = set(
                DuplicateMember.objects
                .filter(question_id__in=dup_ids)
                .values_list("question_id", "cluster_id")
            )
            to_create = []
            for p in to_apply:
                key = (p["duplicate_id"], p["cluster_id"])
                if key in existing_members:
                    continue
                to_create.append(DuplicateMember(
                    cluster_id=p["cluster_id"],
                    question_id=p["duplicate_id"],
                    similarity_score=1.0,
                ))
            if to_create:
                DuplicateMember.objects.bulk_create(to_create, ignore_conflicts=True)

            updated = (
                Question.objects
                .filter(id__in=dup_ids)
                .update(is_dropped=True, is_active=False)
            )

        self.stdout.write(self.style.SUCCESS(
            f"APPLIED: soft-dropped {updated} rows; "
            f"created {len(to_create)} missing DuplicateMember rows."
        ))
