"""Read-only dry-run: list every non-canonical cluster member that
the existing bulk-merge would soft-drop.

Safe. No writes. Uses the canonical_question already stored in
DuplicateCluster — does NOT recompute canonicals.

Output: docs/DRYRUN_MERGE_DUPLICATES_2026_07_28.json

Run:
    cd backend
    python scripts/dryrun_merge_duplicates_2026_07_28.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras


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
    _load_env()
    url = os.environ.get('DATABASE_URL') or os.environ.get('SUPABASE_DATABASE_URL')
    conn = psycopg2.connect(url)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT
          c.id AS cluster_id,
          c.canonical_question_id,
          q_canonical.is_active AS canonical_is_active,
          q_canonical.is_dropped AS canonical_is_dropped,
          q_canonical.question_text AS canonical_question_text,
          m.question_id AS duplicate_id,
          q_dup.is_active AS duplicate_is_active,
          q_dup.is_dropped AS duplicate_is_dropped,
          q_dup.question_text AS duplicate_question_text,
          m.similarity_score
        FROM questions_duplicatecluster c
        JOIN questions_question q_canonical ON q_canonical.id = c.canonical_question_id
        JOIN questions_duplicatemember m ON m.cluster_id = c.id
        JOIN questions_question q_dup ON q_dup.id = m.question_id
        WHERE m.question_id != c.canonical_question_id
        ORDER BY c.id, m.question_id
    """)
    rows = cur.fetchall()

    total = len(rows)
    still_active = sum(1 for r in rows if r['duplicate_is_active'] and not r['duplicate_is_dropped'])
    already_dropped = total - still_active

    print(f"Total non-canonical cluster members: {total}")
    print(f"  still-active (visible to students): {still_active}")
    print(f"  already dropped/inactive: {already_dropped}")
    print()

    # Sanity check: any canonical rows that are themselves dropped?
    canonicals_dropped = sum(1 for r in rows if r['canonical_is_dropped'])
    if canonicals_dropped:
        print(f"  WARNING: {canonicals_dropped} clusters have a DROPPED canonical!")

    # Show first 20 largest clusters
    cluster_sizes: dict[int, int] = {}
    for r in rows:
        cluster_sizes[r['cluster_id']] = cluster_sizes.get(r['cluster_id'], 0) + 1
    top_clusters = sorted(cluster_sizes.items(), key=lambda kv: -kv[1])[:20]
    print("Top 20 largest clusters (id, non-canonical member count):")
    for cid, n in top_clusters:
        print(f"  cluster {cid}: {n} non-canonical members")

    # Group rows by cluster for JSON
    by_cluster: dict[int, dict] = {}
    for r in rows:
        cid = r['cluster_id']
        if cid not in by_cluster:
            by_cluster[cid] = {
                'cluster_id': cid,
                'canonical_question_id': r['canonical_question_id'],
                'canonical_question_text': (r['canonical_question_text'] or '')[:200],
                'members': [],
            }
        by_cluster[cid]['members'].append({
            'duplicate_id': r['duplicate_id'],
            'is_active': r['duplicate_is_active'],
            'is_dropped': r['duplicate_is_dropped'],
            'similarity_score': float(r['similarity_score']) if r['similarity_score'] else 1.0,
        })

    out = Path(__file__).resolve().parent.parent.parent / "docs" / "DRYRUN_MERGE_DUPLICATES_2026_07_28.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        'total_non_canonical_members': total,
        'still_active_to_drop': still_active,
        'already_dropped': already_dropped,
        'top_20_clusters': [{'cluster_id': cid, 'non_canonical_member_count': n} for cid, n in top_clusters],
        'clusters': list(by_cluster.values()),
    }, indent=2, ensure_ascii=False))
    print(f"\nJSON written to {out}")


if __name__ == '__main__':
    main()