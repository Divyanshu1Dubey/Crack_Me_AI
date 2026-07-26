"""Heuristic fixer for the ~143 mocktest questions where the B-schema parser
couldn't classify options and they ended up glued onto the stem.

Two patterns handled:
  (A) Bullet-list options (Parkinson's features, migraine triggers, ...):
      stem ends with newline-separated feature list + "Reference:" line.
      Split on newline into 4 options.
  (B) B4-style "(a) 1 and 2 only" / "(b) 1, 2, 3 and 4" / "(c) ..." / "(d) ..."
      + "Ans: (a|...)" line. Extract options and correct answer.

Both heuristics are conservative; rows that don't match are skipped and
remain in `needs_review` for manual / AI backfill.
"""
import os
import re

import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crack_cms.settings")
django.setup()

from django.db import transaction
from questions.models import Question


# Pattern A: bullet list terminated by Reference: line
REFERENCE_LINE_RE = re.compile(r"\bReference\s*:\s*.+$", re.I | re.M)
# Pattern B: "(a) ..." / "(b) ..." / "(c) ..." / "(d) ..."
LC_OPT_RE = re.compile(r"\(([a-d])\)\s*([^\n]+)")
# Pattern B': "A. I, II and III only" — uppercase letter with period (CODE_OPT_RE style)
UC_OPT_RE = re.compile(r"(?:^|\n)\s*([A-D])\s*\.\s*([^\n]+)")
# Pattern B'': inline "a. ... b. ... c. ... d. ..." (no newline separators)
# e.g. "...diagnosis? a. Peripheral ... b. Deep ... c. Acute ... d. Osteomyelitis"
INLINE_LC_RE = re.compile(r"(?:\s|^)([abcd])\.\s+", re.I)
ANS_LC_RE = re.compile(r"Ans(?:wer)?\s*:\s*\(([a-d])\)", re.I)
ANS_UC_RE = re.compile(r"Ans(?:wer)?\s*:\s*([A-D])(?:\s|\.|$)", re.I | re.M)
# Newline splitter for bullet-style options
NL_RE = re.compile(r"\n+")


def _fix_bullet(q: Question) -> bool:
    """Pattern A — bullet-list options, terminated by Reference:."""
    text = q.question_text or ""
    if "Reference" not in text:
        return False
    m = REFERENCE_LINE_RE.search(text)
    if not m:
        return False
    after_ref_idx = m.end()
    # Strip everything from Reference: onward (that's the citation, not options)
    body = text[:after_ref_idx].rstrip()
    # Try splitting tail of body on newline — last few non-empty lines are the
    # options. Find the earliest "option" line by looking for short capitalized
    # lines OR lines starting with a dash/bullet.
    lines = [ln.strip(" \t\r•-—*") for ln in body.split("\n") if ln.strip()]
    if len(lines) < 5:
        return False
    # Last 4 lines = options
    options = lines[-4:]
    stem_lines = lines[:-4]
    new_stem = "\n".join(stem_lines).strip()
    if len(new_stem) < 30:
        return False
    q.question_text = new_stem
    q.option_a = options[0]
    q.option_b = options[1]
    q.option_c = options[2]
    q.option_d = options[3]
    return True


def _fix_b4(q: Question) -> bool:
    """Pattern B — "(a) ... (b) ... (c) ... (d) ..." OR "A. ... B. ..." with
    'Ans: (X)' or 'Answer: X'."""
    text = q.question_text or ""
    # Try lowercase "(a)" pattern first, then uppercase "A." pattern,
    # then inline "a. ... b. ..." pattern.
    matches = list(LC_OPT_RE.finditer(text))
    used_pattern = LC_OPT_RE
    if len(matches) < 3:
        matches = list(UC_OPT_RE.finditer(text))
        used_pattern = UC_OPT_RE
    if len(matches) < 3:
        matches = list(INLINE_LC_RE.finditer(text))
        used_pattern = INLINE_LC_RE
    if len(matches) < 3:
        return False
    # Extract option letter → text (always uppercase A-D)
    by_letter = {}
    is_inline = used_pattern is INLINE_LC_RE
    if is_inline:
        # Inline pattern: matches give positions only; split text between positions
        for i, m in enumerate(matches):
            letter = m.group(1).upper()
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            by_letter[letter] = text[start:end].strip()
    else:
        for m in matches:
            letter = m.group(1).upper()
            by_letter[letter] = m.group(2).strip()
    if len(by_letter) < 3:
        return False
    # Find stem end = first option position
    first_opt_pos = matches[0].start()
    # For inline, back up past the leading punctuation (e.g. "? " or ". ")
    if is_inline:
        # Walk back to find ? or . before the option
        pre = text[:first_opt_pos]
        qmark = max(pre.rfind("?"), pre.rfind("."))
        if qmark >= 0 and qmark > len(pre) - 20:
            first_opt_pos = qmark + 1
    new_stem = text[:first_opt_pos].strip()
    if len(new_stem) < 30:
        return False
    q.question_text = new_stem
    for letter in ("A", "B", "C", "D"):
        setattr(q, f"option_{letter.lower()}", by_letter.get(letter, ""))
    # Extract correct answer — try both patterns
    ans_m = ANS_LC_RE.search(text) or ANS_UC_RE.search(text)
    if ans_m:
        q.correct_answer = ans_m.group(1).upper()
    # Extract explanation (text after "Explanation:" if present)
    expl_m = re.search(r"Explanation\s*:\s*(.+)$", text, re.I | re.S)
    if expl_m and not q.explanation:
        q.explanation = expl_m.group(1).strip()
    return True


def main() -> None:
    from django.db.models import Q
    bad = Question.objects.filter(source__endswith=".docx").filter(
        Q(option_a="") | Q(option_b="") | Q(option_c="") | Q(option_d="")
    )
    fixed_a, fixed_b, skipped = 0, 0, 0
    with transaction.atomic():
        for q in bad.iterator(chunk_size=200):
            if _fix_b4(q):
                fixed_b += 1
            elif _fix_bullet(q):
                fixed_a += 1
            else:
                skipped += 1
                continue
            q.needs_review = True
            q.verified_note = (
                "Post-import fixer recovered options from stem (bullet-list or "
                "B4 '(a)/(b)/(c)/(d)' pattern); verify correct answer."
            )
            q.save(update_fields=[
                "question_text", "option_a", "option_b", "option_c", "option_d",
                "correct_answer", "explanation", "needs_review", "verified_note",
            ])
    print(f"Fixed (bullet-list): {fixed_a}")
    print(f"Fixed (B4 style):    {fixed_b}")
    print(f"Skipped:             {skipped}")


if __name__ == "__main__":
    main()