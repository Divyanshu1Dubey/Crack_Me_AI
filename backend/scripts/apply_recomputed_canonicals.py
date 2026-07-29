"""Apply the recomputed canonical selection + field-merges + soft-drop.

Reads docs/CANONICAL_RECOMPUTATION.json and:

  1. For each cluster where `changed=True`:
       a. UPDATE questions_duplicatecluster.canonical_question_id = new
       b. For each merge_plan entry: copy the corresponding field from
          the non-canonical member INTO the canonical (only when the
          action is one of: copy, replace_with_longer, set_true,
          merge_json, relink_images).
       c. Soft-drop every non-canonical member.

All operations in one transaction.atomic() block. Idempotent (the
algorithm in recompute_canonicals.py is deterministic from a fixed
`now`, so on rerun the actions don't change).

Usage:
    cd backend
    python scripts/apply_recomputed_canonicals.py            # dry-run
    python scripts/apply_recomputed_canonicals.py --apply    # commit
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


# List of fields we are ALLOWED to write into canonical from a duplicate
# (whitelisted so a buggy merge plan can't accidentally nuke unrelated
# fields like correct_answer).
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


def _load_env():
    with open('.env', 'rb') as f:
        for line in f:
            try:
                line = line.decode('utf-8').strip()
            except UnicodeDecodeError:
                continue
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true',
                        help='Persist changes (default: dry-run)')
    parser.add_argument('--report',
                        default='docs/CANONICAL_RECOMPUTATION.json',
                        help='Input JSON report')
    parser.add_argument('--out',
                        default='docs/APPLY_RECOMPUTED_RESULT.json',
                        help='Output result JSON')
    args = parser.parse_args()

    _load_env()
    import psycopg2
    import psycopg2.extras

    url = os.environ.get('DATABASE_URL') or os.environ.get('SUPABASE_DATABASE_URL')
    conn = psycopg2.connect(url)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    report = json.loads(Path(args.report).read_text(encoding='utf-8'))
    cluster_records = report['report']

    # Pre-pull the field values we'll need for any copy / replace_with_longer /
    # merge_json action. Pre-pulled to avoid round-tripping per row.
    #
    # The "actions" list captures every cluster that has a merge plan OR a
    # canonical change — every cluster where we'll write something.
    needed_ids: set[int] = set()
    actions: list[dict] = []
    for r in cluster_records:
        merge_plans = r.get('merge_plans') or []
        changed = r.get('changed', False)
        if not changed and not merge_plans:
            continue
        cid = r['cluster_id']
        new_canon = r['new_canonical_id']
        actions.append({
            'cluster_id': cid,
            'new_canonical_id': new_canon,
            'old_canonical_id': r['old_canonical_id'],
            'merge_plans': merge_plans,
            'non_canonical_member_ids': [
                mp['from_id'] for mp in merge_plans
            ],
            'confidence': r.get('confidence', 0.0),
            'changed': changed,
        })
        needed_ids.add(new_canon)
        for mp in merge_plans:
            needed_ids.add(mp['from_id'])

    print(f"Total changed clusters: {len(actions)}")
    print(f"Distinct question ids touched: {len(needed_ids)}")

    # Fetch every value we'll write or read for the actions.
    if needed_ids:
        placeholders = ','.join(['%s'] * len(needed_ids))
        COPY_FIELDS_PG = ', '.join(f'q.{f}' for f in sorted(COPY_FIELDS))
        BOOL_FIELDS_PG = ', '.join(f'q.{f}' for f in sorted(BOOLEAN_FLAG_FIELDS))
        cur.execute(f"""
            SELECT q.id, q.is_active, q.is_dropped,
                   {COPY_FIELDS_PG},
                   {BOOL_FIELDS_PG}
            FROM questions_question q
            WHERE q.id IN ({placeholders})
        """, list(needed_ids))
        rows_by_id = {r['id']: dict(r) for r in cur.fetchall()}
    else:
        rows_by_id = {}

    # Build the executable plan (one entry per question_id that needs
    # field updates from dups INTO it).
    canonical_updates: dict[int, dict] = {}  # question_id -> {field: value}

    skipped_zero_risk = 0
    skipped_field_not_whitelisted = 0
    copy_actions_planned = 0
    replace_actions_planned = 0
    bool_set_actions_planned = 0

    for a in actions:
        new_canon = a['new_canonical_id']
        canon_row = rows_by_id.get(new_canon)
        if canon_row is None:
            print(f"WARNING: canonical {new_canon} not found — skipping cluster {a['cluster_id']}")
            continue

        for mp in a['merge_plans']:
            dup_id = mp['from_id']
            dup_row = rows_by_id.get(dup_id)
            if dup_row is None:
                continue

            for field, spec in mp['plan'].items():
                action = spec['action']

                if action == 'copy':
                    if field not in COPY_FIELDS:
                        skipped_field_not_whitelisted += 1
                        continue
                    val = dup_row.get(field)
                    cur_val = canon_row.get(field)
                    if (cur_val is None or (isinstance(cur_val, str) and not cur_val.strip())):
                        canonical_updates.setdefault(new_canon, {})[field] = val
                        copy_actions_planned += 1

                elif action == 'replace_with_longer':
                    if field not in COPY_FIELDS:
                        skipped_field_not_whitelisted += 1
                        continue
                    val = dup_row.get(field)
                    cur_val = canon_row.get(field)
                    if val and (not cur_val or len(val) > len(cur_val or '') + 100):
                        canonical_updates.setdefault(new_canon, {})[field] = val
                        replace_actions_planned += 1

                elif action == 'set_true':
                    if field not in BOOLEAN_FLAG_FIELDS:
                        skipped_field_not_whitelisted += 1
                        continue
                    if not canon_row.get(field) and dup_row.get(field):
                        canonical_updates.setdefault(new_canon, {})[field] = True
                        bool_set_actions_planned += 1

                elif action == 'merge_json':
                    if field != 'textbook_references':
                        skipped_field_not_whitelisted += 1
                        continue
                    c = canon_row.get('textbook_references') or []
                    d = dup_row.get('textbook_references') or []
                    seen = set()
                    merged = []
                    for ref in (list(c) + list(d)):
                        if not isinstance(ref, dict):
                            continue
                        key = (ref.get('book',''), ref.get('chapter',''), ref.get('page',''))
                        if key in seen:
                            continue
                        seen.add(key)
                        merged.append(ref)
                    if merged != (c or []):
                        canonical_updates.setdefault(new_canon, {})['textbook_references'] = merged
                        replace_actions_planned += 1

    print(f"\nField copies planned: {copy_actions_planned}")
    print(f"Field replaces planned: {replace_actions_planned}")
    print(f"Flag set_true planned: {bool_set_actions_planned}")
    print(f"Skipped (not whitelisted): {skipped_field_not_whitelisted}")
    print()

    # Build soft-drop plan.
    #
    # Two populations:
    #   (A) "active" clusters (canonical changed OR has merge plan):
    #       every non-canonical member gets soft-dropped.
    #   (B) "passive" clusters (unchanged, no merge plan): the existing
    #       canonical is already optimal — but we still want to soft-drop
    #       their non-canonical members to fulfill the original bulk merge
    #       plan. We pull them in below.
    soft_drops: set[int] = set()
    canonical_id_changes: list[tuple[int, int]] = []  # (cluster_id, new_canon_id)
    active_cluster_ids: set[int] = set()
    for a in actions:
        active_cluster_ids.add(a['cluster_id'])
        if a['changed']:
            canonical_id_changes.append((a['cluster_id'], a['new_canonical_id']))
        else:
            # Unchanged cluster with merge plan: drop only the merge-plan
            # sources (the dup whose field is being merged).
            soft_drops.update(a['non_canonical_member_ids'])

    # Pull every non-canonical member of every ACTIVE cluster.
    if active_cluster_ids:
        cluster_ids = list(active_cluster_ids)
        ph = ','.join(['%s'] * len(cluster_ids))
        cur.execute(f"""
            SELECT m.cluster_id, m.question_id, c.canonical_question_id
            FROM questions_duplicatemember m
            JOIN questions_duplicatecluster c ON c.id = m.cluster_id
            WHERE m.cluster_id IN ({ph})
        """, cluster_ids)
        for r in cur.fetchall():
            if r['question_id'] != r['canonical_question_id']:
                soft_drops.add(r['question_id'])

    # Pull every non-canonical member of every PASSIVE cluster (unchanged
    # + no merge plan). These are clean soft-drops.
    passive_ids: set[int] = set()
    for r in cluster_records:
        cid = r['cluster_id']
        if cid in active_cluster_ids:
            continue
        if not r.get('merge_plans'):
            passive_ids.add(cid)
    if passive_ids:
        ph = ','.join(['%s'] * len(passive_ids))
        cur.execute(f"""
            SELECT m.question_id
            FROM questions_duplicatemember m
            JOIN questions_duplicatecluster c ON c.id = m.cluster_id
            WHERE m.cluster_id IN ({ph})
              AND m.question_id != c.canonical_question_id
        """, list(passive_ids))
        for r in cur.fetchall():
            soft_drops.add(r['question_id'])

    # Filter soft_drops: skip rows that ARE a canonical in any other cluster
    # (shouldn't happen given the integrity report, but defensive).
    if soft_drops:
        ph2 = ','.join(['%s'] * len(soft_drops))
        cur.execute(f"""
            SELECT canonical_question_id
            FROM questions_duplicatecluster
            WHERE canonical_question_id IN ({ph2})
        """, list(soft_drops))
        still_canons = {r['canonical_question_id'] for r in cur.fetchall()}
        if still_canons:
            print(f"WARNING: {len(still_canons)} would-be-soft-dropped rows are STILL canonicals elsewhere — will skip those.")
            soft_drops -= still_canons

    print(f"Total to soft-drop: {len(soft_drops)}")
    print(f"Total canonical_id changes: {len(canonical_id_changes)}")

    if not args.apply:
        print("\nDRY RUN. Re-run with --apply to commit.")
        # Write out a summary file the user can inspect
        Path(args.out).write_text(json.dumps({
            'mode': 'dry-run',
            'clusters_changed': len(actions),
            'canonical_id_changes': canonical_id_changes,
            'canonical_field_updates_count': len(canonical_updates),
            'soft_drop_count': len(soft_drops),
            'sample_field_updates': [
                {'question_id': qid, 'fields': list(fields.keys())}
                for qid, fields in list(canonical_updates.items())[:20]
            ],
        }, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f"Result summary -> {args.out}")
        return

    # APPLY: run inside transaction.atomic.
    from django.conf import settings as _dj_settings
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')
    if not _dj_settings.configured:
        django.setup()

    from django.db import transaction
    from questions.models import DuplicateCluster, Question

    with transaction.atomic():
        # 1. Field copies into canonicals
        for qid, fields in canonical_updates.items():
            Question.objects.filter(id=qid).update(**fields)

        # 2. Canonical id changes
        for cid, new_id in canonical_id_changes:
            DuplicateCluster.objects.filter(id=cid).update(
                canonical_question_id=new_id,
            )

        # 3. Soft-drops (single bulk update)
        Question.objects.filter(id__in=soft_drops).update(
            is_dropped=True,
            is_active=False,
        )

    # Verify
    cur.execute("SELECT COUNT(*) c FROM questions_question WHERE is_active=true AND is_dropped=false")
    public_after = cur.fetchone()['c']
    cur.execute("SELECT COUNT(DISTINCT canonical_question_id) c FROM questions_duplicatecluster")
    distinct_canon = cur.fetchone()['c']
    print(f"\nPost-apply state:")
    print(f"  currently_public_questions : {public_after}")
    print(f"  distinct_canonicals        : {distinct_canon}")

    Path(args.out).write_text(json.dumps({
        'mode': 'apply',
        'clusters_changed': len(actions),
        'canonical_id_changes_count': len(canonical_id_changes),
        'canonical_field_updates_count': len(canonical_updates),
        'soft_drop_count': len(soft_drops),
        'post_public_count': public_after,
        'post_distinct_canonicals': distinct_canon,
    }, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"Result JSON -> {args.out}")


if __name__ == '__main__':
    main()
