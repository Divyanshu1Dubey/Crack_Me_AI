"""The scholarship challenge's question pool (2026-11-07).

``accounts.views.ScholarshipStartView`` draws five questions flagged ``is_scholarship_eligible`` and
shows each one as plain text with its four options (no figure, no explanation); a student needs 5/5.
So a pool question has to stand on its own text, carry a valid key and never be free content (its
answer would be public). ``pool_refusal`` says why a question cannot join; the admin endpoint
(``PATCH /api/questions/<id>/scholarship/``) and ``manage.py apply_scholarship_pool`` both use it.

Joining the pool does not verify a key: the question keeps its stored key, untouched. A pool file
(``fixtures/scholarship_pool.json``) pins the key and the stem/options hash of the version that was
reviewed, so a question edited since is skipped instead of joining unseen.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

POOL_FORMAT = 'scholarship-pool/1'

REFUSALS = {
    'inactive': 'The question is not active in the bank.',
    'dropped': 'The question was dropped from its paper.',
    'no_key': 'The question has no answer key A-D.',
    'missing_option': 'The challenge needs all four options.',
    'figure': 'The challenge shows text only, and this question has a figure.',
    'image_token': 'The stem or an option points at a figure.',
    'showcase': 'The question is in the free showcase, so its answer is public.',
    'disputed': 'The question is disputed.',
    'controversial': 'The question is marked controversial.',
    'needs_review': 'The question is waiting for review.',
}
# Pool-file checks on top of the refusals above.
FILE_SKIPS = {
    'missing': 'No question with this id.',
    'key_changed': 'The stored key is not the key the pool file was reviewed for.',
    'content_changed': 'The stem or an option changed since the pool file was reviewed.',
}
_SHOWN_FIELDS = ('question_text', 'option_a', 'option_b', 'option_c', 'option_d')
_HASH_RE = re.compile(r'^[0-9a-f]{64}$')


def _models(question_model=None, showcase_model=None):
    """The live models, or the historical ones a data migration passes in."""
    if question_model is None:
        from questions.models import Question as question_model
    if showcase_model is None:
        from accounts.models_freemium import FreeShowcaseQuestion as showcase_model
    return question_model, showcase_model


def pool_refusal(question, showcase_model=None) -> Optional[str]:
    """Why ``question`` cannot be in the scholarship challenge (a ``REFUSALS`` code), or None."""
    from questions.content_hashes import valid_key
    from questions.image_context import TOKEN_RE

    _, FreeShowcaseQuestion = _models(showcase_model=showcase_model)
    if not question.is_active:
        return 'inactive'
    if question.is_dropped:
        return 'dropped'
    if not valid_key(question.correct_answer):
        return 'no_key'
    if any(not (getattr(question, f'option_{letter}') or '').strip() for letter in 'abcd'):
        return 'missing_option'
    if question.is_image_based or question.images.filter(is_active=True).exists():
        return 'figure'
    if any(TOKEN_RE.search(getattr(question, name) or '') for name in _SHOWN_FIELDS):
        return 'image_token'
    if FreeShowcaseQuestion.objects.filter(question_id=question.pk).exists():
        return 'showcase'
    if question.is_disputed:
        return 'disputed'
    if question.is_controversial:
        return 'controversial'
    if question.needs_review:
        return 'needs_review'
    return None


def load_pool(path) -> dict:
    """The pool file, checked: ``{'questions': [{'id', 'key', 'stem_hash', ...}], ...}``."""
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('format') != POOL_FORMAT:
        raise ValueError(f'not a {POOL_FORMAT} file')
    seen = set()
    for row in data.get('questions') or []:
        qid, key, digest = row.get('id'), row.get('key'), row.get('stem_hash')
        if not isinstance(qid, int) or isinstance(qid, bool) or qid in seen:
            raise ValueError(f'bad or repeated question id: {qid!r}')
        if key not in ('A', 'B', 'C', 'D') or not isinstance(digest, str) or not _HASH_RE.match(digest):
            raise ValueError(f'question {qid}: key must be A-D and stem_hash a sha256 hex digest')
        seen.add(qid)
    if not seen:
        raise ValueError('the pool file lists no questions')
    return data


def plan_pool(entries, question_model=None, showcase_model=None) -> list:
    """``[{'id', 'action': 'add' | 'already' | 'skip', 'reason'}]`` for the pool file's entries."""
    from questions.content_hashes import stem_hash, valid_key

    Question, showcase_model = _models(question_model, showcase_model)
    found = Question.objects.in_bulk([row['id'] for row in entries])
    plan = []
    for row in entries:
        question = found.get(row['id'])
        if question is None:
            reason = 'missing'
        elif valid_key(question.correct_answer) != row['key']:
            reason = 'key_changed'
        elif stem_hash(question) != row['stem_hash']:
            reason = 'content_changed'
        else:
            reason = pool_refusal(question, showcase_model=showcase_model)
        if reason:
            plan.append({'id': row['id'], 'action': 'skip', 'reason': reason})
        else:
            plan.append({'id': row['id'], 'action': 'already' if question.is_scholarship_eligible else 'add',
                         'reason': ''})
    return plan


def set_eligible(question_ids, eligible: bool, question_model=None) -> int:
    """Flag (or unflag) these questions; returns how many changed. ``save(update_fields=...)``, so the
    post_save receivers see exactly which field changed."""
    from django.db import transaction

    Question, _ = _models(question_model, showcase_model=False)
    changed = 0
    with transaction.atomic():
        for question in Question.objects.select_for_update().filter(pk__in=list(question_ids)):
            if question.is_scholarship_eligible != eligible:
                question.is_scholarship_eligible = eligible
                question.save(update_fields=['is_scholarship_eligible'])
                changed += 1
    return changed


def eligible_count(question_model=None) -> int:
    """What ScholarshipStartView draws from."""
    Question, _ = _models(question_model, showcase_model=False)
    return Question.objects.filter(is_scholarship_eligible=True, is_active=True).count()
