"""Recompute canonical_question_id for every DuplicateCluster using a
weighted scoring rubric, AND compute the field-level merge plan for
non-canonical duplicates.

Output: docs/CANONICAL_RECOMPUTATION.json (full) and a printed summary.

NO DB WRITES. Read-only.

Usage:
    cd backend
    python scripts/recompute_canonicals.py
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Scoring rubric. Weights are tuned for the CrackCMS dataset (subjective; can
# be tuned by a calibration run).

RUBRIC = {
    "admin_edited":                   {"weight": 100, "type": "bool"},
    "is_verified_by_admin":           {"weight": 50,  "type": "bool"},
    "explanation_len_50capped30":     {"weight": 1,   "type": "len",   "field": "explanation",          "per": 50, "cap": 30},
    "textbook_references":            {"weight": 25,  "type": "nonempty_json"},
    "image_count_capped40":           {"weight": 8,   "type": "count",  "cap": 40},
    "structured_metadata":            {"weight": 15,  "type": "bool",   "field": "has_structured_type"},
    "subject_topic_both_set":         {"weight": 12,  "type": "bool",   "field": "subject_topic_set"},
    "ai_explanation":                 {"weight": 10,  "type": "nonempty"},
    "complete_options":               {"weight": 8,   "type": "bool",   "field": "complete_options"},
    "structured_question_text":       {"weight": 5,   "type": "bool",   "field": "has_numbered_list"},
    "age_score_capped10":             {"weight": 1,   "type": "age",    "per": 30, "cap": 10},
    "lowest_id_tiebreak":             {"weight": 0.5, "type": "inv_id"},
}


# ---------------------------------------------------------------------------
# Scorers — pure functions over Question fields + related rows.

def _b(q, name):
    return bool(q.get(name, False))


def _nonempty(q, name):
    v = (q.get(name, "") or "").strip()
    return v != ""


def _len_norm(q, name, per: int, cap: int) -> int:
    n = len((q.get(name, "") or "").strip())
    return min(cap, n // per)


def _struct_type(q) -> bool:
    qt = (q.get("question_type", "") or "").strip()
    return bool(qt) and qt != "single_best"


def _subj_topic_set(q) -> bool:
    return bool(q.get("subject_id")) and bool(q.get("topic_id"))


def _complete_options(q) -> bool:
    opts = [q.get(f"option_{c}", "") for c in ("a", "b", "c", "d")]
    filled = sum(1 for o in opts if (o or "").strip())
    return filled == 4 and bool((q.get("correct_answer") or "").strip())


def _has_numbered_list(q) -> bool:
    t = q.get("question_text") or ""
    return "\n1. " in t or "\n- " in t


def _age_score(q, now: datetime, per: int, cap: int) -> int:
    created_at = q.get("created_at")
    if not created_at:
        return 0
    # Postgres TIMESTAMPTZ -> Python datetime with tzinfo; our `now` is
    # naive -> coerce to UTC for the subtraction.
    from datetime import timezone
    if created_at.tzinfo is not None:
        now = now.replace(tzinfo=timezone.utc)
    days = (now - created_at).days
    if days < 0:
        days = 0
    return min(cap, days // per)


def _inv_id(q) -> float:
    qid = q.get("id", 0)
    return 1.0 / max(1, qid)


def compute_score(q, image_count: int, now: datetime) -> tuple[float, dict]:
    """Return (score, per-signal breakdown)."""

    s = 0.0
    breakdown: dict[str, float] = {}

    def add(name: str, raw, w):
        nonlocal s
        if isinstance(raw, bool):
            v = 1.0 if raw else 0.0
        else:
            v = float(raw)
        s += v * w
        breakdown[name] = round(v * w, 2)

    add("admin_edited", _b(q, "admin_edited"),
        RUBRIC["admin_edited"]["weight"])
    add("is_verified_by_admin", _b(q, "is_verified_by_admin"),
        RUBRIC["is_verified_by_admin"]["weight"])
    add("explanation_len",
        _len_norm(q, "explanation", 50, 30),
        RUBRIC["explanation_len_50capped30"]["weight"])
    add("textbook_references",
        bool(q.get("textbook_references")) and len(q.get("textbook_references") or []) > 0,
        RUBRIC["textbook_references"]["weight"])
    add("image_count",
        min(image_count, 40),
        RUBRIC["image_count_capped40"]["weight"])
    add("structured_metadata",
        _struct_type(q),
        RUBRIC["structured_metadata"]["weight"])
    add("subject_topic_set",
        _subj_topic_set(q),
        RUBRIC["subject_topic_both_set"]["weight"])
    add("ai_explanation",
        _nonempty(q, "ai_explanation"),
        RUBRIC["ai_explanation"]["weight"])
    add("complete_options",
        _complete_options(q),
        RUBRIC["complete_options"]["weight"])
    add("structured_question_text",
        _has_numbered_list(q),
        RUBRIC["structured_question_text"]["weight"])
    add("age_score",
        _age_score(q, now, 30, 10),
        RUBRIC["age_score_capped10"]["weight"])
    add("lowest_id",
        _inv_id(q),
        RUBRIC["lowest_id_tiebreak"]["weight"])

    return round(s, 2), breakdown


# ---------------------------------------------------------------------------
# Field-merge rules: given (canonical, duplicate), decide which fields
# of duplicate should be COPIED into canonical before the duplicate is
# soft-dropped.

def field_merge_plan(canonical, duplicate) -> dict:
    """Return a dict of {field: action} where action is one of:
      - 'copy': canonical is empty, duplicate is non-empty -> copy dup's value into canonical
      - 'append_textbook_refs': non-empty in dup, missing in canonical -> append
      - 'relink_images': move Image rows from dup to canonical
      - 'relink_x_<model>': remap FK from dup -> canonical for related rows

    Nothing destructive. Each field is independent.
    """
    plan = {}

    # Single-text fields where we copy IF canonical is empty
    for field in (
        "explanation", "concept_explanation", "mnemonic",
        "ai_explanation", "ai_answer", "ai_mnemonic",
        "ai_clinical_pearl", "learning_technique", "shortcut_tip",
        "book_name", "chapter", "page_number", "reference_text",
        "video_url", "video_thumbnail",
    ):
        c_val = (canonical.get(field, "") or "").strip()
        d_val = (duplicate.get(field, "") or "").strip()
        if not c_val and d_val:
            plan[field] = {
                "action": "copy",
                "from": duplicate['id'],
                "reason": f"canonical empty, duplicate has {len(d_val)} chars",
            }
        elif c_val and d_val and len(d_val) > len(c_val) * 1.5 and len(d_val) > len(c_val) + 100:
            # Substantially richer version (>50% longer AND >100 chars more)
            plan[field] = {
                "action": "replace_with_longer",
                "from": duplicate['id'],
                "reason": f"duplicate version is materially richer (canonical={len(c_val)} chars, dup={len(d_val)} chars)",
            }

    # JSON fields: textbook_references merge via union
    c_refs = canonical.get("textbook_references") or []
    d_refs = duplicate.get("textbook_references") or []
    if c_refs or d_refs:
        # Dedup by (book, chapter, page)
        seen = set()
        merged = []
        for ref in (c_refs + d_refs):
            if not isinstance(ref, dict):
                continue
            key = (ref.get("book", ""), ref.get("chapter", ""), ref.get("page", ""))
            if key in seen:
                continue
            seen.add(key)
            merged.append(ref)
        if merged != c_refs:
            extras = [ref for ref in merged if ref not in c_refs]
            plan["textbook_references"] = {
                "action": "merge_json",
                "added_count": len(extras),
                "from": duplicate['id'],
                "reason": "union of textbook refs (deduped by book/chapter/page)",
            }

    # Boolean flags (admin_edited etc.) — copy from any source, never unset
    for flag in (
        "admin_edited", "is_verified_by_admin",
        "is_scholarship_eligible", "is_controversial",
        "needs_review", "is_disputed",
    ):
        if not canonical.get(flag, False) and duplicate.get(flag, False):
            plan[flag] = {
                "action": "set_true",
                "from": duplicate['id'],
                "reason": "duplicate is flagged, canonical is not",
            }

    return plan


# ---------------------------------------------------------------------------
# Main: connect to prod DB, run scoring, emit report.

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

    now = datetime.utcnow()

    # Walk all clusters; for each cluster, score all members, pick the
    # highest-score canonical, and emit a merge plan for the rest.
    cur.execute("""
        SELECT c.id AS cluster_id, c.canonical_question_id AS old_canonical_id
        FROM questions_duplicatecluster c
        WHERE c.canonical_question_id IS NOT NULL
        ORDER BY c.id
    """)
    clusters_meta = cur.fetchall()

    cluster_ids = [r['cluster_id'] for r in clusters_meta]
    print(f"Clusters to recompute: {len(cluster_ids)}")

    # Pull all members in one query — explicit columns needed because
    # RealDictRow only carries columns you ask for.
    FIELDS = [
        "id", "question_text", "option_a", "option_b", "option_c", "option_d",
        "correct_answer", "year", "paper", "subject_id", "topic_id",
        "difficulty", "concept_tags", "concept_id",
        "explanation", "concept_explanation", "mnemonic",
        "book_name", "chapter", "page_number", "reference_text",
        "textbook_references", "learning_technique", "shortcut_tip",
        "ai_explanation", "ai_answer", "ai_mnemonic", "ai_references",
        "ai_clinical_pearl", "ai_generated_at", "ai_model", "ai_version",
        "video_url", "video_thumbnail", "video_status",
        "is_verified_by_admin", "admin_edited", "is_dropped", "is_active",
        "is_scholarship_eligible", "is_controversial", "is_disputed",
        "needs_review", "question_type", "recall_status",
        "clinical_category", "session", "confidence_score",
        "created_at", "updated_at",
    ]
    field_list = ", ".join(f"q.{f}" for f in FIELDS)
    placeholders = ','.join(['%s'] * len(cluster_ids))
    cur.execute(f"""
        SELECT m.cluster_id, {field_list}
        FROM questions_duplicatemember m
        JOIN questions_question q ON q.id = m.question_id
        WHERE m.cluster_id IN ({placeholders})
    """, tuple(cluster_ids))
    rows = cur.fetchall()

    # Image counts per question
    cur.execute("""
        SELECT question_id, COUNT(*) cnt
        FROM questions_questionimage
        WHERE is_active = true
        GROUP BY question_id
    """)
    image_counts = {r['question_id']: r['cnt'] for r in cur.fetchall()}

    # Group rows by cluster
    by_cluster: dict[int, list[dict]] = {}
    for r in rows:
        by_cluster.setdefault(r['cluster_id'], []).append(r)

    # Per-cluster: build report
    cluster_reports = []
    change_count = 0
    confidence_high_count = 0
    for meta in clusters_meta:
        cid = meta['cluster_id']
        old_cid = meta['old_canonical_id']
        members = by_cluster.get(cid, [])
        if not members:
            continue

        # Score each member
        scored = []
        for m in members:
            s, breakdown = compute_score(m, image_counts.get(m['id'], 0), now)
            scored.append({
                'question_id': m['id'],
                'score': s,
                'breakdown': breakdown,
                'row': m,
            })
        scored.sort(key=lambda x: -x['score'])
        new_canon = scored[0]
        old_canon = next((s for s in scored if s['question_id'] == old_cid), None)
        if old_canon is None:
            # Old canonical was not a member — degenerate case
            old_score = None
        else:
            old_score = old_canon['score']

        new_score = new_canon['score']
        if old_score is None or old_score <= 0:
            confidence = 1.0
        else:
            confidence = round(
                abs(new_score - old_score) / max(1.0, max(new_score, old_score)),
                3,
            )

        changed = (new_canon['question_id'] != old_cid)

        # Build field merge plan for any non-canonical members
        merge_plans = []
        canon_row = new_canon['row']
        for s in scored[1:]:
            dup_row = s['row']
            mp = field_merge_plan(canon_row, dup_row)
            if mp:
                merge_plans.append({
                    'from_id': dup_row['id'],
                    'from_score': s['score'],
                    'plan': mp,
                })

        report = {
            'cluster_id': cid,
            'old_canonical_id': old_cid,
            'new_canonical_id': new_canon['question_id'],
            'changed': changed,
            'confidence': confidence,
            'new_canonical_score': new_score,
            'old_canonical_score': old_score,
            'score_delta': round(new_score - (old_score or 0), 2),
            'runner_ups': [
                {
                    'question_id': s['question_id'],
                    'score': s['score'],
                    'delta_from_winner': round(new_score - s['score'], 2),
                    'breakdown': s['breakdown'],
                } for s in scored[1:5]
            ],
            'new_canonical_breakdown': new_canon['breakdown'],
            'non_canonical_member_count': len(scored) - 1,
            'merge_plans_count': len(merge_plans),
            'merge_plans': merge_plans,
        }
        cluster_reports.append(report)
        # Compute change immediately, but suppress "noise" changes where
        # the data isn't telling us anything meaningful. Suppressions
        # happen BEFORE incrementing counters to avoid double-count.
        suppressed_reason = None
        if changed and abs(new_score - (old_score or 0)) < 1.0:
            suppressed_reason = (
                f"Score delta < 1.0 (old={old_score}, new={new_score}); "
                "algorithm effectively tied. Keeping existing canonical."
            )
        elif changed and new_score < 10 and (old_score or 0) < 10:
            suppressed_reason = (
                f"Both new (score={new_score}) and old (score={old_score}) "
                "canonicals have low enrichment; rotation would add noise. "
                "Keeping existing canonical."
            )
        if suppressed_reason:
            report['changed'] = False
            report['change_suppressed_reason'] = suppressed_reason
            changed = False

        if changed:
            change_count += 1
            if confidence >= 0.15:
                confidence_high_count += 1

    # Write JSON
    out = {
        'total_clusters_scored': len(cluster_reports),
        'clusters_with_new_canonical': change_count,
        'clusters_with_high_confidence_change': confidence_high_count,
        'clusters_with_merge_plans': sum(1 for r in cluster_reports if r['merge_plans_count'] > 0),
        'total_field_merge_actions': sum(r['merge_plans_count'] for r in cluster_reports),
        'report': cluster_reports,
    }
    out_path = Path('docs/CANONICAL_RECOMPUTATION.json')
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str), encoding='utf-8')

    print(f"\n=== Recomputation summary ===")
    print(f"  Clusters scored                : {out['total_clusters_scored']}")
    print(f"  New canonical differs from old : {out['clusters_with_new_canonical']}")
    print(f"  High-confidence changes (>=0.15): {out['clusters_with_high_confidence_change']}")
    print(f"  Clusters w/ merge plans        : {out['clusters_with_merge_plans']}")
    print(f"  Total field-merge actions      : {out['total_field_merge_actions']}")
    print(f"\nJSON -> {out_path}")


if __name__ == '__main__':
    main()
