"""
One-off backfill: populate `Question.display_number` for every active
question, ordered per (exam_type, year, id).

Why: the field was added but never populated for NEET PG 2021 (and
likely other years), so the player UI shows null ordinals.

Safe to re-run — the script only writes rows where display_number IS
NULL.  After the backfill, a `git diff backend/questions_fixture.json`
will reveal what to commit.
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crack_cms.settings")
django.setup()

from django.db import transaction
from django.db.models import F, Window
from django.db.models.functions import RowNumber

from questions.models import Question


def backfill(dry_run: bool = True, batch_size: int = 500) -> int:
    """Assign display_number = 1..N per (exam_type, year), ordered by id.

    Returns the number of rows touched.
    """
    qs = (
        Question.objects
        .filter(is_active=True, display_number__isnull=True)
        .annotate(
            ordinal=Window(
                expression=RowNumber(),
                partition_by=["exam_type", "year"],
                order_by=F("id").asc(),
            ),
        )
        .values("id", "ordinal")
    )

    # Iterate + write in batches so we don't blow memory on large exams.
    touched = 0
    batch: list[tuple[int, int]] = []
    for row in qs.iterator(chunk_size=batch_size):
        batch.append((row["id"], row["ordinal"]))
        if len(batch) >= batch_size:
            touched += _flush(batch, dry_run)
            batch = []
    if batch:
        touched += _flush(batch, dry_run)
    return touched


def _flush(batch: list[tuple[int, int]], dry_run: bool) -> int:
    if not batch:
        return 0
    if dry_run:
        print(f"[dry-run] would update {len(batch)} rows (sample: {batch[:3]})")
        return 0
    with transaction.atomic():
        for qid, ordinal in batch:
            Question.objects.filter(id=qid).update(display_number=ordinal)
    return len(batch)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true", help="actually write the changes")
    p.add_argument("--batch", type=int, default=500)
    args = p.parse_args()
    n = backfill(dry_run=not args.apply, batch_size=args.batch)
    print(f"{'[dry-run] would touch' if not args.apply else 'touched'} {n} rows")
