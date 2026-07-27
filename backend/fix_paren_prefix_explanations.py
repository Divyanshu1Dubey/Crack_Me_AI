"""
One-shot cleanup: fix Expert Curated explanations that start with a stray
") " (a leaked Answer-key fragment from the docx Schema-A "Solution" cell).

Root cause: `import_mocktests.py:246` reads the docx "Solution" cell verbatim
into `Question.explanation`. Several cms_exclusive_material files wrote the
answer key inside the Solution cell using "Answer: B) Octreotide scanning..."
or ") 1, 2 and 3 only" — the `) ` ended up as the FIRST char of the stored
explanation. Frontend renders it verbatim (ReactMarkdown only kicks in if the
text starts with `#` or `*`, not for a leading `)`).

Heuristics applied:
  - Explanations that START with ") " (whitespace optional) are aggressively
    trimmed until the first character is alphabetic / numeric / "(".
  - Empty after trim → leave field blank (so renderer's "Why correct" hint
    can fire instead).
  - Skip rows whose explanation still looks real (starts with letter, starts
    with "The", "It is", etc.) — this script only touches contaminated rows.

Run:
    PYTHONIOENCODING=utf-8 python fix_paren_prefix_explanations.py [--dry-run]
"""
from __future__ import annotations

import os
import re
import sys
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crack_cms.settings")
django.setup()

from questions.models import Question  # noqa: E402

# Matches a leading ") ", "] ", "1) ", "a) ", "A) " etc. — anything that
# looks like an orphaned list / answer-key fragment.
LEADING_DELIM_RE = re.compile(r"^\s*(?:[\)\]\.\,\:\;]|[\(\[]?\d{1,3}[\.\)]|\(?[A-Da-d]\))\s+")
# Trim until we hit the first alphabetic char (skip up to 8 leading fragments)
MAX_TRIMS = 8


def looks_like_real_explanation(text: str) -> bool:
    """Return True when the first non-space char is a letter — likely real."""
    s = text.lstrip()
    return bool(s) and s[0].isalpha()


def clean_explanation(text: str) -> str:
    s = text
    for _ in range(MAX_TRIMS):
        if not s or looks_like_real_explanation(s):
            return s.strip()
        new = LEADING_DELIM_RE.sub("", s, count=1)
        if new == s:
            return s.strip()
        s = new
    return s.strip()


def main(dry_run: bool = False) -> int:
    qs = (
        Question.objects.filter(explanation__regex=r"^\s*[\)\]]")
        .only("id", "explanation")
    )
    total = qs.count()
    print(f"Found {total} explanations starting with ) or ]")
    fixed = 0
    emptied = 0
    samples_before: list[tuple[int, str, str]] = []
    samples_after: list[tuple[int, str, str]] = []
    for q in qs.iterator(chunk_size=500):
        original = q.explanation or ""
        cleaned = clean_explanation(original)
        if cleaned == original.strip():
            continue
        if not cleaned:
            emptied += 1
        else:
            fixed += 1
        if len(samples_before) < 5:
            samples_before.append((q.id, original[:80], ""))
            samples_after.append((q.id, cleaned[:80], ""))
        if not dry_run:
            q.explanation = cleaned
            q.save(update_fields=["explanation"])
    print(f"\nDry run: {dry_run}")
    print(f"Trimmed leading junk from : {fixed}")
    print(f"Emptied (became blank)     : {emptied}")
    print(f"Total rows touched          : {fixed + emptied}\n")
    for (b_id, b, _), (_, a, _) in zip(samples_before, samples_after):
        print(f"  #{b_id}\n    BEFORE: {b!r}\n    AFTER : {a!r}\n")
    return 0


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    sys.exit(main(dry_run=dry))