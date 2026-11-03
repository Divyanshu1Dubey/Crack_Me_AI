"""Strict parsing of AI answer votes, and the rule that turns votes into a review signal (2026-11).

An AI vote is never an answer key (docs/audit/MEDICAL_ACCURACY_DESIGN.md, ground rules 1-2). It is
recorded as a review signal on the question's ``QuestionAudit`` and the audit classifies it; only
``questions.editorial.change_answer_key()`` changes a key, on an explicit admin decision.

The old parser took the first character of the reply (``"Answer: B"`` became ``A``, ``"The answer
is C"`` became nothing) and accepted 2 of 4 votes as a "majority" when another letter also had 2.
``parse_vote`` accepts a reply only when it names exactly one option letter in a recognised form;
``majority`` needs more than half of the valid votes.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Iterable, Optional

LETTERS = ('A', 'B', 'C', 'D')
VOTE_REVIEWER = 'llm:consensus:majority-vote'

# Markdown / quoting around a short reply: **B**, `B`, "B", 'B'.
_WRAP_RE = re.compile(r'^[\s*_`"\'“”‘’]+|[\s*_`"\'“”‘’]+$')
# The whole reply is the letter: "B", "b", "(B)", "B.", "b)", "[C]".
_BARE_RE = re.compile(r'^[(\[]?\s*([A-Da-d])\s*[)\].:]?$')
# A label then the letter: "Answer: B", "The correct answer is (c).", "Option D", "Ans - a".
_LABELLED_RE = re.compile(
    r'^(?:the\s+)?(?:(?:correct|right|best|final|most\s+appropriate)\s+)?'
    r'(?:answer|ans|option|choice|response)(?:\s+is)?\s*[:\-–—=]?\s*'
    r'(?:option\s*)?[(\[]?\s*([A-Da-d])\s*[)\]]?\s*[.:]?$',
    re.IGNORECASE,
)
# The letter followed by option text: "B) Metformin", "Answer: C. Thiamine" (checked against the options).
_WITH_TEXT_RE = re.compile(
    r'^(?:(?:the\s+)?(?:(?:correct|right|best|final)\s+)?(?:answer|ans|option|choice)(?:\s+is)?\s*[:\-–—=]?\s*)?'
    r'(?:option\s*)?[(\[]?\s*([A-Da-d])\s*[)\].:\-–—]\s*(.+)$',
    re.IGNORECASE | re.DOTALL,
)


def _norm(text) -> str:
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', str(text or '').lower()).split())


def parse_vote(reply, options: Optional[dict] = None) -> str:
    """'A'-'D' when ``reply`` names exactly one option letter in a recognised form, else ''.

    Accepted: the bare letter (``"B"``, ``"(b)"``, ``"B."``), a label and the letter (``"Answer: B"``,
    ``"The correct answer is C"``, ``"Option D"``), or the letter followed by text that repeats that
    option's text (only when ``options`` -- ``{'A': text, ...}`` -- is given). Anything else (prose,
    two letters, a letter with other text) is not a vote.
    """
    if not isinstance(reply, str) or len(reply) > 2000:
        return ''
    lines = [line.strip() for line in reply.splitlines() if line.strip()]
    # Only the first line counts ("B\n\nBecause ..." is a vote for B; "A 30-year-old ..." is not).
    text = _WRAP_RE.sub('', lines[0]) if lines else ''
    if not text or len(text) > 400:
        return ''
    match = _BARE_RE.match(text) or _LABELLED_RE.match(text)
    if match:
        return match.group(1).upper()
    match = _WITH_TEXT_RE.match(text)
    if match and options:
        letter, rest = match.group(1).upper(), _norm(match.group(2))
        option = _norm(options.get(letter, ''))
        if option and rest and (rest == option or rest.startswith(option + ' ') or option.startswith(rest)) \
                and len(rest) >= min(3, len(option)):
            return letter
    return ''


def tally(votes: Iterable) -> dict:
    """``{'votes': [...valid letters...], 'counts': {letter: n}, 'invalid': n, 'majority': letter or ''}``."""
    raw = list(votes or [])
    valid = [v for v in (str(x or '').strip().upper() for x in raw) if v in LETTERS]
    counts = Counter(valid)
    return {'votes': valid, 'counts': dict(counts), 'invalid': len(raw) - len(valid), 'majority': majority(valid)}


def majority(votes: Iterable, *, min_votes: int = 2) -> str:
    """The letter that holds more than half of the valid votes and at least ``min_votes`` of them, else ''.

    ``[B, B, C]`` -> ``B``; ``[B, B, C, C]`` -> ``''`` (a tie is not a majority); ``[B]`` -> ``''``.
    """
    valid = [v for v in (str(x or '').strip().upper() for x in (votes or [])) if v in LETTERS]
    if not valid:
        return ''
    letter, count = Counter(valid).most_common(1)[0]
    if count * 2 > len(valid) and count >= min_votes:
        return letter
    return ''


def vote_review(letter: str, *, stored_key: str, source: str, providers: str = '', at: str = '') -> dict:
    """A review-signal dict (``key_audit.reviews`` format) for an AI consensus vote.

    The vote is a review signal labelled ``llm:consensus:majority-vote``: the audit classifies it
    (an agreeing vote is at most *likely correct*; a disagreeing one sends the question to review).
    """
    from .reviews import normalize_review

    letter = (letter or '').strip().upper()[:1]
    stored = (stored_key or '').strip().upper()[:1]
    if letter in LETTERS and stored in LETTERS:
        verdict = 'agree' if letter == stored else 'disagree'
    elif letter in LETTERS:
        verdict = 'uncertain'
    else:
        verdict = 'unanswerable'
    review = normalize_review({
        'question_id': 0, 'pass': 0, 'reviewer': VOTE_REVIEWER, 'reviewer_id': source,
        'verdict': verdict, 'best_option': letter if letter in LETTERS else 'none',
        'confidence': 'medium' if letter in LETTERS else 'low', 'issues': [],
        'reason': f'AI majority vote ({providers})' if providers else 'AI majority vote',
        'stored_key': stored, 'at': at,
    }, source=source)
    return review
