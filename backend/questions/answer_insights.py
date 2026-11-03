"""Answer log, per-option answer distribution and per-question attempt history (2026-11).

* ``log_answer`` appends one ``QuestionAttemptLog`` row per question-bank / practice answer
  (``QuestionAttempt`` keeps only the latest pick). It never raises and never breaks the answer
  submission (a savepoint isolates its insert). It runs whatever the flag says, so the log has
  no gaps when the read side is switched on.
* ``option_distribution`` counts each student's FIRST pick only (the earlier of their first
  logged answer and their earliest completed test answer); admins and staff are excluded;
  below ``MIN_SAMPLE`` students the counts are withheld so a small sample does not reveal
  individual answers. Cached for ``CACHE_SECONDS`` (invalidated by a new first answer).
* ``attempt_history`` merges the caller's logged answers with their completed test answers.

The read side (answer-stats / attempt-history endpoints, ``answer_stats`` in the attempt
responses) is behind ``ANSWER_INSIGHTS`` (setting, else env; default off). Not an answer-key
signal: the distribution says how students answered, never what is right.
"""
from __future__ import annotations

import logging
import os

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q

from questions.content_hashes import valid_key

logger = logging.getLogger(__name__)

MIN_SAMPLE = 5
CACHE_SECONDS = 600
HISTORY_LIMIT = 50
LETTERS = ('A', 'B', 'C', 'D')
SOURCES = ('bank', 'practice')
_MAX_SECONDS = 3600


def insights_enabled() -> bool:
    value = getattr(settings, 'ANSWER_INSIGHTS', None)
    if value is None:
        value = os.getenv('ANSWER_INSIGHTS', '0')
    if isinstance(value, bool):
        return value
    return str(value or '').strip().lower() in ('1', 'true', 'yes', 'on')


def distribution_cache_key(question_id) -> str:
    return f'qstats:dist:v1:{question_id}'


def _letter(value) -> str:
    letter = str(value or '').strip().upper()[:1]
    return letter if letter in 'ABCDE' and letter else ''


def _excluded_user(user) -> bool:
    return bool(getattr(user, 'role', '') == 'admin' or getattr(user, 'is_staff', False)
                or getattr(user, 'is_superuser', False))


def log_answer(user, question, selected, is_correct, source, seconds=0) -> None:
    """Append one answer to the log. ``is_correct`` None = the question had no valid key.
    Never raises."""
    try:
        if user is None or not getattr(user, 'is_authenticated', False) or question is None:
            return
        letter = _letter(selected)
        if not letter or source not in SOURCES:
            return
        try:
            seconds = max(0, min(int(seconds or 0), _MAX_SECONDS))
        except (TypeError, ValueError):
            seconds = 0
        from questions.models import QuestionAttemptLog

        question_id = getattr(question, 'pk', question)
        with transaction.atomic():
            first = not QuestionAttemptLog.objects.filter(user=user, question_id=question_id).exists()
            QuestionAttemptLog.objects.create(
                user=user, question_id=question_id, selected_answer=letter,
                is_correct=None if is_correct is None else bool(is_correct), source=source,
                time_spent_seconds=seconds, is_first=first,
            )
        if first:
            cache.delete(distribution_cache_key(question_id))
    except Exception:  # noqa: BLE001 - the log must never break an answer submission
        logger.warning('log_answer failed for user=%s question=%s', getattr(user, 'pk', None),
                       getattr(question, 'pk', question), exc_info=True)


def _first_picks(question_ids) -> dict:
    """``{question_id: {user_id: letter}}``: each non-staff user's earliest pick (log or test)."""
    from questions.models import QuestionAttemptLog
    from tests_engine.models import QuestionResponse

    staff = Q(user__role='admin') | Q(user__is_staff=True) | Q(user__is_superuser=True)
    earliest = {}
    for qid, user_id, letter, at in QuestionAttemptLog.objects.filter(question_id__in=question_ids).exclude(
            staff).values_list('question_id', 'user_id', 'selected_answer', 'created_at'):
        current = earliest.get((qid, user_id))
        if current is None or at < current[0]:
            earliest[(qid, user_id)] = (at, letter)
    test_staff = (Q(attempt__user__role='admin') | Q(attempt__user__is_staff=True)
                  | Q(attempt__user__is_superuser=True))
    responses = QuestionResponse.objects.filter(
        question_id__in=question_ids, attempt__is_completed=True,
    ).exclude(selected_answer__isnull=True).exclude(selected_answer='').exclude(test_staff).values_list(
        'question_id', 'attempt__user_id', 'selected_answer', 'attempt__completed_at', 'attempt__started_at')
    for qid, user_id, letter, completed_at, started_at in responses:
        at = completed_at or started_at
        if at is None:
            continue
        current = earliest.get((qid, user_id))
        if current is None or at < current[0]:
            earliest[(qid, user_id)] = (at, letter)
    out = {qid: {} for qid in question_ids}
    for (qid, user_id), (_at, letter) in earliest.items():
        letter = _letter(letter)
        if letter in LETTERS:
            out[qid][user_id] = letter
    return out


def _raw_counts(question_ids) -> dict:
    """``{question_id: {'total', 'counts'}}`` from the cache, computing the misses in bulk."""
    keys = {qid: distribution_cache_key(qid) for qid in question_ids}
    try:
        cached = cache.get_many(list(keys.values()))
    except Exception:  # noqa: BLE001 - a cache outage only costs the recomputation
        cached = {}
    out = {qid: cached[key] for qid, key in keys.items() if key in cached}
    missing = [qid for qid in question_ids if qid not in out]
    if missing:
        fresh = {}
        for qid, picks in _first_picks(missing).items():
            counts = {letter: 0 for letter in LETTERS}
            for letter in picks.values():
                counts[letter] += 1
            fresh[qid] = {'total': sum(counts.values()), 'counts': counts}
        try:
            cache.set_many({keys[qid]: value for qid, value in fresh.items()}, CACHE_SECONDS)
        except Exception:  # noqa: BLE001
            pass
        out.update(fresh)
    return out


def _shape(question_id, raw: dict, key: str) -> dict:
    total = int(raw.get('total') or 0)
    payload = {'question_id': question_id, 'total': total, 'min_sample': MIN_SAMPLE,
               'below_threshold': total < MIN_SAMPLE}
    if total >= MIN_SAMPLE:
        counts = {letter: int(raw['counts'].get(letter, 0)) for letter in LETTERS}
        payload['counts'] = counts
        payload['percent'] = {letter: round(100.0 * n / total, 1) for letter, n in counts.items()}
        payload['correct_share'] = round(100.0 * counts[key] / total, 1) if key in counts else None
    return payload


def option_distributions(questions) -> dict:
    """Bulk ``option_distribution``: ``{question_id: payload}`` for Question instances."""
    questions = [q for q in questions if q is not None]
    raw = _raw_counts([q.pk for q in questions])
    return {q.pk: _shape(q.pk, raw.get(q.pk) or {}, valid_key(q.correct_answer)) for q in questions}


def option_distribution(question) -> dict:
    """``{question_id, total, min_sample, below_threshold[, counts, percent, correct_share]}``:
    how students first answered (counts withheld below MIN_SAMPLE). ``correct_share`` uses the
    current key (the cache holds only the counts, so a key change needs no invalidation)."""
    return option_distributions([question])[question.pk]


def first_answer(user, question) -> str:
    """The caller's first pick on ``question`` ('' when they have not answered it)."""
    from questions.models import QuestionAttemptLog
    from tests_engine.models import QuestionResponse

    candidates = []
    row = QuestionAttemptLog.objects.filter(user=user, question=question).order_by('created_at', 'id').values_list(
        'created_at', 'selected_answer').first()
    if row:
        candidates.append(row)
    for completed_at, started_at, letter in QuestionResponse.objects.filter(
            attempt__user=user, attempt__is_completed=True, question=question,
    ).exclude(selected_answer__isnull=True).exclude(selected_answer='').values_list(
            'attempt__completed_at', 'attempt__started_at', 'selected_answer'):
        at = completed_at or started_at
        if at is not None:
            candidates.append((at, letter))
    if not candidates:
        return ''
    return _letter(min(candidates, key=lambda item: item[0])[1])


def has_answered(user, question) -> bool:
    return bool(first_answer(user, question))


def stats_for_viewer(user, question) -> dict:
    """The distribution plus ``your_first_answer`` (entitlement checked by the caller)."""
    payload = option_distribution(question)
    payload['your_first_answer'] = first_answer(user, question) or None
    return payload


def response_fields(user, question) -> dict:
    """``{'answer_stats': ...}`` for the attempt responses when ANSWER_INSIGHTS is on, else {}.
    Never raises (an answer submission must not fail on its statistics)."""
    if not insights_enabled():
        return {}
    try:
        return {'answer_stats': stats_for_viewer(user, question)}
    except Exception:  # noqa: BLE001
        logger.warning('answer stats failed for question=%s', getattr(question, 'pk', None), exc_info=True)
        return {}


def attempt_history(user, question, *, can_view_answer: bool, limit=HISTORY_LIMIT) -> dict:
    """The caller's answers to ``question``, newest first: logged bank / practice answers and
    completed test answers. Without ``can_view_answer`` every ``is_correct`` is null and
    ``answer_locked`` is true (a right / wrong verdict identifies a locked question's answer)."""
    from questions.models import QuestionAttemptLog
    from tests_engine.models import QuestionResponse
    from tests_engine.serializers import public_test_title

    items = []
    for row in QuestionAttemptLog.objects.filter(user=user, question=question).order_by('-created_at', '-id')[:limit]:
        items.append({
            'source': row.source, 'at': row.created_at, 'selected_answer': row.selected_answer,
            'is_correct': row.is_correct, 'time_spent_seconds': row.time_spent_seconds,
            'test_id': None, 'attempt_id': None, 'test_title': '',
        })
    responses = QuestionResponse.objects.filter(
        attempt__user=user, attempt__is_completed=True, question=question,
    ).select_related('attempt__test').order_by('-attempt__completed_at', '-attempt_id')[:limit]
    for response in responses:
        attempt = response.attempt
        items.append({
            'source': 'test', 'at': attempt.completed_at or attempt.started_at,
            'selected_answer': response.selected_answer or '', 'is_correct': response.is_correct,
            'time_spent_seconds': response.time_taken_seconds or 0, 'test_id': attempt.test_id,
            'attempt_id': attempt.pk, 'test_title': public_test_title(getattr(attempt.test, 'title', '') or ''),
        })
    items = [item for item in items if item['at'] is not None]
    items.sort(key=lambda item: item['at'], reverse=True)
    items = items[:limit]
    if not can_view_answer:
        for item in items:
            item['is_correct'] = None
    answered = [item for item in items if item['selected_answer']]
    graded = [item for item in answered if item['is_correct'] is not None]
    summary = {
        'count': len(answered),
        'correct': sum(1 for item in graded if item['is_correct']) if can_view_answer else None,
        'first_answer': answered[-1]['selected_answer'] if answered else None,
        'last_answer': answered[0]['selected_answer'] if answered else None,
        'last_correct': answered[0]['is_correct'] if answered else None,
    }
    for item in items:
        item['at'] = item['at'].isoformat()
    return {'question_id': question.pk, 'items': items, 'summary': summary, 'answer_locked': not can_view_answer}
