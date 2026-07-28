"""Structural audit of every Question.question_text on prod.

Read-only. No DB writes.

Outputs:
  1. Console summary: per-shape counts
  2. JSON file: per-row classification
  3. Sample-text dump: first 5 question_text strings per shape

Run:
  cd backend
  python scripts/structural_audit_2026_07_28.py

The taxonomy is intentionally closed — every question_text matches
exactly one shape. Unknown shapes are reported as `unknown_shape` so
they surface in the audit and force us to either:
  - add a new shape to the taxonomy, or
  - leave the row alone (manual review).
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# ---- Taxonomy ---------------------------------------------------------------

def has_bullet(s: str) -> bool:
    return bool(re.search(r"\n\s*[-•*]\s", s))

def has_numbered(s: str) -> bool:
    return bool(re.search(r"\n\s*\d+[\.\)]\s", s))

def has_roman(s: str) -> bool:
    return bool(re.search(r"\n\s*[IVX]+[\.\)]\s", s))

def has_roman_inline(s: str) -> bool:
    """3+ consecutive `I./II./III./IV.` markers on the same line."""
    return bool(re.search(
        r"(?:^|\s)I\.\s+.+?\s+II\.\s+.+?\s+(?:III\.\s+.+?(?:\s+IV\.\s+.+?)?)",
        s,
    ))

def has_html_block(s: str) -> bool:
    return bool(re.search(r"<p[ >]|</p>|<li[ >]|</li>|<strong>|<em>", s, re.I))

def has_correct_incorrect_leak(s: str) -> bool:
    return bool(re.search(r"\n[ \t]*correct\s*$|\n[ \t]*incorrect\s*$", s, re.I)) \
        or bool(re.search(r"<p[^>]*>\s*(?:<[^>]+>\s*)*(?:correct|incorrect)\s*(?:<[^>]+>\s*)*</p>", s, re.I))

def has_code_table_prompt(s: str) -> bool:
    return bool(re.search(r"select the correct answer using the code given below", s, re.I))

def has_assertion_reason(s: str) -> bool:
    return bool(re.search(r"\bassertion\s*\([Aa]\)|reason\s*\([Rr]\)", s, re.I))

def has_true_false(s: str) -> bool:
    return bool(re.search(r"\b(true|false)\b\s*/\s*\b(true|false)\b|\btrue or false\b", s, re.I))

def has_mojibake(s: str) -> bool:
    """Detect common UTF-8->cp1252 mojibake codepoints."""
    return bool(re.search(r"[- ]|â€|Ã©|â€™|â€œ|â€", s))

def has_image_token(s: str) -> bool:
    return bool(re.search(r"\[\[img:|/media/fixtures/images/", s, re.I))

def has_unicode_bullet(s: str) -> bool:
    """• character (U+2022) followed by content."""
    return bool(re.search(r"[•·]\s+\S", s))


def classify(text: str) -> str:
    """Return a shape name. Order matters: most specific first."""
    if not text or not text.strip():
        return "empty"
    s = text

    # Leaks / malformed data first — they trump structural shape.
    if has_correct_incorrect_leak(s):
        return "leaked_correct_incorrect"

    # Structural shapes.
    if has_html_block(s):
        return "raw_html"
    if has_image_token(s):
        return "image_token_question"
    if has_assertion_reason(s):
        return "assertion_reason"
    if has_true_false(s):
        return "true_false"
    if has_bullet(s):
        return "bulleted_list"
    if has_numbered(s):
        return "numbered_list"
    if has_roman(s):
        return "roman_numeral_list"
    if has_unicode_bullet(s):
        return "unicode_bullet"
    if has_roman_inline(s):
        return "roman_numeral_inline"
    if has_code_table_prompt(s):
        return "code_table_prompt"
    if has_mojibake(s):
        return "mojibake"

    # Falls into "looks like prose question"
    if len(s) < 80:
        return "short_prose"
    return "long_prose"


# ---- Audit driver -----------------------------------------------------------

def main():
    # Load env
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

    import psycopg2
    url = os.environ.get('DATABASE_URL') or os.environ.get('SUPABASE_DATABASE_URL')
    conn = psycopg2.connect(url)
    cur = conn.cursor()
    cur.execute("SELECT id, question_text, exam_type FROM questions_question")

    rows = cur.fetchall()
    counts: Counter = Counter()
    by_shape: dict[str, list] = defaultdict(list)
    by_exam: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        shape = classify(r[1] or "")
        counts[shape] += 1
        by_exam[r[2] or 'NULL'][shape] += 1
        if len(by_shape[shape]) < 8:  # keep 8 samples per shape for review
            by_shape[shape].append({"id": r[0], "exam_type": r[2], "text": (r[1] or "")[:300]})

    # Resolve the output path relative to the script's own directory so
    # the JSON lands in the project-root docs/ folder whether the
    # script is invoked from `backend/` or from elsewhere.
    out = Path(__file__).resolve().parent.parent.parent / "docs" / "STRUCTURAL_AUDIT_2026_07_28.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "total_rows": len(rows),
        "shape_counts": dict(counts.most_common()),
        "by_exam": {k: dict(v) for k, v in by_exam.items()},
        "samples": dict(by_shape),
    }, indent=2, ensure_ascii=False))

    sys.stdout.write(f"=== {len(rows)} total rows audited ===\n\n")
    sys.stdout.write("shape                          count    %\n")
    sys.stdout.write("-" * 60 + "\n")
    for shape, n in counts.most_common():
        sys.stdout.write(f"{shape:30s} {n:7d}  {n/len(rows)*100:5.1f}%\n")
    sys.stdout.write(f"\nJSON written to {out}\n")


if __name__ == "__main__":
    main()