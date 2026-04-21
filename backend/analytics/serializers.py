from rest_framework import serializers
from .models import UserTopicPerformance, DailyActivity, Feedback, Announcement, StudyStreak, Badge, UserBadge


class TopicPerformanceSerializer(serializers.ModelSerializer):
    topic_name = serializers.CharField(source='topic.name', read_only=True, default='')
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    accuracy = serializers.ReadOnlyField()
    avg_time_per_question = serializers.ReadOnlyField()

    class Meta:
        model = UserTopicPerformance
        fields = ['id', 'topic', 'topic_name', 'subject', 'subject_name',
                  'total_attempts', 'correct_answers', 'incorrect_answers',
                  'total_time_seconds', 'accuracy', 'avg_time_per_question',
                  'avg_confidence', 'last_attempted']


class DailyActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyActivity
        fields = ['date', 'questions_attempted', 'correct_answers',
                  'time_spent_minutes', 'tests_completed']


class FeedbackSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Feedback
        fields = ['id', 'username', 'category', 'rating', 'title', 'message',
                  'is_read', 'admin_reply', 'created_at']
        read_only_fields = ['id', 'username', 'is_read', 'admin_reply', 'created_at']


class AnnouncementSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.username', read_only=True, default='')
    is_expired = serializers.ReadOnlyField()

    class Meta:
        model = Announcement
        fields = [
            'id', 'title', 'message', 'image_url', 'deep_link', 'audience_filter',
            'priority', 'is_active', 'is_expired', 'scheduled_for', 'sent_at',
            'delivery_status', 'delivery_count', 'failure_report',
            'created_by', 'created_by_name', 'expires_at', 'created_at'
        ]
        read_only_fields = [
            'id', 'created_by', 'created_by_name', 'created_at',
            'sent_at', 'delivery_status', 'delivery_count', 'failure_report',
        ]


class StudyStreakSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = StudyStreak
        fields = ['username', 'current_streak', 'longest_streak', 'total_study_days',
                  'xp_points', 'last_activity_date']
        read_only_fields = fields


class BadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Badge
        fields = ['id', 'name', 'description', 'icon', 'xp_reward', 'criteria_type', 'criteria_value']


class UserBadgeSerializer(serializers.ModelSerializer):
    badge = BadgeSerializer(read_only=True)

    class Meta:
        model = UserBadge
        fields = ['id', 'badge', 'earned_at']


class LeaderboardEntrySerializer(serializers.Serializer):
    rank = serializers.IntegerField()
    username = serializers.CharField()
    user_id = serializers.IntegerField()
    xp_points = serializers.IntegerField()
    current_streak = serializers.IntegerField()
    total_study_days = serializers.IntegerField()
    accuracy = serializers.FloatField()
    tests_completed = serializers.IntegerField()
