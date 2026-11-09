"""Batch AI explanations for the questions that have no usable one (docs/EXPLANATION_BATCH.md).

Selection (``needs_explanation``): active questions with a valid key (A-D) whose ``explanation`` is empty, a
placeholder or only image tokens, or was written for another key (a corrected key). Never a locked explanation, never
a question with a figure (the model cannot see it: a human writes those).

Generation (``process_item``): ``AIService.explain_after_answer``, which answers the question itself and says when it
disagrees with the key. The explanation is saved only when

* the model's answer is the stored key (otherwise the item is ``disagrees``: nothing is saved, the question is listed
  for an editor, who checks the key),
* the output passes the schema checks (why the key is right, at least two wrong options explained, text only: no
  provider error, no "as an AI" text),

and never carries the model's textbook / page references: they are not retrieved sources, so reference lines and
"(Harrison, p. 1234)"-style citations are removed and the ``textbook_reference`` / ``similar_pyq`` parts are not
used. Verified citations come only from the evidence app (quotes checked on the page). The text is composed from its
parts (answer, why it is right, why each other option is wrong, high-yield points, clinical pearl; the core concept
and the mnemonic in their own fields) and saved through ``editorial.save_explanation``: explanation_status
``ai_generated``, written for the stored key and the current stem. Students see it labelled "AI-generated, not yet
reviewed" until an admin reviews it (``review_queue``).

Checkpoints: one ``ExplanationBatchItem`` per question and run. An item is claimed (``claimed_until``) with a
conditional UPDATE before generation, so two workers never take the same question and an interrupted run resumes
where it stopped; an AI outage puts the item back (retried later, at most ``MAX_ATTEMPTS`` times); before saving, the
question is checked again (an admin edit or a new key since it was queued wins).
"""
from __future__ import annotations

import re
import time
from collections import Counter
from datetime import timedelta

from django.db.models import Count, F, Q
from django.utils import timezone

PLACEHOLDERS = ('Reference: NEET PG previous year question bank.',)
TOKENS_ONLY = r'^(\s*\[\[img:\d+\]\]\s*)+$'
MAX_ATTEMPTS = 3
LEASE_SECONDS = 600
KEYS = ('A', 'B', 'C', 'D')

_REFERENCE_LINE = re.compile(r'(?im)^[ \t]*[*_>\-#]*[ \t]*(textbook[ \t]+)?(references?|sources?|ref|citations?)'
                             r'[ \t]*[*_]*[ \t]*[:\-].*(?:\r?\n|$)')
_PAREN_CITATION = re.compile(r'[ \t]*\((?=[^()]*\d)[^()]*\b(p|pp|pg|page|pages|chapter|chap|ch|edition|ed|vol)\b\.?'
                             r'[ \t]*\d[^()]*\)', re.I)
_CITE_ARTEFACT = re.compile(r'\[(cite|citation|source)[^\]]*\]', re.I)
_REFUSE = re.compile(r'(?i)\b(rate[ -]?limit|quota (exceeded|exhausted)|as an ai( language model)?|api key|'
                     r'i (cannot|can\'t) (access|browse|see the image)|internal server error)\b')


def key_of(question) -> str:
    return (getattr(question, 'correct_answer', '') or '').strip().upper()[:1]


def _missing_q():
    return (Q(explanation='') | Q(explanation__isnull=True) | Q(explanation__in=PLACEHOLDERS)
            | Q(explanation__regex=TOKENS_ONLY))


def _stale_q():
    return (Q(explanation_status='stale', explanation_status_reason__startswith='Key changed')
            | (Q(explanation_for_key__gt='') & ~Q(explanation_for_key=F('correct_answer'))))


def needs_explanation(*, exam_type=None, years=None, include_stale=True):
    """Active questions with a valid key and no usable explanation (no locked text, no figure questions)."""
    from questions.models import Question

    wanted = _missing_q() | _stale_q() if include_stale else _missing_q()
    qs = (Question.objects.filter(is_active=True, correct_answer__in=[*KEYS, *(k.lower() for k in KEYS)],
                                  lock_explanation=False)
          .filter(wanted)
          .exclude(is_image_based=True)
          .exclude(images__role='primary', images__is_active=True))
    if exam_type:
        qs = qs.filter(exam_type=exam_type)
    if years:
        qs = qs.filter(year__in=list(years))
    return qs.distinct()


def needed_by_exam(**filters) -> dict:
    """{exam_type: number of questions that need an explanation} (counted over ids: needs_explanation is DISTINCT,
    and a DISTINCT values_list would count exam_type x default-ordering combinations instead)."""
    from questions.models import Question

    ids = needs_explanation(**filters).order_by().values('pk')
    rows = Question.objects.filter(pk__in=ids).order_by().values('exam_type').annotate(n=Count('id'))
    return {row['exam_type']: row['n'] for row in rows}


def _has_figure(question) -> bool:
    return bool(question.is_image_based) or question.images.filter(role='primary', is_active=True).exists()


def still_needed(question, item) -> str:
    """'' when the question still needs this explanation, else why it is skipped."""
    from questions.content_hashes import stem_hash

    if not question.is_active:
        return 'question hidden since it was queued'
    if key_of(question) != item.key:
        return 'answer key changed since it was queued'
    if stem_hash(question) != item.stem_hash:
        return 'question edited since it was queued'
    if question.lock_explanation:
        return 'explanation locked by an admin'
    if _has_figure(question):
        return 'figure question: a human writes this explanation'
    text = (question.explanation or '').strip()
    missing = not text or text in PLACEHOLDERS or re.match(TOKENS_ONLY, text)
    for_other_key = (question.explanation_for_key and question.explanation_for_key != key_of(question)) or (
        question.explanation_status == 'stale' and (question.explanation_status_reason or '').startswith('Key changed'))
    if not missing and not for_other_key:
        return 'has an explanation now'
    return ''


def create_run(*, exam_type=None, years=None, include_stale=True, limit=None, user=None, note=''):
    """A run with one queued item per question that needs an explanation (oldest question first)."""
    from questions.content_hashes import stem_hash
    from questions.models import ExplanationBatchItem, ExplanationBatchRun, Question

    ids = list(needs_explanation(exam_type=exam_type, years=years, include_stale=include_stale)
               .order_by('pk').values_list('pk', flat=True))
    if limit:
        ids = ids[:limit]
    run = ExplanationBatchRun.objects.create(
        created_by=user if getattr(user, 'is_authenticated', False) else None, note=note[:200],
        scope={'exam_type': exam_type or '', 'years': list(years or []), 'include_stale': include_stale,
               'limit': limit or 0})
    items = []
    for q in Question.objects.filter(pk__in=ids).only('id', 'correct_answer', 'question_text', 'option_a', 'option_b',
                                                      'option_c', 'option_d').iterator(chunk_size=500):
        items.append(ExplanationBatchItem(run=run, question_id=q.pk, key=key_of(q), stem_hash=stem_hash(q)))
    ExplanationBatchItem.objects.bulk_create(items, batch_size=500)
    return run


def claim_next(run, *, lease_seconds=LEASE_SECONDS, now=None):
    """Claim the next queued item (or one whose claim expired) of the run; None when there is none left."""
    from questions.models import ExplanationBatchItem

    now = now or timezone.now()
    open_q = Q(status='queued') | Q(status='claimed', claimed_until__lt=now)
    for pk in ExplanationBatchItem.objects.filter(run=run).filter(open_q).order_by('pk').values_list('pk', flat=True)[:25]:
        claimed = ExplanationBatchItem.objects.filter(pk=pk).filter(open_q).update(
            status='claimed', claimed_until=now + timedelta(seconds=lease_seconds), attempts=F('attempts') + 1)
        if claimed:
            return ExplanationBatchItem.objects.get(pk=pk)
    return None


def _finish(item, status, detail='', provider=''):
    type(item).objects.filter(pk=item.pk).update(status=status, detail=detail[:300], provider=provider[:60],
                                                 claimed_until=None, updated_at=timezone.now())


def _retry_or_give_up(item, status, detail):
    if item.attempts >= MAX_ATTEMPTS:
        _finish(item, status, detail)
        return status
    type(item).objects.filter(pk=item.pk).update(status='queued', claimed_until=None, detail=detail[:300],
                                                 updated_at=timezone.now())
    return 'retry'


def clean_text(value) -> str:
    """Model text without citations it made up (reference lines, "(Book, p. 12)") or provider noise; '' if unusable."""
    if not isinstance(value, str):
        return ''
    text = _REFERENCE_LINE.sub('', value)
    text = _PAREN_CITATION.sub('', text)
    text = _CITE_ARTEFACT.sub('', text)
    text = re.sub(r'[ \t]+([.,;:])', r'\1', text)
    text = re.sub(r'[ \t]+\n', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    if _REFUSE.search(text):
        return ''
    return text


def compose(result: dict, key: str, options: dict) -> tuple[dict, str]:
    """The explanation fields from a model result (``explain_after_answer``), or ({}, why it is unusable)."""
    why_correct = clean_text(result.get('why_correct'))
    if len(why_correct) < 40:
        return {}, 'no usable reason why the key is right'
    why_wrong = result.get('why_wrong') if isinstance(result.get('why_wrong'), dict) else {}
    wrong_lines = []
    for letter in KEYS:
        if letter == key:
            continue
        reason = clean_text(why_wrong.get(letter) or why_wrong.get(letter.lower()))
        if reason:
            option = ' '.join(str(options.get(letter) or '').split())
            wrong_lines.append(f'- **{letter}. {option}**: {reason}')
    if len(wrong_lines) < 2:
        return {}, 'fewer than two wrong options explained'
    answer = ' '.join(str(options.get(key) or '').split())
    parts = [f'**Answer: {key}. {answer}**', '', f'**Why {key} is correct:** {why_correct}', '',
             '**Why the other options are wrong:**', *wrong_lines]
    points = [clean_text(p) for p in (result.get('high_yield_points') or []) if isinstance(p, str)]
    points = [p for p in points if p][:6]
    if points:
        parts += ['', '**High-yield points:**', *[f'- {p}' for p in points]]
    pearl = clean_text(result.get('clinical_pearl'))
    if pearl:
        parts += ['', f'**Clinical pearl:** {pearl}']
    fields = {'explanation': '\n'.join(parts)[:8000]}
    concept = clean_text(result.get('core_concept'))
    if concept:
        fields['concept_explanation'] = concept[:4000]
    mnemonic = clean_text(result.get('mnemonic'))
    if len(mnemonic) >= 8:
        fields['mnemonic'] = mnemonic[:600]
    return fields, ''


def process_item(item, *, ai) -> str:
    """Generate and save one claimed item's explanation; returns its outcome ('done', 'disagrees', 'retry', ...)."""
    from ai_engine.services import AIOutputUnusable, AIUnavailable
    from questions import editorial
    from questions.models import Question

    question = Question.objects.select_related('subject', 'topic').get(pk=item.question_id)
    why = still_needed(question, item)
    if why:
        _finish(item, 'skipped', why)
        return 'skipped'
    key = item.key
    options = {letter: getattr(question, f'option_{letter.lower()}') or '' for letter in KEYS}
    try:
        result = ai.explain_after_answer(
            question_text=question.question_text, options=options, correct_answer=key, selected_answer=key,
            subject=getattr(question.subject, 'name', '') or '', topic=getattr(question.topic, 'name', '') or '',
            question_id=question.pk, cache_scope='batch')
    except AIOutputUnusable:
        return _retry_or_give_up(item, 'invalid', 'the AI output could not be used')
    except AIUnavailable as exc:
        if getattr(exc, 'offline', False):
            type(item).objects.filter(pk=item.pk).update(status='queued', claimed_until=None,
                                                         attempts=F('attempts') - 1)
            raise
        return _retry_or_give_up(item, 'failed', 'no AI provider answered')
    provider = getattr(ai, 'last_provider', '') or ''
    chosen = str(result.get('ai_verified_answer') or '').strip().upper()[:1]
    if result.get('answer_mismatch') is True or (chosen in KEYS and chosen != key):
        _finish(item, 'disagrees', f'AI chose {chosen or "another answer"}; stored key {key}', provider)
        return 'disagrees'
    fields, problem = compose(result, key, options)
    if problem:
        return _retry_or_give_up(item, 'invalid', problem)
    question.refresh_from_db()
    why = still_needed(question, item)  # an admin may have written one meanwhile
    if why:
        _finish(item, 'skipped', why, provider)
        return 'skipped'
    editorial.save_explanation(question, fields, actor=None, for_key=key)
    _finish(item, 'done', '', provider)
    return 'done'


def run_batch(run, *, max_items=None, sleep_seconds=0.0, ai=None, log=None) -> Counter:
    """Process claimed items of the run one after another until none is left or ``max_items`` were taken."""
    from ai_engine.offline import ai_offline_mode
    from ai_engine.services import AIUnavailable

    log = log or (lambda message: None)
    stats = Counter()
    if ai_offline_mode():
        stats['refused: AI_OFFLINE_MODE is on'] = 1
        return stats
    if ai is None:
        from ai_engine.services import AIService
        ai = AIService()
    taken = 0
    while max_items is None or taken < max_items:
        item = claim_next(run)
        if item is None:
            break
        taken += 1
        try:
            outcome = process_item(item, ai=ai)
        except AIUnavailable:
            stats['stopped: AI is offline'] += 1
            break
        except Exception as exc:  # noqa: BLE001 - one bad question must not stop the batch
            _finish(item, 'failed', f'error {type(exc).__name__}')
            outcome = 'failed'
        stats[outcome] += 1
        log(f'Q{item.question_id}: {outcome}')
        if sleep_seconds:
            time.sleep(sleep_seconds)
    return stats


def run_summary(run) -> dict:
    counts = dict(run.items.values('status').annotate(n=Count('id')).values_list('status', 'n'))
    return {'id': run.pk, 'created_at': run.created_at, 'scope': run.scope, 'note': run.note,
            'total': sum(counts.values()), 'counts': counts}
