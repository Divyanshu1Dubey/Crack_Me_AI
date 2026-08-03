"""Dry-run the two new fixes against the production DB.

Reports:
  - option_* pollution: rows that WOULD be changed + before/after preview
  - space-joined stems: rows that WOULD be changed + before/after preview

No DB writes. Read-only.
"""
from __future__ import annotations

import json
import os
import sys
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

    from questions.migrations._option_pollution import clean_option_pollution
    from questions.migrations._statement_splitter import split_space_joined_stems

    url = os.environ.get('DATABASE_URL') or os.environ.get('SUPABASE_DATABASE_URL')
    conn = psycopg2.connect(url)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # ---- Bug 1: option_* pollution ----
    print("=== Bug 1: option_* pollution DRY-RUN ===\n")
    OP_COLS = ("option_a", "option_b", "option_c", "option_d")
    option_touches = []
    for col in OP_COLS:
        cur.execute(
            f"SELECT id, question_text, {col} FROM questions_question "
            f"WHERE {col} IS NOT NULL"
        )
        for r in cur.fetchall():
            opt = r[col] or ""
            out = clean_option_pollution(opt)
            if out.should_change:
                option_touches.append({
                    "id": r["id"],
                    "col": col,
                    "before": opt[:200],
                    "after": out.cleaned_value,
                    "contributed_to_explanation": out.contributed_to_explanation[:200],
                })
    print(f"  total option cell touches: {len(option_touches)}")
    for t in option_touches[:8]:
        print(f"  id={t['id']:6d} {t['col']}")
        print(f"    before : {t['before']}")
        print(f"    after  : {t['after']}")
        print(f"    contrib: {t['contributed_to_explanation']}")
        print()

    # ---- Bug 2: space-joined stems ----
    print("\n=== Bug 2: space-joined stems DRY-RUN ===\n")
    cur.execute("SELECT id, question_text FROM questions_question WHERE question_text IS NOT NULL")
    stem_touches = []
    for r in cur.fetchall():
        before = r["question_text"] or ""
        after = split_space_joined_stems(before)
        if after != before:
            stem_touches.append({
                "id": r["id"],
                "before": before[:300],
                "after": after[:400],
            })
    print(f"  total stem touches: {len(stem_touches)}")
    for t in stem_touches[:5]:
        print(f"  id={t['id']:6d}")
        print(f"    before:\n{t['before']}")
        print(f"    after :\n{t['after']}")
        print()

    out = Path(__file__).resolve().parent.parent.parent / "docs" / "DRYRUN_2026_07_28_V2_FIXES.json"
    out.write_text(json.dumps({
        "option_touches": {
            "total": len(option_touches),
            "samples": option_touches[:30],
        },
        "stem_touches": {
            "total": len(stem_touches),
            "samples": stem_touches[:30],
        },
    }, indent=2, ensure_ascii=False))
    print(f"\nJSON written to {out}")


if __name__ == "__main__":
    main()
