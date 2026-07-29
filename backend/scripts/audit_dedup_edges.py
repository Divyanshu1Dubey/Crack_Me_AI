"""Phase 4 audit: edge-case scan before merge."""
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

    # (1) Chain overlap: a question appearing in 2+ clusters
    cur.execute("""
        SELECT question_id, COUNT(DISTINCT cluster_id) c
        FROM questions_duplicatemember
        GROUP BY question_id
        HAVING COUNT(DISTINCT cluster_id) > 1
    """)
    chains = cur.fetchall()
    out['chain_overlap_count'] = len(chains)
    out['chain_overlap_samples'] = chains[:25]

    # (2) Year/subject/topic mismatches within clusters
    cur.execute("""
        SELECT m.cluster_id,
          COUNT(DISTINCT q.year) n_year,
          COUNT(DISTINCT q.subject_id) n_subject,
          COUNT(DISTINCT q.topic_id) n_topic,
          COUNT(DISTINCT q.paper) n_paper,
          array_agg(DISTINCT q.year) years,
          array_agg(DISTINCT q.subject_id) subjects
        FROM questions_duplicatemember m
        JOIN questions_question q ON q.id = m.question_id
        GROUP BY m.cluster_id
        HAVING COUNT(DISTINCT q.year) > 1
            OR COUNT(DISTINCT q.subject_id) > 1
            OR COUNT(DISTINCT q.topic_id) > 1
            OR COUNT(DISTINCT q.paper) > 1
        LIMIT 50
    """)
    out['mismatch_clusters'] = cur.fetchall()
    out['year_mismatch_count'] = len([r for r in out['mismatch_clusters'] if r['n_year'] > 1])
    out['subject_mismatch_count'] = len([r for r in out['mismatch_clusters'] if r['n_subject'] > 1])
    out['topic_mismatch_count'] = len([r for r in out['mismatch_clusters'] if r['n_topic'] > 1])

    # (3) Format-only diff: clusters where longest text is 3x shortest
    cur.execute("""
        SELECT cluster_id,
          MIN(LENGTH(q.question_text)) min_len,
          MAX(LENGTH(q.question_text)) max_len
        FROM questions_duplicatemember m
        JOIN questions_question q ON q.id = m.question_id
        GROUP BY cluster_id
        HAVING MAX(LENGTH(q.question_text)) >= 3 * MIN(LENGTH(q.question_text))
          AND MIN(LENGTH(q.question_text)) > 0
    """)
    out['format_diff_clusters_count'] = cur.rowcount
    out['format_diff_clusters_samples'] = cur.fetchall()[:30]

    # (4) Image-only variants: clusters where exactly one member has images
    cur.execute("""
        SELECT m.cluster_id,
          COUNT(*) total,
          SUM(CASE WHEN img.cnt > 0 THEN 1 ELSE 0 END) with_imgs
        FROM questions_duplicatemember m
        JOIN questions_question q ON q.id = m.question_id
        LEFT JOIN (
          SELECT question_id, COUNT(*) cnt FROM questions_questionimage
          GROUP BY question_id
        ) img ON img.question_id = q.id
        GROUP BY m.cluster_id
        HAVING SUM(CASE WHEN img.cnt > 0 THEN 1 ELSE 0 END) = 1
           AND COUNT(*) >= 2
    """)
    out['image_variant_count'] = cur.rowcount
    cur.execute("""
        SELECT q.id, q.question_text, q.is_active, q.is_dropped,
          (SELECT COUNT(*) FROM questions_questionimage i WHERE i.question_id=q.id) AS img_count,
          m.cluster_id
        FROM questions_duplicatemember m
        JOIN questions_question q ON q.id = m.question_id
        LEFT JOIN (
          SELECT question_id, COUNT(*) cnt FROM questions_questionimage
          GROUP BY question_id
        ) img ON img.question_id = q.id
        WHERE m.cluster_id IN (
          SELECT m2.cluster_id
          FROM questions_duplicatemember m2
          JOIN questions_question q2 ON q2.id = m2.question_id
          LEFT JOIN (SELECT question_id, COUNT(*) cnt FROM questions_questionimage GROUP BY question_id) i2 ON i2.question_id=q2.id
          GROUP BY m2.cluster_id
          HAVING SUM(CASE WHEN i2.cnt > 0 THEN 1 ELSE 0 END) = 1 AND COUNT(*) >= 2
        )
        AND (SELECT COUNT(*) FROM questions_questionimage i WHERE i.question_id=q.id) > 0
        LIMIT 20
    """)
    out['image_variant_samples'] = cur.fetchall()

    # (5) Option-letter reassignment: option_a of one == option_b of another
    cur.execute("""
        SELECT m.cluster_id, COUNT(*) c
        FROM questions_duplicatemember m
        JOIN questions_duplicatemember m2 ON m.cluster_id = m2.cluster_id
          AND m.question_id < m2.question_id
        JOIN questions_question q ON q.id = m.question_id
        JOIN questions_question q2 ON q2.id = m2.question_id
        WHERE (q.option_a = q2.option_b AND q.option_b = q2.option_a AND q.option_c = q2.option_c AND q.option_d = q2.option_d)
           OR (q.option_a = q2.option_c AND q.option_c = q2.option_a AND q.option_b = q2.option_b AND q.option_d = q2.option_d)
           OR (q.option_a = q2.option_d AND q.option_d = q2.option_a AND q.option_b = q2.option_b AND q.option_c = q2.option_c)
        GROUP BY m.cluster_id
    """)
    rows = cur.fetchall()
    out['option_letter_reassignment_count'] = len(rows)
    out['option_letter_reassignment_samples'] = rows[:20]

    # (6) Cluster size distribution
    cur.execute("""
        SELECT cnt, COUNT(*) c
        FROM (
          SELECT cluster_id, COUNT(*) cnt
          FROM questions_duplicatemember GROUP BY cluster_id
        ) x GROUP BY cnt ORDER BY cnt
    """)
    out['cluster_size_distribution'] = {str(r['cnt']): r['c'] for r in cur.fetchall()}

    # (7) Unclustered text-exact duplicates
    cur.execute("""
      SELECT COUNT(*) AS triples
      FROM (
        SELECT question_text
        FROM questions_question
        WHERE question_text IS NOT NULL AND question_text != ''
          AND NOT EXISTS (SELECT 1 FROM questions_duplicatemember m WHERE m.question_id = questions_question.id)
          AND NOT EXISTS (SELECT 1 FROM questions_duplicatecluster c WHERE c.canonical_question_id = questions_question.id)
        GROUP BY question_text
        HAVING COUNT(*) > 1
      ) t
    """)
    out['unclustered_text_duplicates_triples'] = cur.fetchone()['triples']
    cur.execute("""
      SELECT question_text, array_agg(id) AS ids
      FROM questions_question
      WHERE question_text IS NOT NULL AND question_text != ''
        AND NOT EXISTS (SELECT 1 FROM questions_duplicatemember m WHERE m.question_id = questions_question.id)
        AND NOT EXISTS (SELECT 1 FROM questions_duplicatecluster c WHERE c.canonical_question_id = questions_question.id)
      GROUP BY question_text
      HAVING COUNT(*) > 1
      ORDER BY COUNT(*) DESC
      LIMIT 10
    """)
    out['unclustered_text_duplicates_samples'] = cur.fetchall()

    out_path = Path('docs/AUDIT_DEDUP_EDGE_CASES.json')
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str), encoding='utf-8')

    print("=== Phase 4: Edge cases ===")
    print(f"chain_overlap_count: {out['chain_overlap_count']}")
    print(f"year_mismatch_count : {out['year_mismatch_count']}")
    print(f"subject_mismatch_count: {out['subject_mismatch_count']}")
    print(f"topic_mismatch_count: {out['topic_mismatch_count']}")
    print(f"format_diff_clusters: {out['format_diff_clusters_count']}")
    print(f"image_variant_count : {out['image_variant_count']}")
    print(f"option_letter_reassignment_count: {out['option_letter_reassignment_count']}")
    print(f"cluster_size_distribution: {out['cluster_size_distribution']}")
    print(f"unclustered_text_duplicates: {out['unclustered_text_duplicates_triples']}")
    print(f"JSON -> {out_path}")


if __name__ == '__main__':
    main()
