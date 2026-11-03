"""Answer-key audit: the one place that turns signals into a status (2026-11).

Pure functions over plain data (``AuditInput``), so every rule has a unit test without a database;
``key_audit.services`` gathers the data. Ground rules (docs/audit/MEDICAL_ACCURACY_DESIGN.md): the
result never changes a key, and AI output is a review signal, never evidence.

Status (``QuestionAudit.STATUS_CHOICES``), the first rule that applies:

1. ``needs_review`` / ``invalid_or_missing_key``   the stored key is not A-D.
2. An official answer key: ``needs_review`` / ``official_key_disagrees`` when it names another
   option, ``verified`` / ``official_key_match`` when it names the stored one.
3. The latest human decision on the question, when it was made for the current key:
   ``needs_review`` / ``new_signal_after_review``  a risk signal was recorded after it;
   ``verified`` / ``human_verified_with_evidence``  it cites strong evidence (official key, errata,
   guideline, page-cited passage); ``likely_correct`` / ``human_confirmed``  it cites none.
   A human request for review (unverify, defer) is ``needs_review`` / ``human_requested_review``;
   a decision for another letter than the current key is ``needs_review`` /
   ``key_changed_after_review``.
4. ``contradictory_sources``  verified passages, or two confident source keys, back different options.
5. ``needs_review`` / <strongest open signal>  any risk signal that opens a review.
6. ``image_context_missing``  the question needs an image that is not attached.
7. ``verified`` / ``evidence_verified``  verified passages (tier <= 3) support the stored key and two
   other independent signals agree. ``likely_correct`` / ``evidence_supported`` (the passages alone)
   or ``independent_agreement`` (two independent signals agree, e.g. the source's printed key and an
   AI review; an AI-chosen key needs one agreement that is not an AI review).
8. ``insufficient_evidence``  anything else: one AI opinion, or one printed key, is not enough.

Priority (queue order, higher first) is the strongest open signal plus 0.5 per further open signal
(at most 5). ``suggested_key`` is what the strongest signal that names a letter points to; it is
shown to the reviewer and never applied.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

LETTERS = ('A', 'B', 'C', 'D')
METHOD_VERSION = 'audit-v2-2026-11-03'

# code: (severity, priority, opens_review). Signals that do not open a review are shown to the
# reviewer but leave the status alone.
SIGNAL_RULES = {
    'official_key_disagrees': ('critical', 100.0, True),
    'source_key_mismatch': ('critical', 95.0, True),
    'evidence_conflict': ('critical', 92.0, True),
    'invalid_or_missing_key': ('critical', 90.0, True),
    'explanation_states_other': ('critical', 90.0, True),
    'label_key_conflict': ('high', 85.0, True),
    'human_requested_review': ('high', 85.0, True),
    'key_changed_after_review': ('high', 80.0, True),
    'open_wrong_answer_report': ('high', 80.0, True),
    'source_key_mismatch_unverified': ('high', 75.0, True),
    'ai_review_disagrees': ('high', 70.0, True),
    'duplicate_key_conflict': ('high', 65.0, True),
    'skewed_key_distribution': ('high', 60.0, True),
    'is_disputed': ('medium', 60.0, True),
    'ai_no_correct_option': ('medium', 55.0, True),
    'label_hold': ('medium', 50.0, True),
    'ai_content_defect': ('medium', 45.0, True),
    'ai_ambiguous': ('low', 35.0, True),
    'image_context_missing': ('high', 60.0, False),
    'explanation_conflicts_with_reviewed_key': ('medium', 40.0, False),
    'ai_chosen_key': ('info', 0.0, False),
    'needs_review_flag': ('info', 0.0, False),
    'ai_answer_in_text': ('info', 0.0, False),
    'ai_wrong_subject': ('info', 0.0, False),
    'source_year_differs': ('info', 0.0, False),
    'stale_reviews_ignored': ('info', 0.0, False),
}
# Signals that name a letter, strongest first: the first open one gives suggested_key.
SUGGESTION_ORDER = (
    'official_key_disagrees', 'key_changed_after_review', 'evidence_conflict', 'source_key_mismatch',
    'explanation_states_other',
    'label_key_conflict', 'source_key_mismatch_unverified', 'ai_review_disagrees',
)
# After a human decision these keep (or bring back) a review; every other signal recorded before the
# decision was in front of the reviewer and is settled by it.
ONGOING_AFTER_DECISION = ('official_key_disagrees', 'is_disputed', 'invalid_or_missing_key')
AI_ISSUE_SIGNALS = {
    'no_correct_option': 'ai_no_correct_option', 'multiple_correct': 'ai_no_correct_option',
    'options_incomplete': 'ai_content_defect', 'garbled_text': 'ai_content_defect',
    'duplicate_options': 'ai_content_defect',
    'ambiguous': 'ai_ambiguous', 'outdated_or_guideline_dependent': 'ai_ambiguous',
    'answer_in_text': 'ai_answer_in_text', 'wrong_subject': 'ai_wrong_subject',
}
AI_DISAGREE_PRIORITY = {'high': 70.0, 'medium': 55.0, 'low': 40.0}
STRONG_EVIDENCE_KINDS = ('official_key', 'errata', 'guideline_url', 'passage')


@dataclass
class Signal:
    code: str
    detail: str = ''
    at: Optional[datetime] = None          # when it was recorded; None = a current state of the question
    suggested_key: str = ''
    data: dict = field(default_factory=dict)
    priority: Optional[float] = None        # overrides the rule's priority (AI confidence)

    @property
    def severity(self) -> str:
        return SIGNAL_RULES[self.code][0]

    @property
    def opens_review(self) -> bool:
        return SIGNAL_RULES[self.code][2]

    def effective_priority(self) -> float:
        return self.priority if self.priority is not None else SIGNAL_RULES[self.code][1]

    def as_dict(self, *, settled: bool = False) -> dict:
        out = {'code': self.code, 'severity': self.severity, 'detail': self.detail,
               'opens_review': self.opens_review, 'priority': self.effective_priority()}
        if self.suggested_key:
            out['suggested_key'] = self.suggested_key
        if self.at is not None:
            out['at'] = self.at.isoformat()
        if self.data:
            out['data'] = self.data
        if settled:
            out['settled_by_review'] = True
        return out


@dataclass
class Agreement:
    kind: str         # source_key | ai_review | evidence
    detail: str = ''


@dataclass
class HumanDecision:
    reviewer: str                 # 'human:<user id>'
    verdict: str                  # agree | disagree | uncertain
    best_option: str
    strong_evidence: bool
    at: Optional[datetime]
    source: str = ''              # review_queue | key_change | admin_verify
    ref: str = ''


@dataclass
class AuditInput:
    key: str                                   # valid stored key or ''
    signals: list = field(default_factory=list)          # deterministic Signal objects
    ai_reviews: list = field(default_factory=list)       # effective, non-stale AI reviews (dicts)
    official_reviews: list = field(default_factory=list)  # effective official-key reviews (dicts)
    human: Optional[HumanDecision] = None
    source_keys: list = field(default_factory=list)      # [{letter, confident, source_file, question_page, ...}]
    evidence: Optional[dict] = None            # {status, evidence_answer, citations, tier_ok}
    image_missing: bool = False
    image_detail: str = ''
    ai_chosen_key: bool = False
    stale_review_count: int = 0


@dataclass
class AuditResult:
    status: str
    reason: str
    priority: float
    suggested_key: str
    suggested_from: str
    signals: list          # dicts, open first
    agreements: list       # dicts
    human: Optional[dict]


def _letter(value) -> str:
    text = (value or '').strip().upper()[:1] if isinstance(value, str) else ''
    return text if text in LETTERS else ''


def _effective(review: dict, key: str) -> tuple:
    from key_audit.reviews import effective
    return effective(review, key)


def collect(inp: AuditInput) -> tuple:
    """(signals, agreements) for ``inp``: the deterministic signals plus those the reviews,
    source keys and evidence add."""
    key = inp.key
    signals = list(inp.signals)
    agreements = []

    for review in inp.ai_reviews:
        verdict, best = _effective(review, key)
        label = review.get('reviewer') or 'AI reviewer'
        reason = (review.get('reason') or '')[:240]
        if verdict == 'agree':
            agreements.append(Agreement('ai_review', f'{label} (pass {review.get("pass", "?")})'))
        elif verdict == 'disagree':
            confidence = review.get('confidence') or 'low'
            signals.append(Signal(
                'ai_review_disagrees', f'{label} picks {best or "another option"} ({confidence} confidence): {reason}',
                at=_parse(review.get('at')), suggested_key=_letter(best),
                priority=AI_DISAGREE_PRIORITY.get(confidence, 40.0),
                data={'reviewer': label, 'pass': review.get('pass'), 'confidence': confidence},
            ))
        by_code = {}
        for issue in review.get('issues') or []:
            code = AI_ISSUE_SIGNALS.get(issue)
            if code:   # ('image_required' adds nothing: the deterministic image check decides)
                by_code.setdefault(code, []).append(issue)
        for code, issues in by_code.items():
            words = ', '.join(i.replace('_', ' ') for i in issues)
            signals.append(Signal(code, f'{label} reports {words}', at=_parse(review.get('at')),
                                  data={'reviewer': label, 'issues': issues}))

    for review in inp.official_reviews:
        verdict, best = _effective(review, key)
        source = review.get('official_source') or 'official answer key'
        if verdict == 'disagree' and best:
            signals.append(Signal('official_key_disagrees', f'{source} gives {best}', at=_parse(review.get('at')),
                                  suggested_key=best, data={'official_source': source}))

    confident_match = any(row.get('confident') and _letter(row.get('letter')) == key for row in inp.source_keys)
    for row in inp.source_keys:
        letter = _letter(row.get('letter'))
        if not letter or not key:
            continue
        where = f"{row.get('source_file', '?')} p.{row.get('question_page', '?')} Q{row.get('question_number', '?')}"
        if letter == key:
            if row.get('confident'):
                agreements.append(Agreement('source_key', f'printed key {letter} in {where}'))
            continue
        if not row.get('confident') and confident_match:
            continue   # an unchecked reading loses to a confident one that agrees with the key
        code = 'source_key_mismatch' if row.get('confident') else 'source_key_mismatch_unverified'
        why = '' if row.get('confident') else (
            ' (stem not found in the source text)' if not row.get('located') else ' (option order not checked)')
        signals.append(Signal(code, f'{where} prints {row.get("printed_letter") or letter}'
                                    f'{"" if letter == row.get("printed_letter") else f" = {letter} here"}; stored {key}{why}',
                              at=row.get('imported_at'), suggested_key=letter,
                              data={k: row.get(k) for k in ('source_file', 'question_page', 'answer_page',
                                                            'question_number', 'method', 'option_order', 'located')}))

    evidence = inp.evidence or {}
    if evidence.get('status') == 'conflict' and _letter(evidence.get('evidence_answer')) not in ('', key):
        signals.append(Signal('evidence_conflict', f"reference passages support {evidence['evidence_answer']}",
                              at=evidence.get('at'), suggested_key=_letter(evidence.get('evidence_answer')),
                              data={'run_id': evidence.get('run_id')}))
    elif evidence.get('status') == 'supported' and key and _letter(evidence.get('evidence_answer')) == key \
            and evidence.get('tier_ok'):
        agreements.append(Agreement('evidence', f"{evidence.get('citations', 0)} verified passage(s) support {key}"))

    if inp.image_missing:
        signals.append(Signal('image_context_missing', inp.image_detail or 'the question needs an image that is not attached'))
    if inp.ai_chosen_key:
        signals.append(Signal('ai_chosen_key', 'the stored key was chosen by an AI importer'))
    if inp.stale_review_count:
        signals.append(Signal('stale_reviews_ignored',
                              f'{inp.stale_review_count} review(s) of an earlier version of the question ignored'))
    return signals, agreements


def _parse(value):
    from key_audit.reviews import parse_at
    return value if isinstance(value, datetime) else parse_at(value)


def _priority(open_signals) -> float:
    if not open_signals:
        return 0.0
    ranked = sorted((s.effective_priority() for s in open_signals), reverse=True)
    return ranked[0] + 0.5 * min(len(ranked) - 1, 5)


def _suggestion(open_signals) -> tuple:
    for code in SUGGESTION_ORDER:
        letters = [s.suggested_key for s in open_signals if s.code == code and s.suggested_key]
        if letters:
            letter, _n = Counter(letters).most_common(1)[0]
            return letter, code
    return '', ''


def _independent(agreements, *, ai_chosen_key: bool) -> bool:
    kinds = Counter(a.kind for a in agreements)
    non_ai = sum(n for kind, n in kinds.items() if kind != 'ai_review')
    if ai_chosen_key and not non_ai:
        return False
    return sum(kinds.values()) >= 2


def classify(inp: AuditInput) -> AuditResult:
    signals, agreements = collect(inp)
    key = inp.key
    contradictory = _contradictory(inp)
    human = inp.human

    def result(status, reason, open_signals, settled=()):
        suggested, suggested_from = _suggestion(open_signals)
        if suggested == key:
            suggested, suggested_from = '', ''
        settled_ids = {id(s) for s in settled}
        ordered = sorted(signals, key=lambda s: (id(s) in settled_ids, not s.opens_review, -s.effective_priority()))
        priority = _priority(open_signals)
        explanation_fix = [s for s in signals if s.code == 'explanation_conflicts_with_reviewed_key']
        if not open_signals and explanation_fix:
            priority = explanation_fix[0].effective_priority()
        return AuditResult(
            status=status, reason=reason, priority=priority, suggested_key=suggested, suggested_from=suggested_from,
            signals=[s.as_dict(settled=id(s) in settled_ids) for s in ordered],
            agreements=[{'kind': a.kind, 'detail': a.detail} for a in agreements],
            human=None if human is None else {
                'reviewer': human.reviewer, 'verdict': human.verdict, 'best_option': human.best_option,
                'strong_evidence': human.strong_evidence, 'at': human.at.isoformat() if human.at else None,
                'source': human.source, 'ref': human.ref,
            },
        )

    opening = [s for s in signals if s.opens_review]

    # 1. invalid key
    if not key:
        return result('needs_review', 'invalid_or_missing_key', opening)

    # 2. official answer key
    official_disagree = [s for s in signals if s.code == 'official_key_disagrees']
    if official_disagree:
        return result('needs_review', 'official_key_disagrees', opening)
    if any(_effective(r, key)[0] == 'agree' for r in inp.official_reviews):
        return result('verified', 'official_key_match', [])

    # 3. the latest human decision
    if human is not None:
        if human.verdict in ('disagree', 'uncertain'):
            signals.append(Signal('human_requested_review', f'{human.reviewer} asked for a review', at=human.at))
            return result('needs_review', 'human_requested_review', [s for s in signals if s.opens_review])
        if human.best_option and human.best_option != key:
            signals.append(Signal('key_changed_after_review',
                                  f'{human.reviewer} decided {human.best_option}; the key is now {key}', at=human.at,
                                  suggested_key=human.best_option))
            return result('needs_review', 'key_changed_after_review', [s for s in signals if s.opens_review])
        new = [s for s in opening if s.code in ONGOING_AFTER_DECISION
               or (s.at is not None and human.at is not None and s.at > human.at)]
        settled = [s for s in signals if s not in new]
        for s in list(signals):
            if s.code == 'explanation_states_other' and s not in new:
                signals.append(Signal('explanation_conflicts_with_reviewed_key',
                                      f'the explanation names {s.suggested_key}, the reviewed key is {key}'))
        if new:
            return result('needs_review', 'new_signal_after_review', new, settled)
        if human.strong_evidence:
            return result('verified', 'human_verified_with_evidence', [], settled)
        return result('likely_correct', 'human_confirmed', [], settled)

    # 4. contradictory sources
    if contradictory:
        return result('contradictory_sources', contradictory, opening)

    # 5. open risk signals
    if opening:
        strongest = max(opening, key=lambda s: s.effective_priority())
        return result('needs_review', strongest.code, opening)

    # 6. image needed and missing
    if inp.image_missing:
        return result('image_context_missing', 'image_context_missing', [])

    # 7. agreement
    evidence_ok = any(a.kind == 'evidence' for a in agreements)
    others = [a for a in agreements if a.kind != 'evidence']
    if evidence_ok and len(others) >= 2:
        return result('verified', 'evidence_verified', [])
    if evidence_ok:
        return result('likely_correct', 'evidence_supported', [])
    if _independent(agreements, ai_chosen_key=inp.ai_chosen_key):
        return result('likely_correct', 'independent_agreement', [])

    # 8. nothing either way
    return result('insufficient_evidence', 'no_independent_agreement' if agreements else 'no_evidence', [])


def _contradictory(inp: AuditInput) -> str:
    if (inp.evidence or {}).get('status') == 'contradictory_sources':
        return 'evidence_contradictory'
    letters = {_letter(row.get('letter')) for row in inp.source_keys if row.get('confident')} - {''}
    if len(letters) > 1:
        return 'source_keys_disagree'
    return ''
