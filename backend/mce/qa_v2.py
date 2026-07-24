"""QA V2 — Per-question educational-fidelity scoring.

Replaces the page-level engineering gate (which was mathematically
unreachable for image-based questions — see
``docs/neetpg2021/QA_SYSTEM_REVIEW.md``) with a **per-question
semantic fidelity score** that runs on the *extracted content* of
each Stage-7 ``ParsedQuestion``.

The 9 axes:

  1. Question completeness (stem)
  2. Option completeness (4-5 lettered options)
  3. Answer correctness (1-2 answer labels, mapped to options)
  4. Explanation completeness (>= 40 chars)
  5. Image correctness (image attached if referenced)
  6. Image placement (image bbox inside question bbox)
  7. Table correctness (table attached if referenced)
  8. Clinical pearl presence (optional, no FAIL)
  9. Reference correctness (optional, no FAIL)

Each axis returns True/False.  A question's overall ``status`` is:

  - "Production Ready" when 7+ of 9 axes pass
  - "Needs Review"     when 5-6 of 9 axes pass
  - "Extraction Failure" when < 5 axes pass

The page-level import gate becomes:

  page.importable = all(q.status != "Extraction Failure"
                        for q in page.questions)

i.e. import is BLOCKED only when at least one question is an
extraction failure (the genuine Stage-5/7 bugs).  Questions that are
"Needs Review" are still imported but flagged for admin review.
"""
from __future__ import annotations

import re
from typing import Any


# Axis 1 — stem must be substantive, not page furniture
_RE_FOOTER_PATTERN = re.compile(
    r"medical[\s-]*junction|medco|^\s*page\s+\d+\s+of\s+\d+",
    re.IGNORECASE,
)

# Axis 5 — stem references an image
_RE_IMAGE_REFERENCE = re.compile(
    r"\b(?:radiograph|x[\s-]?ray|image|figure|photograph|shown|identify|ct scan|mri|ecg|eeg|ultrasound|endoscopy|fundus)\b",
    re.IGNORECASE,
)

# Axis 7 — stem references a table
_RE_TABLE_REFERENCE = re.compile(
    r"\b(?:table|chart|values? shown)\b",
    re.IGNORECASE,
)

# Bbox containment tolerance (in points).
_BBOX_TOL = 5.0


def _bbox_contains(outer: list[float], inner: list[float], tol: float = _BBOX_TOL) -> bool:
    """Return True when ``inner`` bbox is geometrically inside ``outer``
    bbox (with ``tol`` px of tolerance on every edge)."""
    if not outer or not inner or len(outer) < 4 or len(inner) < 4:
        return False
    try:
        return (
            float(outer[0]) - tol <= float(inner[0])
            and float(outer[1]) - tol <= float(inner[1])
            and float(outer[2]) + tol >= float(inner[2])
            and float(outer[3]) + tol >= float(inner[3])
        )
    except (TypeError, ValueError):
        return False


def axis_1_stem_complete(q: dict[str, Any]) -> bool:
    """Axis 1: stem is substantive (>= 30 chars) AND is not page
    furniture (footer, header, or stray "Answer"/"Explanation" line)."""
    stem = (q.get("stem") or "").strip()
    if len(stem) < 30:
        return False
    if _RE_FOOTER_PATTERN.search(stem):
        return False
    if stem.lower().startswith(("answer", "explanation", "exp:", "explain:")):
        return False
    return True


def axis_2_options_complete(q: dict[str, Any]) -> bool:
    """Axis 2: 2-6 options, each with non-empty text, each labelled
    with a single uppercase letter A-F."""
    options = q.get("options") or []
    if not (2 <= len(options) <= 6):
        return False
    for o in options:
        # Use explicit single-char check — ``"" in "ABCDEF"`` returns
        # True because Python's ``in`` treats empty string as a
        # substring of every string.  We need a real non-empty match.
        raw_lbl = o.get("label")
        if not raw_lbl:
            return False
        lbl = raw_lbl.upper()
        if len(lbl) != 1 or lbl not in "ABCDEF":
            return False
        if not (o.get("text") or "").strip():
            return False
    return True


def axis_3_answer_correct(q: dict[str, Any]) -> bool:
    """Axis 3: 1-2 answer labels A-F AND every answer label is
    mapped to an option marked is_correct=True."""
    answer_labels = q.get("answer_labels") or []
    if not (1 <= len(answer_labels) <= 2):
        return False
    if not all((a or "").upper() in "ABCDEF" for a in answer_labels):
        return False
    options = q.get("options") or []
    correct = {o.get("label") for o in options if o.get("is_correct")}
    answer_set = {(a or "").upper() for a in answer_labels}
    return answer_set == (answer_set & correct)


def axis_4_explanation_complete(q: dict[str, Any]) -> bool:
    """Axis 4: explanation >= 40 chars (a real sentence, not a label)."""
    expl = (q.get("explanation") or "").strip()
    return len(expl) >= 40


def axis_5_image_attached_if_referenced(q: dict[str, Any]) -> bool:
    """Axis 5: when stem references an image, the question has
    >= 1 image_id attached."""
    stem = (q.get("stem") or "").strip()
    if not _RE_IMAGE_REFERENCE.search(stem):
        # Stem doesn't reference an image — anything goes.
        return True
    return len(q.get("image_ids") or []) >= 1


def axis_6_image_placement(q: dict[str, Any]) -> bool:
    """Axis 6: at least one attached image's bbox is geometrically
    inside the question's bbox (with tolerance)."""
    qbbox = q.get("bbox") or []
    if not qbbox:
        # No question bbox → can't verify placement; treat as N/A pass.
        return True
    images = q.get("image_bboxes") or []
    if not images:
        # No attached images → only fail when stem references an image.
        return not _RE_IMAGE_REFERENCE.search(q.get("stem") or "")
    return any(_bbox_contains(qbbox, ib) for ib in images)


def axis_7_table_attached_if_referenced(q: dict[str, Any]) -> bool:
    """Axis 7: when stem references a table, asset_ids is non-empty."""
    stem = (q.get("stem") or "").strip()
    if not _RE_TABLE_REFERENCE.search(stem):
        return True
    return len(q.get("asset_ids") or []) >= 1


def axis_8_clinical_pearl(q: dict[str, Any]) -> bool:
    """Axis 8: clinical_pearl is non-empty (LENIENT — many real
    questions have no pearl; this axis is graded but does not
    contribute to FAIL/PASS count)."""
    return bool((q.get("clinical_pearl") or "").strip())


def axis_9_reference_field_present(q: dict[str, Any]) -> bool:
    """Axis 9: ``references`` field exists and is a list (LENIENT —
    empty list is OK)."""
    refs = q.get("references")
    return isinstance(refs, list)


# Required axes (count toward the PASS threshold)
_REQUIRED_AXES = (
    axis_1_stem_complete,
    axis_2_options_complete,
    axis_3_answer_correct,
    axis_4_explanation_complete,
    axis_5_image_attached_if_referenced,
    axis_6_image_placement,
    axis_7_table_attached_if_referenced,
)

# Optional axes (count when present, but never block)
_OPTIONAL_AXES = (
    axis_8_clinical_pearl,
    axis_9_reference_field_present,
)


def score_question(q: dict[str, Any]) -> dict[str, Any]:
    """Compute the per-axis score for one question.

    Returns a dict with one entry per axis (True/False), the total
    passing count (required + optional), and a ``status`` of
    "Production Ready" / "Needs Review" / "Extraction Failure".

    Status thresholds (over all 9 axes):

      Production Ready       >= 7 axes pass
      Needs Review           5-6 axes pass
      Extraction Failure     <= 4 axes pass
    """
    axes = {
        "stem_complete": axis_1_stem_complete(q),
        "options_complete": axis_2_options_complete(q),
        "answer_correct": axis_3_answer_correct(q),
        "explanation_complete": axis_4_explanation_complete(q),
        "image_attached_if_referenced": axis_5_image_attached_if_referenced(q),
        "image_placement": axis_6_image_placement(q),
        "table_attached_if_referenced": axis_7_table_attached_if_referenced(q),
        "clinical_pearl_present": axis_8_clinical_pearl(q),
        "reference_field_present": axis_9_reference_field_present(q),
    }
    passing = sum(1 for v in axes.values() if v)
    if passing >= 7:
        status = "Production Ready"
    elif passing >= 5:
        status = "Needs Review"
    else:
        status = "Extraction Failure"
    failing_axes = [name for name, ok in axes.items() if not ok]
    return {
        "axes": axes,
        "passing_count": passing,
        "total_axes": len(axes),
        "status": status,
        "failing_axes": failing_axes,
    }


def is_page_importable(question_scores: list[dict[str, Any]]) -> bool:
    """Return True when every question on the page is not an
    ``Extraction Failure``.  This is the V2 page-level import gate."""
    return all(s["status"] != "Extraction Failure" for s in question_scores)


__all__ = [
    "score_question",
    "is_page_importable",
    "axis_1_stem_complete",
    "axis_2_options_complete",
    "axis_3_answer_correct",
    "axis_4_explanation_complete",
    "axis_5_image_attached_if_referenced",
    "axis_6_image_placement",
    "axis_7_table_attached_if_referenced",
    "axis_8_clinical_pearl",
    "axis_9_reference_field_present",
]