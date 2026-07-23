"""cleanup_neetpg_mojibake.py — repair the last 20 mojibake-leaking NEET PG rows.

After Phase 7 only 20 / 2,185 NEET PG rows still contain UTF-8-as-latin1
signatures ("ÃÂ", "Ã©", etc.). Those were imported in earlier runs that
fixed bytes-but-not-text normalisation. The repair below:

1. Detects rows whose `question_text` matches a mojibake signature
   (`Â`/`Ã`/`Â°`/`Â·`/`Â®` followed by a non-ASCII byte).
2. Re-runs `bytes(latin1).decode('utf-8')` round-trip on the affected
   fields until no further repair reduces the mojibake score.
3. Soft-deletes (`is_active=False`) rows that cannot be repaired
   after two passes — better to remove junk than to ship it.

Run::

    cd backend
    python cleanup_neetpg_mojibake.py

Idempotent: rows that are already clean are skipped.
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

LOG = logging.getLogger("neetpg.mojibake")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Strings that count as "mojibake signatures" once they survive UTF-8
# decoding as latin-1. The full set is conservative — these are common
# in MARROW + Way2online + zygote PDF flavours.
_MOJI = re.compile(r"(Ã|Â|â)[^\na-zA-Z]")


def _mojibake_score(text: str) -> int:
    if not text:
        return 0
    return len(_MOJI.findall(text))


def _repair(text: str) -> tuple[str, int]:
    """Best-effort UTF-8-as-latin1 round-trip.

    Returns (possibly_cleaned_text, residual_score). Iterates the
    bytes-level repair up to two passes — extra passes don't help.
    """
    if not text or _mojibake_score(text) == 0:
        return text, 0
    prev = text
    best = text
    best_score = _mojibake_score(text)
    for _ in range(2):
        try:
            candidate = prev.encode("latin-1", "replace").decode("utf-8", "replace")
        except (UnicodeEncodeError, UnicodeDecodeError):
            break
        score = _mojibake_score(candidate)
        if score < best_score:
            best, best_score = candidate, score
        prev = candidate
    return best, best_score


def main() -> int:
    fields = ("question_text", "option_a", "option_b", "option_c", "option_d",
              "explanation", "mnemonic")
    fixed = 0
    soft_deleted = 0
    skipped = 0
    qs = Question.objects.filter(exam_type="neet_pg", is_active=True)
    for q in qs.iterator():
        if _mojibake_score(q.question_text or "") == 0:
            skipped += 1
            continue
        updates: dict[str, str] = {}
        max_residual = 0
        for f in fields:
            current = getattr(q, f) or ""
            if _mojibake_score(current) == 0:
                continue
            cleaned, score = _repair(current)
            if cleaned != current:
                updates[f] = cleaned
                max_residual = max(max_residual, score)
        if not updates:
            continue
        if max_residual > 1:
            # Two-pass repair still mojibake-heavy → soft-delete so the
            # row stops surfacing in the player.
            q.is_active = False
            q.save(update_fields=["is_active"])
            soft_deleted += 1
            LOG.info("Q%s soft-deleted (residual mojibake score=%d)", q.id, max_residual)
            continue
        for f, v in updates.items():
            setattr(q, f, v)
        q.save(update_fields=list(updates.keys()))
        fixed += 1
        LOG.info("Q%s repaired (%d fields)", q.id, len(updates))
    LOG.info("Done. fixed=%d soft_deleted=%d skipped=%d", fixed, soft_deleted, skipped)
    return 0


if __name__ == "__main__":
    sys.exit(main())
