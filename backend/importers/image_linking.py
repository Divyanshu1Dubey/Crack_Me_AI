"""Attach extracted PDF images to the question they belong to.

Used by the NEET PG and INI-CET recall runners. An ``ImageRecord`` only
knows its page (there is no per-question link from the text parser), so an
image is attached only when the page makes the owner unambiguous:

  1. Decorative images — the same image bytes on 3+ different pages (logos,
     headers, watermarks) — are never attached.
  2. If the page has exactly one image-based question (its stem references a
     figure), the image goes to that question.
  3. Otherwise, if the page has exactly one question, the image goes to it.
  4. Anything else is ambiguous: the image is left unlinked, reported in the
     run summary, and the page's image-based questions are flagged
     ``needs_review`` so an admin can attach it by hand.

The runners used to fall back to "the first question of the PDF", so every
image of every recall import landed on question #1.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Iterable

LOG = logging.getLogger(__name__)

DECORATIVE_MIN_PAGES = 3
MAX_REPORTED_UNLINKED = 200


def _is_image_based(parsed) -> bool:
    return bool(getattr(parsed, "is_image_based", False) or getattr(parsed, "image_refs", None))


def link_images_by_page(writer, written: Iterable, image_records: Iterable, recall_source) -> dict:
    """Link images to questions; returns counts + the unlinked image list.

    ``written`` is an iterable of ``(ParsedQuestion, Question)`` pairs for the
    questions the writer actually stored.
    """
    from questions.models import Question

    by_page: dict[int, list] = defaultdict(list)
    for parsed, row in written:
        by_page[int(getattr(parsed, "page_number", 0) or 0)].append((parsed, row))

    images = list(image_records)
    pages_per_sha: dict[str, set] = defaultdict(set)
    for img in images:
        if getattr(img, "sha256_short", ""):
            pages_per_sha[img.sha256_short].add(int(img.page_number or 0))

    linked = 0
    decorative = 0
    # ``unlinked`` is the detail list (capped at MAX_REPORTED_UNLINKED for the
    # run summary); ``unlinked_count`` is the real total.
    unlinked: list[dict] = []
    unlinked_count = 0
    flag_ids: set[int] = set()
    for img in images:
        sha = getattr(img, "sha256_short", "") or ""
        if sha and len(pages_per_sha[sha]) >= DECORATIVE_MIN_PAGES:
            decorative += 1
            continue
        candidates = by_page.get(int(img.page_number or 0), [])
        image_based = [(p, r) for p, r in candidates if _is_image_based(p)]
        target = None
        if len(image_based) == 1:
            target = image_based[0][1]
        elif not image_based and len(candidates) == 1:
            target = candidates[0][1]
        if target is None:
            flag_ids.update(r.id for _p, r in image_based)
            unlinked_count += 1
            if len(unlinked) < MAX_REPORTED_UNLINKED:
                unlinked.append({
                    "page_number": img.page_number,
                    "image_index_in_page": getattr(img, "image_index_in_page", 0),
                    "sha256_short": sha,
                    "file_path": getattr(img, "file_path", ""),
                    "candidates": len(candidates),
                })
            continue
        if writer.write_image(img, target, recall_source) is not None:
            linked += 1

    if flag_ids:
        (
            Question.objects.filter(id__in=flag_ids)
            .exclude(admin_edited=True).exclude(lock_answer=True)
            .exclude(is_verified_by_admin=True)
            .update(needs_review=True)
        )
    if unlinked_count:
        LOG.warning("%d image(s) left unlinked for review (ambiguous page owner)", unlinked_count)
    return {
        "images_linked": linked,
        "images_decorative_skipped": decorative,
        "images_unlinked": unlinked_count,
        "unlinked_images": unlinked,
        "unlinked_images_truncated": unlinked_count > len(unlinked),
        "questions_flagged_for_image_review": len(flag_ids),
    }


__all__ = ["link_images_by_page"]
