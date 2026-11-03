"""Loading answer-key audit signals from JSON-lines files (2026-11).

Two file kinds, one JSON object per line, both checked against the question's current content:

* **source keys** (``manage.py import_source_keys``, written by ``ai_eval.recover_source_keys``)::

    {question_id, stem_hash, source_file, source_sha256?, question_page, question_number,
     answer_page?, chapter?, source_exam?, source_year?, printed_letter, letter, option_order,
     method, located, recovery_version, recovered_at}

  The prototype's names are accepted too (``source_page``, ``qno``, ``evidence_page``,
  ``source_letter``, ``bank_letter``, ``chapter_parsed``); lines without a single printed letter
  (``status`` ``no_source_key`` / ``source_ambiguous``) are skipped.

* **review signals** (``manage.py import_review_signals``): AI reviews and official answer keys in
  the ``key_audit.reviews`` format, plus ``question_id`` and ``stem_hash``. Human decisions are never
  imported: they are made in the review queue.

``stem_hash`` (``questions.content_hashes.stem_hash`` of the content the line was made for) must equal
the question's current hash; lines without one are skipped unless the caller vouches that the content is
unchanged (``assume_current_content``, meant for the database the file was made from). Nothing here
changes a key.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import PureWindowsPath
from typing import Iterable

from django.utils import timezone

from key_audit.models import SourceKey
from key_audit.reviews import ReviewError, clean_text, normalize_review, parse_at
from questions.content_hashes import stem_hash, valid_key
from questions.models import Question

_HEX64 = re.compile(r'^[0-9a-f]{64}$')
OPTION_ORDERS = {choice for choice, _label in SourceKey.OPTION_ORDER_CHOICES}
METHODS = {choice for choice, _label in SourceKey.METHOD_CHOICES}
MAX_LINE = 20_000


class LineError(ValueError):
    """A line that cannot be used (the message is the skip reason)."""


@dataclass
class Report:
    lines: int = 0
    valid: int = 0
    skipped: Counter = field(default_factory=Counter)
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    questions: set = field(default_factory=set)
    notes: Counter = field(default_factory=Counter)

    def as_dict(self) -> dict:
        return {
            'lines': self.lines, 'valid': self.valid, 'skipped': dict(self.skipped.most_common()),
            'created': self.created, 'updated': self.updated, 'unchanged': self.unchanged,
            'questions': len(self.questions), 'notes': dict(self.notes.most_common()),
        }


def read_lines(path) -> Iterable[tuple]:
    """``(line_no, obj or LineError)`` for each non-empty line of a UTF-8 JSON-lines file."""
    with open(path, encoding='utf-8') as fh:
        for number, line in enumerate(fh, 1):
            text = line.strip()
            if not text:
                continue
            if len(text) > MAX_LINE:
                yield number, LineError('line_too_long')
                continue
            try:
                obj = json.loads(text)
            except json.JSONDecodeError:
                yield number, LineError('not_json')
                continue
            yield number, obj if isinstance(obj, dict) else LineError('not_an_object')


def _int(value, *, low=1, high=100_000):
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if low <= number <= high else None


def _hash_check(obj, question, *, assume_current_content: bool) -> str:
    current = stem_hash(question)
    recorded = clean_text(obj.get('stem_hash'), 64).lower()
    if recorded:
        if not _HEX64.match(recorded):
            raise LineError('bad_stem_hash')
        if recorded != current:
            raise LineError('content_changed')
        return current
    if assume_current_content:
        return current
    raise LineError('no_stem_hash')


def _questions(ids) -> dict:
    return {q.pk: q for q in Question.objects.filter(pk__in=ids).only(
        'id', 'question_text', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_answer')}


# --------------------------------------------------------------------------- source keys

def parse_source_key(obj: dict, question, *, assume_current_content: bool = False) -> dict:
    """The SourceKey field values of one line. Raises ``LineError``."""
    if obj.get('status') in ('no_source_key', 'source_ambiguous'):
        raise LineError(obj['status'])
    printed = valid_key(obj.get('printed_letter') or obj.get('source_letter'))
    letter = valid_key(obj.get('letter') or obj.get('bank_letter'))
    if not printed or not letter:
        raise LineError('bad_letter')
    page = _int(obj.get('question_page', obj.get('source_page')))
    number = _int(obj.get('question_number', obj.get('qno')), high=10_000)
    if page is None or number is None:
        raise LineError('bad_location')
    method = clean_text(obj.get('method'), 24)
    if method not in METHODS:
        raise LineError('bad_method')
    order = clean_text(obj.get('option_order'), 16)
    if order not in OPTION_ORDERS:
        order = 'assumed_same'   # an unknown value is never read as "checked"
    name = PureWindowsPath(clean_text(obj.get('source_file'), 400)).name[:255]   # never a local path
    if not name:
        raise LineError('no_source_file')
    sha = clean_text(obj.get('source_sha256'), 64).lower()
    parsed = obj.get('chapter_parsed') if isinstance(obj.get('chapter_parsed'), dict) else {}
    year = _int(obj.get('source_year', parsed.get('year')), low=1950, high=2100)
    recovered = parse_at(obj.get('recovered_at')) or timezone.now()
    return {
        'question_id': question.pk,
        'source_file': name,
        'source_sha256': sha if _HEX64.match(sha) else '',
        'question_page': page,
        'question_number': number,
        'answer_page': _int(obj.get('answer_page', obj.get('evidence_page'))),
        'chapter': clean_text(obj.get('chapter'), 160),
        'source_exam': clean_text(obj.get('source_exam', parsed.get('exam')), 16),
        'source_year': year,
        'printed_letter': printed,
        'letter': letter,
        'option_order': order,
        'method': method,
        'located': obj.get('located') is True,
        'stem_hash': _hash_check(obj, question, assume_current_content=assume_current_content),
        'recovery_version': clean_text(obj.get('recovery_version') or 'prototype-2026-11-02', 32),
        'recovered_at': recovered,
    }


IDENTITY = ('question_id', 'source_file', 'question_page', 'question_number')


def import_source_keys(path, *, apply: bool = False, assume_current_content: bool = False) -> Report:
    """Validate (and with ``apply`` upsert) the source keys in ``path``. Never deletes rows."""
    report = Report()
    entries = []
    for _number, obj in read_lines(path):
        report.lines += 1
        if isinstance(obj, LineError):
            report.skipped[str(obj)] += 1
            continue
        entries.append(obj)
    ids = {_int(obj.get('question_id'), high=10**9) for obj in entries} - {None}
    questions = _questions(ids)
    rows = {}
    for obj in entries:
        qid = _int(obj.get('question_id'), high=10**9)
        question = questions.get(qid)
        if question is None:
            report.skipped['unknown_question'] += 1
            continue
        try:
            values = parse_source_key(obj, question, assume_current_content=assume_current_content)
        except LineError as exc:
            report.skipped[str(exc)] += 1
            continue
        ident = tuple(values[k] for k in IDENTITY)
        if ident in rows:
            report.skipped['duplicate_line'] += 1
            continue
        rows[ident] = values
        report.valid += 1
        report.questions.add(qid)
        key = valid_key(question.correct_answer)
        confident = values['located'] and values['option_order'] in ('same', 'reordered')
        report.notes[f"{'confident' if confident else 'unchecked'}_{'match' if values['letter'] == key else 'mismatch'}"] += 1

    existing = {}
    for row in SourceKey.objects.filter(question_id__in={k[0] for k in rows}):
        existing[(row.question_id, row.source_file, row.question_page, row.question_number)] = row
    compare = [f for f in rows[next(iter(rows))] if f not in IDENTITY] if rows else []
    to_create, to_update = [], []
    for ident, values in rows.items():
        row = existing.get(ident)
        if row is None:
            report.created += 1
            to_create.append(SourceKey(**values))
            continue
        if all(getattr(row, f) == values[f] for f in compare if f != 'recovered_at'):
            report.unchanged += 1
            continue
        report.updated += 1
        for f in compare:
            setattr(row, f, values[f])
        to_update.append(row)
    if apply:
        from django.db import transaction
        with transaction.atomic():
            SourceKey.objects.bulk_create(to_create, batch_size=500)
            if to_update:
                SourceKey.objects.bulk_update(to_update, compare, batch_size=500)
    return report


# --------------------------------------------------------------------------- review signals

def parse_review(obj: dict, question, *, source: str, ordinal: int, assume_current_content: bool = False) -> dict:
    """One review (``key_audit.reviews`` format) for ``question``. Raises ``LineError``."""
    current = _hash_check(obj, question, assume_current_content=assume_current_content)
    try:
        review = normalize_review(obj, source=source, ordinal=ordinal, stem_hash=current)
    except ReviewError as exc:
        raise LineError(f'bad_review: {exc}') from None
    if not review['stored_key']:
        review['stored_key'] = clean_text(obj.get('stored_key'), 4).upper()[:1]
    return review


def import_review_signals(path, *, apply: bool = False, assume_current_content: bool = False,
                          source: str = '') -> tuple:
    """Validate the reviews in ``path``. Returns ``(report, {question_id: [review, ...]})``; with
    ``apply`` they are merged into the audits and the questions re-classified."""
    report = Report()
    entries = []
    for number, obj in read_lines(path):
        report.lines += 1
        if isinstance(obj, LineError):
            report.skipped[str(obj)] += 1
            continue
        entries.append((number, obj))
    ids = {_int(obj.get('question_id'), high=10**9) for _n, obj in entries} - {None}
    questions = _questions(ids)
    label = clean_text(source or PureWindowsPath(str(path)).name, 120)
    by_question = defaultdict(list)
    ordinals = Counter()
    for _number, obj in entries:
        qid = _int(obj.get('question_id'), high=10**9)
        question = questions.get(qid)
        if question is None:
            report.skipped['unknown_question'] += 1
            continue
        ordinals[qid] += 1
        try:
            review = parse_review(obj, question, source=label, ordinal=ordinals[qid],
                                  assume_current_content=assume_current_content)
        except LineError as exc:
            report.skipped[str(exc)] += 1
            continue
        by_question[qid].append(review)
        report.valid += 1
        report.questions.add(qid)
        report.notes[f"{review['reviewer']}: {review['verdict']}"] += 1
    if apply and by_question:
        from key_audit.services import audit_questions
        rows = list(Question.objects.filter(pk__in=list(by_question)))
        audit_questions(rows, save=True, extra_reviews=dict(by_question))
    return report, dict(by_question)
