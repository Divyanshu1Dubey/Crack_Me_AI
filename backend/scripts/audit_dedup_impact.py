"""Phase 7: impact estimate."""
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

    cur.execute("SELECT COUNT(*) c FROM questions_question")
    out['total_questions'] = cur.fetchone()['c']
    cur.execute("SELECT COUNT(*) c FROM questions_question WHERE is_active=true AND is_dropped=false")
    out['currently_public_questions'] = cur.fetchone()['c']
    cur.execute("SELECT COUNT(*) c FROM questions_duplicatecluster")
    out['duplicate_clusters'] = cur.fetchone()['c']
    cur.execute("SELECT COUNT(*) c FROM questions_duplicatemember")
    out['duplicate_members'] = cur.fetchone()['c']
    cur.execute("""
        SELECT COUNT(*) c
        FROM questions_duplicatemember m
        JOIN questions_question q ON q.id = m.question_id
        JOIN questions_duplicatecluster c ON c.id = m.cluster_id
        WHERE m.question_id != c.canonical_question_id
          AND q.is_active = true AND q.is_dropped = false
    """)
    out['would_be_soft_dropped'] = cur.fetchone()['c']
    cur.execute("""
        SELECT COUNT(*) c
        FROM questions_duplicatemember m
        JOIN questions_question q ON q.id = m.question_id
        JOIN questions_duplicatecluster c ON c.id = m.cluster_id
        WHERE m.question_id != c.canonical_question_id
          AND (q.is_active = false OR q.is_dropped = true)
    """)
    out['would_be_soft_dropped_already_inactive'] = cur.fetchone()['c']
    cur.execute("SELECT COUNT(DISTINCT canonical_question_id) c FROM questions_duplicatecluster")
    out['distinct_canonicals'] = cur.fetchone()['c']
    out['public_after_merge'] = out['currently_public_questions'] - out['would_be_soft_dropped']

    # Per-subject
    cur.execute("""
        SELECT q.subject_id, COUNT(*) c
        FROM questions_duplicatemember m
        JOIN questions_question q ON q.id = m.question_id
        JOIN questions_duplicatecluster c ON c.id = m.cluster_id
        WHERE m.question_id != c.canonical_question_id
          AND q.is_active = true AND q.is_dropped = false
        GROUP BY q.subject_id ORDER BY c DESC LIMIT 20
    """)
    out['per_subject_impact'] = cur.fetchall()
    cur.execute("""
        SELECT q.year, COUNT(*) c
        FROM questions_duplicatemember m
        JOIN questions_question q ON q.id = m.question_id
        JOIN questions_duplicatecluster c ON c.id = m.cluster_id
        WHERE m.question_id != c.canonical_question_id
          AND q.is_active = true AND q.is_dropped = false
        GROUP BY q.year ORDER BY q.year DESC
    """)
    out['per_year_impact'] = cur.fetchall()

    # Clusters needing manual review: canonical has empty explanation, dup has non-empty
    cur.execute("""
        WITH cluster_with_dups AS (
          SELECT m.cluster_id, m.question_id, q.explanation,
            (q.id = c.canonical_question_id) AS is_canon
          FROM questions_duplicatemember m
          JOIN questions_duplicatecluster c ON c.id = m.cluster_id
          JOIN questions_question q ON q.id = m.question_id
        )
        SELECT cluster_id
        FROM cluster_with_dups
        GROUP BY cluster_id
        HAVING SUM(CASE WHEN is_canon=true AND LENGTH(TRIM(COALESCE(explanation, ''))) = 0 THEN 1 ELSE 0 END) >= 1
           AND SUM(CASE WHEN is_canon=false AND LENGTH(TRIM(COALESCE(explanation, ''))) > 0 THEN 1 ELSE 0 END) >= 1
        ORDER BY cluster_id
        LIMIT 200
    """)
    out['clusters_needing_manual_review_ids'] = [r['cluster_id'] for r in cur.fetchall()]
    out['require_manual_review_count'] = len(out['clusters_needing_manual_review_ids'])

    out_path = Path('docs/AUDIT_DEDUP_IMPACT.json')
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str), encoding='utf-8')
    print("=== Phase 7: Impact estimate ===")
    print(f"  total_questions              : {out['total_questions']}")
    print(f"  currently_public_questions   : {out['currently_public_questions']}")
    print(f"  duplicate_clusters           : {out['duplicate_clusters']}")
    print(f"  duplicate_members            : {out['duplicate_members']}")
    print(f"  would_be_soft_dropped        : {out['would_be_soft_dropped']}")
    print(f"  already_inactive (sanity)    : {out['would_be_soft_dropped_already_inactive']}")
    print(f"  distinct_canonicals          : {out['distinct_canonicals']}")
    print(f"  public_after_merge           : {out['public_after_merge']}")
    print(f"  require_manual_review_count  : {out['require_manual_review_count']}")
    print()
    print("Per-subject top 10:")
    for r in out['per_subject_impact'][:10]:
        print(f"  subject_id={r['subject_id']:>4} -> {r['c']} soft-drops")
    print()
    print("Per-year impact:")
    for r in out['per_year_impact']:
        print(f"  year={r['year']} -> {r['c']} soft-drops")
    print()
    print(f"JSON -> {out_path}")


if __name__ == '__main__':
    main()
