from rest_framework import serializers
from .models import Test, TestAttempt, QuestionResponse
from questions.serializers import QuestionListSerializer, QuestionDetailSerializer


class TestSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True, default='')
    topic_name = serializers.CharField(source='topic.name', read_only=True, default='')
    attempt_count = serializers.SerializerMethodField()

    class Meta:
        model = Test
        fields = ['id', 'title', 'test_type', 'description', 'subject',
                  'subject_name', 'topic', 'topic_name', 'num_questions',
                  'time_limit_minutes', 'negative_marking', 'negative_mark_value',
                  'is_published', 'attempt_count', 'created_at']

    def get_attempt_count(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.attempts.filter(user=request.user).count()
        return 0


class TestDetailSerializer(serializers.ModelSerializer):
    questions = QuestionListSerializer(many=True, read_only=True)

    class Meta:
        model = Test
        fields = '__all__'


class QuestionResponseSerializer(serializers.ModelSerializer):
    question_detail = QuestionDetailSerializer(source='question', read_only=True)

    class Meta:
        model = QuestionResponse
        fields = ['id', 'question', 'question_detail', 'selected_answer',
                  'is_correct', 'time_taken_seconds', 'is_marked_for_review',
                  'confidence_level']
        read_only_fields = ['is_correct']


class TestAttemptSerializer(serializers.ModelSerializer):
    test_title = serializers.CharField(source='test.title', read_only=True)
    accuracy = serializers.ReadOnlyField()

    class Meta:
        model = TestAttempt
        fields = ['id', 'test', 'test_title', 'started_at', 'completed_at',
                  'score', 'total_marks', 'correct_count', 'incorrect_count',
                  'unanswered_count', 'time_taken_seconds', 'is_completed',
                  'accuracy']
        read_only_fields = ['id', 'started_at', 'score', 'total_marks',
                            'correct_count', 'incorrect_count', 'unanswered_count']


class TestAttemptDetailSerializer(TestAttemptSerializer):
    responses = QuestionResponseSerializer(many=True, read_only=True)

    class Meta(TestAttemptSerializer.Meta):
        fields = TestAttemptSerializer.Meta.fields + ['responses']


class SubmitAnswerSerializer(serializers.Serializer):
    """Serializer for submitting test answers."""
    answers = serializers.ListField(
        child=serializers.DictField(),
        help_text='List of {question_id, selected_answer, time_taken_seconds, confidence_level}'
    )
