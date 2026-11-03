"""Answer-key audit services (docs/audit/MEDICAL_ACCURACY_DESIGN.md, phase 3).

``audit_questions`` gathers what the database knows about each question and lets
``key_audit.classify`` decide its status. Nothing here changes a key: a key changes only through
``questions.editorial.change_answer_key()`` on an explicit admin decision.

Everything comes from the database, so the audit gives the same result on every deployment:

* the question: key, stem, options, explanation, flags, exam and year;
* ``SourceKey`` rows: keys printed by the source documents (``manage.py import_source_keys``);
* ``QuestionAudit.reviews``: AI reviews and official keys (``manage.py import_review_signals``);
* human decisions: ``AnswerKeyChange`` (key changes by staff), ``AuditResolution`` (review-queue
  decisions) and the admin verification fields;
* open "wrong answer" reports, duplicate clusters, answer labels in the text, attached images;
* the latest audit ``EvidenceRun`` made after the question's last edit;
* the key distribution of the question's exam and year (an importer that keyed nearly everything
  'A' leaves a skewed distribution).

Rows recorded for other content (a SourceKey or review whose ``stem_hash`` differs from the
question's current one) are ignored and counted.
"""
from __future__ import annotations

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

from django.db import IntegrityError, transaction
from django.db.models import Count
from django.utils import timezone

from key_audit import classify as rules
from key_audit.explanation_check import STATES_OTHER, check_explanation
from key_audit.models import AuditResolution, QuestionAudit, SourceKey
from key_audit.reviews import (
    STRONG_EVIDENCE_KINDS, effective, has_strong_evidence, is_stale, merge, reviewer_kind,
)
from questions.content_hashes import stem_hash, valid_key
from questions.models import AnswerKeyChange, Question, QuestionFeedback, QuestionImage

logger = logging.getLogger('key_audit.services')

CHUNK = 400
# A (exam, year) group is skewed when one letter holds at least SKEW_MIN_SHARE of at least
# SKEW_MIN_GROUP active questions (four options: about 25 % each is expected).
SKEW_MIN_GROUP = 50
SKEW_MIN_SHARE = 0.60
# Key changes recorded by these paths are not decisions of the person who ran them.
NON_DECISION_SOURCES = ('legacy_snapshot', 'management_command')
# Review-queue resolutions that are a decision about the current key, and what they say.
# ('image_requested' is not about the key: the image signal keeps the status.)
RESOLUTION_VERDICTS = {'key_confirmed': 'agree', 'deferred': 'uncertain'}


# --------------------------------------------------------------------------- key distribution

def key_skew(exam_years: Optional[Iterable[tuple]] = None) -> dict:
    """``{(exam_type, year): {'letter', 'share', 'n'}}`` for skewed groups of active questions."""
    qs = Question.objects.filter(is_active=True)
    if exam_years is not None:
        pairs = {(exam, year) for exam, year in exam_years}
        if not pairs:
            return {}
        from django.db.models import Q
        cond = Q()
        for exam, year in pairs:
            cond |= Q(exam_type=exam, year=year)
        qs = qs.filter(cond)
    groups = defaultdict(Counter)
    for row in qs.values('exam_type', 'year', 'correct_answer').annotate(n=Count('id')):
        groups[(row['exam_type'], row['year'])][valid_key(row['correct_answer'])] += row['n']
    out = {}
    for group, counts in groups.items():
        total = sum(counts.values())
        letter, n = max(((k, v) for k, v in counts.items() if k), key=lambda kv: kv[1], default=('', 0))
        if total >= SKEW_MIN_GROUP and letter and n / total >= SKEW_MIN_SHARE:
            out[group] = {'letter': letter, 'share': round(n / total, 3), 'n': total}
    return out


# --------------------------------------------------------------------------- context

@dataclass
class _Context:
    audits: dict
    source_keys: dict
    reports: dict
    images: dict
    duplicates: set
    key_changes: dict
    resolutions: dict
    evidence: dict
    tiers: dict
    skew: dict


def _load_context(questions: Sequence[Question], *, skew: Optional[dict], lock: bool) -> _Context:
    from questions.key_status import _duplicate_conflicts

    ids = [q.pk for q in questions]
    audit_qs = QuestionAudit.objects.filter(question_id__in=ids)
    if lock:
        audit_qs = audit_qs.select_for_update()
    audits = {a.question_id: a for a in audit_qs}

    source_keys = defaultdict(list)
    for row in SourceKey.objects.filter(question_id__in=ids):
        source_keys[row.question_id].append(row)

    reports = defaultdict(list)
    for qid, created in QuestionFeedback.objects.filter(
            question_id__in=ids, category='wrong_answer', status__in=('new', 'in_progress'),
    ).values_list('question_id', 'created_at'):
        reports[qid].append(created)

    images = defaultdict(list)
    for img in QuestionImage.objects.filter(question_id__in=ids, is_active=True):
        images[img.question_id].append(img)

    key_changes = defaultdict(list)
    for change in AnswerKeyChange.objects.filter(question_id__in=ids).order_by('changed_at', 'id'):
        key_changes[change.question_id].append(change)

    resolutions = defaultdict(list)
    for res in AuditResolution.objects.filter(question_id__in=ids).order_by('resolved_at', 'id'):
        resolutions[res.question_id].append(res)

    evidence, tiers = {}, {}
    try:
        from reference_corpus.models import EvidenceRun
        for run in EvidenceRun.objects.filter(question_id__in=ids, purpose='audit').order_by('question_id', '-created_at'):
            evidence.setdefault(run.question_id, run)
        shas = {c.get('source_sha256') for run in evidence.values() for c in (run.citations or [])
                if isinstance(c, dict) and c.get('source_sha256')}
        if shas:
            from evidence.models import EvidenceSource
            tiers = dict(EvidenceSource.objects.filter(sha256__in=shas).values_list('sha256', 'tier'))
    except Exception:  # noqa: BLE001 - the evidence apps are optional for the audit
        logger.exception('could not load evidence runs')
        evidence, tiers = {}, {}

    if skew is None:
        skew = key_skew({(q.exam_type, q.year) for q in questions})
    return _Context(audits=audits, source_keys=source_keys, reports=reports, images=images,
                    duplicates=_duplicate_conflicts(list(questions)), key_changes=key_changes,
                    resolutions=resolutions, evidence=evidence, tiers=tiers, skew=skew)


# --------------------------------------------------------------------------- inputs

def _human_decision(question, key: str, current_hash: str, audit, ctx: _Context) -> Optional[rules.HumanDecision]:
    """The latest human decision about this question that still applies to its content."""
    changed_at = getattr(audit, 'content_changed_at', None) if audit is not None else None
    candidates = []
    for change in ctx.key_changes.get(question.pk, []):
        if change.changed_by_id is None or change.source in NON_DECISION_SOURCES:
            continue
        candidates.append(rules.HumanDecision(
            reviewer=f'human:{change.changed_by_id}', verdict='agree', best_option=valid_key(change.new_key),
            strong_evidence=has_strong_evidence(change.evidence), at=change.changed_at, source='key_change',
            ref=f'key_change:{change.pk}',
        ))
    for res in ctx.resolutions.get(question.pk, []):
        verdict = RESOLUTION_VERDICTS.get(res.resolution)
        if verdict is None or res.key_change_id:
            continue   # a key change is its own decision; other resolutions are not about the key
        if res.stem_hash and res.stem_hash != current_hash:
            continue
        candidates.append(rules.HumanDecision(
            reviewer=f'human:{res.resolved_by_id}' if res.resolved_by_id else 'human:unknown', verdict=verdict,
            best_option=valid_key(res.stored_key) or (key if verdict == 'agree' else ''),
            strong_evidence=verdict == 'agree' and has_strong_evidence(res.evidence),
            at=res.resolved_at, source='review_queue', ref=f'resolution:{res.pk}',
        ))
    if question.verified_at and question.verified_by_id:
        later_change = any(c.changed_at > question.verified_at for c in ctx.key_changes.get(question.pk, []))
        if not later_change:
            candidates.append(rules.HumanDecision(
                reviewer=f'human:{question.verified_by_id}', verdict='agree', best_option=key,
                strong_evidence=False, at=question.verified_at, source='admin_verify', ref='verified_at',
            ))
    if changed_at is not None:
        candidates = [c for c in candidates if c.at is not None and c.at >= changed_at]
    if not candidates:
        return None
    return max(candidates, key=lambda c: c.at or timezone.now())


def _deterministic_signals(question, key: str, ctx: _Context) -> list:
    from questions.answer_leak import plan_repair, row_has_answer_label

    signals = []
    raw = (question.correct_answer or '').strip()
    if not key:
        signals.append(rules.Signal('invalid_or_missing_key', f'the stored key {raw[:8]!r} is not one of A-D'))

    expl = check_explanation(question)
    if expl.get('status') == STATES_OTHER:
        stated = valid_key(expl.get('stated_key'))
        if stated and stated != key:
            excerpt = ' '.join(str(expl.get('excerpt') or '').split())[:160]
            signals.append(rules.Signal('explanation_states_other',
                                        f'the explanation names {stated} ({expl.get("method", "")}): "{excerpt}"',
                                        suggested_key=stated))

    if row_has_answer_label(question):
        repair = plan_repair(question)
        if repair.deactivate:
            signals.append(rules.Signal('label_hold', 'the text holds an answer label that needs a manual repair: '
                                        + '; '.join(repair.reasons)[:200]))
        elif repair.conflict:
            signals.append(rules.Signal('label_key_conflict', '; '.join(repair.conflicts)[:240]))

    reports = ctx.reports.get(question.pk, [])
    if reports:
        signals.append(rules.Signal('open_wrong_answer_report', f'{len(reports)} open student report(s) of a wrong key',
                                    at=max(reports)))
    if question.is_disputed:
        signals.append(rules.Signal('is_disputed', 'the question is marked disputed'))
    if question.pk in ctx.duplicates:
        signals.append(rules.Signal('duplicate_key_conflict', 'a duplicate of this question is keyed to another answer'))
    if question.needs_review:
        signals.append(rules.Signal('needs_review_flag', 'the needs-review flag is set'))
    return signals


def _image_missing(question, ctx: _Context) -> tuple:
    from questions.image_context import image_context

    info = image_context(question, images=ctx.images.get(question.pk, []), check_files=False)
    if info['dependency'] == 'missing':
        return True, 'the question needs a figure and none is attached'
    if info['dependency'] == 'unresolved_tokens':
        return True, f"the text points at figure(s) {info['unresolved_token_ids']} that are not attached"
    return False, ''


def _evidence_input(question, key: str, ctx: _Context) -> Optional[dict]:
    run = ctx.evidence.get(question.pk)
    if run is None:
        return None
    # A run made before the question's last save may describe other content: ignore it.
    if question.updated_at and run.created_at < question.updated_at:
        return None
    if valid_key(run.stored_key) != key:
        return None
    citations = [c for c in (run.citations or []) if isinstance(c, dict)]
    tier_ok = any((ctx.tiers.get(c.get('source_sha256')) or 9) <= 3 for c in citations)
    return {'status': run.status, 'evidence_answer': run.evidence_answer, 'citations': len(citations),
            'tier_ok': tier_ok, 'at': run.created_at, 'run_id': run.pk}


def _source_key_dicts(rows, current_hash: str, key: str) -> tuple:
    fresh, stale = [], 0
    for row in rows:
        if row.stem_hash and row.stem_hash != current_hash:
            stale += 1
            continue
        fresh.append({
            'letter': row.letter, 'printed_letter': row.printed_letter, 'confident': row.confident,
            'located': row.located, 'option_order': row.option_order, 'method': row.method,
            'source_file': row.source_file, 'question_page': row.question_page, 'answer_page': row.answer_page,
            'question_number': row.question_number, 'chapter': row.chapter, 'source_exam': row.source_exam,
            'source_year': row.source_year, 'imported_at': row.imported_at, 'id': row.pk,
        })
    return fresh, stale


def _provenance(question, key: str, ctx: _Context, official_agrees: bool) -> str:
    from questions.key_status import AI_SOLVED_SOURCE_RE

    changes = [c for c in ctx.key_changes.get(question.pk, []) if valid_key(c.new_key) == key]
    if changes and changes[-1].changed_by_id and changes[-1].source not in NON_DECISION_SOURCES:
        return 'admin'
    if official_agrees:
        return 'official_key'
    if AI_SOLVED_SOURCE_RE.match(question.source or '') and not question.admin_edited:
        return 'ai_enrichment'
    return 'import' if (question.source or '').strip() else 'unknown'


def _original_key(question, key: str, ctx: _Context) -> str:
    for change in ctx.key_changes.get(question.pk, []):
        if valid_key(change.old_key):
            return valid_key(change.old_key)
    return key


@dataclass
class Prepared:
    question: Question
    result: rules.AuditResult
    fields: dict


def prepare(question: Question, ctx: _Context, *, extra_reviews: Sequence[dict] = ()) -> Prepared:
    """The audit of one question (nothing saved)."""
    key = valid_key(question.correct_answer)
    current_hash = stem_hash(question)
    audit = ctx.audits.get(question.pk)
    reviews = merge_keep_at(list(audit.reviews or []) if audit else [], list(extra_reviews))

    ai_reviews, official, stale_reviews = [], [], 0
    for review in reviews:
        if is_stale(review, current_hash):
            stale_reviews += 1
            continue
        kind = reviewer_kind(review.get('reviewer'))
        if kind == 'official':
            official.append(review)
        elif kind == 'ai':
            ai_reviews.append(review)

    source_keys, stale_keys = _source_key_dicts(ctx.source_keys.get(question.pk, []), current_hash, key)
    image_missing, image_detail = _image_missing(question, ctx)
    signals = _deterministic_signals(question, key, ctx)

    skew = ctx.skew.get((question.exam_type, question.year))
    confident_agree = any(sk['confident'] and valid_key(sk['letter']) == key for sk in source_keys)
    if skew and key == skew['letter'] and not confident_agree:
        signals.append(rules.Signal(
            'skewed_key_distribution',
            f"{skew['share']:.0%} of the {skew['n']} active {question.exam_type} {question.year} questions are keyed "
            f"{skew['letter']} (about 25 % expected); this key may be an importer default",
            data=dict(skew)))
    for sk in source_keys:
        if sk.get('source_year') and question.year and sk['source_year'] != question.year:
            signals.append(rules.Signal(
                'source_year_differs',
                f"{sk['source_file']} files the question under {sk.get('chapter') or sk['source_year']}; "
                f"the bank says {question.exam_type} {question.year}"))
            break

    official_agrees = any(effective(r, key)[0] == 'agree' for r in official) if key else False
    provenance = _provenance(question, key, ctx, official_agrees)
    inp = rules.AuditInput(
        key=key, signals=signals, ai_reviews=ai_reviews, official_reviews=official,
        human=_human_decision(question, key, current_hash, audit, ctx), source_keys=source_keys,
        evidence=_evidence_input(question, key, ctx), image_missing=image_missing, image_detail=image_detail,
        ai_chosen_key=provenance == 'ai_enrichment', stale_review_count=stale_reviews + stale_keys,
    )
    result = rules.classify(inp)
    summary = {
        'suggested_from': result.suggested_from,
        'agreements': result.agreements,
        'human_decision': result.human,
        'source_keys': [{k: v for k, v in sk.items() if k != 'imported_at'} for sk in source_keys],
        'stale_ignored': {'reviews': stale_reviews, 'source_keys': stale_keys},
        'stem_hash': current_hash,
    }
    if inp.evidence:
        summary['evidence'] = {k: v for k, v in inp.evidence.items() if k != 'at'}
    fields = {
        'status': result.status,
        'status_reason': result.reason[:64],
        'stored_key': key,
        'original_key': _original_key(question, key, ctx),
        'key_provenance': provenance,
        'suggested_key': result.suggested_key,
        'confidence': None,
        'priority': result.priority,
        'signals': result.signals,
        'reviews': reviews,
        'evidence_run_id': (inp.evidence or {}).get('run_id'),
        'evidence_summary': summary,
        'method_version': rules.METHOD_VERSION,
        'is_stale': False,
    }
    return Prepared(question=question, result=result, fields=fields)


# --------------------------------------------------------------------------- audit + save

def audit_questions(questions: Sequence[Question], *, save: bool = False, skew: Optional[dict] = None,
                    extra_reviews: Optional[dict] = None) -> list:
    """Audit ``questions`` (Question instances). Returns ``Prepared`` items; with ``save`` the
    QuestionAudit rows are written (reviews kept) and ``Question.answer_key_status`` mirrors the status.

    ``extra_reviews``: ``{question_id: [review, ...]}`` merged into the stored reviews.
    """
    questions = list(questions)
    extra_reviews = extra_reviews or {}
    if skew is None:
        skew = key_skew({(q.exam_type, q.year) for q in questions})
    out = []
    for start in range(0, len(questions), CHUNK):
        chunk = questions[start:start + CHUNK]
        if not save:
            ctx = _load_context(chunk, skew=skew, lock=False)
            out.extend(prepare(q, ctx, extra_reviews=extra_reviews.get(q.pk, ())) for q in chunk)
            continue
        try:
            out.extend(_save_chunk(chunk, skew, extra_reviews))
        except IntegrityError:
            # Another process created an audit row for one of these questions meanwhile: once more.
            out.extend(_save_chunk(chunk, skew, extra_reviews))
    return out


def _save_chunk(chunk, skew, extra_reviews) -> list:
    now = timezone.now()
    with transaction.atomic():
        ctx = _load_context(chunk, skew=skew, lock=True)
        prepared = [prepare(q, ctx, extra_reviews=extra_reviews.get(q.pk, ())) for q in chunk]
        update, create = [], []
        for item in prepared:
            audit = ctx.audits.get(item.question.pk)
            if audit is None:
                audit = QuestionAudit(question=item.question)
                create.append(audit)
            else:
                update.append(audit)
            for name, value in item.fields.items():
                setattr(audit, name, value)
            audit.audited_at = now
            audit.updated_at = now   # bulk_update does not apply auto_now
        if update:
            names = [('evidence_run' if name == 'evidence_run_id' else name) for name in prepared[0].fields]
            QuestionAudit.objects.bulk_update(update, names + ['audited_at', 'updated_at'])
        if create:
            QuestionAudit.objects.bulk_create(create)
        by_status = defaultdict(list)
        for item in prepared:
            if item.question.answer_key_status != item.fields['status']:
                by_status[item.fields['status']].append(item.question.pk)
        for status, ids in by_status.items():
            Question.objects.filter(pk__in=ids).update(answer_key_status=status)
    return prepared


def audit_question(question: Question, *, reviews: Optional[Sequence[dict]] = None, run_evidence: bool = False,
                   save: bool = True) -> QuestionAudit:
    """Audit one question (contract: docs/audit/MEDICAL_ACCURACY_DESIGN.md section 4).

    ``reviews`` are merged into the stored ones; ``run_evidence`` first records a reference-corpus
    evidence decision when the store is available. Returns the QuestionAudit (unsaved with ``save=False``).
    """
    if run_evidence:
        _run_evidence(question)
    question = Question.objects.get(pk=question.pk)   # fresh: the caller's copy may predate a change
    extra = {question.pk: list(reviews)} if reviews else None
    prepared = audit_questions([question], save=save, extra_reviews=extra)[0]
    if save:
        return QuestionAudit.objects.get(question_id=question.pk)
    audit = QuestionAudit(question=question, audited_at=timezone.now())
    for name, value in prepared.fields.items():
        setattr(audit, name, value)
    return audit


def _run_evidence(question) -> None:
    try:
        from reference_corpus import api
        if api.store_available():
            api.decide(question, stored_key=valid_key(question.correct_answer), purpose='audit', save=True)
    except Exception:  # noqa: BLE001 - evidence is optional; the audit still runs
        logger.exception('evidence decision failed for question %s', question.pk)


# --------------------------------------------------------------------------- review signals

def merge_keep_at(existing: Sequence[dict], incoming: Sequence[dict]) -> list:
    """``existing`` with ``incoming`` merged (same identity replaces). A re-imported review keeps its
    first ``at`` when its verdict, letter and content hash are unchanged, so importing a file again
    does not look like new information to a human decision made in between."""
    from key_audit.reviews import identity

    by_identity = {identity(r): r for r in existing if isinstance(r, dict)}
    kept = []
    for review in incoming:
        old = by_identity.get(identity(review))
        if old and all(old.get(k) == review.get(k) for k in ('verdict', 'best_option', 'stem_hash')):
            review = dict(review, at=old.get('at') or review.get('at'))
        kept.append(review)
    return merge(existing, kept)


def record_reviews(question_id: int, reviews: Sequence[dict]) -> Prepared:
    """Merge ``reviews`` (normalized, ``key_audit.reviews`` format) into the question's audit and
    re-classify it (row-locked)."""
    question = Question.objects.get(pk=question_id)
    return audit_questions([question], save=True, extra_reviews={question_id: list(reviews)})[0]


# --------------------------------------------------------------------------- hooks

def queue_question_audit(question_id: int, reason: str = '') -> None:
    """Mark the question's audit stale (contract name; ``on_question_changed`` also re-audits)."""
    QuestionAudit.objects.filter(question_id=question_id).update(is_stale=True)


def on_question_changed(question, *, old_key: str = '', old_stem_hash: str = '', reason: str = '', actor=None) -> None:
    """``questions.content_hooks`` reaction: record a content change and re-audit the question.

    A stem / option change voids the human decisions made before it (``content_changed_at``); a key
    change is itself a decision (``AnswerKeyChange``) and needs nothing more here.
    """
    qid = getattr(question, 'pk', question)
    fresh = Question.objects.filter(pk=qid).first()
    if fresh is None:
        return
    if old_stem_hash and old_stem_hash != stem_hash(fresh):
        QuestionAudit.objects.filter(question_id=qid).update(content_changed_at=timezone.now(), is_stale=True)
    else:
        queue_question_audit(qid, reason)
    audit_questions([fresh], save=True)


def key_status_for(question_ids: Iterable[int]) -> dict:
    """``{question_id: audit status}`` (contract; used by questions.key_status)."""
    qs = QuestionAudit.objects.filter(question_id__in=list(question_ids)).values('question_id', 'status')
    return {row['question_id']: row['status'] for row in qs}


__all__ = [
    'STRONG_EVIDENCE_KINDS', 'Prepared', 'audit_question', 'audit_questions', 'key_skew', 'key_status_for',
    'on_question_changed', 'prepare', 'queue_question_audit', 'record_reviews',
]
