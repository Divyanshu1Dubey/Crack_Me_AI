"""Read-only probe for the latest two bug shapes reported by user.

Bug 1: option_d (or other option_*) contains explanation/answer text
        concatenated into the option value. Sample marker: "Answer: (a)" or
        "Statement N is incorrect/correct" appearing inside option_*.

Bug 2: question_text has multi-statement stem joined by single spaces
        with no separators at all between statements. Migration 0030
        only triggers on `\n` or `. ` boundaries.

Idempotent, read-only, no schema writes.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# --------------- env load (same pattern as structural_audit) ---------------

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


# --------------- Bug 1: option_d / option_* contamination ---------------------

# Patterns that mark the START of contamination:
#   "Answer:" / "Answer ("  inside an option cell means the explanation bled in.
#   "Statement 1 is correct" / "Statement 4 is incorrect" — explanation text.
ANSWER_HINT_RE = re.compile(
    r"\banswer\s*[:\(\[]|statement\s+\d+\s+is\s+(correct|incorrect)",
    re.I,
)

# Patterns meaning the cell *legitimately* contains the word "Answer":
#   true/false grids where option text is "Answer: True" — extremely rare in
#   MCQ format. None expected in prod MCQ dataset.

# What columns to scan:
OPTION_COLS = ("option_a", "option_b", "option_c", "option_d")


def probe_option_pollution(conn):
    import psycopg2.extras
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    findings = {}
    print("=== BUG 1: option_* contamination probe ===\n")
    for col in OPTION_COLS:
        cur.execute(
            f"SELECT id, question_text, {col} AS col_value "
            f"FROM questions_question "
            f"WHERE {col} IS NOT NULL AND {col} ~* %s",
            (r"(?:\banswer\s*[:\(\[]|statement\s+\d+\s+is\s+(?:correct|incorrect))",),
        )
        rows = cur.fetchall()
        col_total = len(rows)
        print(f"  {col:10s} rows-with-hint = {col_total}")
        if col_total:
            findings[col] = {
                "count": col_total,
                "samples": [
                    {
                        "id": r["id"],
                        "question_text": (r["question_text"] or "")[:200],
                        col: (r["col_value"] or "")[:400],
                    }
                    for r in rows[:6]
                ],
            }
    return findings


# --------------- Bug 2: space-joined stems in question_text -------------------

# What it looks like: multiple full-sentence statements running together
# on the same line, separated only by a space, with no `\n`, no `1.` `2.`
# markers, no `I.` `II.` markers, no `-` bullets. Migration 0030 misses
# these because it requires `. ` or `\n` boundaries.

# Conservative detector: 3+ "Sentence starts" (capital letter followed by
# lowercase word ≥ 8 chars) on a single line, with no list markers anywhere,
# AND that line contains an upper-case-mid-sentence pattern.
SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z][a-z]{4,})")


def _count_statements_on_a_line(line: str) -> int:
    """How many sentence-like statements are glued together by spaces only?"""
    line = line.strip()
    if not line:
        return 0
    # Don't fire on lines already containing list markers.
    if re.search(r"\n\s*(?:\d+[\.\)]|I+\.|\-|\*|•)\s", "\n" + line):
        return 0
    if ANSWER_HINT_RE.search(line):
        return 0
    # Count occurrences of `[.!?] <Capital> <7 lowercase>` — sentence starts.
    return len(re.findall(r"[.!?]\s+[A-Z][a-z]{6,}", line))


def probe_space_joined_stems(conn):
    import psycopg2.extras
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    print("\n=== BUG 2: space-joined multi-statement stems ===\n")

    # Pull all question_text; we'll do a conservative in-Python pass because
    # regex with backreferences can't always be expressed in pure SQL easily.
    cur.execute("SELECT id, question_text FROM questions_question WHERE question_text IS NOT NULL")
    rows = cur.fetchall()

    # First-pass filter: question_text that ENDS with the canonical tail
    # pattern (e.g. "Which of the above statements are correct?"). That tail
    # is the strongest signal that the body is a list — and if there's no
    # list, the body must be the missing-list shape.
    canonical_tail_re = re.compile(
        r"(?:which of the (?:above|following)\s+(?:statements?|is|are|options?)[^?\n]*\??"
        r"|select the correct (?:answer|code)[^?\n]*\??"
        r"|select the correct (?:answer|code)[^?\n]*:?\s*$)",
        re.I,
    )

    skip_markers_re = re.compile(r"\n\s*(?:\d+[\.\)]|I+\.|\-|\*|•)\s")

    suspects = []
    for r in rows:
        qt = r["question_text"] or ""
        if not canonical_tail_re.search(qt):
            continue
        # Already has list markers → skip.
        if skip_markers_re.search(qt):
            continue
        # Look at the longest line — the one likely to contain the joined stem.
        lines = [ln for ln in qt.split("\n") if ln.strip()]
        if not lines:
            continue
        longest = max(lines, key=len)
        n = _count_statements_on_a_line(longest)
        if n >= 3:  # 3+ sentences glued together on one line
            suspects.append({
                "id": r["id"],
                "question_text": qt[:500],
                "longest_line": longest[:400],
                "n_glued_sentences_on_line": n,
                "line_count": len(lines),
            })
    print(f"  candidates (tail + already-not-bulleted + >=3 glued sentences): {len(suspects)}")
    # Report by line_count to see if they're primarily 1-line stems (most glued)
    # or multi-line (some structural cues we might have missed).
    by_line_count = {}
    for s in suspects:
        by_line_count.setdefault(s["line_count"], 0)
        by_line_count[s["line_count"]] += 1
    print(f"  by line count: {dict(sorted(by_line_count.items()))}")
    return suspects


# --------------- driver --------------------------------------------------------

def main():
    _load_env()
    import psycopg2
    url = os.environ.get('DATABASE_URL') or os.environ.get('SUPABASE_DATABASE_URL')
    if not url:
        print("DATABASE_URL / SUPABASE_DATABASE_URL not set", file=sys.stderr)
        sys.exit(1)
    conn = psycopg2.connect(url)

    out_dir = Path(__file__).resolve().parent.parent.parent / "docs"
    out_dir.mkdir(parents=True, exist_ok=True)

    option_findings = probe_option_pollution(conn)
    stem_suspects = probe_space_joined_stems(conn)

    out = out_dir / "PROBE_2026_07_28_OPTION_AND_STEMS.json"
    payload = {
        "option_pollution": option_findings,
        "space_joined_stems": {
            "total": len(stem_suspects),
            "samples": stem_suspects[:25],
        },
    }
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    print(f"\nJSON written to {out}")


if __name__ == "__main__":
    main()
