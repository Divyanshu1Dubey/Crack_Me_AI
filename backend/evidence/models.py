"""Curated question -> source evidence (docs/audit/MEDICAL_ACCURACY_DESIGN.md).

Rows are self-contained (citation metadata + a verbatim snippet + an optional figure crop), so
student citations work where the books and the reference store are absent (production). Pages
are 1-based physical page numbers of the source file (what a PDF viewer shows as "page N");
``page_label`` is the printed page number when it is known. DOCX sources use the section ordinal.

All writes go through ``evidence.services`` (record_passage_evidence, review, mark_stale).
Students only ever see accepted, student-visible, non-stale rows, as a citation plus a snippet
of at most EVIDENCE_SNIPPET_MAX_CHARS characters -- never full pages.
"""
from django.conf import settings
from django.db import models
from django.db.models import F, Q


class EvidenceSource(models.Model):
    """A reference document, mirrored from the reference-store registry (keyed by file sha256)."""

    KIND_CHOICES = [
        ('textbook', 'Textbook'), ('guideline', 'Guideline'), ('notes', 'Notes'),
        ('pyq_compilation', 'PYQ compilation'), ('question_paper', 'Question paper'),
        ('question_set', 'Question set'), ('answer_key', 'Answer key'), ('workbook', 'Workbook'),
        ('other', 'Other'),
    ]
    STUDENT_DISPLAY_CHOICES = [
        ('none', 'Not shown'), ('citation', 'Citation only'), ('snippet', 'Citation and snippet'),
        ('figure', 'Citation, snippet and figure crop'),
    ]
    METADATA_SOURCE_CHOICES = [
        ('registry', 'Registry (file name)'), ('pdf_metadata', 'PDF metadata'),
        ('title_page', 'Title page'), ('admin', 'Admin'),
    ]

    sha256 = models.CharField(max_length=64, unique=True)
    title = models.CharField(max_length=300)
    edition = models.CharField(max_length=60, blank=True, default='')
    year = models.SmallIntegerField(null=True, blank=True)
    kind = models.CharField(max_length=24, choices=KIND_CHOICES)
    tier = models.PositiveSmallIntegerField(help_text='1 official key, 2 guideline, 3 textbook, 4 notes, 5 question paper')
    subject = models.CharField(max_length=80, blank=True, default='')
    licence = models.CharField(max_length=200, blank=True, default='')
    student_display = models.CharField(max_length=12, choices=STUDENT_DISPLAY_CHOICES, default='citation')
    is_excerpt = models.BooleanField(default=False)
    page_count = models.PositiveIntegerField(null=True, blank=True)
    page_labels = models.JSONField(default=dict, blank=True, help_text='{"<page_no>": "<printed label>"}')
    metadata_source = models.CharField(max_length=16, choices=METADATA_SOURCE_CHOICES, default='registry')
    metadata_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['tier', 'title']

    def __str__(self):
        return f'{self.title}{", " + self.edition if self.edition else ""} (tier {self.tier})'


class EvidenceFigure(models.Model):
    """A figure cropped from a source page (admin-made). Served to students only as a small signed crop."""

    source = models.ForeignKey(EvidenceSource, on_delete=models.PROTECT, related_name='figures')
    page_no = models.PositiveIntegerField()
    bbox = models.JSONField(help_text='[x0, y0, x1, y1] in PDF points')
    image = models.ImageField(upload_to='evidence_figures/%Y/%m/', blank=True, null=True)
    caption = models.TextField(blank=True, default='')
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Figure#{self.pk} {self.source_id} p.{self.page_no}'


class QuestionEvidence(models.Model):
    """One passage (and optional figure) linked to a question, with its stance towards an option."""

    ORIGIN_CHOICES = [
        ('answer_key_audit', 'Answer-key audit'), ('ai_explain', 'AI explain'), ('admin_manual', 'Admin'),
        ('recall_source', 'Recall source page'), ('legacy_reference', 'Legacy reference field'),
        ('official_key', 'Official answer key'),
    ]
    STANCE_CHOICES = [
        ('candidate', 'Candidate'), ('supports', 'Supports'), ('contradicts', 'Contradicts'),
        ('mentions', 'Mentions'), ('states_key', 'States the key'), ('figure_match', 'Figure match'),
    ]
    REVIEW_CHOICES = [('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected'), ('stale', 'Stale')]

    question = models.ForeignKey('questions.Question', on_delete=models.PROTECT, related_name='evidence')
    question_image = models.ForeignKey('questions.QuestionImage', on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='evidence')
    source = models.ForeignKey(EvidenceSource, on_delete=models.PROTECT, related_name='question_evidence')
    page_start = models.PositiveIntegerField()
    page_end = models.PositiveIntegerField()
    page_label = models.CharField(max_length=32, blank=True, default='')
    chapter = models.CharField(max_length=300, blank=True, default='')
    snippet = models.TextField(help_text='Verbatim text from the source page (<= 600 chars).')
    snippet_sha1 = models.CharField(max_length=40, db_index=True)
    char_start = models.IntegerField(null=True, blank=True)
    char_end = models.IntegerField(null=True, blank=True)
    quote_verified = models.BooleanField(default=False)
    bbox = models.JSONField(null=True, blank=True)
    figure = models.ForeignKey(EvidenceFigure, on_delete=models.SET_NULL, null=True, blank=True, related_name='uses')
    option_letter = models.CharField(max_length=1, blank=True, default='', help_text='A-D; blank = whole question')
    stance = models.CharField(max_length=16, choices=STANCE_CHOICES, default='candidate')
    score = models.FloatField(null=True, blank=True)
    retrieval_method = models.CharField(max_length=24, blank=True, default='')
    origin = models.CharField(max_length=24, choices=ORIGIN_CHOICES, db_index=True)
    run_ref = models.CharField(max_length=64, blank=True, default='', db_index=True,
                               help_text='EvidenceRun id / audit run id that produced the row')
    review_status = models.CharField(max_length=12, choices=REVIEW_CHOICES, default='pending', db_index=True)
    student_visible = models.BooleanField(default=False)
    key_at_creation = models.CharField(max_length=1, blank=True, default='')
    content_sha256 = models.CharField(max_length=64, blank=True, default='',
                                      help_text='questions.content_hashes.stem_hash() at creation')
    stale_reason = models.CharField(max_length=40, blank=True, default='')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='+')
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='+')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['question', 'source__tier', '-score']
        constraints = [
            models.UniqueConstraint(fields=['question', 'source', 'page_start', 'snippet_sha1', 'option_letter', 'origin'],
                                    name='uniq_question_evidence_passage'),
            models.CheckConstraint(condition=Q(page_end__gte=F('page_start')), name='question_evidence_page_range'),
        ]
        indexes = [
            models.Index(fields=['question', 'review_status'], name='qev_question_review'),
            models.Index(fields=['source', 'page_start'], name='qev_source_page'),
            models.Index(fields=['origin', 'review_status'], name='qev_origin_review'),
        ]

    def __str__(self):
        return f'Evidence#{self.pk} Q{self.question_id} {self.stance} {self.option_letter or "-"} ({self.review_status})'


class EvidenceReviewLog(models.Model):
    ACTION_CHOICES = [('create', 'Create'), ('accept', 'Accept'), ('reject', 'Reject'), ('edit', 'Edit'),
                      ('crop', 'Crop'), ('restale', 'Marked stale')]

    evidence = models.ForeignKey(QuestionEvidence, on_delete=models.CASCADE, related_name='review_log')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='+')
    action = models.CharField(max_length=16, choices=ACTION_CHOICES)
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)
    note = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
