from django.db import models


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
