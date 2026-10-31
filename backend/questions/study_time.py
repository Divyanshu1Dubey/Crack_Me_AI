"""Server-side study-time tracking (``StudyTimeBreakdown``).

Nothing in the client ever posted study time, so the Study Time page and
the dashboard's weekly study-time figures were always empty. Time is now
recorded when answers reach the server: per-question timings at test
submission and the optional ``time_spent_seconds`` sent with question-bank
and practice answers.
"""
from __future__ import annotations

import logging
from collections import defaultdict

from django.db.models import F
from django.utils import timezone

logger = logging.getLogger(__name__)

# A single question cannot plausibly account for more than this (idle tab).
MAX_SECONDS_PER_QUESTION = 30 * 60


def clamp_seconds(value, hi: int = MAX_SECONDS_PER_QUESTION) -> int:
    try:
        return max(0, min(int(float(value)), int(hi)))
    except (TypeError, ValueError, OverflowError):
        return 0


def record_study_time(user, rows, date=None) -> None:
    """Add study time. ``rows``: iterable of (subject_id, seconds, question_count).

    Rows are aggregated per subject and applied with atomic increments.
    Never raises: analytics must not break answer submission.
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return
    totals = defaultdict(lambda: [0, 0])
    for subject_id, seconds, count in rows:
        if not subject_id:
            continue
        totals[subject_id][0] += max(0, int(seconds or 0))
        totals[subject_id][1] += max(0, int(count or 0))
    day = date or timezone.localdate()
    try:
        from questions.models import StudyTimeBreakdown

        for subject_id, (seconds, count) in totals.items():
            if not seconds and not count:
                continue
            obj, _ = StudyTimeBreakdown.objects.get_or_create(
                user=user, subject_id=subject_id, date=day,
                defaults={'seconds': 0, 'question_count': 0},
            )
            StudyTimeBreakdown.objects.filter(pk=obj.pk).update(
                seconds=F('seconds') + seconds,
                question_count=F('question_count') + count,
            )
    except Exception:  # pragma: no cover - defensive
        logger.exception('record_study_time failed for user=%s', getattr(user, 'pk', None))


def rows_for_test_submission(items, elapsed_seconds, time_limit_minutes):
    """Per-subject rows for one submitted test.

    ``items``: iterable of (subject_id, time_taken_seconds or None, answered).
    Per-question timings are trusted only up to the real elapsed time of
    the attempt (scaled down proportionally when they add up to more).
    Clients that sent no timings get the attempt duration, capped at the
    paper's time limit, spread evenly over its questions.
    """
    rows = [[sid, clamp_seconds(t), 1 if answered else 0] for sid, t, answered in items if sid]
    if not rows:
        return []
    limit = max(1, int(time_limit_minutes or 30)) * 60
    try:
        # Unknown / zero elapsed time (old rows) means "do not scale".
        elapsed = min(max(0.0, float(elapsed_seconds or 0)), 24 * 3600.0)
    except (TypeError, ValueError):
        elapsed = 0.0
    reported = sum(r[1] for r in rows)
    if reported == 0:
        share = min(int(elapsed), limit) // len(rows)
        for r in rows:
            r[1] = share
    elif elapsed > 0 and reported > elapsed:
        budget = int(elapsed)
        for r in rows:
            r[1] = r[1] * budget // reported
    return [tuple(r) for r in rows]
