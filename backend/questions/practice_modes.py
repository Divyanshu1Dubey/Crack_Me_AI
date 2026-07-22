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


def _wrong_for_user(user):
    """Questions the user got wrong at least once."""
    from analytics.models import TestAttempt
    return _qs_for_user(user).filter(
        attempts__user=user,
        attempts__is_correct=False,
    ).distinct()


def _bookmarked_for_user(user):
    from questions.models import QuestionBookmark
    return _qs_for_user(user).filter(
        bookmarks__user=user,
        bookmarks__is_active=True,
    ).distinct()


def _weak_topics_for_user(user, limit: int = 5):
    """Top-N topics by mistake rate for this user (min 5 attempts)."""
    from analytics.models import TestAttempt
    from questions.models import Topic
    rows = (
        TestAttempt.objects
        .filter(user=user)
        .values("question__topic_id")
        .annotate(
            attempts=Count("id"),
            mistakes=Count("id", filter=Q(is_correct=False)),
        )
        .filter(attempts__gte=5)
        .order_by("-mistakes")
    )
    if not rows:
        return _qs_for_user(user).filter(topic__isnull=False)
    topic_ids = [r["question__topic_id"] for r in rows[:limit] if r["question__topic_id"]]
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
    "bookmarked":    lambda qs, user, params: list(
        _bookmarked_for_user(user).order_by("-created_at").values_list("id", flat=True)[:params.get("count", 60)]
    ),
    "wrong":         lambda qs, user, params: list(
        _wrong_for_user(user).order_by("-attempts__created_at").values_list("id", flat=True)[:params.get("count", 60)]
    ),
    "image_only":    lambda qs, user, params: _image_only(qs, count=params.get("count", 25)),
    "rapid_revision": lambda qs, user, params: _rapid_revision(qs, count=params.get("count", 30)),
    "high_yield":    lambda qs, user, params: _high_yield(qs, count=params.get("count", 30)),
    "clinical_cases": lambda qs, user, params: _clinical_cases(qs, count=params.get("count", 25)),
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
