from rest_framework import serializers
from .models import UserTopicPerformance, DailyActivity, Feedback, Announcement, StudyStreak, Badge, UserBadge
from questions.models import StudyTimeBreakdown, UserQuest, QuestStreak, MistakeNotebook


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


class StudyTimeBreakdownSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True, default='')
    subject_code = serializers.CharField(source='subject.code', read_only=True, default='')
    subject_color = serializers.CharField(source='subject.color', read_only=True, default='')

    class Meta:
        model = StudyTimeBreakdown
        fields = ['id', 'subject', 'subject_name', 'subject_code', 'subject_color',
                  'date', 'seconds', 'question_count']
        read_only_fields = ['id']


class UserQuestSerializer(serializers.ModelSerializer):
    progress_percent = serializers.IntegerField(read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True, default='')

    class Meta:
        model = UserQuest
        fields = ['id', 'user', 'quest_type', 'difficulty', 'title', 'description',
                  'target_value', 'current_value', 'xp_reward', 'is_completed', 'is_claimed',
                  'progress_percent', 'subject_name', 'quest_date', 'expires_at',
                  'completed_at', 'created_at']
        read_only_fields = ['id', 'user', 'created_at']


class QuestStreakSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestStreak
        fields = ['id', 'user', 'current_streak', 'longest_streak', 'total_quests_completed',
                  'total_xp_earned', 'last_quest_date', 'streak_frozen', 'updated_at']
        read_only_fields = ['id', 'user']


class MistakeNotebookSerializer(serializers.ModelSerializer):
    question_text = serializers.CharField(source='question.question_text', read_only=True, default='')
    option_a = serializers.CharField(source='question.option_a', read_only=True, default='')
    option_b = serializers.CharField(source='question.option_b', read_only=True, default='')
    option_c = serializers.CharField(source='question.option_c', read_only=True, default='')
    option_d = serializers.CharField(source='question.option_d', read_only=True, default='')
    correct_answer = serializers.CharField(source='question.correct_answer', read_only=True, default='')
    explanation = serializers.CharField(source='question.explanation', read_only=True, default='')
    subject_name = serializers.CharField(source='question.subject.name', read_only=True, default='')
    topic_name = serializers.CharField(source='question.topic.name', read_only=True, default='')
    exam_type = serializers.CharField(source='question.exam_type', read_only=True, default='')

    class Meta:
        model = MistakeNotebook
        fields = ['id', 'user', 'question', 'question_text', 'option_a', 'option_b', 'option_c', 'option_d',
                  'selected_answer', 'correct_answer', 'is_correct', 'review_status',
                  'review_count', 'last_reviewed_at', 'next_review_at', 'is_flagged',
                  'user_note', 'explanation', 'subject_name', 'topic_name', 'exam_type', 'created_at']
        read_only_fields = ['id', 'user', 'created_at']


class TopicNoteListSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    exam_type = serializers.CharField()
    subject = serializers.IntegerField()
    subject_name = serializers.CharField()
    topic = serializers.IntegerField()
    topic_name = serializers.CharField()
    title = serializers.CharField()
    content_preview = serializers.CharField()
    ai_generated = serializers.BooleanField()
    source_question_count = serializers.IntegerField()
    created_by_username = serializers.CharField()
    is_published = serializers.BooleanField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
