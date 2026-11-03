"""Evidence decisions made over the reference store (docs/audit/MEDICAL_ACCURACY_DESIGN.md).

The reference store itself (sources, pages, chunks, FTS index, embeddings) is a separate,
git-ignored SQLite file at ``settings.REFERENCE_STORE_PATH`` because it holds copyrighted
text. Only decisions about questions live in the Django database.
"""
from django.conf import settings
from django.db import models


class EvidenceRun(models.Model):
    """One evidence decision for one question: what the reference passages support, made
    without looking at the stored key, then compared with it. Never changes a key."""

    MODE_CHOICES = [
        ('deterministic', 'Deterministic'),
        ('llm', 'LLM adjudication'),
        ('reviewer', 'AI reviewer (review signal)'),
        ('human', 'Human'),
    ]
    PURPOSE_CHOICES = [
        ('audit', 'Answer-key audit'),
        ('explain', 'Explanation / editor'),
        ('student', 'Student explanation'),
        ('benchmark', 'Benchmark'),
        ('manual', 'Manual check'),
    ]
    STATUS_CHOICES = [
        ('supported', 'Evidence supports the key'),
        ('conflict', 'Evidence supports another option'),
        ('insufficient_evidence', 'Insufficient evidence'),
        ('contradictory_sources', 'Contradictory sources'),
        ('image_context_missing', 'Image context missing'),
        ('invalid_key', 'Invalid key'),
        ('error', 'Error'),
    ]

    question = models.ForeignKey('questions.Question', on_delete=models.CASCADE, related_name='evidence_runs')
    mode = models.CharField(max_length=16, choices=MODE_CHOICES)
    purpose = models.CharField(max_length=12, choices=PURPOSE_CHOICES, default='audit')
    generator_label = models.CharField(max_length=120, help_text="'deterministic-v1', 'llm:<provider>:<model>', "
                                                                 "'claude-subagent (review signal)'")
    store_build_id = models.CharField(max_length=64, blank=True, default='')
    config_hash = models.CharField(max_length=64, blank=True, default='', db_index=True)
    stored_key = models.CharField(max_length=1, blank=True, default='')
    selected_key = models.CharField(max_length=1, blank=True, default='')
    evidence_answer = models.CharField(max_length=1, blank=True, default='')
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, db_index=True)
    confidence = models.FloatField(null=True, blank=True)
    margin = models.FloatField(null=True, blank=True)
    polarity = models.CharField(max_length=12, blank=True, default='')        # positive | negative
    question_type = models.CharField(max_length=24, blank=True, default='')   # single_best | statement_code | ...
    # {A: {support, contradiction, features, citations: [{chunk_key, source_sha256, page_no, page_label,
    #       section, quote, stance, verified}]}}
    per_option = models.JSONField(default=dict, blank=True)
    citations = models.JSONField(default=list, blank=True)    # verified citations only, flattened
    notes = models.TextField(blank=True, default='')
    image_context_missing = models.BooleanField(default=False)
    acknowledged_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name='+')
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='+')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['question', '-created_at'], name='evrun_question'),
            models.Index(fields=['status', 'purpose'], name='evrun_status_purpose'),
        ]

    def __str__(self):
        return f'EvidenceRun#{self.pk} Q{self.question_id} {self.status} ({self.generator_label})'
