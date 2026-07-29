"""Apply the recomputed canonicals via Django ORM in a single transaction.

Run with:
    cd backend
    python manage.py shell < apply_via_manage.py

Reads docs/CANONICAL_RECOMPUTATION.json, computes the executable plan,
then inside transaction.atomic():
  1. Field copies into canonicals
  2. Canonical id changes
  3. Soft-drops

Idempotent.
"""
from __future__ import annotations

import json
from pathlib import Path

from django.db import transaction

from questions.models import DuplicateCluster, Question


REPORT_PATH = Path('docs/CANONICAL_RECOMPUTATION.json')

COPY_FIELDS = {
    "explanation", "concept_explanation", "mnemonic",
    "ai_explanation", "ai_answer", "ai_mnemonic",
    "ai_clinical_pearl", "learning_technique", "shortcut_tip",
    "book_name", "chapter", "page_number", "reference_text",
    "video_url", "video_thumbnail",
    "textbook_references",
}
BOOLEAN_FLAG_FIELDS = {
    "admin_edited", "is_verified_by_admin",
    "is_scholarship_eligible", "is_controversial",
    "needs_review", "is_disputed",
}


def _load_canonical_state():
    """Build dict question_id -> {field_name: value} for everything we
    might read or write."""
    field_names = list(COPY_FIELDS) + list(BOOLEAN_FLAG_FIELDS)
    fields = ", ".join(f'"{f}"' for f in field_names)
    qs = Question.objects.extra(select={"_fields": fields}).values_list("id", *_field_names_safe(field_names))
    # Simpler approach: just iterate Questions
    state = {}
    needed_fields = list(COPY_FIELDS) + list(BOOLEAN_FLAG_FIELDS)
    for q in Question.objects.only("id", *needed_fields):
        state[q.id] = {f: getattr(q, f) for f in needed_fields}
    return state


def _field_names_safe(names):
    """just return the list as-is; .only() accepts them directly."""
    return list(names)


def main():
    print("=== apply_recomputed_canonicals ===")
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    cluster_records = report["report"]

    # Build plans
    actions = []
    for r in cluster_records:
        merge_plans = r.get("merge_plans") or []
        if not r.get("changed") and not merge_plans:
            continue
        actions.append({
            "cluster_id": r["cluster_id"],
            "new_canonical_id": r["new_canonical_id"],
            "old_canonical_id": r["old_canonical_id"],
            "merge_plans": merge_plans,
            "merge_plan_source_ids": [mp["from_id"] for mp in merge_plans],
            "changed": r.get("changed", False),
        })
    print(f"Actions planned: {len(actions)}")

    # Field copies & replace actions: build now from current DB state
    needed_ids = set()
    active_cluster_ids = set()
    for a in actions:
        active_cluster_ids.add(a["cluster_id"])
        needed_ids.add(a["new_canonical_id"])
        for mp in a["merge_plans"]:
            needed_ids.add(mp["from_id"])
    state = _load_canonical_state()

    canonical_updates = {}
    copy_count = 0
    replace_count = 0
    bool_count = 0
    for a in actions:
        new_canon = a["new_canonical_id"]
        c = state.get(new_canon, {})
        if not c and "id" not in c:
            # Ensure c has the id field even if Question row wasn't found
            pass
        for mp in a["merge_plans"]:
            d = state.get(mp["from_id"], {})
            for field, spec in mp["plan"].items():
                action = spec["action"]
                if action == "copy" and field in COPY_FIELDS:
                    cur = c.get(field)
                    nxt = d.get(field)
                    if (cur is None or (isinstance(cur, str) and not cur.strip())) and nxt:
                        canonical_updates.setdefault(new_canon, {})[field] = nxt
                        copy_count += 1
                elif action == "replace_with_longer" and field in COPY_FIELDS:
                    cur = c.get(field)
                    nxt = d.get(field)
                    if nxt and (not cur or (isinstance(cur, str) and isinstance(nxt, str) and len(nxt) > len(cur) + 100)):
                        canonical_updates.setdefault(new_canon, {})[field] = nxt
                        replace_count += 1
                elif action == "set_true" and field in BOOLEAN_FLAG_FIELDS:
                    if not c.get(field) and d.get(field):
                        canonical_updates.setdefault(new_canon, {})[field] = True
                        bool_count += 1
                elif action == "merge_json" and field == "textbook_references":
                    cs = c.get("textbook_references") or []
                    ds = d.get("textbook_references") or []
                    if cs or ds:
                        seen = set()
                        merged = []
                        for ref in (list(cs) + list(ds)):
                            if not isinstance(ref, dict):
                                continue
                            key = (ref.get("book",""), ref.get("chapter",""), ref.get("page",""))
                            if key in seen:
                                continue
                            seen.add(key)
                            merged.append(ref)
                        if merged != (cs or []):
                            canonical_updates.setdefault(new_canon, {})["textbook_references"] = merged
                            replace_count += 1
    print(f"Field copies: {copy_count}")
    print(f"Field replaces (incl json): {replace_count}")
    print(f"Flag set_true: {bool_count}")
    print(f"Total canonical_updates entries: {len(canonical_updates)}")

    # Soft-drop plan: every non-canonical member of every active cluster,
    # PLUS every non-canonical member of every passive cluster (no change
    # / no merge plan).
    soft_drops = set()
    canonical_id_changes = []
    passive_cluster_ids = set()

    for a in actions:
        if a["changed"]:
            canonical_id_changes.append((a["cluster_id"], a["new_canonical_id"]))
        else:
            # unchanged cluster with merge plans: drop only the source(s)
            soft_drops.update(a["merge_plan_source_ids"])

    # Pull every non-canonical member of every cluster
    all_cluster_ids = list(set(a["cluster_id"] for a in actions))
    all_member_qs = DuplicateMember.objects.filter(
        cluster_id__in=all_cluster_ids,
    ).values_list("cluster_id", "question_id", "cluster__canonical_question_id")
    member_rows = list(all_member_qs)
    for cid, qid, canon_id in member_rows:
        if qid != canon_id:
            soft_drops.add(qid)
        if cid not in active_cluster_ids:
            passive_cluster_ids.add(cid)

    # Passive clusters (untouched) — drop their non-canon members too
    passive_qs = DuplicateMember.objects.filter(
        cluster_id__in=list(passive_cluster_ids),
    ).exclude(
        question_id=models_F("cluster__canonical_question_id"),
    ).values_list("question_id", flat=True)
    passive_qs = list(passive_qs)
    soft_drops.update(passive_qs)

    # Skip rows that are still canonicals elsewhere
    still_canons = set(
        DuplicateCluster.objects.filter(
            canonical_question_id__in=list(soft_drops),
        ).values_list("canonical_question_id", flat=True)
    )
    if still_canons:
        print(f"Skipping {len(still_canons)} still-canonical rows")
        soft_drops -= still_canons

    print(f"Total soft-drops: {len(soft_drops)}")
    print(f"Total canonical_id_changes: {len(canonical_id_changes)}")

    # APPLY
    with transaction.atomic():
        for qid, fields in canonical_updates.items():
            Question.objects.filter(id=qid).update(**fields)
        for cid, new_id in canonical_id_changes:
            DuplicateCluster.objects.filter(id=cid).update(canonical_question_id=new_id)
        Question.objects.filter(id__in=list(soft_drops)).update(
            is_dropped=True,
            is_active=False,
        )

    print("APPLIED.")

    # Verify
    print(f"After apply:")
    print(f"  currently_public (active, not dropped): {Question.objects.filter(is_active=True, is_dropped=False).count()}")
    print(f"  distinct canonicals: {DuplicateCluster.objects.values('canonical_question_id').distinct().count()}")


from django.db.models import F as models_F
main()
