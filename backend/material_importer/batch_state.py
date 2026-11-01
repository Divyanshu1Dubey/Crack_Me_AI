"""Row-locked read-modify-write of ``ImportBatch.summary``.

Several writers share the one ``summary`` JSON dict of a batch: the upload
view (``uploaded_files``), the ingest loop (counters), the background
publish (``publish`` state + heartbeat), the auto-test builder
(``auto_test_ids``), generate-mock (``mock_test_ids``) and rollback
(``rollback``). Each one used to read the dict, change its key and write the
whole dict back, so two writers running at the same moment could silently
drop each other's keys, and the "is a publish already running?" check could
pass for two near-simultaneous requests.

``update_batch_summary`` serialises those writers on the batch row. Its
first statement is a no-op ``UPDATE`` of the row:

* PostgreSQL: the UPDATE takes the row lock until the transaction ends, so a
  concurrent writer waits there and then reads the committed dict.
* SQLite (local dev): ``select_for_update`` is ignored, but the same UPDATE
  takes the database write lock, with the same effect.
"""
from __future__ import annotations

import copy
from typing import Callable, TypeVar

from django.db import transaction
from django.db.models import F
from django.utils import timezone

T = TypeVar("T")


def update_batch_summary(batch_id: int, mutate: Callable[[dict], T]) -> T | None:
    """Apply ``mutate(summary)`` to the batch's summary under a row lock.

    ``mutate`` changes the dict in place and may return a value, which is
    passed back to the caller. The row is written only when the dict changed.
    Returns None (and writes nothing) when the batch does not exist; if
    ``mutate`` raises, nothing is written.
    """
    from .models import ImportBatch

    with transaction.atomic():
        locked = ImportBatch.objects.filter(pk=batch_id).update(summary=F("summary"))
        if not locked:
            return None
        current = ImportBatch.objects.filter(pk=batch_id).values_list("summary", flat=True).first()
        before = dict(current or {})
        summary = copy.deepcopy(before)
        result = mutate(summary)
        if summary != before:
            ImportBatch.objects.filter(pk=batch_id).update(summary=summary, updated_at=timezone.now())
        return result


def set_summary_key(batch_id: int, key: str, value) -> None:
    """Set one top-level ``summary`` key without touching the others."""
    def _set(summary: dict) -> None:
        summary[key] = value

    update_batch_summary(batch_id, _set)


__all__ = ["update_batch_summary", "set_summary_key"]
