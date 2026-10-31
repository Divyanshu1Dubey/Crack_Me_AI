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

from django.db.models import Count
from django.utils import timezone
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

LOG = logging.getLogger(__name__)


def _answer_events(user, days: int | None = 90) -> list[dict]:
    """Every answered question for the user in the window: test answers
    (``QuestionResponse`` on completed attempts, skipped ones excluded) and
    question-bank answers (``QuestionAttempt``).

    This module used to query ``TestAttempt`` for per-question fields it does
    not have (``created_at``, ``is_correct``, ``question``…), so every
    endpoint here returned HTTP 500.
    """
    from questions.models import QuestionAttempt, QuestionPracticeState
    from tests_engine.models import QuestionResponse

    since = timezone.now() - timedelta(days=days) if days else None
    fields = ("question_id", "question__subject_id", "question__subject__name",
              "question__topic_id", "question__topic__name", "is_correct")
    events: list[dict] = []

    responses = QuestionResponse.objects.filter(
        attempt__user=user, attempt__is_completed=True, is_correct__isnull=False)
    if since:
        responses = responses.filter(attempt__started_at__gte=since)
    for r in responses.values(*fields, "time_taken_seconds", "confidence_level",
                              "attempt__completed_at", "attempt__started_at").iterator():
        events.append({
            **{k: r[k] for k in fields},
            "when": r["attempt__completed_at"] or r["attempt__started_at"],
            "seconds": r["time_taken_seconds"] or None,
            "confidence": r["confidence_level"] or None,
        })

    state = {
        qid: (conf, secs) for qid, conf, secs in QuestionPracticeState.objects.filter(user=user)
        .values_list("question_id", "confidence", "time_spent_seconds")
    }
    attempts = QuestionAttempt.objects.filter(user=user)
    if since:
        attempts = attempts.filter(attempted_at__gte=since)
    for a in attempts.values(*fields, "attempted_at").iterator():
        conf, secs = state.get(a["question_id"], (None, None))
        events.append({
            **{k: a[k] for k in fields},
            "when": a["attempted_at"],
            "seconds": secs or None,
            "confidence": conf or None,
        })
    return events


def _accuracy(user, events: list[dict] | None = None) -> dict:
    events = _answer_events(user) if events is None else events
    n = len(events)
    c = sum(1 for e in events if e["is_correct"])
    pct = round((c / n) * 100, 1) if n else 0.0
    return {"total": n, "correct": c, "accuracy_pct": pct}


def _average_time(user, events: list[dict] | None = None) -> dict:
    events = _answer_events(user) if events is None else events
    timed = [e["seconds"] for e in events if e["seconds"]]
    return {"average_seconds": int(sum(timed) / len(timed)) if timed else 0}


def _weak_groups(events: list[dict], key: str, limit: int) -> list[tuple]:
    groups: dict = {}
    for e in events:
        k = e[key]
        if k is None:
            continue
        g = groups.setdefault(k, {"n": 0, "mistakes": 0, "first": e})
        g["n"] += 1
        g["mistakes"] += 0 if e["is_correct"] else 1
    rows = [(k, g) for k, g in groups.items() if g["n"] >= 3]
    rows.sort(key=lambda kg: (-kg[1]["mistakes"], -(kg[1]["mistakes"] / kg[1]["n"])))
    return rows[:limit]


def _weak_subjects(user, limit: int = 6, events: list[dict] | None = None) -> list:
    events = _answer_events(user) if events is None else events
    out = []
    for sid, g in _weak_groups(events, "question__subject_id", limit):
        out.append({
            "subject_id": sid,
            "subject": g["first"]["question__subject__name"],
            "attempts": g["n"],
            "mistakes": g["mistakes"],
            "mistake_rate_pct": round((g["mistakes"] / g["n"]) * 100, 1),
        })
    return out


def _weak_topics(user, limit: int = 6, events: list[dict] | None = None) -> list:
    events = _answer_events(user) if events is None else events
    out = []
    for tid, g in _weak_groups(events, "question__topic_id", limit):
        out.append({
            "topic_id": tid,
            "topic": g["first"]["question__topic__name"],
            "subject": g["first"]["question__subject__name"],
            "attempts": g["n"],
            "mistakes": g["mistakes"],
            "mistake_rate_pct": round((g["mistakes"] / g["n"]) * 100, 1),
        })
    return out


def _performance_trend(user, days: int = 60) -> list:
    """Daily accuracy pct — last 60 days (local dates)."""
    per_day: dict = defaultdict(lambda: {"n": 0, "correct": 0})
    for e in _answer_events(user, days=days):
        if not e["when"]:
            continue
        day = timezone.localdate(e["when"])
        per_day[day]["n"] += 1
        per_day[day]["correct"] += 1 if e["is_correct"] else 0
    out = []
    for day in sorted(per_day):
        r = per_day[day]
        out.append({"date": day.isoformat(), "attempts": r["n"], "correct": r["correct"],
                    "accuracy_pct": round((r["correct"] / r["n"]) * 100, 1) if r["n"] else 0})
    return out


def _revision_progress(user) -> dict:
    """Topic × confidence rating coverage.

    For every (topic, confidence=1..5; 0 = not rated), how many distinct
    questions the user has practised.  Used by the revision schedule UI.
    """
    seen: dict = defaultdict(dict)  # topic -> {question_id: confidence}
    topics: dict = {}
    for e in _answer_events(user, days=None):
        tid = e["question__topic_id"]
        if tid is None:
            continue
        topics[tid] = e["question__topic__name"]
        conf = int(e["confidence"] or 0)
        # Keep the highest confidence seen for the question.
        seen[tid][e["question_id"]] = max(conf, seen[tid].get(e["question_id"], 0))
    out = []
    for tid, name in topics.items():
        buckets: dict = defaultdict(int)
        for conf in seen[tid].values():
            buckets[conf] += 1
        out.append({"topic_id": tid, "topic": name, "by_confidence": dict(buckets),
                    "total": len(seen[tid])})
    out.sort(key=lambda t: -t["total"])
    return {"topics": out}


def _pyq_coverage(user) -> dict:
    """Exam × year grid showing attempted/total questions."""
    from questions.models import Question
    attempted_qids = {e["question_id"] for e in _answer_events(user, days=365)}
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
    """Subject × day-of-week accuracy matrix (last 60 days).

    Keys: subject id (string) → day of week as a string, 0 = Sunday … 6 =
    Saturday (the frontend's DAYS order) → {n, correct}.
    """
    matrix: dict = defaultdict(lambda: defaultdict(lambda: {"n": 0, "correct": 0}))
    for e in _answer_events(user, days=60):
        if not e["when"] or e["question__subject_id"] is None:
            continue
        local = timezone.localtime(e["when"])
        dow = str((local.weekday() + 1) % 7)  # Python: Monday=0 → Sunday=0
        cell = matrix[str(e["question__subject_id"])][dow]
        cell["n"] += 1
        cell["correct"] += 1 if e["is_correct"] else 0
    return {s: dict(days) for s, days in matrix.items()}


# ─── DRF views ────────────────────────────────────────────────────────────


class DashboardV3View(APIView):
    """`GET /api/analytics/dashboard_v3/` — combined Phase-3 payload."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        # 60-second per-user cache — keeps the dashboard snappy when a
        # user refreshes the page repeatedly.  Bypassed via
        # `?nocache=1` for tests / debugging.
        if request.query_params.get("nocache") != "1":
            try:
                from django.core.cache import cache
                key = f"dashboard_v3:{user.id}"
                payload = cache.get(key)
                if payload is not None:
                    payload["cache"] = "hit"
                    return Response(payload)
            except Exception:  # pragma: no cover - defensive
                pass
        events = _answer_events(user)
        payload = {
            "accuracy": _accuracy(user, events),
            "average_time": _average_time(user, events),
            "weak_subjects": _weak_subjects(user, events=events),
            "weak_topics": _weak_topics(user, events=events),
            "performance_trend": _performance_trend(user),
            "revision_progress": _revision_progress(user),
            "pyq_coverage": _pyq_coverage(user),
            "generated_at": timezone.now().isoformat(),
            "cache": "miss",
        }
        try:
            from django.core.cache import cache
            cache.set(f"dashboard_v3:{user.id}", payload, 60)
        except Exception:  # pragma: no cover
            pass
        return Response(payload)


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
