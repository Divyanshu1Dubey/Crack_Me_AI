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
    content_changed_at = models.DateTimeField(
        null=True, blank=True,
        help_text='last change of the stem or an option; human decisions made before it no longer count')
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
    stored_key = models.CharField(max_length=1, blank=True, default='', help_text='the key after the decision')
    stem_hash = models.CharField(max_length=64, blank=True, default='',
                                 help_text='questions.content_hashes.stem_hash the decision was made for')
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


class SourceKey(models.Model):
    """The answer a source document prints for a question, recovered without AI (2026-11).

    A coaching compilation's "Answer Key" table or an inline "Ans." line, read from the document the
    question was imported from by ``ai_eval.recover_source_keys`` (needs the PDFs, so it runs where they
    are) and loaded anywhere with ``manage.py import_source_keys``. Evidence tier 4: a secondary source,
    usually the very document the bank copied, so it shows whether the import kept the printed key, not
    whether that key is medically right. The audit uses it as a review signal; it never changes a key.
    """

    METHOD_CHOICES = [('answer_key_table', 'Answer-key table'), ('inline_answer', 'Inline answer line')]
    OPTION_ORDER_CHOICES = [
        ('same', 'Same option order (checked through the option text)'),
        ('reordered', 'Different option order (mapped through the option text)'),
        ('assumed_same', 'Option order not checked'),
    ]

    question = models.ForeignKey('questions.Question', on_delete=models.CASCADE, related_name='source_keys')
    source_file = models.CharField(max_length=255, help_text='file name of the source document')
    source_sha256 = models.CharField(max_length=64, blank=True, default='')
    question_page = models.PositiveIntegerField(help_text='1-based PDF page the question starts on')
    question_number = models.PositiveIntegerField(help_text='the number the source prints for the question')
    answer_page = models.PositiveIntegerField(null=True, blank=True, help_text='1-based PDF page of the printed answer')
    chapter = models.CharField(max_length=160, blank=True, default='', help_text='source chapter title on that page')
    source_exam = models.CharField(max_length=16, blank=True, default='', help_text='exam named by the chapter title')
    source_year = models.PositiveSmallIntegerField(null=True, blank=True, help_text='year named by the chapter title')
    printed_letter = models.CharField(max_length=1, help_text='the letter the source prints')
    letter = models.CharField(max_length=1, help_text="printed_letter in the bank's option order")
    option_order = models.CharField(max_length=16, choices=OPTION_ORDER_CHOICES)
    method = models.CharField(max_length=24, choices=METHOD_CHOICES)
    located = models.BooleanField(help_text='the stem was found in the source text (not only a page / number link)')
    stem_hash = models.CharField(max_length=64, help_text='questions.content_hashes.stem_hash at recovery')
    recovery_version = models.CharField(max_length=32)
    recovered_at = models.DateTimeField()
    imported_at = models.DateTimeField(auto_now_add=True, help_text='first import into this database')

    class Meta:
        ordering = ['question_id', 'source_file', 'question_page']
        constraints = [
            models.UniqueConstraint(fields=['question', 'source_file', 'question_page', 'question_number'],
                                    name='kaudit_source_key_location'),
        ]

    def __str__(self):
        return f'Q{self.question_id}: {self.letter} ({self.source_file} p.{self.question_page})'

    @property
    def confident(self) -> bool:
        """The stem was found in the source and the letter was mapped through the option text."""
        return bool(self.located and self.option_order in ('same', 'reordered'))


class BundledSignalImport(models.Model):
    """A signal file shipped with the code (``key_audit/data/``) imported into this database, once per version
    (``manage.py import_bundled_key_audit``): its name, sha256 and the importer's report."""

    KIND_CHOICES = [('source_keys', 'Printed source keys'), ('reviews', 'Review signals')]

    name = models.CharField(max_length=120)
    sha256 = models.CharField(max_length=64)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    report = models.JSONField(default=dict, blank=True)
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-imported_at']
        constraints = [models.UniqueConstraint(fields=['name', 'sha256'], name='kaudit_bundle_once')]

    def __str__(self):
        return f'{self.name} ({self.sha256[:12]})'
