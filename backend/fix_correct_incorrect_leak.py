"""
One-shot cleanup: strip leaked "correct" / "incorrect" annotations from the
end of option_a..d / explanation / mnemonics.

Root cause: cms_exclusive_material docx files emitted per-option "correct" /
"incorrect" annotations that the mocktest parser appended verbatim to each
option value. Result: every option row rendered the option letter + answer
combination on line 1 and a stray "correct" / "incorrect" word on line 2.

Heuristics:
  - For each text field, drop any trailing standalone "correct" / "incorrect"
    word (case-insensitive) on its own line, optionally preceded by a
    blank line or hyphen-bullet.
  - Only acts on values that actually contain the leak (fast guard first).
  - Skips fields where the word is the only content.

Run:
    PYTHONIOENCODING=utf-8 python fix_correct_incorrect_leak.py [--dry-run]
"""
from __future__ import annotations

import os
import re
import sys
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crack_cms.settings")
django.setup()

from questions.models import Question  # noqa: E402

TEXT_FIELDS = ("question_text", "option_a", "option_b", "option_c", "option_d",
               "explanation", "mnemonic", "concept_explanation")
# Match a trailing "correct" or "incorrect" word on its OWN LINE at the end
# of the text. Anchored on $ so we don't accidentally eat legitimate uses
# of the word mid-sentence ("2 and 4 are correct", "only the tricuspid is
# incorrect", etc.). The docx leak always produced a single standalone
# trailing word, so requiring `\n…word$` is the safe pattern.
LEAK_RE = re.compile(r"\n[ \t]*[\-•\*]?[ \t]*(?:correct|incorrect)\s*$", re.I)


def strip_leak(text: str) -> str:
    if not text or not LEAK_RE.search(text):
        return text
    new = LEAK_RE.sub("", text).rstrip()
    # Defensive: if stripping left a dangling trailing newline, drop it.
    return new


def main(dry_run: bool = False) -> int:
    qs = Question.objects.all().only("id", *TEXT_FIELDS)
    total = qs.count()
    print(f"Scanning {total} questions for trailing correct/incorrect leaks…")
    touched = 0
    samples: list[tuple[int, str, str, str]] = []
    for q in qs.iterator(chunk_size=500):
        changes: dict[str, str] = {}
        for f in TEXT_FIELDS:
            original = getattr(q, f) or ""
            if "correct" not in original.lower() and "incorrect" not in original.lower():
                continue
            cleaned = strip_leak(original)
            if cleaned != original:
                changes[f] = cleaned
                if len(samples) < 4:
                    samples.append((q.id, f, original[:90], cleaned[:90]))
        if not changes:
            continue
        touched += 1
        if not dry_run:
            for k, v in changes.items():
                setattr(q, k, v)
            q.save(update_fields=list(changes.keys()))
    print(f"\nDry run: {dry_run}")
    print(f"Questions touched : {touched}")
    for qid, field, before, after in samples:
        print(f"  #{qid} [{field}]\n    BEFORE: {before!r}\n    AFTER : {after!r}\n")
    return 0


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    sys.exit(main(dry_run=dry))