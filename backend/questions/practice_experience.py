"""Phase 3 practice-experience helpers.

Endpoints registered from views.py:

* flag / unflag
* confidence_rating (1..5)
* time_spent_seconds (accumulated)
* elimination toggle (per-question option-level strike-through)
* attempt submission

Storage: one ``QuestionPracticeState`` row per (user, question) holds the
flag / confidence / time / eliminated options; attempts are recorded in the
existing ``QuestionAttempt`` table (latest attempt per question). Bookmarks
are untouched -- ``bookmarked`` in ``get_state`` simply reflects whether a
``QuestionBookmark`` exists.
"""
from __future__ import annotations

import logging

LOG = logging.getLogger(__name__)

_VALID_OPTIONS = ("A", "B", "C", "D", "E")


def _state(q, user, create: bool = True):
    from questions.models import QuestionPracticeState
    if create:
        obj, _ = QuestionPracticeState.objects.get_or_create(user=user, question=q)
        return obj
    return QuestionPracticeState.objects.filter(user=user, question=q).first()


def set_flag(q, user, flag: bool):
    st = _state(q, user)
    st.flagged = bool(flag)
    st.save(update_fields=["flagged", "updated_at"])
    return {"flag": st.flagged, "question_id": q.id}


def get_flag(q, user) -> bool:
    st = _state(q, user, create=False)
    return bool(st and st.flagged)


def set_confidence(q, user, rating: int):
    """1..5 confidence rating (clamped)."""
    rating = max(1, min(5, int(rating)))
    st = _state(q, user)
    st.confidence = rating
    st.save(update_fields=["confidence", "updated_at"])
    return {"confidence": rating, "question_id": q.id}


def get_confidence(q, user) -> int:
    st = _state(q, user, create=False)
    return int(st.confidence) if st else 0


def add_time_spent(q, user, seconds: int) -> int:
    """Accumulate seconds spent on a question; returns the new total.

    A single call is capped at 1 hour so a stuck client timer cannot
    inflate study-time statistics.
    """
    from django.db.models import F
    from questions.models import QuestionPracticeState

    seconds = max(0, min(int(seconds), 3600))
    st = _state(q, user)
    if seconds:
        QuestionPracticeState.objects.filter(pk=st.pk).update(
            time_spent_seconds=F("time_spent_seconds") + seconds
        )
        st.refresh_from_db(fields=["time_spent_seconds"])
    return int(st.time_spent_seconds)


def set_elimination(q, user, options: list[str]):
    """Strike-through state. ``options`` is a list of letters (A..E)."""
    if isinstance(options, str):
        options = [o for o in options.split(",")]
    opts = sorted({str(o).strip().upper() for o in (options or []) if str(o).strip()})
    opts = [o for o in opts if o in _VALID_OPTIONS]
    st = _state(q, user)
    st.eliminated_options = opts
    st.save(update_fields=["eliminated_options", "updated_at"])
    return {"eliminated": opts, "question_id": q.id}


def get_state(q, user) -> dict:
    """Return the user's per-question state in one round-trip."""
    from questions.models import QuestionBookmark

    state = {
        "flag": False,
        "confidence": 0,
        "time_spent": 0,
        "eliminated": [],
        "bookmarked": QuestionBookmark.objects.filter(user=user, question=q).exists(),
    }
    st = _state(q, user, create=False)
    if st:
        state.update({
            "flag": bool(st.flagged),
            "confidence": int(st.confidence or 0),
            "time_spent": int(st.time_spent_seconds or 0),
            "eliminated": list(st.eliminated_options or []),
        })
    return state


def record_attempt_stats(user, q, is_correct: bool, seconds: int = 0) -> None:
    """Analytics for a user's FIRST answer to a question-bank question.

    Shared by the question-bank ``attempt`` endpoint and practice mode so
    both count towards topic performance, the daily activity row (which
    drives the "Solve 20 questions" quest) and streak XP. Every counter is
    an atomic ``F()`` increment: the old ``+= 1; save()`` lost updates when
    two tabs answered at the same time.

    ``seconds`` -- the answer time, already clamped by the caller
    (``questions.study_time.clamp_seconds``) -- goes into
    ``UserTopicPerformance.total_time_seconds`` (AN-30: the /analytics
    "Avg Time" column only ever saw test answers). It is added once, with
    the attempt it belongs to, so the average stays time per counted answer.
    """
    from django.db.models import F
    from django.utils import timezone
    from analytics.models import DailyActivity, StudyStreak, UserTopicPerformance

    now = timezone.now()
    perf_inc = {"total_attempts": F("total_attempts") + 1, "last_attempted": now}
    try:
        seconds = max(0, int(seconds or 0))
    except (TypeError, ValueError):
        seconds = 0
    if seconds:
        perf_inc["total_time_seconds"] = F("total_time_seconds") + seconds
    if is_correct:
        perf_inc["correct_answers"] = F("correct_answers") + 1
    else:
        perf_inc["incorrect_answers"] = F("incorrect_answers") + 1

    if q.subject_id:
        if q.topic_id:
            perf, _ = UserTopicPerformance.objects.get_or_create(
                user=user, subject_id=q.subject_id, topic_id=q.topic_id,
            )
            UserTopicPerformance.objects.filter(pk=perf.pk).update(**perf_inc)
        perf_sub, _ = UserTopicPerformance.objects.get_or_create(
            user=user, subject_id=q.subject_id, topic=None,
        )
        UserTopicPerformance.objects.filter(pk=perf_sub.pk).update(**perf_inc)

    activity, _ = DailyActivity.objects.get_or_create(user=user, date=timezone.localdate())
    activity_inc = {"questions_attempted": F("questions_attempted") + 1}
    if is_correct:
        activity_inc["correct_answers"] = F("correct_answers") + 1
    DailyActivity.objects.filter(pk=activity.pk).update(**activity_inc)

    streak, _ = StudyStreak.objects.get_or_create(user=user)
    streak.record_activity()
    streak.add_xp(15 if is_correct else 5)


def submit_attempt(q, user, *, answer: str, correct: bool, time_spent: int = 0,
                   confidence: int | None = None) -> dict:
    """Record the latest practice attempt for this question.

    The returned ``created`` flag is True when this was the user's first
    answer to the question (that is when analytics / quest progress count
    it, exactly like the question-bank ``attempt`` endpoint).
    """
    from questions.models import QuestionAttempt
    from questions.study_time import clamp_seconds, record_study_time

    answer = (answer or "").strip().upper()[:1]
    if not (getattr(q, "correct_answer", "") or "").strip():
        # No answer key: a pick cannot be graded -- never stored as a wrong
        # attempt or a mistake (callers report it as ungraded).
        answer = ""
        correct = False
    seconds = clamp_seconds(time_spent)
    created = False
    if answer:
        attempt, created = QuestionAttempt.objects.update_or_create(
            user=user, question=q,
            defaults={"selected_answer": answer, "is_correct": bool(correct)},
        )
        if not correct:
            from questions.mistakes import record_mistake
            record_mistake(user, q, answer, attempt=attempt)
        if created:
            record_attempt_stats(user, q, bool(correct), seconds=seconds)
    if time_spent:
        add_time_spent(q, user, time_spent)
    if confidence:
        set_confidence(q, user, confidence)
    record_study_time(user, [(q.subject_id, seconds, 1 if answer else 0)])
    return {"question_id": q.id, "correct": bool(correct), "time_spent": time_spent, "created": created}
