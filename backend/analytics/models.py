import logging

from django.db import models
from django.conf import settings
from django.utils import timezone

# Re-export the new analytics-event model so it lives in this app
# (kept in a separate module to keep this file readable).
from .models_events import AnalyticsEvent  # noqa: F401  (re-exported for migrations / admin)

logger = logging.getLogger(__name__)


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
        constraints = [
            # unique_together cannot cover the subject-level row (topic=NULL):
            # NULLs are distinct in unique indexes, so two concurrent first
            # answers in a subject created duplicates and every later
            # get_or_create(topic=None) raised MultipleObjectsReturned.
            models.UniqueConstraint(
                fields=['user', 'subject'],
                condition=models.Q(topic__isnull=True),
                name='uniq_subject_level_topic_performance',
            ),
        ]

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
        topic_name = self.topic.name if self.topic else 'All Topics'
        return f"{self.user.username} | {topic_name}: {self.accuracy}%"


class DailyActivity(models.Model):
    """Track daily user activity for heatmap."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='daily_activities')
    date = models.DateField(db_index=True)
    questions_attempted = models.IntegerField(default=0)
    correct_answers = models.IntegerField(default=0)
    time_spent_minutes = models.IntegerField(default=0)
    tests_completed = models.IntegerField(default=0)

    class Meta:
        unique_together = ['user', 'date']
        indexes = [
            models.Index(fields=['user', 'date']),
        ]
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


class ContactMessage(models.Model):
    """A Contact Us submission (anonymous or signed in).

    Stored before the admin email is attempted, so a message is never lost
    when email delivery is slow, misconfigured or failing.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='contact_messages',
    )
    name = models.CharField(max_length=120, blank=True)
    email = models.EmailField()
    subject = models.CharField(max_length=200, blank=True)
    message = models.TextField()
    email_delivered = models.BooleanField(
        default=False, help_text='The admin notification email was handed to a real mail backend.',
    )
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.email}: {self.subject or '(no subject)'}"


class Announcement(models.Model):
    """Platform-wide announcements displayed on student dashboard."""
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    DELIVERY_STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    ]

    title = models.CharField(max_length=200)
    message = models.TextField()
    image_url = models.URLField(blank=True)
    deep_link = models.CharField(max_length=500, blank=True)
    audience_filter = models.JSONField(default=dict, blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')
    is_active = models.BooleanField(default=True)
    scheduled_for = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivery_status = models.CharField(max_length=20, choices=DELIVERY_STATUS_CHOICES, default='draft')
    delivery_count = models.IntegerField(default=0)
    failure_report = models.TextField(blank=True)
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
    xp_points = models.IntegerField(default=0, db_index=True)

    def record_activity(self):
        today = timezone.localdate()
        if self.last_activity_date == today:
            return
        if self.last_activity_date and (today - self.last_activity_date).days == 1:
            self.current_streak += 1
        elif self.last_activity_date != today:
            self.current_streak = 1
        self.longest_streak = max(self.longest_streak, self.current_streak)
        self.total_study_days += 1
        self.last_activity_date = today
        # Only the streak columns: a full save() wrote back the xp_points
        # value loaded earlier and erased concurrent add_xp() increments.
        self.save(update_fields=['current_streak', 'longest_streak', 'total_study_days', 'last_activity_date'])

    def add_xp(self, points):
        # Atomic increment: concurrent submits (two tabs, retries) used to
        # lose XP with the previous read-modify-write.
        from django.db import DatabaseError, transaction
        from django.db.models import F
        points = int(points)
        type(self).objects.filter(pk=self.pk).update(xp_points=F('xp_points') + points)
        self.refresh_from_db(fields=['xp_points'])
        if points:
            # Dated ledger for weekly / monthly leaderboards. Best effort: a
            # ledger failure must never undo or block the XP award itself.
            try:
                with transaction.atomic():
                    XPEvent.objects.create(user_id=self.user_id, points=points)
            except DatabaseError:
                logger.exception('Could not record XP ledger row for user=%s', self.user_id)

    def __str__(self):
        return f"{self.user.username}: {self.current_streak} day streak, {self.xp_points} XP"


class XPEvent(models.Model):
    """Dated XP ledger: one row per StudyStreak.add_xp() award.

    StudyStreak only keeps the all-time total; this lets the leaderboard rank
    by XP earned this week / month without re-deriving it from award rules
    that live in other apps.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='xp_events')
    points = models.IntegerField()
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        indexes = [models.Index(fields=['user', 'created_at'])]

    def __str__(self):
        return f"{self.user_id}: {self.points:+d} XP @ {self.created_at:%Y-%m-%d %H:%M}"


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
