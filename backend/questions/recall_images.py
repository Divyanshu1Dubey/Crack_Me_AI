"""Image-system helpers for the Phase-3 recall bank.

Built additive on top of Phase-2 `QuestionImage`. Provides:

* bulk image metadata endpoint (`GET /api/questions/images/?question_id=`),
* modality facet endpoint (`GET /api/questions/images/facets/`),
* low-res placeholder support (`QuestionImage.thumbnail_url`),

Existing endpoints (`/api/questions/{id}/images/`,
`/api/questions/{id}/sources/`, `/api/questions/recall_sources/`)
are NOT changed.  Action methods are registered from
`questions/views.py::QuestionViewSet` so URLs stay under
`/api/questions/...` (consistent with current routing).
"""
from __future__ import annotations

import logging

from django.db.models import Count, Q

LOG = logging.getLogger(__name__)


def list_images_for_question(self, request, pk=None):
    """Return `QuestionImage` rows for one question, ordered for viewer.

    Already implemented via `recall_question_images` in `recall_search.py`
    — this module mirrors that contract so `from .recall_images import
    list_images_for_question` is a stable name.
    """
    from questions.recall_search import recall_question_images
    return recall_question_images(self, request, pk=pk)


def list_images_faceted(self, request):
    """`GET /api/questions/images/facets/?modality=radiology&...`

    Returns image-level facet counts (modality, body_region,
    has_diagram, has_table, is_watermarked).  Cheap aggregation query.
    """
    from .models import QuestionImage

    qs = QuestionImage.objects.filter(is_active=True)
    # Optional question-level filters
    for opt in ("modality", "body_region", "has_diagram",
                "has_table", "is_watermarked"):
        raw = request.query_params.get(opt)
        if raw in (None, ""):
            continue
        if opt in ("has_diagram", "has_table", "is_watermarked"):
            val = str(raw).strip().lower() in ("1", "true", "yes")
            qs = qs.filter(**{opt: val})
        else:
            qs = qs.filter(**{opt: raw})

    return [{
        "modality": dict(qs.values_list("modality").annotate(c=Count("id"))),
        "body_region": dict(qs.values_list("body_region").annotate(c=Count("id"))),
        "has_diagram": dict(qs.values_list("has_diagram").annotate(c=Count("id"))),
        "has_table": dict(qs.values_list("has_table").annotate(c=Count("id"))),
        "is_watermarked": dict(qs.values_list("is_watermarked").annotate(c=Count("id"))),
        "caption_source": dict(qs.values_list("caption_source").annotate(c=Count("id"))),
    }]


def q_for_images_q(qs, *, has_image: bool | None = None,
                   modality: str | None = None,
                   body_region: str | None = None,
                   has_diagram: bool | None = None,
                   has_table: bool | None = None) -> "QuerySet":
    """Composes image filters onto a Question queryset for the search action."""
    if has_image is True:
        qs = qs.filter(images__is_active=True).distinct()
    if modality:
        qs = qs.filter(images__modality=modality, images__is_active=True).distinct()
    if body_region:
        qs = qs.filter(images__body_region=body_region, images__is_active=True).distinct()
    if has_diagram is True:
        qs = qs.filter(images__has_diagram=True, images__is_active=True).distinct()
    if has_table is True:
        qs = qs.filter(images__has_table=True, images__is_active=True).distinct()
    return qs


def parse_image_bool(raw):
    if raw in (None, ""):
        return None
    s = str(raw).strip().lower()
    if s in ("1", "true", "yes", "y", "on"):
        return True
    if s in ("0", "false", "no", "n", "off"):
        return False
    return None
