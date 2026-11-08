"""How a test attempt is scored, at submit and when it is scored again after an answer-key change.

Submit (``score_submission``): +1 for a correct answer, minus the test's negative mark for a wrong one, out of one
mark per question. A question UPSC dropped from evaluation (``dropped_by_upsc``: ``is_dropped`` on an active
question; ``is_dropped`` on a hidden one means "removed from the bank") is not scored: it adds nothing, costs
nothing and is not part of the total. The attempt lists such questions in ``TestAttempt.not_scored``, and their
``QuestionResponse.is_correct`` is null (the answer chosen is kept).

Scoring again (``rescore_attempt``) starts from the stored figures and changes them only by what the touched
questions change: a key that now accepts another answer, a question UPSC dropped since (or restored), never the
test's current settings (an admin may have edited its negative marking or its questions since): the negative mark
is the one the stored figures were computed with. A change is written only when something differs, with an
``AttemptRescore`` row holding the old and the new figures and every answer whose verdict changed; the attempt
keeps its first score in ``original_score`` / ``original_total_marks``. ``rescore_pending_key_changes`` does that for
every attempt a pending ``AnswerKeyChange`` or a dropped question touches, brings the question-bank answers
(``QuestionAttempt.is_correct``) of the changed questions in line with the current key, and marks the key changes
done with what they affected. A second run changes nothing. XP already earned is left as it is.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from django.db import transaction
from django.db.models import Q
from django.utils import timezone


def dropped_by_upsc(question) -> bool:
    """UPSC dropped the question from evaluation: it stays in the bank (active) but is never scored."""
    return bool(getattr(question, 'is_dropped', False) and getattr(question, 'is_active', True))


def key_of(question) -> str:
    return (getattr(question, 'correct_answer', '') or '').strip().upper()[:1]


def verdict(question, selected) -> bool | None:
    """True / False against the question's current key; None when nothing was selected."""
    selected = (selected or '').strip().upper()[:1]
    if not selected:
        return None
    return selected == key_of(question)


@dataclass(frozen=True)
class Score:
    score: float
    total_marks: int
    correct: int
    incorrect: int
    unanswered: int


def score_submission(test, question_ids, answers, questions):
    """Score a submission. ``question_ids``: the test's questions; ``answers``: {question_id: selected letter or ''}
    (questions of the test only); ``questions``: {question_id: Question} covering both.

    Returns (Score, verdicts {question_id: True / False / None}, sorted list of the question ids not scored)."""
    question_ids = set(question_ids)
    not_scored = {qid for qid in question_ids if qid in questions and dropped_by_upsc(questions[qid])}
    verdicts, correct, incorrect = {}, 0, 0
    for qid, selected in answers.items():
        question = questions.get(qid)
        if question is None:
            continue
        result = None if qid in not_scored else verdict(question, selected)
        verdicts[qid] = result
        if result is True:
            correct += 1
        elif result is False:
            incorrect += 1
    total = len(question_ids) - len(not_scored)
    penalty = incorrect * test.negative_mark_value if test.negative_marking else 0
    score = Score(score=correct - penalty, total_marks=total, correct=correct, incorrect=incorrect,
                  unanswered=max(0, total - correct - incorrect))
    return score, verdicts, sorted(not_scored)


def negative_mark_of(attempt) -> float:
    """The negative mark the attempt's stored score was computed with (from its own figures when it had a wrong
    answer, else the test's setting)."""
    if attempt.incorrect_count and attempt.score is not None:
        value = (attempt.correct_count - attempt.score) / attempt.incorrect_count
        return round(min(max(value, 0.0), 1.0), 4)
    test = attempt.test
    return float(test.negative_mark_value) if test.negative_marking else 0.0


def _contribution(scored, result, mark):
    """(correct, incorrect, unanswered, total, points) one question adds to an attempt's figures."""
    if not scored:
        return (0, 0, 0, 0, 0.0)
    if result is True:
        return (1, 0, 0, 1, 1.0)
    if result is False:
        return (0, 1, 0, 1, -mark)
    return (0, 0, 1, 1, 0.0)


def rescore_attempt(attempt, *, touched, apply, reason, key_change_ids=(), now=None):
    """Score a completed attempt again for the ``touched`` question ids (and the ones it did not score); returns
    what changed (None when nothing did). Writes only with apply."""
    from questions.models import Question
    from tests_engine.models import AttemptRescore, QuestionResponse, TestAttempt

    before_not_scored = set(attempt.not_scored or [])
    relevant = set(touched) | before_not_scored
    responses = {r.question_id: r for r in QuestionResponse.objects.filter(attempt=attempt,
                                                                            question_id__in=relevant)}
    in_test = set(attempt.test.questions.filter(id__in=relevant).values_list('id', flat=True))
    ids = set(responses) | in_test
    questions = Question.objects.only('id', 'correct_answer', 'is_dropped', 'is_active').in_bulk(ids)
    mark = negative_mark_of(attempt)
    delta = [0, 0, 0, 0, 0.0]
    changed, not_scored = [], set(before_not_scored)
    for qid in sorted(ids):
        question = questions.get(qid)
        if question is None:
            continue
        response = responses.get(qid)
        scored_before = qid not in before_not_scored
        scored_now = not dropped_by_upsc(question)
        was = response.is_correct if response is not None else None
        now_result = verdict(question, response.selected_answer) if (response is not None and scored_now) else None
        old = _contribution(scored_before, was if scored_before else None, mark)
        new = _contribution(scored_now, now_result, mark)
        if old == new and was == now_result:
            continue
        for i in range(5):
            delta[i] += new[i] - old[i]
        if scored_now:
            not_scored.discard(qid)
        else:
            not_scored.add(qid)
        changed.append({'question_id': qid, 'selected': response.selected_answer if response else None,
                        'was': was, 'now': now_result, 'scored_before': scored_before, 'scored_now': scored_now})
    if not changed:
        return None
    old_figures = {'score': attempt.score, 'total_marks': attempt.total_marks,
                   'correct_count': attempt.correct_count, 'incorrect_count': attempt.incorrect_count,
                   'unanswered_count': attempt.unanswered_count}
    new_figures = {
        'score': round((attempt.score or 0) + delta[4], 4),
        'total_marks': (attempt.total_marks or 0) + delta[3],
        'correct_count': attempt.correct_count + delta[0],
        'incorrect_count': attempt.incorrect_count + delta[1],
        'unanswered_count': max(0, attempt.unanswered_count + delta[2]),
    }
    summary = {'attempt_id': attempt.pk, 'old': old_figures, 'new': new_figures, 'answers': changed}
    if not apply:
        return summary
    now = now or timezone.now()
    with transaction.atomic():
        locked = TestAttempt.objects.select_for_update().get(pk=attempt.pk)
        if list(locked.not_scored or []) != list(attempt.not_scored or []) or locked.score != attempt.score:
            return None  # changed meanwhile (a concurrent run): left to the next run
        for row in changed:
            QuestionResponse.objects.filter(attempt=locked, question_id=row['question_id']).update(
                is_correct=row['now'])
        AttemptRescore.objects.create(
            attempt=locked, reason=reason[:300], key_changes=list(key_change_ids), negative_mark=mark,
            old_score=old_figures['score'], new_score=new_figures['score'],
            old_total_marks=old_figures['total_marks'], new_total_marks=new_figures['total_marks'],
            old_correct=old_figures['correct_count'], new_correct=new_figures['correct_count'],
            old_incorrect=old_figures['incorrect_count'], new_incorrect=new_figures['incorrect_count'],
            old_unanswered=old_figures['unanswered_count'], new_unanswered=new_figures['unanswered_count'],
            answers=changed)
        updates = dict(new_figures, rescored_at=now, not_scored=sorted(not_scored))
        if locked.rescored_at is None:
            updates.update(original_score=old_figures['score'], original_total_marks=old_figures['total_marks'])
        TestAttempt.objects.filter(pk=locked.pk).update(**updates)
    return summary


def rescore_pending_key_changes(*, apply, limit=None, log=None, change_ids=None):
    """Score again every completed attempt touched by a pending AnswerKeyChange or by a question UPSC dropped (or
    restored), align the question-bank answers of the changed questions, and mark the pending changes done.
    ``change_ids``: only these pending changes (dropped questions are then left for a full run).

    Returns a Counter of what was (or, in a dry run, would be) changed."""
    from questions.models import AnswerKeyChange, MistakeNotebook, Question, QuestionAttempt
    from tests_engine.models import QuestionResponse, TestAttempt

    log = log or (lambda message: None)
    stats = Counter()
    now = timezone.now()
    pending = AnswerKeyChange.objects.filter(rescore_status='pending').order_by('changed_at', 'pk')
    if change_ids is not None:
        pending = pending.filter(pk__in=change_ids)
    pending = list(pending)
    changes_by_question = defaultdict(list)
    for change in pending:
        changes_by_question[change.question_id].append(change.pk)
    dropped_ids = set() if change_ids is not None else set(
        Question.objects.filter(is_dropped=True, is_active=True).values_list('id', flat=True))
    touched = set(changes_by_question) | dropped_ids
    stats['pending key changes'] = len(pending)
    stats['questions dropped by UPSC'] = len(dropped_ids)

    completed = TestAttempt.objects.filter(is_completed=True)
    attempt_ids = set(QuestionResponse.objects.filter(attempt__is_completed=True, question_id__in=touched)
                      .values_list('attempt_id', flat=True))
    if change_ids is None:
        attempt_ids |= set(completed.filter(test__questions__in=dropped_ids).values_list('id', flat=True))
        attempt_ids |= set(completed.exclude(not_scored=[]).values_list('id', flat=True))
    attempts = completed.filter(id__in=attempt_ids).select_related('test').order_by('pk')
    if limit:
        attempts = attempts[:limit]
    per_change = Counter()
    for attempt in attempts.iterator(chunk_size=200):
        stats['attempts checked'] += 1
        result = rescore_attempt(attempt, touched=touched, apply=False, reason='')
        if result is None:
            continue
        change_ids = sorted({cid for row in result['answers'] for cid in changes_by_question.get(row['question_id'], [])})
        if apply:
            result = rescore_attempt(attempt, touched=touched, apply=True, reason=_reason(result, change_ids),
                                     key_change_ids=change_ids, now=now)
            if result is None:
                stats['attempts left (changed meanwhile)'] += 1
                continue
        stats['attempts rescored'] += 1
        stats['answers re-marked'] += len(result['answers'])
        for cid in change_ids:
            per_change[cid] += 1
        log(f"attempt {attempt.pk}: {result['old']['score']} / {result['old']['total_marks']} -> "
            f"{result['new']['score']} / {result['new']['total_marks']} ({len(result['answers'])} answer(s))")

    # question-bank answers (each student's latest pick) of the changed questions, against the current key
    bank_by_question = Counter()
    for qid in changes_by_question:
        question = Question.objects.only('id', 'correct_answer').get(pk=qid)
        key = key_of(question)
        if not key:
            continue
        wrong_now = QuestionAttempt.objects.filter(question_id=qid, is_correct=True).filter(~Q(selected_answer=key))
        right_now = QuestionAttempt.objects.filter(question_id=qid, is_correct=False, selected_answer=key)
        count = wrong_now.count() + right_now.count()
        if apply and count:
            wrong_now.update(is_correct=False)
            right_now.update(is_correct=True)
        stats['question-bank answers re-marked'] += count
        bank_by_question[qid] = count
        # notebook entries the corrected key now accepts stay in place; the notebook stops listing them
        # (analytics.views._notebook_queryset)
        stats['notebook entries now correct'] += MistakeNotebook.objects.filter(question_id=qid,
                                                                                selected_answer=key).count()

    if apply:
        for change in pending:
            change.rescore_status = 'done'
            change.rescored_at = now
            change.affected = {'test_attempts': per_change.get(change.pk, 0),
                               'qbank_attempts': bank_by_question.get(change.question_id, 0)}
            change.save(update_fields=['rescore_status', 'rescored_at', 'affected'])
        stats['key changes marked done'] = len(pending)
    return stats


def _reason(preview, change_ids):
    parts = []
    if change_ids:
        parts.append('answer-key change ' + ', '.join(f'#{c}' for c in change_ids))
    if any(not row['scored_now'] for row in preview['answers']):
        parts.append('question(s) dropped by UPSC not scored')
    if any(row['scored_now'] and not row['scored_before'] for row in preview['answers']):
        parts.append('question(s) scored again')
    return 'Scored again: ' + '; '.join(parts or ['key now accepts another answer'])
