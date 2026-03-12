from django.db import models
from django.conf import settings
from django.utils import timezone


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


class Announcement(models.Model):
    """Platform-wide announcements displayed on student dashboard."""
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    title = models.CharField(max_length=200)
    message = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='announcements'
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def is_expired(self):
        if self.expires_at and timezone.now() > self.expires_at:
            return True
        return False

    def __str__(self):
        return f"[{self.get_priority_display()}] {self.title}"


class StudyStreak(models.Model):
    """Track daily study streaks for gamification."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='study_streak'
    )
    current_streak = models.IntegerField(default=0)
    longest_streak = models.IntegerField(default=0)
    total_study_days = models.IntegerField(default=0)
    last_activity_date = models.DateField(null=True, blank=True)
    xp_points = models.IntegerField(default=0)

    def record_activity(self):
        today = timezone.now().date()
        if self.last_activity_date == today:
            return
        if self.last_activity_date and (today - self.last_activity_date).days == 1:
            self.current_streak += 1
        elif self.last_activity_date != today:
            self.current_streak = 1
        self.longest_streak = max(self.longest_streak, self.current_streak)
        self.total_study_days += 1
        self.last_activity_date = today
        self.save()

    def add_xp(self, points):
        self.xp_points += points
        self.save(update_fields=['xp_points'])

    def __str__(self):
        return f"{self.user.username}: {self.current_streak} day streak, {self.xp_points} XP"


class Badge(models.Model):
    """Achievement badges for gamification."""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    icon = models.CharField(max_length=50, help_text="Emoji or icon name")
    xp_reward = models.IntegerField(default=0)
    criteria_type = models.CharField(max_length=50, choices=[
        ('streak', 'Study Streak'),
        ('questions', 'Questions Answered'),
        ('tests', 'Tests Completed'),
        ('accuracy', 'Accuracy Milestone'),
        ('subject', 'Subject Mastery'),
        ('special', 'Special Achievement'),
    ])
    criteria_value = models.IntegerField(default=0, help_text="Threshold value for earning this badge")

    class Meta:
        ordering = ['criteria_type', 'criteria_value']

    def __str__(self):
        return f"{self.icon} {self.name}"


class UserBadge(models.Model):
    """Badges earned by users."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='earned_badges'
    )
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name='earners')
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'badge']
        ordering = ['-earned_at']

    def __str__(self):
        return f"{self.user.username} earned {self.badge.name}"
