"""The one definition of "the question's content" used for staleness checks (2026-11).

``stem_hash`` is stored with explanations (Question.explanation_stem_hash), evidence rows
(evidence.QuestionEvidence.content_sha256) and suggestions (ExplanationSuggestion.draft_stem_hash).
Formatting-only edits (case, spacing, mojibake repair) keep the hash; any change of words in the
stem or an option changes it.
"""
from __future__ import annotations

import hashlib
import unicodedata

OPTION_LETTERS = ('A', 'B', 'C', 'D')


def _canon(text) -> str:
    from questions.text_encoding import normalize_text
    text = normalize_text(text or '') if isinstance(text, str) else ''
    text = unicodedata.normalize('NFKC', text).casefold()
    return ' '.join(text.split())


def _get(obj, name):
    if isinstance(obj, dict):
        return obj.get(name, '')
    return getattr(obj, name, '')


def stem_hash(question) -> str:
    """sha256 over the canonical stem and the four options (a Question or a dict with
    question_text, option_a..option_d)."""
    parts = [_canon(_get(question, 'question_text'))]
    parts += [_canon(_get(question, f'option_{letter.lower()}')) for letter in OPTION_LETTERS]
    return hashlib.sha256('\x1f'.join(parts).encode('utf-8')).hexdigest()


def valid_key(value) -> str:
    """The stored key when it is one of A-D, else ''."""
    key = (value or '').strip().upper()[:1]
    return key if key in OPTION_LETTERS else ''
