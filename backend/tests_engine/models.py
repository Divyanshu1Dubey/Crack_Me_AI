from django.db import models
from django.conf import settings


class Test(models.Model):
    """A test/quiz configuration."""
    TEST_TYPES = [
        ('subject', 'Subject-wise Test'),
        ('topic', 'Topic-wise Micro Test'),
        ('mixed', 'Mixed Practice Test'),
        ('paper1', 'Full Paper 1 Mock'),
        ('paper2', 'Full Paper 2 Mock'),
        ('daily', 'Daily Quick Test'),
        ('pyq_year', 'Previous Year Paper'),
        ('weak', 'Weak Topic Test'),
        ('adaptive', 'AI Adaptive Test'),
    ]

    title = models.CharField(max_length=300)
    test_type = models.CharField(max_length=20, choices=TEST_TYPES)
    description = models.TextField(blank=True)
    subject = models.ForeignKey(
        'questions.Subject', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='tests'
    )
    topic = models.ForeignKey(
        'questions.Topic', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='tests'
    )
    questions = models.ManyToManyField('questions.Question', related_name='tests', blank=True)
    num_questions = models.IntegerField(default=20)
    time_limit_minutes = models.IntegerField(default=30, help_text='Time limit in minutes')
    negative_marking = models.BooleanField(default=True)
    negative_mark_value = models.FloatField(default=0.33)
    is_published = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='created_tests'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.get_test_type_display()})"


class TestAttempt(models.Model):
    """A user's attempt at a test."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='test_attempts')
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name='attempts')
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    score = models.FloatField(null=True, blank=True)
    total_marks = models.FloatField(null=True, blank=True)
    correct_count = models.IntegerField(default=0)
    incorrect_count = models.IntegerField(default=0)
    unanswered_count = models.IntegerField(default=0)
    time_taken_seconds = models.IntegerField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.user.username} — {self.test.title} ({self.started_at.date()})"

    @property
    def accuracy(self):
        total = self.correct_count + self.incorrect_count
        if total == 0:
            return 0
        return round((self.correct_count / total) * 100, 1)


class QuestionResponse(models.Model):
    """Individual question response within a test attempt."""
    attempt = models.ForeignKey(TestAttempt, on_delete=models.CASCADE, related_name='responses')
    question = models.ForeignKey('questions.Question', on_delete=models.CASCADE)
    selected_answer = models.CharField(max_length=1, blank=True, null=True)
    is_correct = models.BooleanField(null=True)
    time_taken_seconds = models.IntegerField(null=True, blank=True)
    is_marked_for_review = models.BooleanField(default=False)
    confidence_level = models.IntegerField(
        null=True, blank=True,
        help_text='1-5 confidence rating'
    )

    class Meta:
        unique_together = ['attempt', 'question']

    def __str__(self):
        status = 'Correct' if self.is_correct else ('Incorrect' if self.is_correct is not None else 'Unanswered')
        return f"Q{self.question.id}: {status}"
