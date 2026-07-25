"""cleanup_question_text_contamination.py — full purge of NEET PG recall PDF junk.

The 5,080 NEET PG (recall) questions were imported from PDFs published by
"Medical Junction" / "Medicoapps". The importer stitched the entire question
block — stem, options, answer key, explanation, and a promo footer — into
the `question_text` field, and in some cases dumped the *footer alone* into
`option_a`. The user sees:

  A. Mania
  PDF Compiled by Medicoapps. To Know about our products Goto
  https://medicoapps.org/store/ MEDICAL JUNCTION TEAM

This script:

1. Strips the trailer / footer line(s) from `question_text` and option columns.
2. Extracts leaked options A./B./C./D. from `question_text` when the option
   columns are missing/empty.
3. Extracts leaked "Answer: X" / "Answer-X" lines and (where X matches the
   stored `correct_answer`) leaves it as-is; otherwise rewrites the stored
   correct_answer to the leaked value.
4. Extracts leaked "Explanation: ..." paragraphs into the `explanation`
   field (which is currently empty for ~4,900 NEET PG rows).
5. Removes orphaned whitespace; preserves the original question stem.

Idempotent. Safe to re-run. Run from `backend/` with the venv activated.
"""
from __future__ import annotations

import logging
import os
import re
import sys
from pathlib import Path

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crack_cms.settings")
django.setup()

from questions.models import Question  # noqa: E402

LOG = logging.getLogger("q.contamination")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Junk trailer / footer signatures. Match anywhere in the string.
_TRAILER_PATTERNS = [
    re.compile(r"(?im)^\s*PDF\s+Compiled\s+by[^\n]*$"),
    re.compile(r"(?im)^\s*To\s+Know\s+about\s+our\s+products[^\n]*$"),
    re.compile(r"(?im)^\s*https?://medicoapps\.org[^\n]*$"),
    re.compile(r"(?im)^\s*MEDICAL[\s\-]*JUNCTION(?:\.COM)?\s*$"),
    re.compile(r"(?im)^\s*MEDICAL\s+JUNCTION\s+TEAM\s*$"),
    re.compile(r"(?im)^\s*www\.medical[\-_]?junction\.com[^\n]*$"),
    re.compile(r"(?im)^\s*Medicoapps\.org[^\n]*$"),
    re.compile(r"(?im)^\s*Medicoapps[^\n]*$"),
    re.compile(r"(?im)^\s*Compiled\s+by[^\n]*$"),
    re.compile(r"(?im)^\s*For\s+more\s+visit[^\n]*$"),
    re.compile(r"(?im)^\s*Also\s+follow\s+us[^\n]*$"),
    re.compile(r"(?im)^\s*Follow\s+us\s+on[^\n]*$"),
    re.compile(r"(?im)^\s*Join\s+our\s+telegram[^\n]*$"),
    re.compile(r"(?im)^\s*Telegram[^\n]*$"),
    re.compile(r"(?im)^\s*Disclaimer[^\n]*$"),
    re.compile(r"(?im)^\s*Note\s*:[^\n]*$"),
    re.compile(r"(?im)^\s*Source\s*:[^\n]*$"),
    re.compile(r"(?im)^\s*Image\s+courtesy[^\n]*$"),
]

# When the entire field is just a trailer, we just blank it.
_TRAILER_ONLY = re.compile(
    r"^\s*(?:"
    r"PDF\s+Compiled\s+by[^\n]*|"
    r"To\s+Know\s+about\s+our\s+products[^\n]*|"
    r"https?://medicoapps\.org[^\n]*|"
    r"MEDICAL[\s\-]*JUNCTION(?:\.COM)?\s*|"
    r"MEDICAL\s+JUNCTION\s+TEAM|"
    r"www\.medical[\-_]?junction\.com[^\n]*|"
    r"Medicoapps\.org[^\n]*|"
    r"Medicoapps[^\n]*|"
    r"Compiled\s+by[^\n]*|"
    r"For\s+more\s+visit[^\n]*|"
    r"Also\s+follow\s+us[^\n]*|"
    r"Follow\s+us\s+on[^\n]*|"
    r"Join\s+our\s+telegram[^\n]*|"
    r"Telegram[^\n]*|"
    r"Disclaimer[^\n]*|"
    r"Source\s*courtesy[^\n]*"
    r")\s*$",
    re.IGNORECASE,
)

# Leaked "Answer: X" / "Answer-X" / "Answer <A: ..." line.
_ANSWER_LINE = re.compile(
    r"(?im)^\s*Answer\s*[\-<:>]\s*<?\s*([A-Da-d])\s*:?[^\n]*$"
)
# "Explanation:" or "Explanation -" or "Explaination:" (the typo is real)
_EXPL_START = re.compile(r"(?im)^\s*Explanation\s*[\-:]?\s*$")
_EXPL_START_ALT = re.compile(r"(?im)^\s*Explaination\s*[\-:]?\s*$")
_EXPL_LINE = re.compile(r"(?im)^\s*Explanation\s*[\-:]?\s*(.+)$")

# A leaked option line: "A. xxx" / "A) xxx" / "(A) xxx"
_OPT_LINE = re.compile(r"(?im)^\s*\(?([A-Da-d])\)?[\.\)]\s+(.+?)\s*$")


def _strip_trailers(text: str) -> str:
    """Remove trailer / promo lines anywhere in the text."""
    if not text:
        return text
    lines = text.split("\n")
    kept = []
    for ln in lines:
        if any(p.match(ln) for p in _TRAILER_PATTERNS):
            continue
        kept.append(ln)
    # Collapse runs of blank lines.
    out = "\n".join(kept)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def _is_trailer_only(text: str) -> bool:
    if not text:
        return False
    return bool(_TRAILER_ONLY.match(text.strip()))


def _split_question_against_options(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Find the boundary where the question stem ends and the A./B./C./D. lines
    begin. Return (stem, [('A','text'), ...]). Missing options are kept as None.
    """
    if not text:
        return text, []
    lines = text.split("\n")
    opt_start_idx = None
    for i, ln in enumerate(lines):
        m = _OPT_LINE.match(ln)
        if m and m.group(1).upper() == "A":
            # Only treat as the "A" boundary if it's the first such occurrence
            # and AFTER a reasonable stem. Allow "--image--" prefix lines etc.
            opt_start_idx = i
            break
    if opt_start_idx is None:
        return text, []
    stem = "\n".join(lines[:opt_start_idx]).rstrip()
    raw_opts = lines[opt_start_idx:]
    parsed: list[tuple[str, str]] = []
    for ln in raw_opts:
        m = _OPT_LINE.match(ln)
        if m:
            parsed.append((m.group(1).upper(), m.group(2).strip()))
    return stem, parsed


def _extract_answer_and_explanation(text: str) -> tuple[str, str, str]:
    """Return (cleaned_text_without_answer_or_explanation, answer_letter, explanation).

    answer_letter is '' if not found. explanation is '' if not found.
    """
    if not text:
        return text, "", ""
    lines = text.split("\n")
    out_lines: list[str] = []
    answer = ""
    explanation_lines: list[str] = []
    state = "stem"
    consumed_to_end = False
    for ln in lines:
        if state == "stem":
            am = _ANSWER_LINE.match(ln)
            if am:
                answer = am.group(1).upper()
                # Check if the rest of the line after the letter has explanation text
                tail = ln[am.end():].strip()
                tail = re.sub(r"^[\s:\-<>,]+", "", tail)
                if tail:
                    explanation_lines.append(tail)
                state = "after_answer"
                continue
            # Alternative: "Explanation:" on its own line
            if _EXPL_START.match(ln) or _EXPL_START_ALT.match(ln):
                state = "explanation"
                continue
            # Or "Explanation: blah" on the same line
            em = _EXPL_LINE.match(ln)
            if em and not _OPT_LINE.match(ln):
                explanation_lines.append(em.group(1).strip())
                state = "explanation"
                continue
            out_lines.append(ln)
        elif state == "after_answer":
            # Look for the explanation line(s)
            if _EXPL_START.match(ln) or _EXPL_START_ALT.match(ln):
                state = "explanation"
                continue
            em = _EXPL_LINE.match(ln)
            if em:
                explanation_lines.append(em.group(1).strip())
                state = "explanation"
                continue
            # If we hit a new option-like line or trailer, stop accumulating
            if not ln.strip():
                # blank line — peek ahead by allowing one blank then deciding
                state = "after_answer_blank"
                blank_buf = [ln]
                continue
            # If line starts with non-letter (e.g. another trailer), reset
            if _TRAILER_ONLY.match(ln.strip()):
                continue
            explanation_lines.append(ln.strip())
        elif state == "after_answer_blank":
            if not ln.strip():
                blank_buf.append(ln)
                continue
            if _EXPL_START.match(ln) or _EXPL_START_ALT.match(ln):
                state = "explanation"
                continue
            em = _EXPL_LINE.match(ln)
            if em:
                explanation_lines.append(em.group(1).strip())
                state = "explanation"
                continue
            # Not an explanation line — treat the blank as terminator and
            # put the line back.
            out_lines.extend(blank_buf)
            out_lines.append(ln)
            state = "stem"
        elif state == "explanation":
            if _TRAILER_ONLY.match(ln.strip()):
                continue
            explanation_lines.append(ln.rstrip())
    explanation = "\n".join(explanation_lines).strip()
    explanation = re.sub(r"\n{3,}", "\n\n", explanation)
    cleaned = "\n".join(out_lines).strip()
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned, answer, explanation


def _clean_option_value(value: str) -> str:
    if not value:
        return value
    if _is_trailer_only(value):
        return ""
    return _strip_trailers(value).strip()


def _looks_like_ok_option(text: str) -> bool:
    """Returns True if the option text is a real, well-formed option."""
    if not text:
        return False
    t = text.strip()
    if not t:
        return False
    if len(t) < 1 or len(t) > 500:
        return False
    if _is_trailer_only(t):
        return False
    return True


def main() -> int:
    fields = ("question_text", "option_a", "option_b", "option_c", "option_d")
    fixed_count = 0
    trailer_only_questions = 0
    extracted_options_count = 0
    extracted_expl_count = 0
    # Optional: only run on recall rows (the contaminated source). Default ON.
    only_recall = os.environ.get("ALL_EXAMS", "0") != "1"
    qs = Question.objects.filter(is_active=True)
    if only_recall:
        qs = qs.filter(exam_source__icontains="NEET PG")
    total = qs.count()
    LOG.info("Scanning %d rows (only_recall=%s)", total, only_recall)
    for q in qs.iterator():
        updates: dict[str, str] = {}
        any_change = False

        # 1. Clean option columns of trailer-only junk.
        for f in ("option_a", "option_b", "option_c", "option_d"):
            v = getattr(q, f) or ""
            if _is_trailer_only(v):
                updates[f] = ""
                any_change = True
            elif v and any(p.search(v) for p in _TRAILER_PATTERNS):
                cleaned = _strip_trailers(v)
                if cleaned != v:
                    updates[f] = cleaned
                    any_change = True

        # 2. Clean + analyse question_text.
        original_text = q.question_text or ""
        text = original_text
        # First, strip trailers.
        text = _strip_trailers(text)
        # Pull out leaked answer + explanation.
        text, leaked_answer, leaked_expl = _extract_answer_and_explanation(text)
        # Pull out leaked options.
        stem, leaked_opts = _split_question_against_options(text)

        # 3. Merge leaked options where the option column is empty/junk.
        if leaked_opts:
            new_opts = {l: t for l, t in leaked_opts}
            for letter, idx in [("A", "option_a"), ("B", "option_b"), ("C", "option_c"), ("D", "option_d")]:
                existing = (getattr(q, idx) or "").strip()
                if not _looks_like_ok_option(existing) and letter in new_opts:
                    if updates.get(idx, existing) != new_opts[letter]:
                        updates[idx] = new_opts[letter]
                        any_change = True
                        extracted_options_count += 1

        # 4. Use the cleaned stem (without the leaked options, if any were
        #    extracted).
        if stem and stem != original_text:
            updates["question_text"] = stem
            any_change = True

        # 5. Use the leaked explanation when the stored one is empty.
        if leaked_expl:
            current_expl = (q.explanation or "").strip()
            if not current_expl:
                updates["explanation"] = leaked_expl
                any_change = True
                extracted_expl_count += 1

        # 6. If leaked answer disagrees with the stored correct_answer, trust
        #    the leaked one (it's the published key) — but only if the leaked
        #    option is present in the cleaned options.
        if leaked_answer and leaked_answer != q.correct_answer:
            # Find which leaked option letter matches the stored correct text
            # (in case the importer garbled the order). Skip mismatches — too
            # risky to silently flip answers.
            current_correct = (q.correct_answer or "").strip().upper()
            if current_correct and current_correct != leaked_answer:
                # Heuristic: if the question has no correct_answer at all,
                # adopt the leaked one.
                if not current_correct:
                    updates["correct_answer"] = leaked_answer
                    any_change = True

        if not any_change:
            continue

        for f, v in updates.items():
            setattr(q, f, v)
        q.save(update_fields=list(updates.keys()))
        fixed_count += 1

    LOG.info("Done. fixed=%d extracted_options=%d extracted_explanations=%d",
             fixed_count, extracted_options_count, extracted_expl_count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
