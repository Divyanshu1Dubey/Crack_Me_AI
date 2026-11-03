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

Cost: every endpoint reads one user's answer history (``_answer_events``).
A request loads it once, for the widest window it needs, and derives the
narrower windows from that load (``_window``); the dashboard used to load
the whole history four times per request. Every result is cached per user
for ``CACHE_TTL`` seconds, so a new answer shows up within a minute, and a
dashboard miss also fills the sub-endpoints' entries it has computed.
``?nocache=1`` recomputes only for admins / staff (it let anyone skip the
cache). ``invalidate_user_cache`` drops one user's entries at once.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import timedelta

from django.core.cache import cache
from django.db.models import Count
from django.utils import timezone
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from questions.serializers import public_subject_name

LOG = logging.getLogger(__name__)

# Seconds a computed result is served from the cache: a new answer shows up
# within a minute.
CACHE_TTL = 60
# The active bank's exam x year question counts (PYQ coverage totals) are
# the same for every user: computed once per BANK_TOTALS_TTL seconds instead
# of on every user's cache miss.
BANK_TOTALS_TTL = 300
PYQ_EXAMS = ("cms", "neet_pg", "ini_cet", "aiims_pg")

# Answer-history windows, in days (None: all time).
DASHBOARD_DAYS = 90   # accuracy, average time, weak subjects / topics
TREND_DAYS = 60       # performance trend, subject heatmap
PYQ_DAYS = 365        # PYQ coverage

# One user's cached results: dashboard_v3:<name>:<user id>.
CACHED_RESULTS = ("dashboard", "heatmap_subject", "revision_progress", "pyq_coverage", "average_time")
_BANK_TOTALS_KEY = "dashboard_v3:bank_totals"

_EVENT_FIELDS = ("question_id", "question__subject_id", "question__subject__name",
                 "question__topic_id", "question__topic__name", "is_correct")
# Read with the events (same join) for the PYQ coverage: no second query
# with an IN list of every attempted question id.
_QUESTION_FIELDS = ("question__exam_type", "question__year", "question__is_active")


def _answer_events(user, days: int | None = 90, now=None) -> list[dict]:
    """Every answered question for the user in the window: test answers
    (``QuestionResponse`` on completed attempts, skipped ones excluded) and
    question-bank answers (``QuestionAttempt``).

    This module used to query ``TestAttempt`` for per-question fields it does
    not have (``created_at``, ``is_correct``, ``question``…), so every
    endpoint here returned HTTP 500.

    Besides the public keys each event carries ``_at``, the time the window
    filters on (the test attempt's start / the bank answer's time), so a
    narrower window can be cut from a wider load (``_window``), and
    ``_question``, the question's (exam_type, year, is_active).

    Events come in a fixed order -- test answers by attempt start, then
    question; bank answers by question -- the order the queries' indexes
    gave: ties between weak subjects / topics and a topic's subject name
    (taken from its first event) no longer depend on the query plan.
    """
    from questions.models import QuestionAttempt, QuestionPracticeState
    from tests_engine.models import QuestionResponse

    now = now or timezone.now()
    since = now - timedelta(days=days) if days else None
    fields = _EVENT_FIELDS
    events: list[dict] = []

    responses = QuestionResponse.objects.filter(
        attempt__user=user, attempt__is_completed=True, is_correct__isnull=False)
    if since:
        responses = responses.filter(attempt__started_at__gte=since)
    responses = responses.order_by("attempt__started_at", "attempt_id", "question_id")
    for r in responses.values(*fields, *_QUESTION_FIELDS, "time_taken_seconds", "confidence_level",
                              "attempt__completed_at", "attempt__started_at").iterator():
        events.append({
            **{k: r[k] for k in fields},
            "when": r["attempt__completed_at"] or r["attempt__started_at"],
            "seconds": r["time_taken_seconds"] or None,
            "confidence": r["confidence_level"] or None,
            "_at": r["attempt__started_at"],
            "_question": (r["question__exam_type"], r["question__year"], r["question__is_active"]),
        })

    attempts = QuestionAttempt.objects.filter(user=user)
    if since:
        attempts = attempts.filter(attempted_at__gte=since)
    # Practice state (confidence, time) only of the questions answered here:
    # it used to load every practice-state row of the user, whatever the window.
    state = {
        qid: (conf, secs) for qid, conf, secs in QuestionPracticeState.objects
        .filter(user=user, question_id__in=attempts.values("question_id"))
        .values_list("question_id", "confidence", "time_spent_seconds")
    }
    for a in attempts.order_by("question_id").values(*fields, *_QUESTION_FIELDS, "attempted_at").iterator():
        conf, secs = state.get(a["question_id"], (None, None))
        events.append({
            **{k: a[k] for k in fields},
            "when": a["attempted_at"],
            "seconds": secs or None,
            "confidence": conf or None,
            "_at": a["attempted_at"],
            "_question": (a["question__exam_type"], a["question__year"], a["question__is_active"]),
        })
    return events


def _window(events: list[dict], days: int | None, now) -> list[dict]:
    """The events of the last ``days`` days of a wider load, in load order:
    what ``_answer_events(user, days)`` returns, without another query."""
    if not days:
        return events
    since = now - timedelta(days=days)
    return [e for e in events if e["_at"] is not None and e["_at"] >= since]


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
            "subject": public_subject_name(g["first"]["question__subject__name"]),
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
            "subject": public_subject_name(g["first"]["question__subject__name"]),
            "attempts": g["n"],
            "mistakes": g["mistakes"],
            "mistake_rate_pct": round((g["mistakes"] / g["n"]) * 100, 1),
        })
    return out


def _performance_trend(user, days: int = TREND_DAYS, events: list[dict] | None = None) -> list:
    """Daily accuracy pct — last 60 days (local dates); ``events``: that window."""
    per_day: dict = defaultdict(lambda: {"n": 0, "correct": 0})
    for e in (_answer_events(user, days=days) if events is None else events):
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


def _revision_progress(user, events: list[dict] | None = None) -> dict:
    """Topic × confidence rating coverage.

    For every (topic, confidence=1..5; 0 = not rated), how many distinct
    questions the user has practised.  Used by the revision schedule UI.
    ``events``: the whole history.
    """
    seen: dict = defaultdict(dict)  # topic -> {question_id: confidence}
    topics: dict = {}
    for e in (_answer_events(user, days=None) if events is None else events):
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


def _bank_totals() -> list[tuple]:
    """``(exam_type, year, questions)`` of the active bank's PYQ exams, in
    database order. The same for every user: cached for BANK_TOTALS_TTL."""
    from questions.models import Question

    rows = _cache_get(_BANK_TOTALS_KEY)
    if rows is None:
        rows = [
            (r["exam_type"], r["year"], r["t"])
            for r in Question.objects.filter(is_active=True, exam_type__in=PYQ_EXAMS)
            .values("exam_type", "year").annotate(t=Count("id"))
        ]
        _cache_set_many({_BANK_TOTALS_KEY: rows}, BANK_TOTALS_TTL)
    return rows


def _pyq_coverage(user, events: list[dict] | None = None) -> dict:
    """Exam × year grid showing attempted/total questions (questions
    answered in the last 365 days; ``events``: that window)."""
    events = _answer_events(user, days=PYQ_DAYS) if events is None else events
    grid: dict = defaultdict(lambda: {"attempted": 0, "total": 0, "years": defaultdict(lambda: {"a": 0, "t": 0})})
    for exam, year, total in _bank_totals():
        grid[exam]["total"] += total
        grid[exam]["years"][year]["t"] += total
    # Distinct answered questions that are active and of a PYQ exam (it was
    # a second GROUP BY with `id IN (<every answered question id>)`).
    answered = {e["question_id"]: e["_question"] for e in events}
    attempted: dict = defaultdict(int)
    for exam, year, is_active in answered.values():
        if is_active and exam in PYQ_EXAMS:
            attempted[(exam, year)] += 1
    for (exam, year), count in attempted.items():
        grid[exam]["attempted"] += count
        grid[exam]["years"][year]["a"] += count
    serial = {}
    for exam, payload in grid.items():
        serial[exam] = {
            "attempted": payload["attempted"],
            "total": payload["total"],
            "coverage_pct": round((payload["attempted"] / payload["total"]) * 100, 1) if payload["total"] else 0.0,
            "years": {y: payload["years"][y] for y in sorted(payload["years"])},
        }
    return serial


def _heatmap_subject(user, events: list[dict] | None = None) -> dict:
    """Subject × day-of-week accuracy matrix (last 60 days; ``events``: that window).

    Keys: subject id (string) → day of week as a string, 0 = Sunday … 6 =
    Saturday (the frontend's DAYS order) → {n, correct}.
    """
    matrix: dict = defaultdict(lambda: defaultdict(lambda: {"n": 0, "correct": 0}))
    for e in (_answer_events(user, days=TREND_DAYS) if events is None else events):
        if not e["when"] or e["question__subject_id"] is None:
            continue
        local = timezone.localtime(e["when"])
        dow = str((local.weekday() + 1) % 7)  # Python: Monday=0 → Sunday=0
        cell = matrix[str(e["question__subject_id"])][dow]
        cell["n"] += 1
        cell["correct"] += 1 if e["is_correct"] else 0
    return {s: dict(days) for s, days in matrix.items()}


def _dashboard(user) -> tuple[dict, dict]:
    """The dashboard payload, and the sub-endpoint results it computes on
    the way (by cache name), from one load of the whole history."""
    now = timezone.now()
    events = _answer_events(user, days=None, now=now)
    recent = _window(events, DASHBOARD_DAYS, now)
    trend_window = _window(events, TREND_DAYS, now)
    average_time = _average_time(user, recent)
    revision_progress = _revision_progress(user, events)
    pyq_coverage = _pyq_coverage(user, _window(events, PYQ_DAYS, now))
    payload = {
        "accuracy": _accuracy(user, recent),
        "average_time": average_time,
        "weak_subjects": _weak_subjects(user, events=recent),
        "weak_topics": _weak_topics(user, events=recent),
        "performance_trend": _performance_trend(user, events=trend_window),
        "revision_progress": revision_progress,
        "pyq_coverage": pyq_coverage,
        "generated_at": timezone.now().isoformat(),
        "cache": "miss",
    }
    parts = {
        "heatmap_subject": _heatmap_subject(user, trend_window),
        "revision_progress": revision_progress,
        "pyq_coverage": pyq_coverage,
        "average_time": average_time,
    }
    return payload, parts


# ─── Cache ────────────────────────────────────────────────────────────────


def _cache_key(user_id, name: str) -> str:
    return f"dashboard_v3:{name}:{user_id}"


def _cache_get(key: str):
    try:
        return cache.get(key)
    except Exception:  # pragma: no cover - cache backend hiccup
        return None


def _cache_set_many(values: dict, timeout: int = CACHE_TTL) -> None:
    try:
        cache.set_many(values, timeout)
    except Exception:  # pragma: no cover - cache backend hiccup
        pass


def invalidate_user_cache(user_id) -> None:
    """Drop every cached result of one user here (e.g. after a new answer)."""
    try:
        cache.delete_many([_cache_key(user_id, name) for name in CACHED_RESULTS])
    except Exception:  # pragma: no cover - cache backend hiccup
        LOG.debug("dashboard_v3 cache invalidation failed for user %s", user_id)


def _fresh_requested(request) -> bool:
    """``?nocache=1`` from an admin / staff user: recompute (for debugging).
    Anyone else is served from the cache."""
    user = request.user
    return request.query_params.get("nocache") == "1" and bool(
        getattr(user, "is_admin", False) or getattr(user, "is_staff", False)
        or getattr(user, "is_superuser", False))


# ─── DRF views ────────────────────────────────────────────────────────────


class DashboardV3View(APIView):
    """`GET /api/analytics/dashboard_v3/` — combined Phase-3 payload."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        # Per-user cache (CACHE_TTL) — keeps the dashboard snappy when a
        # user refreshes the page repeatedly; `cache` says "hit" / "miss".
        key = _cache_key(user.id, "dashboard")
        if not _fresh_requested(request):
            payload = _cache_get(key)
            if payload is not None:
                payload["cache"] = "hit"
                return Response(payload)
        payload, parts = _dashboard(user)
        _cache_set_many({key: payload, **{_cache_key(user.id, name): value for name, value in parts.items()}})
        return Response(payload)


class _CachedUserResultView(APIView):
    """A per-user result cached for CACHE_TTL under ``cache_name``."""
    permission_classes = [permissions.IsAuthenticated]
    cache_name = ""

    def compute(self, user):  # pragma: no cover - abstract
        raise NotImplementedError

    def get(self, request):
        key = _cache_key(request.user.id, self.cache_name)
        if not _fresh_requested(request):
            result = _cache_get(key)
            if result is not None:
                return Response(result)
        result = self.compute(request.user)
        _cache_set_many({key: result})
        return Response(result)


class HeatmapSubjectView(_CachedUserResultView):
    cache_name = "heatmap_subject"

    def compute(self, user):
        return _heatmap_subject(user)


class RevisionProgressView(_CachedUserResultView):
    cache_name = "revision_progress"

    def compute(self, user):
        return _revision_progress(user)


class PYQCoverageView(_CachedUserResultView):
    cache_name = "pyq_coverage"

    def compute(self, user):
        return _pyq_coverage(user)


class AverageTimeView(_CachedUserResultView):
    cache_name = "average_time"

    def compute(self, user):
        return _average_time(user)


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
