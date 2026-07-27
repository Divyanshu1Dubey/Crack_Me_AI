"""Fast follow-up: populate DuplicateMember for any cluster that has none.

Re-runnable. Use this after `find_and_merge_duplicates.py --apply` if
the original was interrupted mid-run, or as a maintenance command.
"""
from __future__ import annotations

import os
import sys
from collections import defaultdict

import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crack_cms.settings")
django.setup()

from questions.models import DuplicateCluster, DuplicateMember, Question  # noqa: E402


def _normalize(text: str) -> str:
    import re as _re
    text = (text or "").lower()
    text = _re.sub(r"[^a-z0-9\s]+", " ", text)
    text = _re.sub(r"\s+", " ", text).strip()
    return text


def main() -> int:
    # Group active questions by (normalized_text, year, exam_source).
    qs = Question.objects.filter(is_active=True).only(
        "id", "question_text", "year", "exam_source"
    )
    groups: dict[tuple, list[int]] = defaultdict(list)
    for q in qs.iterator(chunk_size=2000):
        key = (_normalize(q.question_text), q.year, q.exam_source or "")
        groups[key].append(q.id)

    duplicates = {tuple(ids): key for key, ids in groups.items() if len(ids) >= 2}
    print(f"Duplicate groups in DB: {len(duplicates)}")

    # For each group, find or create a DuplicateCluster keyed by the lowest id.
    members_to_insert: list[DuplicateMember] = []
    clusters_with_members: set[int] = set()
    existing_member_keys = set(
        DuplicateMember.objects.values_list("cluster_id", "question_id")
    )

    for ids, key in duplicates.items():
        # Canonical = lowest id (simplest deterministic rule; admin can
        # override via /questions/<id>/duplicates/merge/ later).
        canonical_id = min(ids)
        # Look for an existing cluster pointing at this canonical.
        cluster = (
            DuplicateCluster.objects.filter(canonical_question_id=canonical_id)
            .order_by("-id")
            .first()
        )
        if not cluster:
            # Re-use any cluster that already has one of these ids as a member.
            cluster = (
                DuplicateCluster.objects.filter(members__question_id__in=ids)
                .distinct()
                .order_by("-id")
                .first()
            )
        if not cluster:
            cluster = DuplicateCluster.objects.create(
                canonical_question_id=canonical_id,
                similarity_threshold="1.000",
                detection_method="text-exact",
            )
        for qid in ids:
            if (cluster.id, qid) in existing_member_keys:
                continue
            members_to_insert.append(
                DuplicateMember(cluster_id=cluster.id, question_id=qid, similarity_score=1.0)
            )
            clusters_with_members.add(cluster.id)

    print(f"Existing DuplicateMember rows: {len(existing_member_keys)}")
    print(f"New DuplicateMember rows to insert: {len(members_to_insert)}")

    if members_to_insert:
        DuplicateMember.objects.bulk_create(members_to_insert, batch_size=1000, ignore_conflicts=True)

    print(f"Total clusters: {DuplicateCluster.objects.count()}")
    print(f"Total members: {DuplicateMember.objects.count()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())