"""How far a question's stored answer key can be trusted in study material (2026-11).

``key_statuses(questions)`` sorts each question into

* ``verified``     -- an admin verified it, or the answer-key audit (``key_audit.QuestionAudit``)
                      says ``verified`` for the key it holds now;
* ``provisional``  -- usable with a warning: nothing contradicts the key, but nothing confirms it;
* ``excluded``     -- not usable: no key, inactive, disputed, a risk signal or an audit finding.

Rules (docs/audit/MEDICAL_ACCURACY_DESIGN.md section 4, pyq-notes map A1), first match wins:

EXCLUDED  no_key, inactive, scholarship, disputed, controversial, open_wrong_answer_report,
          label_hold / label_key_conflict (answer labels in the public text, questions.answer_leak),
          image_context_missing (needs an image and has no active stem image),
          duplicate_key_conflict (a duplicate of it -- active or not -- has another answer text),
          audit_needs_review / audit_contradictory_sources / audit_image_context_missing
          (also from an audit made for an older key: excluding is the safe direction).
VERIFIED  audit_verified (a current audit: not stale, made for the key the question holds now),
          admin_verified (no key change after the verification).
PROVISIONAL, with the first matching reason: verification_stale, audit_stale, key_changed
          (an AnswerKeyChange row or a revision snapshot holding another key), ai_solved_import
          (legacy CMS importer rows whose key an LLM chose, or an audit saying so), needs_review,
          audit_likely_correct, audit_insufficient_evidence, recall_key, unverified.

A fixed number of bulk queries per call (no query per question). Nothing here writes.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from questions.content_hashes import valid_key

VERIFIED = 'verified'
PROVISIONAL = 'provisional'
EXCLUDED = 'excluded'
STATUSES = (VERIFIED, PROVISIONAL, EXCLUDED)

# Audit statuses (key_audit.QuestionAudit.status / Question.answer_key_status).
AUDIT_EXCLUDING = ('needs_review', 'contradictory_sources', 'image_context_missing')
AUDIT_PROVISIONAL = ('likely_correct', 'insufficient_evidence')

# Legacy CMS year importers (import_2018_2019_pyqs / 2023_2024 / 2025) stored an LLM's pick as the key.
AI_SOLVED_SOURCE_RE = re.compile(r'^PYQ_\d{4}_Paper\d\.txt$')

# The fields the rules read; callers that load questions themselves can use .only(*QUESTION_FIELDS).
QUESTION_FIELDS = (
    'id', 'correct_answer', 'is_active', 'is_dropped', 'is_scholarship_eligible', 'is_disputed',
    'is_controversial', 'needs_review', 'is_image_based', 'question_type', 'source', 'admin_edited',
    'is_verified_by_admin', 'verified_at', 'answer_key_status', 'recall_status', 'lock_answer',
    'lock_explanation', 'question_text', 'option_a', 'option_b', 'option_c', 'option_d', 'explanation',
)

_STEM_IMAGE_ROLES = ('primary', 'option', 'illustration')


@dataclass(frozen=True)
class KeyStatus:
    status: str   # verified | provisional | excluded
    reason: str

    @property
    def usable(self) -> bool:
        return self.status != EXCLUDED


def _norm_answer(text) -> str:
    """Option text compared across duplicates (letters differ when the option order differs)."""
    from questions.answer_leak import cut_option_text
    text = cut_option_text(text or '') if isinstance(text, str) else ''
    return re.sub(r'[^a-z0-9]+', ' ', text.lower()).strip()


def correct_option_text(row) -> str:
    """The text of the option the key names ('' without a valid key); row = Question or dict."""
    key = valid_key(row.get('correct_answer') if isinstance(row, dict) else getattr(row, 'correct_answer', ''))
    if not key:
        return ''
    name = f'option_{key.lower()}'
    return (row.get(name) if isinstance(row, dict) else getattr(row, name, '')) or ''


def needs_image(question) -> bool:
    return bool(getattr(question, 'is_image_based', False) or getattr(question, 'question_type', '') == 'image_based')


def _load(questions) -> list:
    """Question instances for ``questions`` (instances, ids, or a mix)."""
    from questions.models import Question

    items = list(questions or [])
    ids = [item for item in items if isinstance(item, int)]
    rows = [item for item in items if not isinstance(item, int) and getattr(item, 'pk', None) is not None]
    if ids:
        rows += list(Question.objects.filter(pk__in=ids).only(*QUESTION_FIELDS))
    unique = {}
    for row in rows:
        unique.setdefault(row.pk, row)
    return list(unique.values())


def _open_wrong_answer_reports(ids) -> set:
    from questions.models import QuestionFeedback
    return set(QuestionFeedback.objects.filter(
        question_id__in=ids, category='wrong_answer', status__in=('new', 'in_progress'),
    ).values_list('question_id', flat=True))


def _with_stem_image(ids) -> set:
    from questions.models import QuestionImage
    if not ids:
        return set()
    return set(QuestionImage.objects.filter(
        question_id__in=ids, is_active=True, role__in=_STEM_IMAGE_ROLES,
    ).values_list('question_id', flat=True))


def _duplicate_conflicts(rows) -> set:
    """Ids whose duplicate cluster (active and soft-deleted members, the canonical question included)
    holds a different answer text. Every member is compared: deduplication deactivated all but one
    member of each cluster, so the disagreement is invisible among active rows only."""
    from questions.models import DuplicateCluster, DuplicateMember, Question

    ids = [row.pk for row in rows]
    if not ids:
        return set()
    cluster_ids = set(DuplicateMember.objects.filter(question_id__in=ids).values_list('cluster_id', flat=True))
    cluster_ids |= set(DuplicateCluster.objects.filter(canonical_question_id__in=ids).values_list('id', flat=True))
    if not cluster_ids:
        return set()
    members = defaultdict(set)
    for cluster_id, question_id in DuplicateMember.objects.filter(cluster_id__in=cluster_ids).values_list(
            'cluster_id', 'question_id'):
        members[cluster_id].add(question_id)
    for cluster_id, question_id in DuplicateCluster.objects.filter(id__in=cluster_ids).values_list(
            'id', 'canonical_question_id'):
        members[cluster_id].add(question_id)
    all_ids = {qid for qids in members.values() for qid in qids}
    texts = {}
    for row in Question.objects.filter(pk__in=all_ids).values(
            'id', 'correct_answer', 'option_a', 'option_b', 'option_c', 'option_d'):
        answer = _norm_answer(correct_option_text(row))
        if answer:
            texts[row['id']] = answer
    conflicted = set()
    wanted = set(ids)
    for qids in members.values():
        answers = {texts[qid] for qid in qids if qid in texts}
        if len(answers) > 1:
            conflicted |= qids & wanted
    return conflicted


def _audits(ids) -> dict:
    try:
        from key_audit.models import QuestionAudit
    except Exception:  # pragma: no cover - key_audit app not installed
        return {}
    return {row['question_id']: row for row in QuestionAudit.objects.filter(question_id__in=ids).values(
        'question_id', 'status', 'stored_key', 'is_stale', 'key_provenance')}


def _key_history(rows) -> tuple[set, dict]:
    """(ids whose key differs from an earlier recorded key, {id: latest key-change time})."""
    from django.db.models.fields.json import KT
    from questions.models import AnswerKeyChange, QuestionRevisionSnapshot

    current = {row.pk: valid_key(row.correct_answer) for row in rows}
    ids = list(current)
    changed, last_change = set(), {}
    for qid, changed_at in AnswerKeyChange.objects.filter(question_id__in=ids).values_list('question_id', 'changed_at'):
        changed.add(qid)
        if last_change.get(qid) is None or changed_at > last_change[qid]:
            last_change[qid] = changed_at
    snapshots = QuestionRevisionSnapshot.objects.filter(question_id__in=ids).annotate(
        old_key=KT('snapshot__correct_answer'),
    ).values_list('question_id', 'old_key', 'created_at')
    for qid, old_key, created_at in snapshots:
        old = valid_key(old_key)
        if old and old != current.get(qid):
            changed.add(qid)
            if last_change.get(qid) is None or created_at > last_change[qid]:
                last_change[qid] = created_at
    return changed, last_change


def _label_status(row):
    """'label_hold' / 'label_key_conflict' when an answer label in the public text makes the key unusable."""
    from questions.answer_leak import plan_repair, row_has_answer_label
    if not row_has_answer_label(row):
        return ''
    repair = plan_repair(row)
    if repair.deactivate:
        return 'label_hold'
    if repair.conflict:
        return 'label_key_conflict'
    return ''


def key_statuses(questions) -> dict:
    """``{question_id: KeyStatus}`` for Question instances and/or ids (see the module docstring)."""
    rows = _load(questions)
    if not rows:
        return {}
    ids = [row.pk for row in rows]
    reports = _open_wrong_answer_reports(ids)
    images = _with_stem_image([row.pk for row in rows if needs_image(row)])
    duplicates = _duplicate_conflicts(rows)
    audits = _audits(ids)
    changed, last_change = _key_history(rows)

    out = {}
    for row in rows:
        key = valid_key(row.correct_answer)
        audit = audits.get(row.pk)
        if audit:
            audit_status = audit['status']
            # Current = made for the key the question holds now, and not invalidated by an edit since.
            audit_current = bool(key and not audit['is_stale'] and valid_key(audit['stored_key']) == key)
        else:
            stored = (getattr(row, 'answer_key_status', '') or '').strip()
            audit_status = '' if stored in ('', 'unaudited') else stored
            # Without the audit row a 'verified' status cannot be checked against the key it was
            # given for: it is trusted only while no key change is recorded.
            audit_current = row.pk not in changed

        def excluded(reason):
            out[row.pk] = KeyStatus(EXCLUDED, reason)

        if not key:
            excluded('no_key')
        elif not row.is_active or row.is_dropped:
            excluded('inactive')
        elif row.is_scholarship_eligible:
            excluded('scholarship')
        elif row.is_disputed:
            excluded('disputed')
        elif row.is_controversial:
            excluded('controversial')
        elif row.pk in reports:
            excluded('open_wrong_answer_report')
        elif (label := _label_status(row)):
            excluded(label)
        elif needs_image(row) and row.pk not in images:
            excluded('image_context_missing')
        elif row.pk in duplicates:
            excluded('duplicate_key_conflict')
        elif audit_status in AUDIT_EXCLUDING:
            excluded(f'audit_{audit_status}')
        elif audit_status == 'verified' and audit_current:
            out[row.pk] = KeyStatus(VERIFIED, 'audit_verified')
        elif row.is_verified_by_admin and not _changed_after(last_change.get(row.pk), row.verified_at):
            out[row.pk] = KeyStatus(VERIFIED, 'admin_verified')
        else:
            out[row.pk] = KeyStatus(PROVISIONAL, _provisional_reason(row, audit, audit_status, audit_current, changed))
    return out


def _changed_after(changed_at, verified_at) -> bool:
    """True when the key changed after the admin verification (unknown verification time: any change)."""
    if changed_at is None:
        return False
    return verified_at is None or changed_at > verified_at


def _provisional_reason(row, audit, audit_status, audit_current, changed) -> str:
    if row.is_verified_by_admin:
        return 'verification_stale'
    if audit_status == 'verified' and not audit_current:
        return 'audit_stale'
    if row.pk in changed:
        return 'key_changed'
    if (audit and audit.get('key_provenance') == 'ai_enrichment') or (
            AI_SOLVED_SOURCE_RE.match(row.source or '') and not row.admin_edited):
        return 'ai_solved_import'
    if row.needs_review:
        return 'needs_review'
    if audit_status in AUDIT_PROVISIONAL:
        return f'audit_{audit_status}'
    if (row.recall_status or '') == 'recall':
        return 'recall_key'
    return 'unverified'


def summarize(statuses: dict) -> dict:
    """``{'verified': n, 'provisional': n, 'excluded': n, 'reasons': {reason: n}}``."""
    counts = {status: 0 for status in STATUSES}
    reasons = defaultdict(int)
    for status in statuses.values():
        counts[status.status] += 1
        reasons[f'{status.status}:{status.reason}'] += 1
    counts['reasons'] = dict(sorted(reasons.items()))
    return counts
