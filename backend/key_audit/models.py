"""Answer-key audit (docs/audit/MEDICAL_ACCURACY_DESIGN.md, phase 3).

The audit classifies; it never changes a key. A key changes only through an explicit admin
decision (``AuditResolution`` + ``questions.editorial.change_answer_key``), which keeps the
original key, who changed it, why, and the evidence.

Status meanings (computed by ``key_audit.classify``):
  verified               official key match, a human review with evidence, or a page-cited
                         textbook passage (tier <= 3) that explicitly states the stored answer,
                         its quote verified against the store, confirmed by two independent
                         reviewers, and nothing contradicting it
  likely_correct         independent reviewers agree with the key; supporting evidence is only
                         secondary or unverified; no contradiction and no open risk signal
  needs_review           a reviewer disagrees with the key, or a strong risk signal is unresolved
                         (student report, explanation states another answer, label conflict,
                         duplicate disagreement, invalid / empty key, incomplete options)
  contradictory_sources  verified passages support different options
  insufficient_evidence  nothing found either way; AI opinion alone is not evidence
  image_context_missing  the question depends on an image that is not attached
"""
from django.conf import settings
from django.db import models


class QuestionAudit(models.Model):
    STATUS_CHOICES = [
        ('verified', 'Verified'),
        ('likely_correct', 'Likely correct'),
        ('needs_review', 'Needs review'),
        ('contradictory_sources', 'Contradictory sources'),
        ('insufficient_evidence', 'Insufficient evidence'),
        ('image_context_missing', 'Image context missing'),
    ]
    KEY_PROVENANCE_CHOICES = [
        ('official_key', 'Official answer key'), ('import', 'Imported with the paper'),
        ('ai_enrichment', 'Chosen by an AI importer'), ('admin', 'Set by an admin'), ('unknown', 'Unknown'),
    ]

    question = models.OneToOneField('questions.Question', on_delete=models.CASCADE, related_name='key_audit')
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, db_index=True)
    status_reason = models.CharField(max_length=64, blank=True, default='', help_text='main signal / rule code')
    stored_key = models.CharField(max_length=1, blank=True, default='', help_text='key when audited')
    original_key = models.CharField(max_length=1, blank=True, default='', help_text='earliest known key')
    key_provenance = models.CharField(max_length=16, choices=KEY_PROVENANCE_CHOICES, default='unknown')
    suggested_key = models.CharField(max_length=1, blank=True, default='',
                                     help_text='what the evidence / reviewers point to; never applied automatically')
    confidence = models.FloatField(null=True, blank=True)
    priority = models.FloatField(default=0, db_index=True, help_text='review-queue order (higher first)')
    signals = models.JSONField(default=list, blank=True)    # [{code, severity, detail}]
    # [{reviewer: 'claude-subagent (review signal)' | 'human:<id>' | 'official_key' | 'evidence:deterministic-v1',
    #   pass, verdict, best_option, confidence, explanation_check, issues, reason, quotes: [...], at}]
    reviews = models.JSONField(default=list, blank=True)
    evidence_run = models.ForeignKey('reference_corpus.EvidenceRun', on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='+')
    evidence_summary = models.JSONField(default=dict, blank=True)
    method_version = models.CharField(max_length=32)
    is_stale = models.BooleanField(default=False, db_index=True, help_text='key / stem / options changed since the audit')
    audited_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-priority', 'question_id']
        indexes = [models.Index(fields=['status', '-priority'], name='kaudit_status_priority')]

    def __str__(self):
        return f'Audit Q{self.question_id}: {self.status} ({self.status_reason})'


class AuditResolution(models.Model):
    """An admin decision on an audited question (immutable)."""

    RESOLUTION_CHOICES = [
        ('key_confirmed', 'Key confirmed'), ('key_changed', 'Key changed'),
        ('question_deactivated', 'Question deactivated'), ('dropped', 'Dropped from scoring'),
        ('deferred', 'Deferred'), ('image_requested', 'Image requested'), ('explanation_fixed', 'Explanation fixed'),
    ]

    question = models.ForeignKey('questions.Question', on_delete=models.CASCADE, related_name='audit_resolutions')
    audit = models.ForeignKey(QuestionAudit, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolutions')
    resolution = models.CharField(max_length=24, choices=RESOLUTION_CHOICES)
    reason = models.TextField()
    evidence = models.JSONField(default=list, blank=True)
    key_change = models.ForeignKey('questions.AnswerKeyChange', on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='+')
    status_before = models.CharField(max_length=32, blank=True, default='')
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='+')
    resolved_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-resolved_at']

    def save(self, *args, **kwargs):
        if self.pk is not None and not self._state.adding:
            raise ValueError('AuditResolution is immutable.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError('AuditResolution rows are never deleted.')


class ReviewClaim(models.Model):
    """A reviewer's short-lived claim on a queued question, so two admins do not review it at once."""

    question = models.OneToOneField('questions.Question', on_delete=models.CASCADE, related_name='review_claim')
    claimed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    claimed_at = models.DateTimeField()
    expires_at = models.DateTimeField()
