"""Phase 2 audit: canonical-question state integrity.

Read-only SQL probes against the production DB.
Writes docs/AUDIT_DEDUP_VALIDITY.json + prints summary.
"""
from __future__ import annotations

import json
import os
from pathlib import Path


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
    import psycopg2
    import psycopg2.extras

    url = os.environ.get('DATABASE_URL') or os.environ.get('SUPABASE_DATABASE_URL')
    conn = psycopg2.connect(url)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    out = {}

    # Total counts
    cur.execute("SELECT COUNT(*) c FROM questions_duplicatecluster")
    out['total_clusters'] = cur.fetchone()['c']
    cur.execute("SELECT COUNT(*) c FROM questions_duplicatemember")
    out['total_members'] = cur.fetchone()['c']
    cur.execute("SELECT COUNT(*) c FROM questions_question")
    out['total_questions'] = cur.fetchone()['c']
    cur.execute("SELECT COUNT(*) c FROM questions_question WHERE is_active=true AND is_dropped=false")
    out['currently_public_questions'] = cur.fetchone()['c']

    # Clusters with NULL canonical_question_id
    cur.execute("SELECT id FROM questions_duplicatecluster WHERE canonical_question_id IS NULL")
    out['clusters_with_no_canonical'] = cur.fetchall()

    # Clusters whose canonical_question_id doesn't exist in questions_question
    cur.execute("""
        SELECT c.id, c.canonical_question_id
        FROM questions_duplicatecluster c
        LEFT JOIN questions_question q ON q.id = c.canonical_question_id
        WHERE c.canonical_question_id IS NOT NULL AND q.id IS NULL
    """)
    out['clusters_with_invalid_canonical_id'] = cur.fetchall()

    # Clusters whose canonical is itself is_dropped
    cur.execute("""
        SELECT c.id, c.canonical_question_id, q.is_dropped, q.is_active
        FROM questions_duplicatecluster c
        JOIN questions_question q ON q.id = c.canonical_question_id
        WHERE q.is_dropped = true
    """)
    out['clusters_with_dropped_canonical'] = cur.fetchall()

    # Clusters whose canonical is_active=false
    cur.execute("""
        SELECT c.id, c.canonical_question_id, q.is_active
        FROM questions_duplicatecluster c
        JOIN questions_question q ON q.id = c.canonical_question_id
        WHERE q.is_active = false
    """)
    out['clusters_with_inactive_canonical'] = cur.fetchall()

    # Clusters with NO members at all
    cur.execute("""
        SELECT c.id
        FROM questions_duplicatecluster c
        LEFT JOIN questions_duplicatemember m ON m.cluster_id = c.id
        WHERE m.id IS NULL
    """)
    out['clusters_with_no_members'] = cur.fetchall()

    # Orphan DuplicateMember rows pointing at non-existent questions
    cur.execute("""
        SELECT m.id, m.cluster_id, m.question_id
        FROM questions_duplicatemember m
        LEFT JOIN questions_question q ON q.id = m.question_id
        WHERE q.id IS NULL
    """)
    out['orphan_member_rows'] = cur.fetchall()

    # How many clusters have the canonical registered as a DuplicateMember row
    cur.execute("""
        SELECT COUNT(*) c
        FROM questions_duplicatecluster c
        JOIN questions_duplicatemember m
          ON m.cluster_id = c.id AND m.question_id = c.canonical_question_id
    """)
    out['canonical_is_member_count'] = cur.fetchone()['c']
    out['canonical_not_a_member_count'] = out['total_clusters'] - out['canonical_is_member_count']

    # Lost drops: questions with is_dropped=true that aren't in any cluster
    cur.execute("""
        SELECT q.id, q.year, q.paper, q.is_active, q.is_dropped,
               LEFT(q.question_text, 200) AS qt
        FROM questions_question q
        WHERE q.is_dropped = true
          AND NOT EXISTS (
            SELECT 1 FROM questions_duplicatemember m WHERE m.question_id = q.id
          )
          AND NOT EXISTS (
            SELECT 1 FROM questions_duplicatecluster c WHERE c.canonical_question_id = q.id
          )
        LIMIT 25
    """)
    out['lost_drops_sample'] = cur.fetchall()
    cur.execute("""
        SELECT COUNT(*) c FROM questions_question q
        WHERE q.is_dropped = true
          AND NOT EXISTS (
            SELECT 1 FROM questions_duplicatemember m WHERE m.question_id = q.id
          )
          AND NOT EXISTS (
            SELECT 1 FROM questions_duplicatecluster c WHERE c.canonical_question_id = q.id
          )
    """)
    out['lost_drops_count'] = cur.fetchone()['c']

    out_path = Path('docs/AUDIT_DEDUP_VALIDITY.json')
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str), encoding='utf-8')

    print("=== Phase 2: Canonical validity ===")
    print(f"total_clusters: {out['total_clusters']}")
    print(f"total_members : {out['total_members']}")
    print(f"total_questions: {out['total_questions']}")
    print(f"currently_public_questions: {out['currently_public_questions']}")
    print()
    print(f"clusters_with_no_canonical        : {len(out['clusters_with_no_canonical'])}")
    print(f"clusters_with_invalid_canonical_id: {len(out['clusters_with_invalid_canonical_id'])}")
    print(f"clusters_with_dropped_canonical   : {len(out['clusters_with_dropped_canonical'])}")
    print(f"clusters_with_inactive_canonical  : {len(out['clusters_with_inactive_canonical'])}")
    print(f"clusters_with_no_members          : {len(out['clusters_with_no_members'])}")
    print(f"orphan_member_rows                : {len(out['orphan_member_rows'])}")
    print(f"canonical_is_member_count         : {out['canonical_is_member_count']}")
    print(f"canonical_not_a_member_count      : {out['canonical_not_a_member_count']}")
    print(f"lost_drops_count                  : {out['lost_drops_count']}")
    print()
    print(f"JSON -> {out_path}")


if __name__ == '__main__':
    main()
