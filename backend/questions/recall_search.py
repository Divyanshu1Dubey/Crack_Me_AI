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

# Phase 3 — clinical-axis keyword filters. These are dimension-agnostic
# keyword matches for the given dimension (diagnosis / drug / disease /
# investigation / clinical_system / subtopic).  Cheaper than a clinical
# ontology and matches what front-end Recalls demonstrate.
#
# Entitlement (questions.views.user_can_view_answer): the stem and the
# options are public -- every list row shows them -- so a keyword matches
# them on any question. The explanation, the mnemonics and the AI study text
# name the correct option, so they are matched only on questions whose
# answer the caller may read: matching them on a locked question was an
# answer oracle (an anonymous ``?drug=<option>`` returned the question for
# its correct option only).
_PUBLIC_TEXT_FIELDS = ("question_text", "option_a", "option_b", "option_c", "option_d")
_CLINICAL_ANSWER_FIELDS = (
    "explanation", "ai_explanation", "mnemonic", "ai_mnemonic", "ai_clinical_pearl",
)
# Free-text ``q`` tokens: the stem, plus the same kind of answer-linked text.
_Q_PUBLIC_FIELDS = ("question_text",)
_Q_ANSWER_FIELDS = ("explanation", "mnemonic", "ai_explanation", "ai_clinical_pearl")
# A ``[[img:N]]`` reference from these fields (and not from the stem or an
# option) makes an image an explanation figure; a reference from the stem or
# an option makes it a stem-side figure whatever its stored role
# (questions.image_context.runtime_role).
_IMAGE_EXPLANATION_REF_FIELDS = ("explanation", "concept_explanation", "mnemonic")
_IMAGE_STEM_SIDE_REF_FIELDS = ("question_text", "option_a", "option_b", "option_c", "option_d")


def _text_match(raw: str, public_fields, answer_fields, answer_scope):
    """Q: ``raw`` (icontains) in a public field of any question, or in an
    answer-linked field of a question inside ``answer_scope``.

    ``answer_scope`` is a Q selecting the questions whose answer the caller
    may read, or None when the caller may read every answer.
    """
    public = Q()
    for f in public_fields:
        public |= Q(**{f"{f}__icontains": raw})
    answer = Q()
    for f in answer_fields:
        answer |= Q(**{f"{f}__icontains": raw})
    if answer_scope is not None:
        answer &= answer_scope
    return public | answer


def _apply_clinical_token(qs, param: str, raw: str, *, answer_scope):  # noqa: ARG001 — param kept for forward-compat
    """Filter `qs` to the questions matching the clinical keyword `raw`
    (see ``_text_match`` for ``answer_scope``)."""
    if not raw:
        return qs
    return qs.filter(
        _text_match(raw, _PUBLIC_TEXT_FIELDS, _CLINICAL_ANSWER_FIELDS, answer_scope)
    ).distinct()


def _visible_images(answer_question_ids):
    """Active QuestionImage rows whose metadata (OCR text, modality, flags)
    the caller may search on.

    ``answer_question_ids``: the ids of the questions whose answer the
    caller may read (a values() queryset), or None for every question.
    Otherwise an explanation figure -- referenced by ``[[img:N]]`` from the
    explanation text but not from the stem or an option, or stored as
    'explanation' and not referenced from the stem or an option -- counts
    only on those questions: it belongs to the explanation, which the list
    rows hide on a locked question, and its OCR text can name the answer.
    """
    from django.db.models import CharField, Value
    from django.db.models.functions import Cast, Concat
    from .models import QuestionImage

    images = QuestionImage.objects.filter(is_active=True)
    if answer_question_ids is None:
        return images
    token = Concat(
        Value("[[img:"), Cast("id", output_field=CharField()), Value("]]"),
        output_field=CharField(),
    )
    in_explanation = Q()
    for f in _IMAGE_EXPLANATION_REF_FIELDS:
        in_explanation |= Q(**{f"question__{f}__contains": token})
    in_stem_side = Q()
    for f in _IMAGE_STEM_SIDE_REF_FIELDS:
        in_stem_side |= Q(**{f"question__{f}__contains": token})
    stem_figure = in_stem_side | (~Q(role="explanation") & ~in_explanation)
    return images.filter(stem_figure | Q(question_id__in=answer_question_ids))


def _split_csv(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]\



def _parse_bool(raw):
    if raw in (None, ""):
        return None
    return str(raw).strip().lower() in ("1", "true", "yes", "y")


# Integer-valued filters: a malformed value used to reach the ORM and raise
# ValueError (HTTP 500).
_INT_PARAMS = ("year", "subject", "topic")

# Free-text bounds. Each ``q`` token adds an OR of five ILIKEs per row and
# the same WHERE runs about ten times per request (facets, count, page); the
# token list was unbounded (~1,300 tokens fit in one request line). Only the
# first MAX_Q_TOKENS distinct tokens are used, each cut to
# MAX_Q_TOKEN_CHARS; the keyword filters are cut to MAX_KEYWORD_CHARS.
MAX_Q_TOKENS = 8
MAX_Q_TOKEN_CHARS = 40
MAX_KEYWORD_CHARS = 100
_CLINICAL_PARAMS = ("diagnosis", "drug", "disease", "investigation", "clinical_system", "subtopic")
# Every query param recall_search reads: the cache key is built from these
# (normalised), so an extra throwaway param no longer bypasses the cache.
_CACHE_KEY_PARAMS = tuple(sorted(
    set(_PARAM_FILTERS) | set(_CLINICAL_PARAMS) | {
        "page", "page_size", "min_confidence", "modality", "image_ocr",
        "has_image", "has_diagram", "has_table",
    }
))


def _q_tokens(q_text: str) -> list[str]:
    """The ``q`` tokens searched: whitespace-split, at least 2 characters,
    de-duplicated case-insensitively, the first MAX_Q_TOKENS of them, each
    cut to MAX_Q_TOKEN_CHARS."""
    tokens: list[str] = []
    seen: set[str] = set()
    for token in (q_text or "").split():
        if len(token) < 2:
            continue
        token = token[:MAX_Q_TOKEN_CHARS]
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        tokens.append(token)
        if len(tokens) >= MAX_Q_TOKENS:
            break
    return tokens


def _keyword_param(request, name: str) -> str:
    return (request.query_params.get(name) or "").strip()[:MAX_KEYWORD_CHARS]


def _cache_key_params(request) -> str:
    """Digest of the normalised query string the response depends on (a
    fixed-length key: a raw ``q`` made keys of several KB)."""
    import hashlib
    from urllib.parse import urlencode

    pairs = []
    for name in _CACHE_KEY_PARAMS:
        value = request.query_params.get(name)
        if value not in (None, ""):
            pairs.append((name, value))
    return hashlib.sha256(urlencode(pairs).encode()).hexdigest()


def _bad_request(message: str):
    return Response({"error": message}, status=status.HTTP_400_BAD_REQUEST)


def _int_param(request, name: str, default: int, *, minimum: int, maximum: int):
    """Parse a bounded integer query param. Returns (value, error_response)."""
    raw = request.query_params.get(name)
    if raw in (None, ""):
        return default, None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None, _bad_request(f"{name} must be an integer")
    return max(minimum, min(value, maximum)), None


def recall_search(self, request):
    """GET /api/questions/recall_search/?q=...&recall_status=recall&...&min_confidence=0.5

    Filters + facets in one round trip. Existing DRF `list` action is
    unchanged.
    """
    # Phase 3: short-lived cache keyed on (query, query-stamp minute)
    # keeps DB cost under control for repeat front-end queries.
    # SECURITY (Fix #6): the cache key MUST include a per-user bucket so
    # a free user's restricted query (10 showcase items) cannot be served
    # to a premium user (or vice-versa) and so that freemium-restricted
    # result sets cannot leak via cache poisoning. We bucket by either
    # the authenticated user id or "anon" — never by raw QUERY_STRING
    # alone, which is shared across users.
    from django.core.cache import cache
    from .models import Question
    from .serializers import QuestionListSerializer

    # SECURITY (Fix #6): apply the freemium gate that views.py already
    # applies to `list` / `retrieve`. Without this, a free user could
    # `GET /api/questions/recall_search/?q=…` and bypass the showcase
    # filter — `recall_search` is wired as an AllowAny @action so it
    # was previously exempt from the gate. Now: premium + admin get the
    # full set; free users get only the admin-curated 10 showcase rows.
    request_user = getattr(request, "user", None)
    is_authed = bool(request_user and getattr(request_user, "is_authenticated", False))
    is_admin = bool(
        is_authed
        and (
            getattr(request_user, "is_superuser", False)
            or getattr(request_user, "is_staff", False)
            or getattr(request_user, "role", "") == "admin"
        )
    )
    # is_premium() lives in accounts.utils; import lazily to avoid a
    # circular import at module load time.
    is_premium = False
    if is_authed and not is_admin:
        try:
            from accounts.utils import is_premium as _is_premium
            is_premium = _is_premium(request_user)
        except Exception:
            is_premium = False

    # Validate before touching the cache or the ORM -- malformed ints and an
    # out-of-range page_size used to raise inside the query (HTTP 500).
    for name in _INT_PARAMS:
        raw = request.query_params.get(name)
        if raw not in (None, ""):
            try:
                int(raw)
            except (TypeError, ValueError):
                return _bad_request(f"{name} must be an integer")
    page_size, err = _int_param(request, "page_size", 25, minimum=1, maximum=100)
    if err is not None:
        return err
    page, err = _int_param(request, "page", 1, minimum=1, maximum=100000)
    if err is not None:
        return err
    min_conf_raw = request.query_params.get("min_confidence")
    min_conf = None
    if min_conf_raw not in (None, ""):
        try:
            min_conf = float(min_conf_raw)
        except (TypeError, ValueError):
            return _bad_request("min_confidence must be a number")
        import math
        if not math.isfinite(min_conf):
            return _bad_request("min_confidence must be a finite number")

    cache_bucket = (
        f"u{request_user.id}" if is_authed else "anon"
    )
    # v5: keyed on the params the response depends on (normalised), not on
    # the raw QUERY_STRING -- a throwaway param made every request a miss --
    # and answer / explanation labels in locked rows' text are cut
    # (questions.answer_leak). v6: text filters no longer match inside the
    # cut-away part (questions.locked_text_search).
    cache_key = f"recall_search:v6:{cache_bucket}:" + _cache_key_params(request)
    cached = cache.get(cache_key)
    if cached is not None:
        return Response(cached)

    from .views import free_showcase_rows  # lazy: views imports this module

    # Answer-linked text and explanation figures are searched only on the
    # questions whose answer the caller may read: every question for
    # premium / admin, the free showcase for everyone else -- anonymous
    # visitors included, who see the whole bank (stem and options only).
    entitled = is_admin or is_premium
    answer_ids = None if entitled else free_showcase_rows().values("question_id")
    answer_scope = None if entitled else Q(pk__in=answer_ids)
    visible_images = _visible_images(answer_ids)

    qs = (Question.objects.filter(is_active=True)
          .select_related("subject", "topic"))

    # Freemium gate (Fix #6). Mirrors the showcase filter in views.py:
    # only questions whose PK appears in FreeShowcaseQuestion for the
    # requested year (or any year, if year is omitted) are visible to a
    # free authenticated user.
    if is_authed and not is_admin and not is_premium:
        from django.db.models import Exists, OuterRef
        showcase_qs = free_showcase_rows().filter(question_id=OuterRef("pk"))
        year_param = request.query_params.get("year")
        if year_param not in (None, ""):
            try:
                showcase_qs = showcase_qs.filter(year=int(year_param))
            except (TypeError, ValueError):
                pass
        qs = qs.filter(Exists(showcase_qs))

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
        # in build_fts_query() below for future use. Bounded token list
        # (see MAX_Q_TOKENS).
        tokens = _q_tokens(q_text)
        if tokens:
            token_q = Q()
            for t in tokens:
                token_q |= _text_match(t, _Q_PUBLIC_FIELDS, _Q_ANSWER_FIELDS, answer_scope)
            qs = qs.filter(token_q).distinct()

    # Image filters look at the images the caller may see (see
    # ``_visible_images``).
    modality = request.query_params.get("modality")
    if modality:
        qs = qs.filter(pk__in=visible_images.filter(modality=modality).values("question_id"))

    image_ocr = _keyword_param(request, "image_ocr")
    if image_ocr:
        qs = qs.filter(
            pk__in=visible_images.filter(ocr_text__icontains=image_ocr).values("question_id")
        )

    # Phase 3 — clinical-axis keyword filters (diagnosis/drug/disease/
    # investigation/clinical_system/subtopic).  These are simple icontains
    # over the canonical text fields, cheap, and consistent with the front
    # end search box.
    for dim in _CLINICAL_PARAMS:
        raw = _keyword_param(request, dim)
        if raw:
            qs = _apply_clinical_token(qs, dim, raw, answer_scope=answer_scope)

    # Phase 3 — has_image / has_diagram / has_table filters.
    def _bool_param(name):
        v = request.query_params.get(name)
        if v in (None, ""):
            return None
        return str(v).strip().lower() in ("1", "true", "yes", "y")

    want_image = _bool_param("has_image")
    if want_image is True:
        qs = qs.filter(pk__in=visible_images.values("question_id"))
    elif want_image is False:
        qs = qs.exclude(pk__in=visible_images.values("question_id"))
    for opt in ("has_diagram", "has_table"):
        val = _bool_param(opt)
        if val is True:
            qs = qs.filter(pk__in=visible_images.filter(**{opt: True}).values("question_id"))

    if min_conf is not None:
        qs = qs.filter(confidence_score__gte=min_conf)

    # A locked row whose public text carries an answer label / flag shows it
    # cut (questions.answer_leak), but q / the keywords matched the raw text:
    # ``?drug=Correct Answer: B`` returned exactly the rows labelled B. Such a
    # row stays only when the terms occur in the text the caller sees.
    keywords = [kw for kw in (_keyword_param(request, dim) for dim in _CLINICAL_PARAMS) if kw]
    q_phrase = request.query_params.get("q") or ""  # as _PARAM_FILTERS applies it
    if not entitled and (q_phrase or keywords):
        from .locked_text_search import recall_terms_visible, without_hidden_matches
        qs = without_hidden_matches(qs, recall_terms_visible(q_phrase, keywords))

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
    # Image-modality facet (images the caller may see)
    facets["modality"] = dict(
        visible_images.filter(question__in=qs)
        .values_list("modality").annotate(c=Count("id"))
    )

    # Paginate (page / page_size validated and clamped above)
    qs = qs.order_by("-year", "id")
    total = qs.count()
    start = (page - 1) * page_size
    end = start + page_size
    from .views import _question_list_related  # lazy: views imports this module
    page_qs = _question_list_related(qs)[start:end]

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
    """GET /api/questions/{id}/images/  — list QuestionImage rows for a question.

    Goes through ``get_object()`` so removed / archived questions 404 for
    non-admins. ``role`` is the runtime role (``image_context.runtime_role``:
    an image referenced only from the explanation is 'explanation', which
    the stem gallery hides; one referenced from the stem or an option is a
    stem-side figure). Callers who are not entitled to the answer get stem
    images only, with the neutral ``alt_text`` but without captions (a
    caption can name the diagnosis) and without OCR text (a recall
    screenshot's OCR can carry the printed key); entitled callers get the
    explanation figures with a signed ``file_url``.
    """
    from .image_context import option_letter_for, runtime_role
    from .models import QuestionImage
    from .recall_serializers import QuestionImageSerializer  # type: ignore

    question = self.get_object()
    images = (QuestionImage.objects.filter(question_id=question.pk, is_active=True)
              .order_by("page_number", "image_index_in_page", "id"))
    page_size, err = _int_param(request, "page_size", 50, minimum=1, maximum=200)
    if err is not None:
        return err
    images = list(images[:page_size])
    memo: dict = {}
    roles = {img.id: runtime_role(question, img, memo) for img in images}
    option_labels = {img.id: option_letter_for(question, img) for img in images}
    data = QuestionImageSerializer(images, many=True, context={"request": request}).data
    for row in data:
        row["role"] = roles.get(row["id"], row.get("role"))
        row["option_label"] = option_labels.get(row["id"], row.get("option_label", ""))
    if not self._can_view_answer(question):
        data = [row for row in data if row.get("role") != "explanation"]
        for row in data:
            row["caption"] = ""
            row["ocr_text"] = ""
    else:
        # The serve endpoint returns explanation figures only with a signed
        # token (questions.image_access), issued to entitled callers.
        from .image_access import with_image_token
        for row in data:
            if row.get("role") == "explanation" and row.get("file_url"):
                row["file_url"] = with_image_token(row["file_url"], row["id"])
    return Response(data)


def recall_question_sources(self, request, pk=None):
    """GET /api/questions/{id}/sources/  — list QuestionSource rows for a question.

    Provenance metadata only (file name, page, confidences). The stored
    ``original_text`` / ``extracted_text`` are the whole parsed block --
    stem, answer key and explanation -- so they are returned to admins only.
    Removed / archived questions 404 for non-admins (``get_object()``).
    """
    from .models import QuestionSource
    from .recall_serializers import QuestionSourceSerializer  # type: ignore

    question = self.get_object()
    rows = QuestionSource.objects.filter(question_id=question.pk).select_related("recall_source").order_by("imported_at")
    data = QuestionSourceSerializer(rows, many=True, context={"request": request}).data
    user = getattr(request, "user", None)
    is_admin = bool(
        user is not None and getattr(user, "is_authenticated", False)
        and (getattr(user, "is_admin", False) or getattr(user, "is_superuser", False)
             or getattr(user, "is_staff", False))
    )
    if not is_admin:
        for row in data:
            row.pop("original_text", None)
            row.pop("extracted_text", None)
    return Response(data)


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