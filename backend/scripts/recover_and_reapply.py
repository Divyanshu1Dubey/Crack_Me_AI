"""Recovery + re-apply in correct order.

Step 1: Undrop every question we soft-dropped in the previous (incorrect) apply.
        We identify them as: rows that are currently is_dropped=true AND are
        listed in any DuplicateMember of any cluster.

Step 2: Revert the 427 canonical_question_id rotations back to old canonicals.

Step 3: Re-apply in the correct order:
  3a. Rotate canonicals FIRST (UPDATE questions_duplicatecluster)
  3b. THEN soft-drop, but skip any row that is now a canonical of some cluster

All in transaction.atomic blocks.
"""
import os
import sys
import django
from pathlib import Path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')
sys.path.insert(0, '.')
django.setup()

import json
from django.db import transaction
from django.db.models import F
from questions.models import DuplicateCluster, DuplicateMember, Question


REPORT_PATH = Path('docs/CANONICAL_RECOMPUTATION.json')
report = json.loads(REPORT_PATH.read_text(encoding='utf-8'))
changes = [r for r in report['report'] if r.get('changed')]
print(f"changed clusters: {len(changes)}")


# ---- Step 1: undrop all soft-dropped rows that are members of any cluster.
# We dropped ~4074 rows. Some were old canonicals of changed clusters.
# To restore: set is_active=true, is_dropped=false for any row that is currently
# dropped AND is listed in any DuplicateMember of any cluster.
with transaction.atomic():
    dropped_member_ids = list(
        DuplicateMember.objects.filter(
            question__is_dropped=True,
            question__is_active=False,
        ).values_list('question_id', flat=True)
    )
    print(f"rows to undrop (currently dropped but still in some cluster): {len(dropped_member_ids)}")
    if dropped_member_ids:
        updated = Question.objects.filter(id__in=dropped_member_ids).update(
            is_active=True, is_dropped=False,
        )
        print(f"undropped: {updated}")


# ---- Step 2: revert the 427 canonical rotations
with transaction.atomic():
    reverted = 0
    for r in changes:
        cid = r['cluster_id']
        old_cid = r['old_canonical_id']
        n_updated = DuplicateCluster.objects.filter(id=cid).update(
            canonical_question_id=old_cid,
        )
        reverted += n_updated
    print(f"reverted canonical rotations: {reverted}")


# ---- Step 3a: rotate canonicals to the new ones (the recomputed winners)
with transaction.atomic():
    rotated = 0
    for r in changes:
        cid = r['cluster_id']
        new_cid = r['new_canonical_id']
        n_updated = DuplicateCluster.objects.filter(id=cid).update(
            canonical_question_id=new_cid,
        )
        rotated += n_updated
    print(f"rotated canonicals (3a): {rotated}")


# ---- Step 3b: soft-drop non-canonical members — but SKIP any row that is
#               currently the canonical of any cluster.
with transaction.atomic():
    # Find current canonicals
    current_canonicals = set(
        DuplicateCluster.objects.values_list('canonical_question_id', flat=True)
    )
    # Find non-canonical members of all clusters
    non_canon_ids = set(
        DuplicateMember.objects.exclude(
            question_id=F('cluster__canonical_question_id'),
        ).values_list('question_id', flat=True)
    )
    # Soft-drop set = non-canon ids MINUS current canonicals
    to_drop = list(non_canon_ids - current_canonicals)
    print(f"current canonicals: {len(current_canonicals)}")
    print(f"non-canon members: {len(non_canon_ids)}")
    print(f"to soft-drop: {len(to_drop)}")
    if to_drop:
        updated = Question.objects.filter(id__in=to_drop).update(
            is_active=False, is_dropped=True,
        )
        print(f"soft-dropped: {updated}")


# ---- Final sanity
print()
print("=== Final state ===")
public = Question.objects.filter(is_active=True, is_dropped=False).count()
dropped = Question.objects.filter(is_dropped=True).count()
canonicals = DuplicateCluster.objects.values('canonical_question_id').distinct().count()
broken = DuplicateCluster.objects.filter(
    canonical_question__is_dropped=True,
).count()
print(f"public active+not-dropped: {public}")
print(f"dropped questions: {dropped}")
print(f"distinct canonicals: {canonicals}")
print(f"clusters with dropped canonical: {broken}")