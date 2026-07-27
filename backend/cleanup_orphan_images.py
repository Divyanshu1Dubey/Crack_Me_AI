"""One-shot cleanup for orphan QuestionImage rows.

Context: the docx mocktest ingestion (and earlier recall imports) created
QuestionImage rows even when the actual image bytes were never attached
to a `[[img:N]]` token in the question text. Some questions accumulated
hundreds of rows. This script soft-deletes (is_active=False) every active
row whose id is NOT referenced in any of the question's text fields AND
the question retains at least one referenced image — so we never zero
out a question by accident.

Run:
    python manage.py shell < cleanup_orphan_images.py

Or directly:
    python cleanup_orphan_images.py            # DRY-RUN
    python cleanup_orphan_images.py --apply    # mark orphans is_active=False
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from collections import defaultdict

import django

# Allow running as a standalone script: bootstrap Django.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crack_cms.settings")
django.setup()

from questions.models import Question, QuestionImage  # noqa: E402

TOKEN_RE = re.compile(r"\[\[img:(\d+)\]\]")


def referenced_ids_for_question(q: Question) -> set[int]:
    """Return the set of QuestionImage ids referenced via [[img:N]] in any text field."""
    blob = " ".join(
        filter(
            None,
            [
                q.question_text,
                q.option_a,
                q.option_b,
                q.option_c,
                q.option_d,
                q.explanation,
                q.mnemonic,
                q.concept_explanation,
            ],
        )
    )
    return {int(m) for m in TOKEN_RE.findall(blob)}


def find_orphans() -> tuple[list[tuple[int, int]], dict[int, set[int]]]:
    """Return (orphan_list, referenced_map) where:
      - orphan_list = [(image_id, question_id), ...] for active rows that are
        NOT referenced in any text field AND their question has >= 1
        referenced image (so we don't wipe the only image on a question).
      - referenced_map = {question_id: {image_ids referenced in text}}.
    """
    referenced_map: dict[int, set[int]] = {}
    for q in Question.objects.only("id", "question_text", "option_a", "option_b",
                                    "option_c", "option_d", "explanation",
                                    "mnemonic", "concept_explanation").iterator():
        referenced_map[q.id] = referenced_ids_for_question(q)

    orphans: list[tuple[int, int]] = []
    # Iterate active images in chunks; we only need id + question_id + is_active.
    qs = QuestionImage.objects.filter(is_active=True).only("id", "question_id").iterator(chunk_size=2000)
    for img in qs:
        referenced = referenced_map.get(img.question_id, set())
        # Skip if row is referenced in text.
        if img.id in referenced:
            continue
        # Skip if question has zero referenced images — the user may still
        # want to attach one, so we keep the existing row(s) as a "drawing board".
        if not referenced:
            continue
        orphans.append((img.id, img.question_id))
    return orphans, referenced_map


def main() -> int:
    parser = argparse.ArgumentParser(description="Soft-delete orphan QuestionImage rows.")
    parser.add_argument("--apply", action="store_true",
                        help="Mark orphans as is_active=False (default: dry-run report only)")
    args = parser.parse_args()

    orphans, referenced_map = find_orphans()
    total_active = QuestionImage.objects.filter(is_active=True).count()
    total_referenced = sum(len(v) for v in referenced_map.values())
    questions_with_imgs = sum(1 for v in referenced_map.values() if v)

    print(f"Active QuestionImage rows: {total_active}")
    print(f"Distinct referenced [[img:N]] tokens across questions: {total_referenced}")
    print(f"Questions with >= 1 referenced image: {questions_with_imgs}")
    print(f"Orphan rows (active, not referenced, parent has >= 1 reference): {len(orphans)}")
    print()

    # Per-question orphan counts so the user can see who got inflated.
    by_question: dict[int, int] = defaultdict(int)
    for _img_id, q_id in orphans:
        by_question[q_id] += 1
    top = sorted(by_question.items(), key=lambda kv: -kv[1])[:20]
    print("Top 20 questions by orphan count:")
    for q_id, n in top:
        # Sanity-check: how many referenced images does this question have?
        ref = len(referenced_map.get(q_id, set()))
        print(f"  Q{q_id:>6}: {n:>4} orphan rows  ({ref} referenced)")
    print()

    if not args.apply:
        print("DRY-RUN. Re-run with --apply to mark these is_active=False.")
        return 0

    if not orphans:
        print("Nothing to do.")
        return 0

    ids = [i for i, _ in orphans]
    updated = QuestionImage.objects.filter(id__in=ids, is_active=True).update(is_active=False)
    print(f"Marked {updated} rows is_active=False.")
    print(f"Remaining active: {QuestionImage.objects.filter(is_active=True).count()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())