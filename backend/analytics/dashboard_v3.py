"""Phase-3 analytics dashboard views.

Additive — every new endpoint is a separate URL pattern and never
edits the existing `DashboardView`/`WeakTopicsView`/etc.

Endpoints:

* `GET /api/analytics/dashboard_v3/` — one aggregated payload for the
  front-end dashboard.
* `GET /api/analytics/heatmap/subject/` — accuracy × subject × year
  matrix.
* `GET /api/analytics/revision_progress/` — per-topic SR-style
  coverage %.
* `GET /api/analytics/pyq_coverage/` — exam/year matrix for the
  recall bank.
* `GET /api/analytics/average_time/` — average time on question by
  subject/topic/exam.
* `GET /api/analytics/search_analytics/` — top search queries
  (falls back to empty list if no log table exists).
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import timedelta

from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

LOG = logging.getLogger(__name__)


def _attempts_for(user, days: int = 90):
    from tests_engine.models import TestAttempt
    return TestAttempt.objects.filter(
        user=user,
        created_at__gte=timezone.now() - timedelta(days=days),
    )


def _accuracy(user) -> dict:
    rows = _attempts_for(user).aggregate(
        n=Count("id"),
        correct=Count("id", filter=Q(is_correct=True)),
    )
    n, c = rows["n"] or 0, rows["correct"] or 0
    pct = round((c / n) * 100, 1) if n else 0.0
    return {"total": n, "correct": c, "accuracy_pct": pct}


def _average_time(user) -> dict:
    rows = _attempts_for(user).aggregate(avg=Avg("time_spent_seconds"))
    return {"average_seconds": int(rows["avg"] or 0)}


def _weak_subjects(user, limit: int = 6) -> list:
    rows = (
        _attempts_for(user)
        .values("question__subject_id", "question__subject__name")
        .annotate(
            n=Count("id"),
            mistakes=Count("id", filter=Q(is_correct=False)),
        )
        .filter(n__gte=3)
        .order_by("-mistakes")[:limit]
    )
    out = []
    for r in rows:
        rate = round((r["mistakes"] / r["n"]) * 100, 1) if r["n"] else 0
        out.append({
            "subject_id": r["question__subject_id"],
            "subject": r["question__subject__name"],
            "attempts": r["n"],
            "mistakes": r["mistakes"],
            "mistake_rate_pct": rate,
        })
    return out


def _weak_topics(user, limit: int = 6) -> list:
    rows = (
        _attempts_for(user)
        .values("question__topic_id", "question__topic__name", "question__subject__name")
        .annotate(
            n=Count("id"),
            mistakes=Count("id", filter=Q(is_correct=False)),
        )
        .filter(n__gte=3)
        .order_by("-mistakes")[:limit]
    )
    out = []
    for r in rows:
        rate = round((r["mistakes"] / r["n"]) * 100, 1) if r["n"] else 0
        out.append({
            "topic_id": r["question__topic_id"],
            "topic": r["question__topic__name"],
            "subject": r["question__subject__name"],
            "attempts": r["n"],
            "mistakes": r["mistakes"],
            "mistake_rate_pct": rate,
        })
    return out


def _performance_trend(user, days: int = 60) -> list:
    """Daily accuracy pct — last 60 days."""
    from tests_engine.models import TestAttempt
    since = timezone.now() - timedelta(days=days)
    rows = (
        TestAttempt.objects
        .filter(user=user, created_at__gte=since)
        .extra(select={"d": "date(created_at)"})
        .values("d")
        .annotate(n=Count("id"), correct=Count("id", filter=Q(is_correct=True)))
        .order_by("d")
    )
    out = []
    for r in rows:
        pct = round((r["correct"] / r["n"]) * 100, 1) if r["n"] else 0
        out.append({"date": r["d"], "attempts": r["n"],
                    "correct": r["correct"], "accuracy_pct": pct})
    return out


def _revision_progress(user) -> dict:
    """Topic × confidence rating coverage.

    For every (topic, confidence=1..5), how many distinct questions the
    user has practised.  Used by the revision schedule UI.
    """
    from tests_engine.models import TestAttempt
    rows = (
        TestAttempt.objects.filter(user=user)
        .values("question__topic_id", "question__topic__name",
                "confidence_rating")
        .annotate(n=Count("id", distinct=True))
    )
    buckets: dict = defaultdict(lambda: defaultdict(int))
    topics: dict[int, str] = {}
    for r in rows:
        tid = r["question__topic_id"]
        if tid is None:
            continue
        topics[tid] = r["question__topic__name"]
        conf = r["confidence_rating"] or 0
        buckets[tid][conf] += r["n"]
    out = []
    for tid, name in topics.items():
        out.append({
            "topic_id": tid,
            "topic": name,
            "by_confidence": dict(buckets[tid]),
            "total": sum(buckets[tid].values()),
        })
    return {"topics": out}


def _pyq_coverage(user) -> dict:
    """Exam × year grid showing attempted/total questions."""
    from questions.models import Question
    attempted_qids = set(_attempts_for(user, days=365).values_list("question_id", flat=True))
    grid: dict = defaultdict(lambda: {"attempted": 0, "total": 0, "years": defaultdict(lambda: {"a": 0, "t": 0})})
    qs = Question.objects.filter(is_active=True, exam_type__in=["cms", "neet_pg", "ini_cet", "aiims_pg"])
    rows = qs.values("exam_type", "year").annotate(t=Count("id"))
    for r in rows:
        grid[r["exam_type"]]["total"] += r["t"]
        grid[r["exam_type"]]["years"][r["year"]]["t"] += r["t"]
    if attempted_qids:
        a_rows = (qs.filter(id__in=attempted_qids)
                    .values("exam_type", "year")
                    .annotate(a=Count("id")))
        for r in a_rows:
            grid[r["exam_type"]]["attempted"] += r["a"]
            grid[r["exam_type"]]["years"][r["year"]]["a"] += r["a"]
    serial = {}
    for exam, payload in grid.items():
        serial[exam] = {
            "attempted": payload["attempted"],
            "total": payload["total"],
            "coverage_pct": round((payload["attempted"] / payload["total"]) * 100, 1) if payload["total"] else 0.0,
            "years": {y: payload["years"][y] for y in sorted(payload["years"])},
        }
    return serial


def _heatmap_subject(user) -> dict:
    """Subject × day-of-week accuracy matrix (last 60 days)."""
    from tests_engine.models import TestAttempt
    since = timezone.now() - timedelta(days=60)
    rows = (
        TestAttempt.objects
        .filter(user=user, created_at__gte=since)
        .extra(select={"dow": "strftime('%w', created_at)",
                       "subject": "question__subject_id"})
        .values("dow", "subject")
        .annotate(n=Count("id"), correct=Count("id", filter=Q(is_correct=True)))
    )
    matrix = defaultdict(lambda: defaultdict(lambda: {"n": 0, "correct": 0}))
    for r in rows:
        s = r["subject"] or "0"
        matrix[str(s)][str(r["dow"])] = {"n": r["n"], "correct": r["correct"]}
    return {s: dict(matrix[s]) for s in matrix}


# ─── DRF views ────────────────────────────────────────────────────────────


class DashboardV3View(APIView):
    """`GET /api/analytics/dashboard_v3/` — combined Phase-3 payload."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            "accuracy": _accuracy(user),
            "average_time": _average_time(user),
            "weak_subjects": _weak_subjects(user),
            "weak_topics": _weak_topics(user),
            "performance_trend": _performance_trend(user),
            "revision_progress": _revision_progress(user),
            "pyq_coverage": _pyq_coverage(user),
            "generated_at": timezone.now().isoformat(),
        })


class HeatmapSubjectView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(_heatmap_subject(request.user))


class RevisionProgressView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(_revision_progress(request.user))


class PYQCoverageView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(_pyq_coverage(request.user))


class AverageTimeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(_average_time(request.user))


class SearchAnalyticsView(APIView):
    """`GET /api/analytics/search_analytics/`

    Phase-3 ships a stub returning `{ 'top_queries': [], 'daily': [] }`
    so the UI can be wired without a search-log table.  Phase-4 should
    add a `SearchLog` model and instrument the search box.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response({
            "top_queries": [],
            "daily": [],
            "note": "Search analytics is phase-3 placeholder; instrument client → /api/analytics/search_log/ in phase 4.",
        })
