"""Promote an `ExtractedQuestion` row into the real `Question` table.

The promotion is idempotent: an `ExtractedQuestion` is linked to its
`PublishedQuestion` via `published_question`. Calling twice is a no-op.

Used by the admin action `publish_to_questions` and the auto-publish loop
that the AI enrichment command kicks off.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from django.core.files.base import ContentFile
from django.db import transaction

log = logging.getLogger(__name__)


@transaction.atomic
def publish_extracted_question(eq: "ExtractedQuestion") -> bool:  # noqa: F821
    """Create a real `Question` from an `ExtractedQuestion`.

    Returns True if a new Question was created, False if it was already
    published or missing required fields.
    """
    if eq.published_question_id:
        return False
    if eq.status not in ("approved", "pending"):
        return False
    if not (eq.question_text and (eq.option_a or eq.option_b or eq.option_c or eq.option_d)):
        return False
    from questions.models import Question, Subject, ExamTrack

    # Resolve a subject — fall back to a generic "Imported" subject if none.
    # Use the question's exam_type (or default to cms) so multiple exam tracks
    # do not collide on the unique `name = "Imported"` constraint. Combined
    # with the merge_loader_fallback_subjects migration, the public
    # Question Bank filter shows a single "Expert Curated" row per exam.
    subject = eq.subject
    if subject is None:
        target_exam_type = getattr(eq, "exam_type", None) or "cms"
        subject = Subject.objects.filter(name__iexact="Imported", exam_type=target_exam_type).first()
    if subject is None:
        target_exam_type = getattr(eq, "exam_type", None) or "cms"
        exam_code_map = {"cms": "cms", "neet_pg": "neet_pg", "ini_cet": "ini_cet"}
        exam_track_code = exam_code_map.get(target_exam_type, "cms")
        exam_track, _ = ExamTrack.objects.get_or_create(
            code=exam_track_code,
            defaults={"name": target_exam_type.upper().replace("_", " ")},
        )
        subject, _ = Subject.objects.get_or_create(
            name="Imported",
            exam_type=target_exam_type,
            defaults={"code": "IMPORTED", "exam_track": exam_track},
        )

    from questions.models import Question as _Q
    paper = 0
    if eq.material and "PYQ" in (eq.material.original_filename or "").upper():
        paper = 0  # unknown

    # The bank Question has a `year` field; pull it from the question text
    # (PYQ year) or fall back to 0 ("Expert Curated"). UPSC CMS PYQs run
    # 2010-2025. Years 2026+ (e.g. "End TB Strategy 2030") are SDG targets
    # inside the question text, not the question's own year — fall through.
    import re
    from datetime import date as _date
    haystack = (eq.question_text or "") + " " + (eq.material.original_filename if eq.material else "")
    year = 0  # default = Expert Curated (no real PYQ year found)
    for y in re.findall(r"\b(19[89]\d|20[0-2]\d)\b", haystack):
        yi = int(y)
        if 2010 <= yi <= _date.today().year:
            year = yi  # earliest plausible PYQ year wins
            break

    q = _Q.objects.create(
        question_text=eq.question_text,
        option_a=eq.option_a or "",
        option_b=eq.option_b or "",
        option_c=eq.option_c or "",
        option_d=eq.option_d or "",
        correct_answer=eq.correct_answer or "",
        explanation=eq.explanation or "",
        year=year,
        subject=subject,
        topic=eq.topic,
        difficulty=eq.inferred_difficulty or "medium",
        exam_type=subject.exam_type or "cms",
        exam_track=subject.exam_track,
        concept_keywords=[],
    )
    eq.published_question = q
    eq.status = "published"
    eq.save(update_fields=["published_question", "status"])

    # P1 — propagate per-question images from staging to the live Question.
    # ImportedImage.linked_questions is the M2M that already wired staging rows
    # during ingest; iterate it and create QuestionImage rows on the new Q.
    # QuestionImage.file is an ImageField — we feed it the bytes read back from
    # the stored_path on disk so the live Question is fully self-contained.
    try:
        from questions.models import QuestionImage as _QI
        from .models import ImportedImage as _II
        linked = _II.objects.filter(linked_questions=eq)
        for imp in linked:
            qi = _QI(
                question=q,
                page_number=1,  # DOCX images don't carry page numbers — default 1
                image_index_in_page=0,
                url=imp.public_url or "",
                caption=imp.original_filename or "",
                mime=imp.mime_type or "image/png",
                width=imp.width or 0,
                height=imp.height or 0,
                bytes=imp.size_bytes or 0,
                sha256=imp.sha256 or "",
                sha256_short=(imp.sha256 or "")[:16],
                role="illustration",
            )
            # Re-load bytes from stored_path and save to the ImageField. The
            # stored_path is an absolute file path under MEDIA_ROOT.
            if imp.stored_path and os.path.isfile(imp.stored_path):
                with open(imp.stored_path, "rb") as fh:
                    qi.file.save(imp.original_filename or f"img_{imp.id}.png",
                                 ContentFile(fh.read()), save=False)
            qi.save()
    except Exception as exc:  # pragma: no cover
        log.warning("Image propagation failed for EQ %s -> Q %s: %s", eq.id, q.id, exc)
    return True


def _nullify_published_links(extracted_question_ids) -> int:
    """P12 helper — unlink ExtractedQuestion rows from their published Question rows.

    Used by ``delete_batch(delete_published=True)`` so the published Question
    rows can be deleted without violating FK constraints.

    Returns the number of rows updated.
    """
    from .models import ExtractedQuestion
    return ExtractedQuestion.objects.filter(id__in=extracted_question_ids).update(published_question=None)
