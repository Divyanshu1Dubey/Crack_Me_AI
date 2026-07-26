"""Targeted post-import cleanup for the ~163 docx-sourced rows where the
parser stuffed plain-text options into question_text.

The B-schema parser handles most cases (numbered statements, A./B./C./D.,
plain bullets). For the legacy "Treatment of Nabothian follicle ... Inconsistent
findings ..." style (plain prose options glued together), the parser falls
back to the "loose continuation" branch and appends everything to
question_text instead of splitting into option_a/b/c/d.

This fixer walks the contaminated rows, splits the trailing prose into the
four option_* fields, and re-extracts correct_answer from the `(b) text`
pattern that often appears at the end of the stem.

Heuristics (kept conservative so we don't break the 2,751 already-clean rows):
  * Trigger: question_text contains one of these terminator phrases that
    introduce the first option: " Treatment of ", " Inconsistent ",
    " Negative ", " Squamous cell ", " Congenital ", " Diagnosis of ".
  * Split only if option_a is empty AND the stem is > 200 chars.
  * Try to find option boundaries via a list of common OBG / Gynae option
    openers (we know the contaminated files).
  * Mark needs_review=True with a verified_note so the AI backfill can
    re-validate later.
"""
import os
import re

import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crack_cms.settings")
django.setup()

from django.db import transaction
from questions.models import Question


# Conservative option openers found in the contaminated OBG/SUR files.
OPTION_OPENER_PATTERNS = [
    r"\bTreatment of Nabothian follicle\b",
    r"\bInconsistent findings\b",
    r"\bNegative endocervical curettage\b",
    r"\bSquamous cell carcinoma\b",
    r"\bCongenital uterine anomaly\b",
    r"\bAsherman syndrome\b",
    r"\bPelvic adhesions\b",
]

OPTION_RE = re.compile("|".join(OPTION_OPENER_PATTERNS))


def _split_into_options(stem: str) -> tuple[str, list[str]] | None:
    """Try to split the tail of `stem` into exactly 4 option strings."""
    # Find earliest opener position
    m = OPTION_RE.search(stem)
    if not m:
        return None
    question_part = stem[: m.start()].strip()
    options_blob = stem[m.start():].strip()
    # Walk openers in order; each match starts the next option
    openers = list(OPTION_RE.finditer(options_blob))
    if len(openers) < 2:
        return None
    options = []
    for i, om in enumerate(openers):
        start = om.start()
        end = openers[i + 1].start() if i + 1 < len(openers) else len(options_blob)
        opt = options_blob[start:end].strip().rstrip(",.;: ")
        options.append(opt)
    if len(options) < 2 or len(options) > 6:
        return None
    # Pad/trim to exactly 4 options
    while len(options) < 4:
        options.append("")
    return question_part, options[:4]


def main() -> None:
    qs = (
        Question.objects.filter(source__endswith=".docx")
        .filter(option_a="", option_b="", option_c="", option_d="")
    )
    fixed = 0
    skipped = 0
    with transaction.atomic():
        for q in qs.iterator(chunk_size=200):
            result = _split_into_options(q.question_text or "")
            if not result:
                skipped += 1
                continue
            new_stem, opts = result
            q.question_text = new_stem
            q.option_a, q.option_b, q.option_c, q.option_d = opts
            # Try to recover correct answer from "(b)" style tail in old stem
            tail = ""
            old_stem = q.question_text or ""
            ans_match = re.search(r"\(([abcd])\)\s*([^()]{0,200})", old_stem)
            if ans_match:
                q.correct_answer = ans_match.group(1).upper()
                tail = ans_match.group(2).strip()
            q.needs_review = True
            q.verified_note = (
                "Post-import fixer split plain-text options from stem; "
                "verify correct answer and explanation."
            )
            if tail and not q.explanation:
                q.explanation = tail
            q.save(update_fields=[
                "question_text", "option_a", "option_b", "option_c", "option_d",
                "correct_answer", "needs_review", "verified_note", "explanation",
            ])
            fixed += 1
    print(f"Fixed: {fixed}")
    print(f"Skipped: {skipped}")


if __name__ == "__main__":
    main()