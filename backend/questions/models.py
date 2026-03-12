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
        ]


    def __str__(self):
        return f"[{self.year}] {self.subject.code}: {self.question_text[:80]}..."

    def get_correct_option_text(self):
        mapping = {'A': self.option_a, 'B': self.option_b, 'C': self.option_c, 'D': self.option_d}
        return mapping.get(self.correct_answer, '')


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

    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='feedbacks')
    user = models.ForeignKey('accounts.CustomUser', on_delete=models.SET_NULL, null=True, blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    comment = models.TextField()
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Feedback on Q{self.question.id}: {self.get_category_display()}"


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
    """Flashcards for spaced repetition review."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='flashcards')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, null=True, blank=True, related_name='flashcards')
    subject = models.ForeignKey('questions.Subject', on_delete=models.CASCADE, null=True, blank=True)
    front = models.TextField(help_text="Question or prompt side")
    back = models.TextField(help_text="Answer or explanation side")
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
