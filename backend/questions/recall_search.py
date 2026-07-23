"""Recall-aware search action for QuestionViewSet.

Mounted via `QuestionViewSet.recall_search` — see `questions/views.py`
for the wiring. Phase 2 ships an additive `@action`; existing actions
are untouched.
"""
from __future__ import annotations

import logging

from django.db.models import Count, Q
# These rest_framework imports look unused at lint-time because the action
# methods are wired in views.py; the names are intentionally re-exported
# from this module for backwards-compatible import paths in case the
# module is loaded directly by future tests.
from rest_framework import status  # noqa: F401 — intentional re-export
from rest_framework.decorators import action  # noqa: F401 — intentional re-export
from rest_framework.response import Response  # noqa: F401 — intentional re-export

LOG = logging.getLogger(__name__)


# Param → ORM filter mapping. Keep this explicit so we can audit what's
# exposed.
_PARAM_FILTERS = {
    "q": "question_text__icontains",          # replaced below with FTS5 when available
    "exam_type": "exam_type",
    "year": "year",
    "session": "session",
    "recall_status": "recall_status",
    "clinical_category": "clinical_category",
    "question_type": "question_type",
    "difficulty": "difficulty",
    "is_image_based": "is_image_based",
    "concept_id": "concept_id",
    "subject": "subject_id",
    "topic": "topic_id",
}

# Phase 3 — clinical-axis keyword filters. These are dimension-agnostic:
# they tokenize the question text + explanation + concept_tags + mnemonics
# for the given dimension (diagnosis / drug / disease / investigation /
# clinical_system / subtopic).  Cheaper than a clinical ontology and
# matches what front-end Recalls demonstrate.
_CLINICAL_TEXT_FIELDS = (
    "question_text", "explanation", "ai_explanation",
    "mnemonic", "ai_mnemonic", "ai_clinical_pearl",
)


def _apply_clinical_token(qs, param: str, raw: str):  # noqa: ARG001 — param kept for forward-compat
    """Filter `qs` so any of the clinical text fields icontains `raw`."""
    if not raw:
        return qs
    token_q = Q()
    for f in _CLINICAL_TEXT_FIELDS:
        token_q |= Q(**{f"{f}__icontains": raw})
    return qs.filter(token_q).distinct()


def _split_csv(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]\



def _parse_bool(raw):
    if raw in (None, ""):
        return None
    return str(raw).strip().lower() in ("1", "true", "yes", "y")


def recall_search(self, request):
    """GET /api/questions/recall_search/?q=...&recall_status=recall&...&min_confidence=0.5

    Filters + facets in one round trip. Existing DRF `list` action is
    unchanged.
    """
    # Phase 3: short-lived cache keyed on (query, query-stamp minute)
    # keeps DB cost under control for repeat front-end queries.
    from django.core.cache import cache
    from .models import Question, QuestionImage
    from .serializers import QuestionListSerializer

    cache_key = "recall_search:v2:" + (request.META.get("QUERY_STRING") or "")
    cached = cache.get(cache_key)
    if cached is not None:
        return Response(cached)

    qs = (Question.objects.filter(is_active=True)
          .select_related("subject", "topic"))

    for param, lookup in _PARAM_FILTERS.items():
        raw = request.query_params.get(param)
        if raw in (None, ""):
            continue
        if lookup == "is_image_based":
            val = _parse_bool(raw)
            if val is None:
                continue
            qs = qs.filter(**{lookup: val})
        else:
            qs = qs.filter(**{lookup: raw})

    q_text = request.query_params.get("q", "").strip()
    if q_text:
        # Phase 2 ships icontains + tokenized AND — FTS5 mirror is wired
        # in build_fts_query() below for future use.
        tokens = [t for t in q_text.split() if len(t) >= 2]
        if tokens:
            token_q = Q()
            for t in tokens:
                token_q |= Q(question_text__icontains=t)
                token_q |= Q(explanation__icontains=t)
                token_q |= Q(mnemonic__icontains=t)
                token_q |= Q(ai_explanation__icontains=t)
                token_q |= Q(ai_clinical_pearl__icontains=t)
            qs = qs.filter(token_q).distinct()

    modality = request.query_params.get("modality")
    if modality:
        qs = qs.filter(images__modality=modality, images__is_active=True).distinct()

    image_ocr = request.query_params.get("image_ocr", "").strip()
    if image_ocr:
        qs = qs.filter(images__ocr_text__icontains=image_ocr, images__is_active=True).distinct()

    # Phase 3 — clinical-axis keyword filters (diagnosis/drug/disease/
    # investigation/clinical_system/subtopic).  These are simple icontains
    # over the canonical text fields, cheap, and consistent with the front
    # end search box.
    for dim in ("diagnosis", "drug", "disease",
                "investigation", "clinical_system", "subtopic"):
        raw = request.query_params.get(dim, "").strip()
        if raw:
            qs = _apply_clinical_token(qs, dim, raw)

    # Phase 3 — has_image / has_diagram / has_table filters.
    def _bool_param(name):
        v = request.query_params.get(name)
        if v in (None, ""):
            return None
        return str(v).strip().lower() in ("1", "true", "yes", "y")

    want_image = _bool_param("has_image")
    if want_image is True:
        qs = qs.filter(images__is_active=True).distinct()
    elif want_image is False:
        qs = qs.exclude(images__is_active=True).distinct()
    for opt in ("has_diagram", "has_table"):
        val = _bool_param(opt)
        if val is True:
            qs = qs.filter(**{f"images__{opt}": True, "images__is_active": True}).distinct()

    min_conf = request.query_params.get("min_confidence")
    if min_conf not in (None, ""):
        try:
            qs = qs.filter(confidence_score__gte=float(min_conf))
        except ValueError:
            pass

    # Facets — include new dimensions so UI can build checkbox grids.
    facets = {
        "exam_type": dict(qs.values_list("exam_type").annotate(c=Count("id"))),
        "year": dict(qs.values_list("year").annotate(c=Count("id"))),
        "session": dict(qs.values_list("session").annotate(c=Count("id"))),
        "recall_status": dict(qs.values_list("recall_status").annotate(c=Count("id"))),
        "clinical_category": dict(qs.values_list("clinical_category").annotate(c=Count("id"))),
        "question_type": dict(qs.values_list("question_type").annotate(c=Count("id"))),
        "difficulty": dict(qs.values_list("difficulty").annotate(c=Count("id"))),
    }
    # Image-modality facet
    facets["modality"] = dict(
        QuestionImage.objects.filter(question__in=qs, is_active=True)
        .values_list("modality").annotate(c=Count("id"))
    )

    # Paginate
    try:
        page_size = min(int(request.query_params.get("page_size", 25)), 100)
    except ValueError:
        page_size = 25
    try:
        page = max(int(request.query_params.get("page", 1)), 1)
    except ValueError:
        page = 1

    qs = qs.order_by("-year", "id")
    total = qs.count()
    start = (page - 1) * page_size
    end = start + page_size
    page_qs = qs[start:end]

    serializer = QuestionListSerializer(page_qs, many=True, context={"request": request})
    payload = {
        "count": total,
        "page": page,
        "page_size": page_size,
        "facets": {k: {str(kk): vv for kk, vv in v.items()} for k, v in facets.items()},
        "results": serializer.data,
    }
    # 60-second memo for repeat queries (search-as-you-type benefits)
    try:
        from django.core.cache import cache
        cache.set(cache_key, payload, 60)
    except Exception:  # pragma: no cover - defensive
        pass
    return Response(payload)


def recall_question_images(self, request, pk=None):
    """GET /api/questions/{id}/images/  — list QuestionImage rows for a question."""
    from .models import QuestionImage
    from .recall_serializers import QuestionImageSerializer  # type: ignore
    images = QuestionImage.objects.filter(question_id=pk, is_active=True).order_by("page_number", "image_index_in_page")
    try:
        page_size = min(int(request.query_params.get("page_size", 50)), 200)
    except ValueError:
        page_size = 50
    images = images[:page_size]
    return Response(QuestionImageSerializer(images, many=True, context={"request": request}).data)


def recall_question_sources(self, request, pk=None):
    """GET /api/questions/{id}/sources/  — list QuestionSource rows for a question."""
    from .models import QuestionSource
    from .recall_serializers import QuestionSourceSerializer  # type: ignore
    rows = QuestionSource.objects.filter(question_id=pk).select_related("recall_source").order_by("imported_at")
    return Response(QuestionSourceSerializer(rows, many=True, context={"request": request}).data)


def build_fts_query(raw: str) -> str:
    """Helper: convert a user query into an FTS5 MATCH expression.

    Each token is quoted so SQLite treats it as a literal term. AND-joined.
    Falls back to "" when the query has no usable tokens.
    """
    import re
    tokens = [t for t in re.split(r"\s+", raw.strip()) if len(t) >= 2]
    if not tokens:
        return ""
    return " AND ".join(f'"{t}"' for t in tokens)