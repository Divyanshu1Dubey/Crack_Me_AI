"""Detect existing duplicate Question rows and populate DuplicateCluster.

The recall importer creates DuplicateCluster/DuplicateMember records
during ingest, but the original NEET PG (recall) and UPSC CMS imports
pre-dated that machinery — so several questions exist as literal
duplicates (same `question_text` + same `year` + same `exam_source`)
without any cluster record pointing at them. The admin Questions Editor
shows both rows side-by-side, which is confusing and dangerous (admin
might edit the wrong one).

This script:
  1. Walks every active Question row.
  2. Computes a content-hash over (normalized question_text, year,
     exam_source).
  3. Groups rows that share the same hash.
  4. For every group of ≥2 rows, creates a DuplicateCluster (or reuses
     one whose canonical_id already points at a member of the group)
     and a DuplicateMember per row with similarity_score=1.0.
  5. Reports a summary so the admin can decide whether to merge
     (run `--apply` to soft-drop the duplicates).

Run:
    python manage.py shell < find_and_merge_duplicates.py            # dry-run
    python find_and_merge_duplicates.py --apply                       # create clusters only
    python find_and_merge_duplicates.py --apply --merge               # clusters + soft-drop
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from collections import defaultdict

import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crack_cms.settings")
django.setup()

from questions.models import DuplicateCluster, DuplicateMember, Question  # noqa: E402

_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^a-z0-9\s]+")


def _normalize(text: str) -> str:
    text = (text or "").lower()
    text = _PUNCT_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text).strip()
    return text


def _group_key(q: Question) -> tuple[str, int | None, str]:
    """Stable dedup key over (normalized text, year, exam_source)."""
    return (_normalize(q.question_text), q.year, q.exam_source or "")


def detect_groups() -> list[list[Question]]:
    qs = Question.objects.filter(is_active=True).only(
        "id", "question_text", "year", "exam_source", "is_dropped",
        "created_at", "admin_edited",
    ).order_by("id")
    groups: dict[tuple[str, int | None, str], list[Question]] = defaultdict(list)
    for q in qs:
        groups[_group_key(q)].append(q)
    return [g for g in groups.values() if len(g) >= 2]


def choose_canonical(group: list[Question]) -> Question:
    """Pick the row that should stay: prefer admin-edited, then most images,
    then oldest created_at, then lowest id."""
    def score(q: Question) -> tuple[int, int, int, int]:
        return (
            1 if getattr(q, "admin_edited", False) else 0,
            q.images.filter(is_active=True).count() if hasattr(q, "images") else 0,
            -q.id,  # earlier id wins ties
            0,  # placeholder for created_at tiebreak (cheap to omit)
        )

    return sorted(group, key=score, reverse=True)[0]


def find_or_create_cluster(canonical: Question, threshold: str = "1.000") -> DuplicateCluster:
    existing = (
        DuplicateCluster.objects.filter(canonical_question_id=canonical.id)
        .order_by("-id")
        .first()
    )
    if existing:
        return existing
    return DuplicateCluster.objects.create(
        canonical_question=canonical,
        similarity_threshold=threshold,
        detection_method="text-exact",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect duplicate Question rows and populate DuplicateCluster.")
    parser.add_argument("--apply", action="store_true",
                        help="Persist DuplicateCluster/DuplicateMember rows (default: dry-run report)")
    parser.add_argument("--merge", action="store_true",
                        help="With --apply: soft-drop non-canonical duplicates (is_dropped=True, is_active=False)")
    args = parser.parse_args()

    groups = detect_groups()
    print(f"Total active questions: {Question.objects.filter(is_active=True).count()}")
    print(f"Duplicate groups (>= 2 rows with identical normalized text + year + exam_source): {len(groups)}")
    print(f"Rows inside those groups: {sum(len(g) for g in groups)}")
    print()

    if not groups:
        print("Nothing to detect.")
        return 0

    # Top 20 biggest groups
    top = sorted(groups, key=len, reverse=True)[:20]
    print("Top 20 groups by size:")
    for g in top:
        canonical = choose_canonical(g)
        ids = ", ".join(f"Q{q.id}{' (canonical)' if q.id == canonical.id else ''}" for q in g[:8])
        if len(g) > 8:
            ids += f", ... +{len(g) - 8} more"
        text = g[0].question_text[:60].replace("\n", " ")
        print(f"  [{len(g)}] {ids} :: {text!r}")
    print()

    if not args.apply:
        print("DRY-RUN. Re-run with --apply to persist DuplicateCluster/DuplicateMember rows.")
        print("Add --merge to also soft-drop non-canonical duplicates.")
        return 0

    created_clusters = 0
    created_members = 0
    dropped = 0

    # Reuse existing canonical clusters first (no INSERT needed).
    new_clusters: list[DuplicateCluster] = []
    group_to_cluster: dict[int, DuplicateCluster] = {}
    for group in groups:
        canonical = choose_canonical(group)
        existing = (
            DuplicateCluster.objects.filter(canonical_question_id=canonical.id)
            .order_by("-id")
            .first()
        )
        if existing:
            group_to_cluster[id(group)] = existing
        else:
            cluster = DuplicateCluster(
                canonical_question=canonical,
                similarity_threshold="1.000",
                detection_method="text-exact",
            )
            new_clusters.append(cluster)
            group_to_cluster[id(group)] = cluster

    if new_clusters:
        DuplicateCluster.objects.bulk_create(new_clusters, batch_size=500)
        created_clusters = len(new_clusters)
        # Reload pks so DuplicateMember rows reference real cluster ids.
        for c in new_clusters:
            c.refresh_from_db()

    # Build all DuplicateMember rows in one go.
    new_members: list[DuplicateMember] = []
    seen_member_keys: set[tuple[int, int]] = set()
    for group in groups:
        cluster = group_to_cluster[id(group)]
        for q in group:
            key = (cluster.id, q.id)
            if key in seen_member_keys:
                continue
            seen_member_keys.add(key)
            new_members.append(
                DuplicateMember(cluster=cluster, question=q, similarity_score=1.0)
            )

    if new_members:
        # Skip members that already exist (race with other writers).
        existing_pairs = set(
            DuplicateMember.objects.filter(
                cluster_id__in=[m.cluster_id for m in new_members],
                question_id__in=[m.question_id for m in new_members],
            ).values_list("cluster_id", "question_id")
        )
        fresh = [
            m for m in new_members
            if (m.cluster_id, m.question_id) not in existing_pairs
        ]
        DuplicateMember.objects.bulk_create(fresh, batch_size=500, ignore_conflicts=True)
        created_members = len(fresh)

    if args.merge:
        ids_to_drop: list[int] = []
        for group in groups:
            canonical = choose_canonical(group)
            for q in group:
                if q.id == canonical.id or q.is_dropped:
                    continue
                ids_to_drop.append(q.id)
        if ids_to_drop:
            Question.objects.filter(id__in=ids_to_drop).update(is_dropped=True, is_active=False)
            dropped = len(ids_to_drop)

    print(f"Clusters: {created_clusters} created (existing reused silently)")
    print(f"DuplicateMember rows: {created_members} created")
    if args.merge:
        print(f"Soft-dropped duplicates: {dropped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())