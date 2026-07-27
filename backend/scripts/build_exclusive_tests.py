"""Build auto-tests for the recent "CMS Exclusive Q4 2026" import batches.

After running `ingest_cms_material` on the user's 15 mocktest files, this
script:

  1. Bulk-approves every `pending` / `needs_review` question in those
     batches (they were parsed with verified answers — safe to auto-approve).
  2. Publishes them to the live `Question` bank.
  3. Builds auto-tests with proper naming:
        - Per-subject tests:    "CMS Exclusive — <Subject>" / "CMS Exclusive Mock — <Subject>"
        - Per-batch file tests: "CMS Exclusive — <filename>" (for each source file)
        - Mixed grand test:     "CMS Exclusive Grand Test — Q4 2026" (all)
        - Image-based test:     "CMS Exclusive Image-Based — Q4 2026"

Idempotent: re-running replaces the same Test rows (by title) instead of
duplicating them.

Run:
    python manage.py shell < scripts/build_exclusive_tests.py

Or:
    python -X utf8 manage.py shell -c "
    exec(open('scripts/build_exclusive_tests.py').read())
    "
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from material_importer.models import ExtractedQuestion, ImportBatch
from material_importer.mock_test_builder import (
    _ensure_test,
    _safe_set_questions,
    publish_batch,
)
from questions.models import Subject

LABEL_PREFIX = "CMS Exclusive"
GRAND_TITLE = f"{LABEL_PREFIX} Grand Test — Q4 2026"
IMAGE_TITLE = f"{LABEL_PREFIX} Image-Based — Q4 2026"
ALL_LABEL = "Q4 2026"


def _recent_batches() -> list[ImportBatch]:
    """Return the CMS Exclusive batches the user just ingested."""
    return list(
        ImportBatch.objects
        .filter(source_label__icontains="CMS Exclusive Q4 2026")
        .order_by("id")
    )


def _bulk_approve(batch_ids: list[int]) -> int:
    """Bulk-approve every pending/needs_review row in the given batches."""
    n = ExtractedQuestion.objects.filter(
        material__batch_id__in=batch_ids,
        status__in=["pending", "needs_review"],
    ).update(status="approved")
    return n


def _publish(batch_ids: list[int]) -> dict[int, int]:
    """Publish approved rows to live Question bank. Returns {batch_id: count}."""
    out: dict[int, int] = {}
    for bid in batch_ids:
        out[bid] = publish_batch(bid)
    return out


def _subject_for(eq: ExtractedQuestion) -> str:
    """Best-effort subject name: prefer resolved FK, fall back to inferred text."""
    if eq.subject_id and eq.subject:
        return eq.subject.name
    raw = (eq.inferred_subject or "").strip()
    if not raw:
        return "Imported"
    return raw


def build_per_subject(batches: list[ImportBatch]) -> dict[str, int]:
    """Build a Test per inferred subject. Returns {subject: test_id}."""
    qs = (ExtractedQuestion.objects
          .filter(material__batch__in=batches, status__in=["approved", "published"],
                  published_question__isnull=False)
          .select_related("subject", "material", "material__batch"))
    by_subject: dict[str, list[int]] = defaultdict(list)
    for eq in qs:
        # _safe_set_questions() expects ExtractedQuestion ids and resolves
        # them to live Question ids internally.
        by_subject[_subject_for(eq)].append(eq.id)

    created: dict[str, int] = {}
    for subject_name, eq_ids in sorted(by_subject.items()):
        subj_obj = Subject.objects.filter(name__iexact=subject_name).first()
        title = f"{LABEL_PREFIX} Mock — {subject_name} ({ALL_LABEL})"
        t = _ensure_test(
            name=title,
            kind="subject",
            description=(
                f"Auto-built from CMS Exclusive Q4 2026 batch. "
                f"Subject: {subject_name}. Questions: {len(eq_ids)}."
            ),
            subject=subj_obj,
        )
        n = _safe_set_questions(t, eq_ids, max_per_test=200)
        created[subject_name] = t.id
        print(f"  • subject test: {title!r:<60} q={n} id={t.id}")
    return created


def build_per_file(batches: list[ImportBatch]) -> dict[str, int]:
    """Build a Test per source file. Returns {filename: test_id}."""
    qs = (ExtractedQuestion.objects
          .filter(material__batch__in=batches, status__in=["approved", "published"],
                  published_question__isnull=False)
          .select_related("material"))
    by_file: dict[str, list[int]] = defaultdict(list)
    for eq in qs:
        by_file[eq.material.original_filename].append(eq.id)

    created: dict[str, int] = {}
    for fname, eq_ids in sorted(by_file.items()):
        title = f"{LABEL_PREFIX} — {fname.replace('.docx', '').replace('.pdf', '').strip()}"
        # Skip files with 0 published questions
        if not eq_ids:
            continue
        t = _ensure_test(
            name=title,
            kind="mixed",
            description=(
                f"Auto-built from CMS Exclusive Q4 2026 source file: {fname}. "
                f"Questions: {len(eq_ids)}."
            ),
        )
        n = _safe_set_questions(t, eq_ids, max_per_test=300)
        created[fname] = t.id
        print(f"  • file test:    {title[:60]!r:<62} q={n} id={t.id}")
    return created


def build_grand_test(batches: list[ImportBatch]) -> int:
    """One big mixed test pulling every published question."""
    eq_ids = list(
        ExtractedQuestion.objects
        .filter(material__batch__in=batches, status__in=["approved", "published"],
                published_question__isnull=False)
        .values_list("id", flat=True)
    )
    if not eq_ids:
        return 0
    t = _ensure_test(
        name=GRAND_TITLE,
        kind="mixed",
        description=(
            f"Grand mixed test combining all CMS Exclusive Q4 2026 questions. "
            f"Auto-built at {datetime.utcnow().isoformat()}Z."
        ),
    )
    n = _safe_set_questions(t, eq_ids, max_per_test=500)
    print(f"  • grand test:   {GRAND_TITLE!r:<60} q={n} id={t.id}")
    return t.id


def build_image_test(batches: list[ImportBatch]) -> int:
    """Test consisting only of image-bearing questions."""
    eq_ids = list(
        ExtractedQuestion.objects
        .filter(material__batch__in=batches, status__in=["approved", "published"],
                published_question__isnull=False)
        .exclude(image_refs=[])
        .values_list("id", flat=True)
    )
    if not eq_ids:
        return 0
    t = _ensure_test(
        name=IMAGE_TITLE,
        kind="mixed",
        description=(
            f"Image-based test from CMS Exclusive Q4 2026 batch. "
            f"All questions contain at least one image."
        ),
    )
    n = _safe_set_questions(t, eq_ids, max_per_test=200)
    print(f"  • image test:   {IMAGE_TITLE!r:<60} q={n} id={t.id}")
    return t.id


def main() -> None:
    print("=== CMS Exclusive Q4 2026 — bulk-build auto-tests ===\n")
    batches = _recent_batches()
    if not batches:
        print("No CMS Exclusive Q4 2026 batches found. Did ingest run?")
        return
    batch_ids = [b.id for b in batches]
    print(f"Batches: {len(batches)} ({', '.join(str(b.id) for b in batches)})")

    # 1. Bulk-approve pending / needs_review rows
    n_approved = _bulk_approve(batch_ids)
    print(f"\n[1] Bulk-approved {n_approved} staging rows.")

    # 2. Publish to live Question bank
    pub_counts = _publish(batch_ids)
    total_pub = sum(pub_counts.values())
    print(f"[2] Published {total_pub} Questions to live bank (per-batch: {pub_counts})")

    # 3. Build per-subject tests
    print(f"\n[3] Per-subject tests:")
    by_subj = build_per_subject(batches)

    # 4. Build per-file tests
    print(f"\n[4] Per-source-file tests:")
    by_file = build_per_file(batches)

    # 5. Build grand test
    print(f"\n[5] Mixed grand test:")
    grand_id = build_grand_test(batches)

    # 6. Build image test
    print(f"\n[6] Image-based test:")
    img_id = build_image_test(batches)

    print("\n=== Done. ===")
    print(f"  subjects: {len(by_subj)} | files: {len(by_file)} | grand={grand_id} | image={img_id}")


if __name__ == "__main__":
    main()