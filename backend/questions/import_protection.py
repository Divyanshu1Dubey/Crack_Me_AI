"""Import-time tombstone enforcement for the question bank.

Every Question-create path (NEET PG recall, INI-CET recall, fixture loader,
mocktest importer, PYQ importer, vision extractor, MCE pipeline, admin
editor, duplicate-of copy, …) must honour the durable `RemovedQuestion`
tombstone so an admin-removed question can NEVER silently return on a
re-deploy.

This module provides a single helper, `is_removed(text)`, that any import
path can call before creating a row. The hashing is byte-identical to
`questions.models.compute_stem_hash` and to
`importers/{neetpg,inicet}/deduplicator.text_sha256` so hashes match
across every path.

We intentionally do NOT use a Django pre_save signal: signals cannot
prevent `objects.create()` from inserting the row, so the only correct
behaviour is to short-circuit *before* create() is called.

Import paths that already do this work themselves (e.g. `load_exam_fixture`,
`import_neet_pg._save_questions`, `importers/*/db_writer.write_question`)
should keep using their own dedup set for performance reasons — they
already cache `RemovedQuestion` rows once per run.
"""
from __future__ import annotations

import logging
from typing import Iterable, Optional, Union

from .models import RemovedQuestion, compute_stem_hash

LOG = logging.getLogger(__name__)


__all__ = ["is_removed", "pre_check_create"]


def is_removed(text: Optional[str]) -> bool:
    """Return True iff a tombstone matches this stem's canonical hash.

    Cheap; a single SELECT on the indexed `question_text_hash` column.
    Use this as a guard right before any `Question.objects.create(...)`
    call inside an import loop. For batch loops, prefer building a set
    once with `RemovedQuestion.objects.values_list('question_text_hash',
    flat=True)` and then doing `stem_hash in removed_set` — but this
    helper is the right primitive for one-off admin / dev paths.
    """
    if not text:
        return False
    return RemovedQuestion.objects.filter(
        question_text_hash=compute_stem_hash(text),
    ).exists()


def pre_check_create(text: Optional[str], *, where: str = "") -> bool:
    """Return True iff the import should be skipped (tombstone matched).

    `where` is a short label that gets logged when a skip fires, e.g.
    "import_mocktests._save_question" or "vision_extractor._save_row".
    Centralises the log format so production grep finds every skip site.
    """
    if not text:
        return False
    if not is_removed(text):
        return False
    LOG.warning(
        "Skipping Question create (%s): stem hash matches a RemovedQuestion tombstone",
        where or "unknown site",
    )
    return True