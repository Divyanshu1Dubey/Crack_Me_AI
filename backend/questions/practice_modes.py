"""Practice-mode queue builder for Phase 3.

Reuses existing `Question` model + Phase-2 fields + `Attempt` rows
(`analytics` app) to construct practice queues for every supported mode:

    random / year_wise / subject_wise / topic_wise / weak_topics /
    bookmarked / wrong / image_only / rapid_revision / high_yield /
    clinical_cases

Each queue is returned as a *list* of question ids in deterministic
order.  The DRF view (`QuestionViewSet.practice_queue`) just serialises
them.

Add new modes by appending to `_MODE_BUILDERS` — never replace an
existing entry.
"""
from __future__ import annotations

import logging
import random
from typing import Callable, Optional

from django.db.models import Count, Q

LOG = logging.getLogger(__name__)


def _qs_for_user(user):
    """Return the base queryset every mode filters down."""
    from questions.models import Question
    return Question.objects.filter(is_active=True)


# The three per-user modes below used to 500 on every call: they imported a
# non-existent ``analytics.models.TestAttempt`` and filtered on relations
# Question does not have (``attempts``, ``bookmarks__is_active``). Answers
# live in ``QuestionAttempt`` (related_name ``qbank_attempts``, one row per
# user+question = the latest answer) and in tests_engine ``QuestionResponse``.


def _wrong_ids_for_user(user, count: int) -> list[int]:
    """Active questions the user answered wrong (question bank / practice
    or a test), most recent first."""
    from questions.models import QuestionAttempt
    from tests_engine.models import QuestionResponse

    ordered: list[int] = []
    seen: set[int] = set()
    qbank = (
        QuestionAttempt.objects
        .filter(user=user, is_correct=False, question__is_active=True)
        .order_by("-attempted_at", "-id")
        .values_list("question_id", flat=True)[: count * 2]
    )
    tests = (
        QuestionResponse.objects
        .filter(attempt__user=user, is_correct=False, question__is_active=True)
        .exclude(selected_answer__isnull=True).exclude(selected_answer="")
        .order_by("-attempt__started_at", "-id")
        .values_list("question_id", flat=True)[: count * 4]
    )
    for qid in list(qbank) + list(tests):
        if qid in seen:
            continue
        seen.add(qid)
        ordered.append(qid)
        if len(ordered) >= count:
            break
    return ordered


def _wrong_for_user(user):
    """Questions the user got wrong at least once (queryset)."""
    return _qs_for_user(user).filter(
        Q(qbank_attempts__user=user, qbank_attempts__is_correct=False)
        | Q(questionresponse__attempt__user=user, questionresponse__is_correct=False)
    ).distinct()


def _bookmarked_ids_for_user(user, count: int) -> list[int]:
    """The user's bookmarked active questions, newest bookmark first."""
    from questions.models import QuestionBookmark
    return list(
        QuestionBookmark.objects
        .filter(user=user, question__is_active=True)
        .order_by("-created_at", "-id")
        .values_list("question_id", flat=True)[:count]
    )


def _bookmarked_for_user(user):
    return _qs_for_user(user).filter(bookmarks__user=user).distinct()


def _weak_topics_for_user(user, limit: int = 5):
    """Top-N topics by mistake count for this user (min 5 answers per
    topic), from question-bank / practice answers plus test responses."""
    from collections import Counter
    from questions.models import QuestionAttempt
    from tests_engine.models import QuestionResponse

    attempts: Counter = Counter()
    mistakes: Counter = Counter()
    qbank_rows = (
        QuestionAttempt.objects
        .filter(user=user, question__topic__isnull=False)
        .values("question__topic_id")
        .annotate(n=Count("id"), wrong=Count("id", filter=Q(is_correct=False)))
    )
    test_rows = (
        QuestionResponse.objects
        .filter(attempt__user=user, question__topic__isnull=False)
        .exclude(selected_answer__isnull=True).exclude(selected_answer="")
        .values("question__topic_id")
        .annotate(n=Count("id"), wrong=Count("id", filter=Q(is_correct=False)))
    )
    for row in list(qbank_rows) + list(test_rows):
        topic_id = row["question__topic_id"]
        attempts[topic_id] += row["n"]
        mistakes[topic_id] += row["wrong"]
    topic_ids = [
        topic_id for topic_id, _wrong in mistakes.most_common()
        if attempts[topic_id] >= 5 and mistakes[topic_id] > 0
    ][:limit]
    if not topic_ids:
        return _qs_for_user(user).filter(topic__isnull=False)
    return _qs_for_user(user).filter(topic_id__in=topic_ids)


def _random(qs, *, count: int = 20, seed: Optional[int] = None):
    ids = list(qs.values_list("id", flat=True))
    rng = random.Random(seed) if seed is not None else random
    rng.shuffle(ids)
    return ids[:count]


def _rapid_revision(qs, *, count: int = 30):
    """Highest-confidence, single-best-answer, single-image questions."""
    return list(
        qs.filter(question_type="single_best", confidence_score__gte=0.7)
          .order_by("-year", "-confidence_score")
          .values_list("id", flat=True)[:count]
    )


def _high_yield(qs, *, count: int = 30):
    """Recall questions flagged 'recall' with clinical context."""
    return list(
        qs.filter(recall_status="recall", clinical_category="clinical")
          .filter(Q(is_image_based=True) | Q(concept_tags__len__gt=0))
          .order_by("-year", "-confidence_score")
          .values_list("id", flat=True)[:count]
    )


def _clinical_cases(qs, *, count: int = 25):
    """Long-stem clinical vignettes."""
    return list(
        qs.filter(clinical_category="clinical")
          .filter(question_type__in=["single_best", "multiple_correct"])
          .order_by("-year")
          .values_list("id", flat=True)[:count]
    )


def _image_only(qs, *, count: int = 25):
    return list(
        qs.filter(is_image_based=True)
          .order_by("-year", "-confidence_score")
          .values_list("id", flat=True)[:count]
    )


def _timed_exam(qs, *, count: int = 60):
    """Full-paper timed mock — newest-year questions, mixed difficulty."""
    return list(
        qs.filter(year__isnull=False)
          .order_by("-year", "id")
          .values_list("id", flat=True)[:count]
    )


def _custom(qs, *, count: int = 20, **filters):
    """Multi-filter — Year + Subject + Topic + Difficulty + Image-only.

    Each filter is optional; missing filter = no constraint. Unknown
    filters are silently ignored so future client params don't break
    older builds.
    """
    f = qs
    if filters.get("year"):
        f = f.filter(year=filters["year"])
    if filters.get("subject_id"):
        f = f.filter(subject_id=filters["subject_id"])
    if filters.get("topic_id"):
        f = f.filter(topic_id=filters["topic_id"])
    if filters.get("difficulty"):
        f = f.filter(difficulty=filters["difficulty"])
    if str(filters.get("is_image_based")).lower() in ("true", "1", "yes"):
        f = f.filter(is_image_based=True)
    if str(filters.get("has_explanation")).lower() in ("true", "1", "yes"):
        from django.db.models import Q
        f = f.filter(~Q(explanation="") | ~Q(ai_explanation=""))
    if str(filters.get("has_ai_enrichment")).lower() in ("true", "1", "yes"):
        from django.db.models import Q
        f = f.exclude(ai_explanation="")
    return list(f.order_by("-year", "id").values_list("id", flat=True)[:count])


_MODE_BUILDERS: dict[str, Callable] = {
    "random":        lambda qs, user, params: _random(qs, count=params.get("count", 20),
                                                     seed=params.get("seed")),
    "year_wise":     lambda qs, user, params: list(
        qs.filter(year=params["year"]).order_by("id").values_list("id", flat=True)[:params.get("count", 60)]
    ) if params.get("year") else _random(qs, count=20),
    "subject_wise":  lambda qs, user, params: list(
        qs.filter(subject_id=params["subject_id"]).order_by("-year").values_list("id", flat=True)[:params.get("count", 60)]
    ) if params.get("subject_id") else _random(qs, count=20),
    "topic_wise":    lambda qs, user, params: list(
        qs.filter(topic_id=params["topic_id"]).order_by("-year").values_list("id", flat=True)[:params.get("count", 60)]
    ) if params.get("topic_id") else _random(qs, count=20),
    "weak_topics":   lambda qs, user, params: list(
        _weak_topics_for_user(user).order_by("-year").values_list("id", flat=True)[:params.get("count", 40)]
    ),
    "bookmarked":    lambda qs, user, params: _bookmarked_ids_for_user(user, params.get("count", 60)),
    "wrong":         lambda qs, user, params: _wrong_ids_for_user(user, params.get("count", 60)),
    "image_only":    lambda qs, user, params: _image_only(qs, count=params.get("count", 25)),
    "rapid_revision": lambda qs, user, params: _rapid_revision(qs, count=params.get("count", 30)),
    "high_yield":    lambda qs, user, params: _high_yield(qs, count=params.get("count", 30)),
    "clinical_cases": lambda qs, user, params: _clinical_cases(qs, count=params.get("count", 25)),
    "timed":         lambda qs, user, params: _timed_exam(qs, count=params.get("count", 60)),
    "custom":        lambda qs, user, params: _custom(qs, **params),
}


def build_queue(mode: str, user, params: dict | None = None) -> list[int]:
    """Dispatch by mode. Unknown mode returns 20 random question ids."""
    params = params or {}
    builder = _MODE_BUILDERS.get(mode)
    if builder is None:
        LOG.warning("build_queue: unknown mode=%r — falling back to random", mode)
        return _random(_qs_for_user(user), count=20)
    qs = _qs_for_user(user)
    return builder(qs, user, params) or []


def list_modes() -> list[dict]:
    """Return the supported mode catalogue for the front-end."""
    return [
        {"key": k, "label": k.replace("_", " ").title()}
        for k in _MODE_BUILDERS
    ]
