"""Serializers for the answer-key review queue (admin only)."""
from __future__ import annotations

import re

from rest_framework import serializers

from key_audit.models import AuditResolution, QuestionAudit, SourceKey
from key_audit.reviews import display_label, reviewer_kind
from questions.content_hashes import valid_key

# Explanation fields a resolution may write together with a key change / explanation fix (the ones
# questions.editorial writes; anything else is rejected).
from questions.editorial import EXPLANATION_FIELDS  # noqa: E402
MAX_EXPLANATION = 20_000
MAX_EVIDENCE_ITEMS = 10

# Evidence a reviewer may cite. 'note' is reasoning, 'source_key' points at a printed source key
# (tier 4); neither makes a decision "verified" (key_audit.reviews.STRONG_EVIDENCE_KINDS).
EVIDENCE_KINDS = ('official_key', 'errata', 'guideline_url', 'passage', 'source_key', 'note')
_REQUIRED = {
    'official_key': ('source_title',),
    'errata': ('source_title',),
    'guideline_url': ('source_title', 'url'),
    'passage': ('source_title', 'page_label', 'quote'),
    'source_key': ('source_key_id',),
    'note': ('text',),
}
_TEXT_LIMITS = {'source_title': 200, 'edition': 60, 'page_label': 40, 'quote': 600, 'chunk_key': 160,
                'text': 600, 'url': 500}
_URL_RE = re.compile(r'^https?://[^\s<>"\']{3,}$', re.IGNORECASE)
_SHA_RE = re.compile(r'^[0-9a-f]{64}$')
_CONTROL_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')


def _clean(value, limit):
    text = value if isinstance(value, str) else ('' if value is None else str(value))
    return _CONTROL_RE.sub('', text).strip()[:limit]


def clean_evidence_item(item) -> dict:
    """One evidence item with only the known fields. Raises ``serializers.ValidationError``."""
    if not isinstance(item, dict):
        raise serializers.ValidationError('each evidence item is an object')
    kind = _clean(item.get('kind'), 20)
    if kind not in EVIDENCE_KINDS:
        raise serializers.ValidationError(f'evidence kind must be one of {", ".join(EVIDENCE_KINDS)}')
    out = {'kind': kind}
    for name, limit in _TEXT_LIMITS.items():
        text = _clean(item.get(name), limit)
        if text:
            out[name] = text
    if 'url' in out and not _URL_RE.match(out['url']):
        raise serializers.ValidationError('url must be an http(s) address')
    sha = _clean(item.get('source_sha256'), 64).lower()
    if sha:
        if not _SHA_RE.match(sha):
            raise serializers.ValidationError('source_sha256 must be 64 hex characters')
        out['source_sha256'] = sha
    for name in ('year', 'source_key_id'):
        if item.get(name) not in (None, ''):
            try:
                out[name] = int(item[name])
            except (TypeError, ValueError):
                raise serializers.ValidationError(f'{name} must be a number') from None
    supports = valid_key(item.get('supports_option'))
    if supports:
        out['supports_option'] = supports
    missing = [name for name in _REQUIRED[kind] if not out.get(name)]
    if missing:
        raise serializers.ValidationError(f'{kind} evidence needs {", ".join(missing)}')
    if kind == 'passage' and len(out['quote']) < 10:
        raise serializers.ValidationError('a passage needs the quoted sentence (at least 10 characters)')
    return out


class SourceKeySerializer(serializers.ModelSerializer):
    confident = serializers.BooleanField(read_only=True)

    class Meta:
        model = SourceKey
        fields = ['id', 'source_file', 'question_page', 'question_number', 'answer_page', 'chapter', 'source_exam',
                  'source_year', 'printed_letter', 'letter', 'option_order', 'method', 'located', 'confident',
                  'recovery_version', 'recovered_at', 'imported_at']


class QuestionAuditListSerializer(serializers.ModelSerializer):
    question_text = serializers.SerializerMethodField()
    exam_type = serializers.CharField(source='question.exam_type', read_only=True)
    year = serializers.IntegerField(source='question.year', read_only=True)
    subject = serializers.SerializerMethodField()
    suggested_from = serializers.SerializerMethodField()
    open_signals = serializers.SerializerMethodField()
    claimed_by = serializers.SerializerMethodField()
    printed_key = serializers.SerializerMethodField()

    class Meta:
        model = QuestionAudit
        fields = ['id', 'question_id', 'status', 'status_reason', 'stored_key', 'suggested_key', 'suggested_from',
                  'priority', 'open_signals', 'is_stale', 'audited_at', 'question_text', 'exam_type', 'year',
                  'subject', 'claimed_by', 'printed_key']

    def get_printed_key(self, obj):
        """The confident printed source key behind a ``source_key_mismatch`` suggestion (for batch accept)."""
        summary = obj.evidence_summary or {}
        if summary.get('suggested_from') != 'source_key_mismatch' or not obj.suggested_key:
            return None
        for row in summary.get('source_keys') or []:
            if row.get('confident') and row.get('letter') == obj.suggested_key and row.get('id'):
                return {'id': row['id'], 'letter': row['letter'], 'printed_letter': row.get('printed_letter'),
                        'source_file': row.get('source_file'), 'question_page': row.get('question_page'),
                        'question_number': row.get('question_number'), 'answer_page': row.get('answer_page')}
        return None

    def get_question_text(self, obj):
        return (obj.question.question_text or '')[:240]

    def get_subject(self, obj):
        return obj.question.subject.name if obj.question.subject_id else ''

    def get_suggested_from(self, obj):
        return (obj.evidence_summary or {}).get('suggested_from', '')

    def get_open_signals(self, obj):
        return [s.get('code') for s in (obj.signals or []) if s.get('opens_review') and not s.get('settled_by_review')]

    def get_claimed_by(self, obj):
        claims = self.context.get('claims') or {}
        return claims.get(obj.question_id)


class AuditResolutionSerializer(serializers.ModelSerializer):
    resolved_by = serializers.CharField(source='resolved_by.username', default='', read_only=True)
    key_change_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = AuditResolution
        fields = ['id', 'resolution', 'reason', 'evidence', 'status_before', 'stored_key', 'key_change_id',
                  'resolved_by', 'resolved_at']


def review_for_display(review: dict) -> dict:
    """A stored review with the label the queue shows: AI output is a review signal, never evidence."""
    out = {k: review.get(k) for k in ('reviewer', 'pass', 'verdict', 'best_option', 'confidence',
                                       'explanation_check', 'issues', 'reason', 'stored_key', 'at', 'source',
                                       'official_source')}
    out['kind'] = reviewer_kind(review.get('reviewer'))
    out['label'] = display_label(review)
    return out


class QuestionAuditDetailSerializer(serializers.ModelSerializer):
    question = serializers.SerializerMethodField()
    reviews = serializers.SerializerMethodField()
    source_keys = serializers.SerializerMethodField()
    resolutions = serializers.SerializerMethodField()
    key_changes = serializers.SerializerMethodField()
    claim = serializers.SerializerMethodField()

    class Meta:
        model = QuestionAudit
        fields = ['id', 'question_id', 'status', 'status_reason', 'stored_key', 'original_key', 'key_provenance',
                  'suggested_key', 'priority', 'signals', 'evidence_summary', 'is_stale', 'content_changed_at',
                  'audited_at', 'method_version', 'question', 'reviews', 'source_keys', 'resolutions', 'key_changes',
                  'claim']

    def get_question(self, obj):
        q = obj.question
        return {
            'id': q.id, 'question_text': q.question_text, 'option_a': q.option_a, 'option_b': q.option_b,
            'option_c': q.option_c, 'option_d': q.option_d, 'correct_answer': q.correct_answer,
            'explanation': q.explanation, 'concept_explanation': q.concept_explanation, 'mnemonic': q.mnemonic,
            'exam_type': q.exam_type, 'year': q.year, 'paper': getattr(q, 'paper', ''),
            'subject': q.subject.name if q.subject_id else '', 'topic': q.topic.name if q.topic_id else '',
            'source': q.source, 'is_active': q.is_active, 'is_dropped': q.is_dropped,
            'is_disputed': q.is_disputed, 'needs_review': q.needs_review, 'answer_key_status': q.answer_key_status,
            'question_type': q.question_type, 'is_image_based': q.is_image_based,
            'image_ids': [img.id for img in q.images.all() if img.is_active],
        }

    def get_reviews(self, obj):
        return [review_for_display(r) for r in (obj.reviews or []) if isinstance(r, dict)]

    def get_source_keys(self, obj):
        return SourceKeySerializer(obj.question.source_keys.all(), many=True).data

    def get_resolutions(self, obj):
        rows = AuditResolution.objects.filter(question_id=obj.question_id).select_related('resolved_by')
        return AuditResolutionSerializer(rows, many=True).data

    def get_key_changes(self, obj):
        rows = obj.question.key_changes.select_related('changed_by').order_by('-changed_at')[:20]
        return [{'id': c.id, 'old_key': c.old_key, 'new_key': c.new_key, 'source': c.source, 'reason': c.reason,
                 'evidence': c.evidence, 'changed_by': c.changed_by.username if c.changed_by_id else '',
                 'changed_at': c.changed_at} for c in rows]

    def get_claim(self, obj):
        claim = self.context.get('claim')
        if claim is None:
            return None
        return {'claimed_by': claim.claimed_by.username, 'mine': claim.claimed_by_id == self.context.get('user_id'),
                'expires_at': claim.expires_at}


class ResolveAuditRequestSerializer(serializers.Serializer):
    resolution = serializers.ChoiceField(choices=AuditResolution.RESOLUTION_CHOICES)
    reason = serializers.CharField(min_length=10, max_length=4000)
    new_key = serializers.CharField(max_length=1, required=False, allow_blank=True, default='')
    expected_key = serializers.CharField(max_length=1, required=False, allow_blank=True, default='',
                                         help_text='the key the reviewer saw; a different current key is a conflict')
    evidence = serializers.ListField(child=serializers.JSONField(), required=False, default=list,
                                     max_length=MAX_EVIDENCE_ITEMS)
    explanation_fields = serializers.DictField(child=serializers.CharField(allow_blank=True, max_length=MAX_EXPLANATION),
                                               required=False, default=dict)

    def validate_evidence(self, items):
        return [clean_evidence_item(item) for item in items]

    def validate_explanation_fields(self, fields):
        unknown = sorted(set(fields) - set(EXPLANATION_FIELDS))
        if unknown:
            raise serializers.ValidationError(f'not an explanation field: {", ".join(unknown)}')
        return fields

    def validate(self, attrs):
        resolution = attrs['resolution']
        if resolution == 'key_changed':
            new_key = valid_key(attrs.get('new_key'))
            if not new_key:
                raise serializers.ValidationError({'new_key': 'key_changed needs new_key (A, B, C or D).'})
            attrs['new_key'] = new_key
        elif attrs.get('new_key'):
            raise serializers.ValidationError({'new_key': 'only key_changed takes new_key.'})
        if resolution == 'explanation_fixed' and not attrs.get('explanation_fields'):
            raise serializers.ValidationError({'explanation_fields': 'explanation_fixed needs the corrected fields.'})
        if attrs.get('explanation_fields') and resolution not in ('key_changed', 'explanation_fixed'):
            raise serializers.ValidationError({'explanation_fields': 'only key_changed / explanation_fixed take them.'})
        attrs['expected_key'] = valid_key(attrs.get('expected_key'))
        return attrs
