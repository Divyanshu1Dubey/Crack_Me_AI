"""Automatic Mistake Notebook capture.

Every wrong answer (question-bank answer, practice-mode attempt, test
submission) is recorded once per (user, question). Previously nothing in the
app created MistakeNotebook rows, so the Mistake Notebook was always empty.
"""
from __future__ import annotations

import logging

from django.db import IntegrityError
from django.utils import timezone

logger = logging.getLogger(__name__)


def _letter(value) -> str:
    return (str(value or '').strip().upper() or '?')[:1]


def record_mistake(user, question, selected_answer, attempt=None):
    """Add (or refresh) a Mistake Notebook entry for a wrong answer.

    Never raises: mistake capture must not break answer submission.
    """
    if user is None or not getattr(user, 'is_authenticated', False) or question is None:
        return None
    try:
        from questions.models import MistakeNotebook

        entry, created = MistakeNotebook.objects.get_or_create(
            user=user,
            question=question,
            defaults={
                'selected_answer': _letter(selected_answer),
                'correct_answer': _letter(getattr(question, 'correct_answer', '')),
                'is_correct': False,
                'attempt': attempt,
                'review_status': 'new',
                'next_review_at': timezone.now(),
            },
        )
        if not created:
            # Answered wrong again: back to the front of the review queue.
            fields = {'selected_answer': _letter(selected_answer), 'is_correct': False,
                      'next_review_at': timezone.now()}
            if entry.review_status == 'mastered':
                fields['review_status'] = 'learning'
            MistakeNotebook.objects.filter(pk=entry.pk).update(**fields)
        return entry
    except IntegrityError:
        return None
    except Exception:  # pragma: no cover - defensive
        logger.exception('record_mistake failed for user=%s question=%s', getattr(user, 'pk', None), getattr(question, 'pk', None))
        return None


def record_mistakes_bulk(user, wrong_pairs):
    """wrong_pairs: iterable of (question, selected_answer)."""
    for question, selected in wrong_pairs:
        record_mistake(user, question, selected)
