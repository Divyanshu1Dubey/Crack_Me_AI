from rest_framework import serializers
from .models import UserTopicPerformance, DailyActivity


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
