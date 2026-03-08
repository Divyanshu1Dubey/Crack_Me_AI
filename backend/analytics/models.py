from django.db import models
from django.conf import settings


class UserTopicPerformance(models.Model):
    """Track user performance per topic for analytics."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='topic_performances')
    topic = models.ForeignKey('questions.Topic', on_delete=models.CASCADE, null=True, blank=True, related_name='performances')
    subject = models.ForeignKey('questions.Subject', on_delete=models.CASCADE, related_name='performances')

    total_attempts = models.IntegerField(default=0)
    correct_answers = models.IntegerField(default=0)
    incorrect_answers = models.IntegerField(default=0)
    total_time_seconds = models.IntegerField(default=0)
    avg_confidence = models.FloatField(default=0)
    last_attempted = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['user', 'subject', 'topic']

    @property
    def accuracy(self):
        if self.total_attempts == 0:
            return 0
        return round((self.correct_answers / self.total_attempts) * 100, 1)

    @property
    def avg_time_per_question(self):
        if self.total_attempts == 0:
            return 0
        return round(self.total_time_seconds / self.total_attempts, 1)

    def __str__(self):
        return f"{self.user.username} | {self.topic.name}: {self.accuracy}%"


class DailyActivity(models.Model):
    """Track daily user activity for heatmap."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='daily_activities')
    date = models.DateField()
    questions_attempted = models.IntegerField(default=0)
    correct_answers = models.IntegerField(default=0)
    time_spent_minutes = models.IntegerField(default=0)
    tests_completed = models.IntegerField(default=0)

    class Meta:
        unique_together = ['user', 'date']
        ordering = ['-date']

    def __str__(self):
        return f"{self.user.username} | {self.date}: {self.questions_attempted} Qs"


class Feedback(models.Model):
    """General platform feedback from students."""
    CATEGORY_CHOICES = [
        ('bug', 'Bug Report'),
        ('feature', 'Feature Request'),
        ('content', 'Content Issue'),
        ('ui', 'UI/UX Feedback'),
        ('ai', 'AI Quality'),
        ('general', 'General Feedback'),
    ]
    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='feedbacks'
    )
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='general')
    rating = models.IntegerField(choices=RATING_CHOICES, default=5)
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    admin_reply = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username}: {self.title} ({self.get_category_display()})"
