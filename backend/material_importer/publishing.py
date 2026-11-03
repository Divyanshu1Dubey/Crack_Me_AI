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

from questions.answer_leak import label_hold_reasons

log = logging.getLogger(__name__)

VALID_ANSWERS = frozenset({"A", "B", "C", "D"})

# Only raster images are ever copied to the live bank. SVG (and WMF/EMF)
# can carry script and would be served from the API origin as active
# content by the public image proxy.
RASTER_MIME_TYPES = frozenset({"image/png", "image/jpeg", "image/gif", "image/webp"})


def year_from_filename(filename: str) -> int:
    """PYQ year from the source file name; 0 ("Expert Curated") otherwise.

    Never reads the question stem: a stem such as "In 2015, WHO launched…"
    is not the question's own year. A file name naming more than one
    plausible year (e.g. "PYQs 2015-2023") is ambiguous and also gives 0.
    """
    import re
    from datetime import date as _date

    this_year = _date.today().year
    years = {
        int(y) for y in re.findall(r"(?<!\d)(20[0-9]{2})(?!\d)", filename or "")
        if 2010 <= int(y) <= this_year
    }
    return years.pop() if len(years) == 1 else 0


def _read_staged_image_bytes(imp) -> bytes | None:
    """Bytes of a staged ImportedImage, from storage (or a legacy path/URL)."""
    from django.conf import settings
    from django.core.files.storage import default_storage

    name = (imp.stored_path or "").strip()
    if not name:
        return None
    if os.path.isabs(name) and os.path.isfile(name):
        with open(name, "rb") as fh:
            return fh.read()
    # Legacy rows stored the public URL ("/media/imported/...") here.
    media_url = getattr(settings, "MEDIA_URL", "/media/") or "/media/"
    if name.startswith(media_url):
        name = name[len(media_url):]
    name = name.lstrip("/")
    try:
        if default_storage.exists(name):
            with default_storage.open(name, "rb") as fh:
                return fh.read()
    except Exception as exc:  # pragma: no cover - storage backend edge case
        log.warning("Could not read staged image %s: %s", name, exc)
    return None


def _send_back_for_review(eq, note: str) -> None:
    """Park ``eq`` in the review queue (``needs_review``), noting why once."""
    eq.status = "needs_review"
    if note not in (eq.review_note or ""):
        eq.review_note = f"{eq.review_note}\n{note}".strip() if eq.review_note else note
    eq.save(update_fields=["status", "review_note"])


@transaction.atomic
def publish_extracted_question(eq: "ExtractedQuestion") -> bool:  # noqa: F821
    """Create a real `Question` from an `ExtractedQuestion`.

    Returns True if a new Question was created, False if it was already
    published or missing required fields. A row without a valid A–D answer
    is never published (it is sent back to ``needs_review``): the live bank
    must not show a question with no, or a guessed, correct answer. Nor is a
    row whose stem or options carry an answer / explanation label
    ("Correct Answer: B", "Explanation: ..."): the stem and the options are
    public text, so the label would give the answer away to every viewer.
    """
    if eq.published_question_id:
        return False
    # Lock the staging row and re-check: two overlapping publishes (a re-click
    # on a slow batch, admin action + API) must not both create a Question.
    # The no-op UPDATE takes the row lock on PostgreSQL and the database write
    # lock on SQLite, where select_for_update is ignored; a concurrent publish
    # of the same row waits here and then sees the committed link.
    from django.db.models import F
    from .models import ExtractedQuestion as _EQ
    _EQ.objects.filter(pk=eq.pk).update(status=F("status"))
    locked = _EQ.objects.select_for_update().filter(pk=eq.pk).values_list(
        "published_question_id", flat=True,
    ).first()
    if locked:
        eq.published_question_id = locked
        return False
    if eq.status not in ("approved", "pending"):
        return False
    if not (eq.question_text and (eq.option_a or eq.option_b or eq.option_c or eq.option_d)):
        return False
    answer = (eq.correct_answer or "").strip().upper()
    if answer not in VALID_ANSWERS:
        _send_back_for_review(eq, "Not published: no valid correct answer (A-D) was extracted.")
        return False
    hold = label_hold_reasons(eq.question_text, [eq.option_a, eq.option_b, eq.option_c, eq.option_d])
    if hold:
        # Held, not auto-repaired (questions.answer_leak.plan_repair): an
        # admin cleans the text in review, as with the ingestion gate.
        _send_back_for_review(
            eq,
            "Not published: answer / explanation label in the stem or options "
            f"({', '.join(hold)}).",
        )
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

    # The bank Question has a `year` field. It comes from the source file
    # name only (e.g. "UPSC_CMS_PYQ_2019_Paper1.docx"); a year quoted in the
    # stem ("In 2015, WHO launched…", "End TB Strategy 2030") is content, not
    # the question's own year. No single plausible year → 0 ("Expert Curated").
    year = year_from_filename(eq.material.original_filename if eq.material else "")

    q = _Q.objects.create(
        question_text=eq.question_text,
        option_a=eq.option_a or "",
        option_b=eq.option_b or "",
        option_c=eq.option_c or "",
        option_d=eq.option_d or "",
        correct_answer=answer,
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
    # QuestionImage.file is an ImageField — we feed it the bytes read back
    # through the storage backend (``stored_path`` is the storage name) so the
    # live Question is fully self-contained.
    try:
        from questions.models import QuestionImage as _QI
        from .models import ImportedImage as _II
        linked = _II.objects.filter(linked_questions=eq)
        for imp in linked:
            if (imp.mime_type or "").lower() not in RASTER_MIME_TYPES:
                log.warning("Not publishing non-raster image %s (%s) for EQ %s",
                            imp.id, imp.mime_type, eq.id)
                continue
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
            # Re-load the bytes from storage and save them to the ImageField.
            data = _read_staged_image_bytes(imp)
            if data:
                qi.file.save(imp.original_filename or f"img_{imp.id}.png",
                             ContentFile(data), save=False)
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
