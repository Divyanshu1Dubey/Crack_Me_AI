import re

from django.db import models
from django.conf import settings


class Subject(models.Model):
    """Medical subjects like Medicine, Surgery, PSM, OBG, Pediatrics."""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)
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

    # Core fields
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

    class Meta:
        ordering = ['-year', 'subject']
        indexes = [
            models.Index(fields=['year', 'subject']),
            models.Index(fields=['difficulty']),
            models.Index(fields=['exam_source']),
            models.Index(fields=['paper']),
            models.Index(fields=['is_active', 'is_verified_by_admin']),
            models.Index(fields=['subject', 'topic', 'year', 'difficulty']),
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
        self.question_text = self._normalize_statement_text(self.question_text)
        self.option_a = self._normalize_text_value(self.option_a)
        self.option_b = self._normalize_text_value(self.option_b)
        self.option_c = self._normalize_text_value(self.option_c)
        self.option_d = self._normalize_text_value(self.option_d)
        self.explanation = self._normalize_text_value(self.explanation)
        self.concept_explanation = self._normalize_text_value(self.concept_explanation)
        self.mnemonic = self._normalize_text_value(self.mnemonic)
        self.reference_text = self._normalize_text_value(self.reference_text)

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
