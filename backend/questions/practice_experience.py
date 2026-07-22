"""Phase 3 practice-experience helpers.

Additive on top of Phase-2 `Question`, `QuestionBookmark`, `Note`,
`Flashcard`, `Attempt` rows.  Endpoints registered from views.py:

* flag / unflag
* confidence_rating (1..5)
* time_spent_seconds (per-session)
* elimination toggle (per-question option-level strike-through)
* reveal + explanation
* ai_clinical + memory_trick + related_pyqs (delegated to ai_per_question)

Storage:
- Flag/confidence/time -> `QuestionExtractionItem.metadata` JSON field is
  the existing free-form bucket.  We extend it without breaking
  semantics.
- Elimination -> a small per-user per-question list of strike options
  stored in `QuestionBookmark.notes` (re-used as scratch storage).
  (Phase-4 will introduce a dedicated `QuestionAttemptState` model.)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

LOG = logging.getLogger(__name__)


def set_flag(q, user, flag: bool):
    """Persist flag state on the user's bookmark/notes slot.

    Phase-3 keeps storage light: a single field on `QuestionBookmark.notes`
    encodes `flag:<bool>`.  When the user never bookmarked, we create a
    bookmark with `is_active=False` so the flag persists across sessions
    without polluting the bookmark list.
    """
    from questions.models import QuestionBookmark
    bookmark, _ = QuestionBookmark.objects.get_or_create(
        user=user, question=q,
        defaults={"is_active": False, "notes": ""},
    )
    prefix = "flag:1" if flag else "flag:0"
    parts = []
    for line in (bookmark.notes or "").splitlines():
        if not line.startswith("flag:"):
            parts.append(line)
    parts.insert(0, prefix)
    bookmark.notes = "\n".join(parts)
    bookmark.save(update_fields=["notes", "updated_at"] if hasattr(bookmark, "updated_at") else ["notes"])
    return {"flag": flag, "question_id": q.id}


def get_flag(q, user) -> bool:
    from questions.models import QuestionBookmark
    bookmark = QuestionBookmark.objects.filter(user=user, question=q).first()
    if not bookmark or not bookmark.notes:
        return False
    first = (bookmark.notes or "").splitlines()[0] if bookmark.notes else ""
    return first.startswith("flag:1")


def set_confidence(q, user, rating: int):
    """1..5 confidence rating.  Stored on the bookmark notes field."""
    rating = max(1, min(5, int(rating)))
    from questions.models import QuestionBookmark
    bookmark, _ = QuestionBookmark.objects.get_or_create(
        user=user, question=q,
        defaults={"is_active": False, "notes": ""},
    )
    new_lines = []
    for line in (bookmark.notes or "").splitlines():
        if not line.startswith("conf:"):
            new_lines.append(line)
    new_lines.insert(0, f"conf:{rating}")
    bookmark.notes = "\n".join(new_lines)
    bookmark.save(update_fields=["notes"])
    return {"confidence": rating, "question_id": q.id}


def get_confidence(q, user) -> int:
    from questions.models import QuestionBookmark
    bookmark = QuestionBookmark.objects.filter(user=user, question=q).first()
    if not bookmark or not bookmark.notes:
        return 0
    for line in (bookmark.notes or "").splitlines():
        if line.startswith("conf:"):
            try:
                return int(line.split(":", 1)[1])
            except ValueError:
                return 0
    return 0


def add_time_spent(q, user, seconds: int) -> int:
    """Accumulate seconds on the bookmark notes field."""
    seconds = max(0, int(seconds))
    from questions.models import QuestionBookmark
    bookmark, _ = QuestionBookmark.objects.get_or_create(
        user=user, question=q,
        defaults={"is_active": False, "notes": ""},
    )
    total = 0
    new_lines = []
    for line in (bookmark.notes or "").splitlines():
        if line.startswith("time:"):
            try:
                total = int(line.split(":", 1)[1])
            except ValueError:
                total = 0
            continue
        new_lines.append(line)
    total += seconds
    new_lines.insert(0, f"time:{total}")
    bookmark.notes = "\n".join(new_lines)
    bookmark.save(update_fields=["notes"])
    return total


def set_elimination(q, user, options: list[str]):
    """Strike-through state. `options` is a list of letters (A,B,C,D)."""
    opts = [str(o).upper() for o in (options or []) if o]
    from questions.models import QuestionBookmark
    bookmark, _ = QuestionBookmark.objects.get_or_create(
        user=user, question=q,
        defaults={"is_active": False, "notes": ""},
    )
    new_lines = []
    for line in (bookmark.notes or "").splitlines():
        if not line.startswith("elim:"):
            new_lines.append(line)
    new_lines.insert(0, "elim:" + ",".join(sorted(set(opts))))
    bookmark.notes = "\n".join(new_lines)
    bookmark.save(update_fields=["notes"])
    return {"eliminated": opts, "question_id": q.id}


def get_state(q, user) -> dict:
    """Return the user's per-question state in one round-trip."""
    from questions.models import QuestionBookmark
    bookmark = QuestionBookmark.objects.filter(user=user, question=q).first()
    state = {
        "flag": False,
        "confidence": 0,
        "time_spent": 0,
        "eliminated": [],
        "bookmarked": False,
    }
    if not bookmark:
        return state
    state["bookmarked"] = bool(bookmark.is_active)
    for line in (bookmark.notes or "").splitlines():
        if line.startswith("flag:1"):
            state["flag"] = True
        elif line.startswith("conf:"):
            try:
                state["confidence"] = int(line.split(":", 1)[1])
            except ValueError:
                pass
        elif line.startswith("time:"):
            try:
                state["time_spent"] = int(line.split(":", 1)[1])
            except ValueError:
                pass
        elif line.startswith("elim:"):
            state["eliminated"] = [o for o in line.split(":", 1)[1].split(",") if o]
    return state


def submit_attempt(q, user, *, answer: str, correct: bool, time_spent: int = 0,
                   confidence: int | None = None) -> dict:
    """One-row audit log per attempt.  Writes `analytics.TestAttempt`.

    Falls back to `QuestionAIOperationLog` if the analytics app isn't
    installed in the current deployment.
    """
    try:
        from analytics.models import TestAttempt
        TestAttempt.objects.create(
            user=user,
            question=q,
            submitted_answer=answer,
            is_correct=bool(correct),
            time_spent_seconds=int(time_spent or 0),
            confidence_rating=int(confidence or 0) or None,
        )
    except Exception as e:
        LOG.debug("TestAttempt unavailable, falling back to AI log: %s", e)
        from questions.models import QuestionAIOperationLog
        QuestionAIOperationLog.objects.create(
            question=q,
            operation_type="practice_attempt",
            model_version="phase3",
            success=bool(correct),
            log={
                "answer": answer,
                "time_spent": time_spent,
                "confidence": confidence,
                "at": datetime.now(tz=timezone.utc).isoformat(),
            },
        )
    if time_spent:
        add_time_spent(q, user, time_spent)
    if confidence:
        set_confidence(q, user, confidence)
    return {"question_id": q.id, "correct": bool(correct), "time_spent": time_spent}
