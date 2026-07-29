"""Phase 3 audit: stratified sample of clusters; check if canonical is best."""
from __future__ import annotations

import json
import os
import random
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

    # Cluster size distribution
    cur.execute("""
        SELECT cluster_id, COUNT(*) c
        FROM questions_duplicatemember
        GROUP BY cluster_id
        ORDER BY c DESC
    """)
    sizes = [r['c'] for r in cur.fetchall()]
    size_buckets = {2: 0, 3: 0, '4-5': 0, '6-10': 0, '11+': 0}
    for s in sizes:
        if s == 2:
            size_buckets[2] += 1
        elif s == 3:
            size_buckets[3] += 1
        elif s in (4, 5):
            size_buckets['4-5'] += 1
        elif 6 <= s <= 10:
            size_buckets['6-10'] += 1
        else:
            size_buckets['11+'] += 1

    print(f"Cluster size distribution: {size_buckets}")

    # Stratified sample: take cluster_ids in each bucket
    cur.execute("""
        SELECT cluster_id, COUNT(*) c
        FROM questions_duplicatemember
        GROUP BY cluster_id
        ORDER BY c DESC
    """)
    by_size = {'2': [], '3': [], '4-5': [], '6-10': [], '11+': []}
    for r in cur.fetchall():
        s = r['c']
        if s == 2:
            by_size['2'].append(r['cluster_id'])
        elif s == 3:
            by_size['3'].append(r['cluster_id'])
        elif s in (4, 5):
            by_size['4-5'].append(r['cluster_id'])
        elif 6 <= s <= 10:
            by_size['6-10'].append(r['cluster_id'])
        else:
            by_size['11+'].append(r['cluster_id'])

    rng = random.Random(42)
    sampled = []
    # 50 from size 2 (most common), 30 from 3, 20 from 4-5, 15 from 6-10, all 11+
    for bucket, k in [('2', 50), ('3', 30), ('4-5', 20), ('6-10', 15)]:
        pool = by_size[bucket]
        if len(pool) <= k:
            sampled.extend(pool)
        else:
            sampled.extend(rng.sample(pool, k))
    sampled.extend(by_size['11+'])
    print(f"Total sampled clusters: {len(sampled)}")

    placeholders = ','.join(['%s'] * len(sampled))
    cur.execute(f"""
        SELECT
          c.id AS cluster_id, c.canonical_question_id,
          LEFT(q_canon.question_text, 250) AS canon_text,
          LEFT(q_canon.explanation, 250) AS canon_expl,
          q_canon.correct_answer AS canon_ans,
          q_canon.is_active AS canon_active,
          q_canon.is_dropped AS canon_dropped,
          q_canon.year AS canon_year, q_canon.paper AS canon_paper,
          q_canon.subject_id AS canon_subj, q_canon.topic_id AS canon_topic,
          q_canon.created_at AS canon_created,
          (SELECT COUNT(*) FROM questions_questionimage i WHERE i.question_id=q_canon.id) AS canon_img_count
        FROM questions_duplicatecluster c
        JOIN questions_question q_canon ON q_canon.id = c.canonical_question_id
        WHERE c.id IN ({placeholders})
        ORDER BY c.id
    """, tuple(sampled))
    cluster_meta = {r['cluster_id']: r for r in cur.fetchall()}

    # Members for each sampled cluster
    cur.execute(f"""
        SELECT
          m.cluster_id, m.question_id, m.similarity_score,
          LEFT(q.question_text, 250) AS qt,
          LEFT(q.explanation, 250) AS expl,
          q.correct_answer, q.is_active, q.is_dropped,
          q.year, q.paper, q.subject_id, q.topic_id,
          q.created_at,
          (SELECT COUNT(*) FROM questions_questionimage i WHERE i.question_id=q.id) AS img_count
        FROM questions_duplicatemember m
        JOIN questions_question q ON q.id = m.question_id
        WHERE m.cluster_id IN ({placeholders})
        ORDER BY m.cluster_id, m.question_id
    """, tuple(sampled))
    members_by_cluster: dict[int, list] = {}
    for r in cur.fetchall():
        members_by_cluster.setdefault(r['cluster_id'], []).append(r)

    # Verdict per cluster
    counts = {
        'CANONICAL_IS_BEST': 0,
        'AMBIGUOUS': 0,
        'DROPPED_HAS_BETTER': 0,
        'TIE': 0,
    }
    dropped_better_subtypes = {
        'longer_explanation': 0,
        'more_images': 0,
        'more_images_and_longer_expl': 0,
        'both_longer_expl_and_more_images': 0,
    }
    worst_examples = []
    full_sample = []

    for cid in sampled:
        canon = cluster_meta.get(cid)
        if not canon:
            continue
        members = members_by_cluster.get(cid, [])
        canon_expl_len = len((canon['canon_expl'] or '').strip())
        canon_imgs = canon['canon_img_count'] or 0

        cluster_dup_has_better = False
        cluster_expl_better = False
        cluster_img_better = False
        worst_dup = None

        for m in members:
            if m['question_id'] == canon['canonical_question_id']:
                continue
            dup_expl_len = len((m['expl'] or '').strip())
            dup_imgs = m['img_count'] or 0

            if dup_expl_len > canon_expl_len + 20:  # 20 char tolerance
                cluster_expl_better = True
            if dup_imgs > canon_imgs:
                cluster_img_better = True

            if dup_expl_len > canon_expl_len + 20 or dup_imgs > canon_imgs:
                cluster_dup_has_better = True
                if worst_dup is None or (
                    (dup_expl_len - canon_expl_len) + 50 * (dup_imgs - canon_imgs)
                ) > (
                    len((worst_dup['expl'] or '').strip()) - canon_expl_len + 50 * (worst_dup['img_count'] - canon_imgs)
                ):
                    worst_dup = m

        # Determine verdict
        if cluster_dup_has_better:
            counts['DROPPED_HAS_BETTER'] += 1
            if cluster_expl_better and cluster_img_better:
                dropped_better_subtypes['both_longer_expl_and_more_images'] += 1
            elif cluster_img_better:
                dropped_better_subtypes['more_images'] += 1
            else:
                dropped_better_subtypes['longer_explanation'] += 1
            # Build worst example
            worst_examples.append({
                'cluster_id': cid,
                'canonical_id': canon['canonical_question_id'],
                'canon_text': canon['canon_text'],
                'canon_expl_len': canon_expl_len,
                'canon_img_count': canon_imgs,
                'worst_dup_id': worst_dup['question_id'] if worst_dup else None,
                'worst_dup_expl_len': len((worst_dup['expl'] or '').strip()) if worst_dup else 0,
                'worst_dup_img_count': worst_dup['img_count'] if worst_dup else 0,
                'worst_dup_text': worst_dup['qt'] if worst_dup else None,
            })
        elif canon_expl_len == 0 and any(len((m['expl'] or '').strip()) > 0 for m in members if m['question_id'] != canon['canonical_question_id']):
            # Canonical has empty explanation, dup has non-empty
            counts['DROPPED_HAS_BETTER'] += 1
            dropped_better_subtypes['longer_explanation'] += 1
            non_empty = [m for m in members if m['question_id'] != canon['canonical_question_id'] and len((m['expl'] or '').strip()) > 0]
            if non_empty:
                worst_examples.append({
                    'cluster_id': cid,
                    'canonical_id': canon['canonical_question_id'],
                    'canon_text': canon['canon_text'],
                    'canon_expl_len': 0,
                    'canon_img_count': canon_imgs,
                    'worst_dup_id': non_empty[0]['question_id'],
                    'worst_dup_expl_len': len((non_empty[0]['expl'] or '').strip()),
                    'worst_dup_img_count': non_empty[0]['img_count'],
                    'worst_dup_text': non_empty[0]['qt'],
                    'note': 'canonical explanation is empty; dup has explanation',
                })
        else:
            counts['CANONICAL_IS_BEST'] += 1

        full_sample.append({
            'cluster_id': cid,
            'cluster_size': len(members),
            'canonical_id': canon['canonical_question_id'],
            'canon_text': canon['canon_text'],
            'canon_expl_len': canon_expl_len,
            'canon_img_count': canon_imgs,
            'members_count': len([m for m in members if m['question_id'] != canon['canonical_question_id']]),
        })

    out = {
        'total_sampled': len(sampled),
        'cluster_size_distribution': size_buckets,
        'verdicts': counts,
        'dropped_better_subtypes': dropped_better_subtypes,
        'worst_examples': worst_examples[:25],
        'clusters_sample_summary': full_sample,
    }
    out_path = Path('docs/AUDIT_DEDUP_SAMPLE.json')
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding='utf-8')

    print(f"\n=== Phase 3 results ===")
    print(f"  total_sampled: {len(sampled)}")
    print(f"  CANONICAL_IS_BEST : {counts['CANONICAL_IS_BEST']}")
    print(f"  AMBIGUOUS         : {counts['AMBIGUOUS']}")
    print(f"  DROPPED_HAS_BETTER: {counts['DROPPED_HAS_BETTER']}")
    print(f"  TIE               : {counts['TIE']}")
    print(f"  dropped_better_subtypes: {dropped_better_subtypes}")
    print(f"\nWorst examples (top 5):")
    for w in worst_examples[:5]:
        print(f"  cluster {w['cluster_id']} canon={w['canonical_id']} expl_len={w['canon_expl_len']} img={w['canon_img_count']}")
        print(f"    worst_dup {w.get('worst_dup_id')} expl_len={w.get('worst_dup_expl_len')} img={w.get('worst_dup_img_count')}")
        print(f"    canon: {(w['canon_text'] or '')[:100]!r}")
        if w.get('worst_dup_text'):
            print(f"    dup  : {(w['worst_dup_text'] or '')[:100]!r}")
    print(f"\nJSON -> {out_path}")


if __name__ == '__main__':
    main()
