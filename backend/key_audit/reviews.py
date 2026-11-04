"""Review signals in one format: AI reviewers, AI votes, official answer keys and human decisions.

A review is a verdict about the stored key, never a source (docs/audit/MEDICAL_ACCURACY_DESIGN.md,
ground rule 2). Stored in ``QuestionAudit.reviews`` as dicts::

    {reviewer, pass, reviewer_ref, verdict, best_option, confidence, explanation_check, issues,
     reason, quotes: [{chunk_key, quote}], stored_key, at, source, stem_hash, ...}

* ``reviewer``: ``'claude-subagent (review signal)'`` or ``'llm:<provider>:<model>'`` (AI),
  ``'official_key'`` (an official answer key), ``'human:<user id>'`` (review queue only).
* ``stored_key``: the key the reviewer saw. A review keeps its meaning after a key change because
  the audit re-reads it against the current key (``effective``): the reviewer's ``best_option``
  either is the new key (agree) or is not (disagree).
* ``stem_hash``: ``questions.content_hashes.stem_hash`` when the review was recorded; a review of
  other content (the stem or an option changed since) is stale and no longer counts.
* identity = (reviewer, pass, reviewer_ref): importing a file again replaces its reviews.
  ``reviewer_ref`` is the line's ``reviewer_id`` (or ``agent_id`` / ``agent``) when present; for
  pass >= 2 without one it is ``<workflow_run or file>#<n>`` (the n-th review of that question in
  that run), so the two reviewers of an evidence pass stay two reviews.
"""
from __future__ import annotations

import re
from datetime import datetime

from django.utils import timezone

AI_REVIEWER_LABEL = 'claude-subagent (review signal)'
OFFICIAL_REVIEWER = 'official_key'
HUMAN_PREFIX = 'human:'
LLM_PREFIX = 'llm:'
EVIDENCE_PREFIX = 'evidence:'

LETTERS = ('A', 'B', 'C', 'D')
VERDICTS = ('agree', 'disagree', 'unanswerable', 'uncertain')
CONFIDENCES = ('high', 'medium', 'low')
EXPLANATION_CHECKS = ('absent', 'supports_key', 'contradicts_key', 'unrelated')
KNOWN_ISSUES = (
    'options_incomplete', 'image_required', 'garbled_text', 'answer_in_text', 'key_invalid',
    'wrong_subject', 'no_correct_option', 'ambiguous', 'outdated_or_guideline_dependent',
    'multiple_correct', 'duplicate_options',
)
# Evidence a human decision may carry; a free-text 'note' is reasoning, not evidence.
EVIDENCE_KINDS = ('official_key', 'errata', 'guideline_url', 'passage', 'note')
STRONG_EVIDENCE_KINDS = ('official_key', 'errata', 'guideline_url', 'passage')

MAX_REASON = 600
MAX_QUOTE = 600
MAX_QUOTES = 6
_LABEL_RE = re.compile(r'^[A-Za-z0-9 ():._\-/@+#]{1,80}$')
_CONTROL_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')


class ReviewError(ValueError):
    """A review line that cannot be used."""


def reviewer_kind(reviewer) -> str:
    """'human' | 'official' | 'evidence' | 'ai' for a reviewer label."""
    label = str(reviewer or '')
    if label.startswith(HUMAN_PREFIX):
        return 'human'
    if label == OFFICIAL_REVIEWER:
        return 'official'
    if label.startswith(EVIDENCE_PREFIX):
        return 'evidence'
    return 'ai'


def display_label(review) -> str:
    """How the review queue labels a review: AI output is a review signal, never evidence."""
    kind = reviewer_kind(review.get('reviewer'))
    if kind == 'human':
        return 'Human review'
    if kind == 'official':
        return 'Official answer key'
    if kind == 'evidence':
        return 'Evidence engine (deterministic)'
    return f"AI review signal (not evidence): {review.get('reviewer') or AI_REVIEWER_LABEL}"


def clean_text(value, limit: int) -> str:
    text = value if isinstance(value, str) else ('' if value is None else str(value))
    return _CONTROL_RE.sub('', text).strip()[:limit]


def _iso(value) -> str:
    if isinstance(value, datetime):
        return (value if timezone.is_aware(value) else timezone.make_aware(value)).isoformat()
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
        except ValueError:
            parsed = None
        if parsed is not None:
            return _iso(parsed)
    return timezone.now().isoformat()


def parse_at(value):
    """The review's timestamp as an aware datetime (None when missing / unreadable)."""
    if isinstance(value, datetime):
        return value if timezone.is_aware(value) else timezone.make_aware(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
        except ValueError:
            return None
        return parsed if timezone.is_aware(parsed) else timezone.make_aware(parsed)
    return None


def _letter(value) -> str:
    letter = clean_text(value, 8).upper()
    return letter if letter in LETTERS else ''


def normalize_review(obj, *, source: str = '', ordinal: int = 0, stem_hash: str = '',
                     allow_human: bool = False) -> dict:
    """One review in the stored format. Raises ``ReviewError`` for a line that cannot be used.

    Files hold AI reviews and official keys only; ``human:`` reviews are written by the review
    queue (``allow_human=True``).
    """
    if not isinstance(obj, dict):
        raise ReviewError('not an object')
    reviewer = clean_text(obj.get('reviewer') or AI_REVIEWER_LABEL, 80)
    if not _LABEL_RE.match(reviewer):
        raise ReviewError('reviewer label')
    kind = reviewer_kind(reviewer)
    if kind == 'human' and not allow_human:
        raise ReviewError('human reviews are recorded by the review queue, not imported')
    if kind == 'evidence':
        raise ReviewError('evidence decisions are EvidenceRun rows, not reviews')
    try:
        pass_no = int(obj.get('pass', 1) or 0)
    except (TypeError, ValueError):
        raise ReviewError('pass') from None
    if pass_no < 0 or pass_no > 9:
        raise ReviewError('pass')
    verdict = clean_text(obj.get('verdict'), 20).lower()
    if verdict not in VERDICTS:
        verdict = 'uncertain'
    confidence = clean_text(obj.get('confidence'), 10).lower()
    if confidence not in CONFIDENCES:
        confidence = 'low'
    explanation_check = clean_text(obj.get('explanation_check'), 20).lower()
    if explanation_check not in EXPLANATION_CHECKS:
        explanation_check = ''
    raw_issues = obj.get('issues') if isinstance(obj.get('issues'), list) else []
    issues = []
    for item in raw_issues[:20]:
        code = clean_text(item, 40).lower()
        if code in KNOWN_ISSUES and code not in issues:
            issues.append(code)
    quotes = []
    for item in (obj.get('quotes') if isinstance(obj.get('quotes'), list) else [])[:MAX_QUOTES]:
        if not isinstance(item, dict):
            continue
        chunk_key = clean_text(item.get('chunk_key'), 160)
        quote = clean_text(item.get('quote'), MAX_QUOTE)
        if chunk_key and quote:
            quotes.append({'chunk_key': chunk_key, 'quote': quote})
    ref = clean_text(obj.get('reviewer_id') or obj.get('agent_id') or obj.get('agent') or '', 80)
    if not ref and pass_no >= 2:
        run = clean_text(obj.get('workflow_run') or source, 80)
        ref = f'{run}#{ordinal}'
    review = {
        'reviewer': reviewer,
        'pass': pass_no,
        'reviewer_ref': ref,
        'verdict': verdict,
        'best_option': _letter(obj.get('best_option')),
        'confidence': confidence,
        'explanation_check': explanation_check,
        'issues': issues,
        'reason': clean_text(obj.get('reason'), MAX_REASON),
        'quotes': quotes,
        'stored_key': clean_text(obj.get('stored_key'), 4).upper()[:1],
        'at': _iso(obj.get('at')),
        'source': clean_text(source or obj.get('workflow_run') or '', 120),
        'stem_hash': clean_text(stem_hash or obj.get('stem_hash') or '', 64),
    }
    if kind == 'official':
        official_source = clean_text(obj.get('official_source') or obj.get('reason'), 300)
        if not official_source or not review['best_option']:
            raise ReviewError('an official key needs best_option and official_source')
        review['official_source'] = official_source
        review['verdict'] = 'agree' if review['best_option'] == review['stored_key'] else 'disagree'
        review['confidence'] = 'high'
    if kind == 'human':
        review['evidence'] = obj.get('evidence') if isinstance(obj.get('evidence'), list) else []
        review['has_evidence'] = has_strong_evidence(review['evidence'])
        review['resolution_id'] = obj.get('resolution_id')
    return review


def has_strong_evidence(items) -> bool:
    return any(isinstance(item, dict) and item.get('kind') in STRONG_EVIDENCE_KINDS for item in (items or []))


def identity(review) -> tuple:
    return (review.get('reviewer') or '', str(review.get('pass', '')), review.get('reviewer_ref') or '')


def merge(existing, new) -> list:
    """``existing`` with every review of ``new`` added; a review with the same identity is replaced."""
    out = [dict(r) for r in (existing or []) if isinstance(r, dict)]
    index = {identity(r): i for i, r in enumerate(out)}
    for review in new or []:
        key = identity(review)
        if key in index:
            out[index[key]] = dict(review)
        else:
            index[key] = len(out)
            out.append(dict(review))
    return out


def is_stale(review, stem_hash: str) -> bool:
    recorded = review.get('stem_hash') or ''
    return bool(recorded and stem_hash and recorded != stem_hash)


def effective(review, key: str) -> tuple:
    """(verdict, best_option) of ``review`` read against the current ``key``.

    The reviewer's committed letter decides: ``best_option == key`` is agreement, another letter is
    disagreement, also when the key changed since the review. 'unanswerable' / 'uncertain' stay as
    they are. Against an invalid key nothing can agree.
    """
    best = review.get('best_option') or ''
    verdict = review.get('verdict') or 'uncertain'
    if verdict in ('unanswerable', 'uncertain'):
        return verdict, best
    if key not in LETTERS:
        return 'uncertain', best
    if best in LETTERS:
        return ('agree' if best == key else 'disagree'), best
    seen = review.get('stored_key') or ''
    if seen and seen != key:
        return 'uncertain', ''
    return verdict, ''
