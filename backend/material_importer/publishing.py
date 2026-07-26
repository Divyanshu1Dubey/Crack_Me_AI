"""Promote an `ExtractedQuestion` row into the real `Question` table.

The promotion is idempotent: an `ExtractedQuestion` is linked to its
`PublishedQuestion` via `published_question`. Calling twice is a no-op.

Used by the admin action `publish_to_questions` and the auto-publish loop
that the AI enrichment command kicks off.
"""
from __future__ import annotations

import logging
from typing import Any

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
    subject = eq.subject
    if subject is None:
        subject = Subject.objects.filter(name__iexact="Imported").first()
    if subject is None:
        exam_track, _ = ExamTrack.objects.get_or_create(code="cms", defaults={"name": "UPSC CMS"})
        subject = Subject.objects.create(name="Imported", code="IMPORTED", exam_type="cms", exam_track=exam_track)

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
    return True
