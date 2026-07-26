import re
import uuid
from django.db import models
from django.conf import settings


class ExamTrack(models.Model):
    """
    Core Exam Track model (e.g. UPSC CMS, NEET PG, USMLE, FMGE).
    Drives theme context, eligibility, and job filtering across the platform.
    """
    name = models.CharField(max_length=100, unique=True, help_text="e.g. UPSC CMS")
    code = models.CharField(max_length=20, unique=True, help_text="e.g. cms, neet_pg")
    conducting_body = models.CharField(max_length=100, blank=True)
    notification_date = models.DateField(null=True, blank=True)
    application_start = models.DateField(null=True, blank=True)
    application_end = models.DateField(null=True, blank=True)
    exam_date = models.DateField(null=True, blank=True)
    admit_card_date = models.DateField(null=True, blank=True)
    result_date = models.DateField(null=True, blank=True)
    vacancies = models.CharField(max_length=100, blank=True)
    exam_pattern_summary = models.TextField(blank=True)
    eligibility_summary = models.TextField(blank=True)
    source_url = models.URLField(max_length=500, blank=True)
    last_verified_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.name


class Subject(models.Model):
    """Medical subjects like Medicine, Surgery, PSM, OBG, Pediatrics."""
    EXAM_CHOICES = [
        ('cms', 'UPSC CMS'),
        ('neet_pg', 'NEET PG'),
        ('ini_cet', 'INI-CET'),
        ('usmle', 'USMLE'),
        ('fmge', 'FMGE'),
    ]

    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)
    exam_type = models.CharField(max_length=20, choices=EXAM_CHOICES, default='cms', help_text='Target exam for this subject')
    exam_track = models.ForeignKey(ExamTrack, on_delete=models.SET_NULL, null=True, blank=True, related_name='subjects')
    paper = models.IntegerField(
        choices=[(1, 'Paper 1'), (2, 'Paper 2')],
        default=1,
        help_text='CMS Paper number'
    )
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text='Icon name for UI')
    color = models.CharField(max_length=7, blank=True, help_text='Hex color code')

    class Meta:
        ordering = ['paper', 'name']

    def __str__(self):
        return f"{self.name} (Paper {self.paper})"


class Topic(models.Model):
    """Topics within a subject, e.g., Nephrology under Medicine."""
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='topics')
    exam_track = models.ForeignKey(ExamTrack, on_delete=models.SET_NULL, null=True, blank=True, related_name='topics')
    name = models.CharField(max_length=200)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='subtopics')
    importance = models.IntegerField(
        default=5,
        help_text='1-10 importance for CMS exam'
    )
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['subject', 'name']
        unique_together = ['subject', 'name']

    def __str__(self):
        return f"{self.subject.code} → {self.name}"


class Question(models.Model):
    """Previous year question with full metadata."""
    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]
    EXAM_CHOICES = [
        ('cms', 'UPSC CMS'),
        ('neet_pg', 'NEET PG'),
        ('ini_cet', 'INI-CET'),
        ('usmle', 'USMLE'),
        ('fmge', 'FMGE'),
    ]

    # Core fields
    exam_type = models.CharField(max_length=20, choices=EXAM_CHOICES, default='cms')
    exam_track = models.ForeignKey(ExamTrack, on_delete=models.SET_NULL, null=True, blank=True, related_name='questions')
    question_text = models.TextField()
    option_a = models.TextField()
    option_b = models.TextField()
    option_c = models.TextField()
    option_d = models.TextField()
    correct_answer = models.CharField(
        max_length=1,
        choices=[('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')]
    )

    # Classification
    year = models.IntegerField(db_index=True)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='questions')
    topic = models.ForeignKey(Topic, on_delete=models.SET_NULL, null=True, related_name='questions')
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default='medium')
    concept_tags = models.JSONField(default=list, blank=True, help_text='List of concept tags')
    concept_id = models.CharField(max_length=120, blank=True, db_index=True, help_text='Stable concept identifier for linking related PYQs')

    # Explanation
    explanation = models.TextField(blank=True, help_text='Detailed answer explanation')
    concept_explanation = models.TextField(blank=True, help_text='From-basics concept explanation')
    mnemonic = models.TextField(blank=True, help_text='Memory trick for this concept')

    # Textbook reference
    book_name = models.CharField(max_length=200, blank=True)
    chapter = models.CharField(max_length=200, blank=True)
    page_number = models.CharField(max_length=50, blank=True)
    reference_text = models.TextField(blank=True, help_text='Relevant text from textbook')

    # Metadata
    paper = models.IntegerField(default=0, help_text='Paper 1 or Paper 2')
    source = models.CharField(max_length=200, blank=True, help_text='Source file (PYQ_2019_Paper1.pdf)')
    exam_source = models.CharField(max_length=50, default='UPSC CMS')
    times_asked = models.IntegerField(default=0, help_text='How many times this concept appeared')
    is_active = models.BooleanField(default=True)
    
    # 6-Task Architecture Upgrade Fields
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, null=True, unique=True)
    display_number = models.IntegerField(null=True, blank=True, help_text='Number shown to students (scoped by year/paper)')
    is_dropped = models.BooleanField(default=False, help_text='Dropped/disputed question excluded from scoring')
    admin_edited = models.BooleanField(default=False, help_text='Flag to protect from seed script overwrites')
    needs_review = models.BooleanField(default=False, help_text='Flag for partially digitized or disputed PYQs')
    
    # Scholarship/Review Flags
    is_scholarship_eligible = models.BooleanField(default=False, help_text='Eligible for scholarship test (balanced, verified)')
    is_controversial = models.BooleanField(default=False, help_text='Flag for questions with ambiguous/controversial answers')
    is_disputed = models.BooleanField(default=False, help_text='Answer key disputed by students or flagged for review')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Enhanced fields
    textbook_references = models.JSONField(
        default=list, blank=True,
        help_text='List of {book, chapter, page, excerpt} dicts'
    )
    learning_technique = models.TextField(blank=True, help_text='How to study/approach this concept')
    shortcut_tip = models.TextField(blank=True, help_text='Quick solving trick or shortcut')
    page_screenshot = models.ImageField(
        upload_to='question_screenshots/', blank=True, null=True,
        help_text='Screenshot of textbook page where answer is discussed'
    )
    concept_keywords = models.JSONField(
        default=list, blank=True,
        help_text='Keywords for vector similarity matching'
    )
    ai_explanation = models.TextField(blank=True, help_text='AI-generated detailed explanation')
    ai_answer = models.TextField(blank=True, help_text='AI-generated answer rationale')
    ai_mnemonic = models.TextField(blank=True, help_text='AI-generated mnemonic')
    ai_references = models.JSONField(default=list, blank=True, help_text='AI-generated references')
    ai_clinical_pearl = models.TextField(blank=True, help_text='AI-generated clinical pearl')
    ai_generated_at = models.DateTimeField(null=True, blank=True)
    ai_model = models.CharField(max_length=100, blank=True, help_text='Model used for generation')
    ai_version = models.CharField(max_length=50, blank=True, help_text='Prompt/system version')

    # Video generation fields
    video_url = models.URLField(max_length=500, blank=True, help_text='Supabase storage URL for MP4')
    video_thumbnail = models.URLField(max_length=500, blank=True, help_text='Thumbnail URL')
    video_status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed')
    ], default='pending', db_index=True)
    video_duration = models.IntegerField(null=True, blank=True, help_text='Duration in seconds')
    video_generated_at = models.DateTimeField(null=True, blank=True)
    video_version = models.CharField(max_length=50, blank=True)
    video_error = models.TextField(blank=True)

    # Admin override + lock controls
    admin_answer_override = models.TextField(blank=True)
    admin_explanation_override = models.TextField(blank=True)
    admin_mnemonic_override = models.TextField(blank=True)
    admin_references_override = models.JSONField(default=list, blank=True)
    lock_answer = models.BooleanField(default=False)
    lock_explanation = models.BooleanField(default=False)

    # Trust and verification
    is_verified_by_admin = models.BooleanField(default=False, db_index=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_questions',
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_note = models.TextField(blank=True)

    # Similar questions
    similar_questions = models.ManyToManyField(
        'self',
        blank=True,
        symmetrical=True,
        help_text='Questions testing the same concept'
    )

    # ── Phase 2: NEET PG / recall-bank fields (additive) ────────────────
    # These power the recall importer and recall-aware search. Existing
    # rows are unaffected — every field has a sensible default.
    RECALL_STATUS_CHOICES = [
        ('recall', 'Recall'),
        ('coaching_compiled', 'Coaching Compiled'),
        ('official_compiled', 'Official / Compiled'),
    ]
    QUESTION_TYPE_CHOICES = [
        ('single_best', 'Single Best Answer'),
        ('multiple_correct', 'Multiple Correct'),
        ('assertion_reason', 'Assertion-Reason'),
        ('match', 'Match the Following'),
        ('image_based', 'Image-Based'),
        ('numerical', 'Numerical'),
    ]
    CLINICAL_CATEGORY_CHOICES = [
        ('clinical', 'Clinical'),
        ('preclinical', 'Preclinical'),
        ('paraclinical', 'Paraclinical'),
    ]
    SESSION_CHOICES = [
        ('jan', 'January'),
        ('jul', 'July'),
        ('may', 'May'),
        ('nov', 'November'),
        ('none', 'None'),
    ]

    recall_status = models.CharField(
        max_length=32, choices=RECALL_STATUS_CHOICES,
        default='official_compiled', db_index=True,
        help_text='Recall / coaching-compiled / official-compiled provenance.',
    )
    question_type = models.CharField(
        max_length=32, choices=QUESTION_TYPE_CHOICES,
        default='single_best', db_index=True,
        help_text='Question format (single best, multiple correct, A/R, image-based, etc.)',
    )
    clinical_category = models.CharField(
        max_length=32, choices=CLINICAL_CATEGORY_CHOICES,
        default='clinical', db_index=True,
        help_text='Preclinical / Paraclinical / Clinical classification.',
    )
    session = models.CharField(
        max_length=16, choices=SESSION_CHOICES, default='',
        blank=True, help_text='Exam session for the year (jan/jul/may/nov/none).',
    )
    confidence_score = models.DecimalField(
        max_digits=4, decimal_places=3, default=1.000,
        help_text='Weighted OCR + parse + completeness score (0..1).',
    )
    ocr_confidence = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='Tesseract avg confidence (0..100).',
    )
    extraction_confidence = models.DecimalField(
        max_digits=4, decimal_places=3, default=1.000,
        help_text='Parser confidence (0..1).',
    )
    is_image_based = models.BooleanField(
        default=False, help_text='Image is required to answer this question.',
    )
    recall_text_hash = models.CharField(
        max_length=64, default='', blank=True, db_index=True,
        help_text='sha256 of normalised question text — used for cross-PDF dedup.',
    )

    class Meta:
        ordering = ['-year', 'subject']
        indexes = [
            models.Index(fields=['year', 'subject']),
            models.Index(fields=['difficulty']),
            models.Index(fields=['exam_source']),
            models.Index(fields=['paper']),
            models.Index(fields=['is_active', 'is_verified_by_admin']),
            models.Index(fields=['subject', 'topic', 'year', 'difficulty']),
            models.Index(fields=['question_type']),
            models.Index(fields=['clinical_category']),
        ]

    def _normalize_text_value(self, value):
        text = (value or '').replace('\r\n', '\n').replace('\r', '\n')
        while '\n\n\n' in text:
            text = text.replace('\n\n\n', '\n\n')
        text = text.replace(' ,', ',').replace(' .', '.').replace(' ;', ';').replace(' :', ':')
        return text.strip()

    def _normalize_statement_text(self, value):
        text = self._normalize_text_value(value)
        text = re.sub(r';\s*(?=((?:[IVXLCDM]{1,8}|\d{1,2})\.\s))', ';\n', text)
        markers = list(re.finditer(r'(?:[IVXLCDM]{1,8}|\d{1,2})\.\s', text))
        if len(markers) >= 2:
            first_marker_index = markers[0].start()
            if first_marker_index > 0 and text[first_marker_index - 1] != '\n':
                text = f"{text[:first_marker_index].rstrip()}\n{text[first_marker_index:]}"
        while '\n\n\n' in text:
            text = text.replace('\n\n\n', '\n\n')
        return text

    def save(self, *args, **kwargs):
        # Root-cause fix for the ΓÇÿ / Ã© mojibake seen on the live site:
        # normalize_text() repairs UTF-8-as-Latin-1 doubles and NFC-normalizes
        # so "é" and "é" compare equal. Cheap, idempotent, safe to run on
        # every save.
        from questions.text_encoding import normalize_text

        self.question_text = normalize_text(self._normalize_statement_text(self.question_text))
        self.option_a = normalize_text(self._normalize_text_value(self.option_a))
        self.option_b = normalize_text(self._normalize_text_value(self.option_b))
        self.option_c = normalize_text(self._normalize_text_value(self.option_c))
        self.option_d = normalize_text(self._normalize_text_value(self.option_d))
        self.explanation = normalize_text(self._normalize_text_value(self.explanation))
        self.concept_explanation = normalize_text(self._normalize_text_value(self.concept_explanation))
        self.mnemonic = normalize_text(self._normalize_text_value(self.mnemonic))
        self.reference_text = normalize_text(self._normalize_text_value(self.reference_text))
        # AI-generated fields can also carry mojibake from provider responses
        # that came back through a non-UTF-8 system pipe — sanitize them too.
        self.ai_explanation = normalize_text(self.ai_explanation or "")
        self.ai_mnemonic = normalize_text(self.ai_mnemonic or "")
        self.ai_clinical_pearl = normalize_text(self.ai_clinical_pearl or "")

        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            update_fields = set(update_fields)
            update_fields.update([
                'question_text',
                'option_a',
                'option_b',
                'option_c',
                'option_d',
                'explanation',
                'concept_explanation',
                'mnemonic',
                'reference_text',
                'ai_explanation',
                'ai_mnemonic',
                'ai_clinical_pearl',
            ])
            kwargs['update_fields'] = update_fields

        return super().save(*args, **kwargs)


    def __str__(self):
        return f"[{self.year}] {self.subject.code}: {self.question_text[:80]}..."

    def get_correct_option_text(self):
        mapping = {'A': self.option_a, 'B': self.option_b, 'C': self.option_c, 'D': self.option_d}
        return mapping.get(self.correct_answer, '')


class QuestionImportJob(models.Model):
    """Track import/extraction jobs for admin observability and retry."""

    STATUS_CHOICES = [
        ('queued', 'Queued'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    JOB_TYPE_CHOICES = [
        ('csv', 'CSV Import'),
        ('json', 'JSON Import'),
        ('word', 'Word Extraction'),
        ('pdf', 'PDF Extraction'),
    ]

    job_type = models.CharField(max_length=20, choices=JOB_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='queued')
    source_filename = models.CharField(max_length=255, blank=True)
    stored_file_path = models.CharField(max_length=500, blank=True)
    summary = models.JSONField(default=dict, blank=True)
    error_report = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='question_import_jobs')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.job_type}::{self.status}::{self.source_filename or self.id}"


class QuestionExtractionItem(models.Model):
    """Staged extracted item before it is approved/published as a question."""

    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('published', 'Published'),
    ]

    job = models.ForeignKey(QuestionImportJob, on_delete=models.CASCADE, related_name='items')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    raw_text = models.TextField(blank=True)
    question_text = models.TextField(blank=True)
    option_a = models.TextField(blank=True)
    option_b = models.TextField(blank=True)
    option_c = models.TextField(blank=True)
    option_d = models.TextField(blank=True)
    correct_answer = models.CharField(max_length=1, choices=[('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')], blank=True)
    explanation = models.TextField(blank=True)
    year = models.IntegerField(null=True, blank=True)
    paper = models.IntegerField(default=0)
    subject = models.ForeignKey(Subject, null=True, blank=True, on_delete=models.SET_NULL, related_name='extraction_items')
    topic = models.ForeignKey(Topic, null=True, blank=True, on_delete=models.SET_NULL, related_name='extraction_items')
    tags = models.JSONField(default=list, blank=True)
    published_question = models.ForeignKey('Question', null=True, blank=True, on_delete=models.SET_NULL, related_name='source_extraction_items')
    review_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Item#{self.id} ({self.status}) job={self.job_id}"


class AdminAIPromptVersion(models.Model):
    """Versioned admin prompt definitions for AI explanation behavior."""

    name = models.CharField(max_length=120)
    prompt_text = models.TextField()
    is_active = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='ai_prompt_versions')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        state = 'active' if self.is_active else 'inactive'
        return f"PromptVersion#{self.id} {self.name} ({state})"


class QuestionAIOperationLog(models.Model):
    """Audit timeline of AI operations for admin visibility."""

    OPERATION_CHOICES = [
        ('regenerate', 'Force Regenerate'),
        ('override', 'Admin Override'),
    ]

    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='ai_operation_logs')
    operation_type = models.CharField(max_length=30, choices=OPERATION_CHOICES)
    provider = models.CharField(max_length=80, blank=True)
    prompt_version = models.ForeignKey(AdminAIPromptVersion, on_delete=models.SET_NULL, null=True, blank=True, related_name='operation_logs')
    tokens_used = models.IntegerField(default=0)
    response_excerpt = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='ai_operation_logs')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Q{self.question_id}::{self.operation_type}::{self.tokens_used}t"


class QuestionBookmark(models.Model):
    """User bookmarks on questions."""
    user = models.ForeignKey('accounts.CustomUser', on_delete=models.CASCADE, related_name='bookmarks')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='bookmarks')
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'question']


class QuestionFeedback(models.Model):
    """Feedback from students about questions (wrong answers, typos, etc)."""
    CATEGORY_CHOICES = [
        ('wrong_answer', 'Wrong Answer'),
        ('discrepancy', 'Discrepancy in Options'),
        ('out_of_syllabus', 'Out of Syllabus'),
        ('typo', 'Typo/Formatting Issue'),
        ('explanation_needed', 'Better Explanation Needed'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('new', 'New'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
    ]

    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='feedbacks')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    comment = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new', db_index=True)
    is_resolved = models.BooleanField(default=False)
    resolution_note = models.TextField(blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_question_feedbacks',
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    notified_user = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'is_resolved', 'created_at']),
            models.Index(fields=['question', 'status']),
            models.Index(fields=['category', 'status']),
        ]

    def __str__(self):
        return f"Feedback on Q{self.question.id}: {self.get_category_display()}"


class QuestionRevisionSnapshot(models.Model):
    """Immutable snapshot of editable question fields for diff/undo workflows."""

    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='revision_snapshots')
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='question_revision_snapshots',
    )
    reason = models.CharField(max_length=200, blank=True)
    snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['question', 'created_at']),
        ]

    def __str__(self):
        return f"Q{self.question_id} revision @ {self.created_at:%Y-%m-%d %H:%M:%S}"


class Discussion(models.Model):
    """Per-question discussion threads for doubt clearing."""
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='discussions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='discussions')
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='replies')
    text = models.TextField()
    upvotes = models.IntegerField(default=0)
    downvotes = models.IntegerField(default=0)
    is_pinned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_pinned', '-upvotes', '-created_at']

    def __str__(self):
        return f"{self.user.username} on Q{self.question.id}: {self.text[:60]}"


class DiscussionVote(models.Model):
    """Track individual votes on discussions to prevent duplicate voting."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    discussion = models.ForeignKey(Discussion, on_delete=models.CASCADE, related_name='votes')
    vote_type = models.CharField(max_length=4, choices=[('up', 'Upvote'), ('down', 'Downvote')])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'discussion']


class Note(models.Model):
    """Personal notes per question or topic."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notes')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, null=True, blank=True, related_name='notes')
    topic = models.ForeignKey('questions.Topic', on_delete=models.CASCADE, null=True, blank=True, related_name='notes')
    title = models.CharField(max_length=200, blank=True)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.user.username}: {self.title or self.content[:40]}"


class Flashcard(models.Model):
    """Flashcards for spaced repetition review with personal notes."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='flashcards')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, null=True, blank=True, related_name='flashcards')
    subject = models.ForeignKey('questions.Subject', on_delete=models.CASCADE, null=True, blank=True)
    front = models.TextField(help_text="Question or prompt side")
    back = models.TextField(help_text="Answer or explanation side")
    personal_note = models.TextField(blank=True, help_text="User's personal study notes for this card")
    difficulty = models.CharField(max_length=10, choices=[
        ('easy', 'Easy'), ('medium', 'Medium'), ('hard', 'Hard')
    ], default='medium')
    next_review = models.DateTimeField(null=True, blank=True)
    review_count = models.IntegerField(default=0)
    ease_factor = models.FloatField(default=2.5, help_text="SM-2 algorithm ease factor")
    interval_days = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['next_review', '-created_at']

    def schedule_next_review(self, quality):
        """SM-2 spaced repetition algorithm. quality: 0-5"""
        from django.utils import timezone
        import datetime
        if quality < 3:
            self.interval_days = 1
            self.review_count = 0
        else:
            if self.review_count == 0:
                self.interval_days = 1
            elif self.review_count == 1:
                self.interval_days = 6
            else:
                self.interval_days = round(self.interval_days * self.ease_factor)
            self.ease_factor = max(1.3, self.ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
        self.review_count += 1
        self.next_review = timezone.now() + datetime.timedelta(days=self.interval_days)
        self.save()

    def __str__(self):
        return f"{self.user.username}: {self.front[:50]}"


class QuestionAttempt(models.Model):
    """Tracks a user's practice attempt at a specific Question Bank question."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='question_attempts')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='qbank_attempts')
    selected_answer = models.CharField(max_length=1)
    is_correct = models.BooleanField()
    attempted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'question']

    def __str__(self):
        return f"{self.user.username} | Q{self.question.id} | {'Correct' if self.is_correct else 'Incorrect'}"

class Announcement(models.Model):
    """Admin Notes / Announcements targeted at specific exam tracks."""
    VISIBILITY_CHOICES = [
        ('all', 'All Students'),
        ('cms', 'UPSC CMS Only'),
        ('neet_pg', 'NEET PG Only'),
        ('usmle', 'USMLE Only'),
        ('fmge', 'FMGE Only'),
    ]

    title = models.CharField(max_length=200)
    body = models.TextField(help_text="Rich text content of the announcement")
    target_exam_track = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default='all')
    exam_tracks = models.ManyToManyField(ExamTrack, blank=True, related_name='announcements', help_text="Target exam tracks")
    target_users = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, help_text="Specific users to see this (overrides exam track)")
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


# ════════════════════════════════════════════════════════════════════════
# Phase 2 — NEET PG / INI-CET / AIIMS PG recall-bank models
# ════════════════════════════════════════════════════════════════════════
# These models extend (do not replace) the existing schema. They are the
# integration surface for `backend/importers/neetpg/`. Existing rows are
# unaffected — every model below is new and every field has a default.


class RecallSource(models.Model):
    """One row per source PDF ingested by the recall importer.

    A source is uniquely identified by (pdf_sha256, page_start, page_end)
    — re-importing the same file with a different page range creates a new
    row. The same file ingested twice with the same range is rejected by
    the unique constraint.
    """

    SCAN_TYPE_CHOICES = [
        ('digital', 'Digital'),
        ('scanned', 'Scanned'),
        ('hybrid', 'Hybrid'),
    ]

    pdf_filename = models.CharField(max_length=255)
    pdf_path = models.CharField(max_length=512)
    pdf_sha256 = models.CharField(max_length=64)
    pdf_sha256_short = models.CharField(max_length=16, db_index=True)
    pdf_size_bytes = models.BigIntegerField(default=0)
    page_count = models.IntegerField(default=0)
    page_start = models.IntegerField(null=True, blank=True)
    page_end = models.IntegerField(null=True, blank=True)
    question_count = models.IntegerField(default=0)
    scan_type = models.CharField(max_length=16, choices=SCAN_TYPE_CHOICES, default='hybrid')
    recall_status = models.CharField(max_length=32, default='recall')
    publisher = models.CharField(max_length=160, blank=True)
    pdf_metadata = models.JSONField(default=dict, blank=True)
    import_job = models.ForeignKey(
        'QuestionImportJob',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='recall_sources',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['pdf_sha256', 'page_start', 'page_end'],
                name='uniq_recall_source_sha_pagerange',
            ),
        ]
        indexes = [
            models.Index(fields=['scan_type']),
            models.Index(fields=['recall_status']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.pdf_filename} ({self.pdf_sha256_short})"


class QuestionSource(models.Model):
    """Provenance bridge — every Question may appear in multiple PDFs.

    Records per-PDF original text, OCR confidence, extraction confidence,
    and the import job that produced the row. Append-only — never updated
    or deleted by the importer (rollback soft-deletes the Question, not
    this row).
    """

    question = models.ForeignKey(
        Question, on_delete=models.PROTECT, related_name='recall_sources',
    )
    recall_source = models.ForeignKey(
        RecallSource, on_delete=models.PROTECT, related_name='question_sources',
    )
    page_number = models.IntegerField()
    question_number_in_pdf = models.IntegerField(null=True, blank=True)
    original_text = models.TextField(blank=True)
    extracted_text = models.TextField(blank=True)
    ocr_confidence = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    extraction_confidence = models.DecimalField(max_digits=4, decimal_places=3, default=1.000)
    import_job_id = models.CharField(max_length=64, blank=True)
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['recall_source', 'page_number']
        constraints = [
            models.UniqueConstraint(
                fields=['recall_source', 'page_number', 'question_number_in_pdf'],
                name='uniq_question_source_page_qno',
            ),
        ]
        indexes = [
            models.Index(fields=['question']),
            models.Index(fields=['recall_source', 'page_number']),
            models.Index(fields=['import_job_id']),
        ]

    def __str__(self):
        return f"Q{self.question_id} <- {self.recall_source_id}/p{self.page_number}"


class QuestionImage(models.Model):
    """Multi-image slot for a Question.

    The existing `Question.page_screenshot` (ImageField) is kept as the
    primary image. This model holds every other extracted figure plus
    optional OCR / caption / modality metadata.
    """

    MODALITY_CHOICES = [
        ('radiology', 'Radiology'),
        ('histopathology', 'Histopathology'),
        ('gross_pathology', 'Gross Pathology'),
        ('ecg', 'ECG'),
        ('ct', 'CT'),
        ('mri', 'MRI'),
        ('x_ray', 'X-Ray'),
        ('ultrasound', 'Ultrasound'),
        ('clinical_photo', 'Clinical Photograph'),
        ('instrument', 'Instrument'),
        ('chart', 'Chart'),
        ('flowchart', 'Flowchart'),
        ('microbiology', 'Microbiology Slide'),
        ('slide', 'Slide'),
        ('embryology', 'Embryology'),
        ('anatomy', 'Anatomy Diagram'),
        ('biochem_pathway', 'Biochemistry Pathway'),
        ('dermatology', 'Dermatology'),
        ('ophthalmology_fundus', 'Ophthalmology Fundus'),
        ('other', 'Other'),
    ]
    ROLE_CHOICES = [
        ('primary', 'Primary'),
        ('option', 'Option'),
        ('illustration', 'Illustration'),
        ('explanation', 'Explanation'),
    ]

    question = models.ForeignKey(
        Question, on_delete=models.PROTECT, related_name='images',
    )
    recall_source = models.ForeignKey(
        RecallSource, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='images',
    )
    page_number = models.IntegerField()
    image_index_in_page = models.IntegerField(default=0)
    file = models.ImageField(upload_to='recall_images/%Y/%m/', blank=True, null=True)
    mime = models.CharField(max_length=32, default='image/png')
    width = models.IntegerField(default=0)
    height = models.IntegerField(default=0)
    bytes = models.BigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True)
    sha256_short = models.CharField(max_length=16, blank=True, db_index=True)
    phash = models.CharField(max_length=16, blank=True)
    dhash = models.CharField(max_length=16, blank=True)
    modality = models.CharField(max_length=32, choices=MODALITY_CHOICES, default='other')
    modality_subtype = models.CharField(max_length=64, blank=True)
    body_region = models.CharField(max_length=64, blank=True)
    ocr_text = models.TextField(blank=True)
    caption = models.TextField(blank=True)
    caption_source = models.CharField(max_length=32, default='none')
    ocr_confidence = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    extraction_confidence = models.DecimalField(max_digits=4, decimal_places=3, default=1.000)
    has_diagram = models.BooleanField(default=False)
    has_table = models.BooleanField(default=False)
    is_watermarked = models.BooleanField(default=False)
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default='illustration')
    is_active = models.BooleanField(default=True)
    uploaded_by_admin = models.BooleanField(
        default=False,
        db_index=True,
        help_text='True if uploaded via the admin manual-fix editor (vs recall importer)',
    )
    url = models.URLField(
        max_length=500,
        blank=True,
        default='',
        help_text='Supabase public URL for admin-uploaded images (empty for recall imports)',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['question', 'page_number', 'image_index_in_page']
        indexes = [
            models.Index(fields=['question']),
            models.Index(fields=['modality']),
            models.Index(fields=['phash']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"Image#{self.id} Q{self.question_id} ({self.modality})"


class DuplicateCluster(models.Model):
    """Canonical-question pointer for a set of duplicate Question rows.

    The canonical question is the highest-confidence member; ties broken
    by earliest `created_at`. Member rows are NEVER deleted — they stay
    in `Question` (soft-deleted) and remain queryable.
    """

    canonical_question = models.ForeignKey(
        Question, on_delete=models.PROTECT, related_name='canonical_for',
    )
    similarity_threshold = models.DecimalField(max_digits=4, decimal_places=3, default=0.920)
    detection_method = models.CharField(max_length=32, default='rapidfuzz')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['detection_method']),
        ]

    def __str__(self):
        return f"Cluster#{self.id} -> Q{self.canonical_question_id}"


class DuplicateMember(models.Model):
    cluster = models.ForeignKey(
        DuplicateCluster, on_delete=models.CASCADE, related_name='members',
    )
    question = models.ForeignKey(
        Question, on_delete=models.PROTECT, related_name='cluster_memberships',
    )
    similarity_score = models.DecimalField(max_digits=4, decimal_places=3, default=1.000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['cluster', '-similarity_score']
        constraints = [
            models.UniqueConstraint(
                fields=['cluster', 'question'],
                name='uniq_duplicate_member',
            ),
        ]
        indexes = [
            models.Index(fields=['question']),
        ]

    def __str__(self):
        return f"Cluster{self.cluster_id} <- Q{self.question_id} ({self.similarity_score})"

