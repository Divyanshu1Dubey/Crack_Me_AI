from rest_framework import serializers
from .models import FREE_TEST_MAX_QUESTIONS, Test, TestAttempt, QuestionResponse
from questions.serializers import QuestionListSerializer, QuestionDetailSerializer


class TestSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True, default='')
    topic_name = serializers.CharField(source='topic.name', read_only=True, default='')
    attempt_count = serializers.SerializerMethodField()
    # Derived flag (2026-08-04): a test is free for the current user if it
    # has at most FREE_TEST_MAX_QUESTIONS questions. Mirrors the gate in
    # views.start_attempt so the UI badge matches the server-side check.
    is_free_for_current_user = serializers.SerializerMethodField()

    class Meta:
        model = Test
        fields = ['id', 'title', 'test_type', 'exam_type', 'description', 'subject',
                  'subject_name', 'topic', 'topic_name', 'num_questions',
                  'time_limit_minutes', 'negative_marking', 'negative_mark_value',
                  'is_published', 'is_free_preview', 'is_free_for_current_user',
                  'version', 'attempt_count', 'created_at', 'updated_at']

    def get_attempt_count(self, obj):
        # TestViewSet.get_queryset annotates the viewer's attempt count; the
        # per-row COUNT is only a fallback for unannotated instances.
        annotated = getattr(obj, '_user_attempt_count', None)
        if annotated is not None:
            return int(annotated)
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.attempts.filter(user=request.user).count()
        return 0

    def _viewer_is_premium(self, user):
        """is_premium(user), evaluated once per serializer call (it costs one
        or two Subscription queries and used to run for every listed test)."""
        cache = self.context  # shared by every row of a many=True serializer
        if '_viewer_is_premium' not in cache:
            try:
                from accounts.utils import is_premium as _is_premium
                cache['_viewer_is_premium'] = bool(_is_premium(user))
            except Exception:
                cache['_viewer_is_premium'] = False
        return cache['_viewer_is_premium']

    def get_is_free_for_current_user(self, obj):
        request = self.context.get('request')
        user = getattr(request, 'user', None) if request else None
        # Admins / premium / anonymous: everyone can see these tests.
        if user is None or not getattr(user, 'is_authenticated', False):
            return True
        if getattr(user, 'is_admin', False) or getattr(user, 'is_superuser', False):
            return True
        if self._viewer_is_premium(user):
            return True
        # Free user: free iff the test has at most FREE_TEST_MAX_QUESTIONS
        # questions. Neither the test_type (a client-chosen 'daily' used to
        # be exempt) nor the retired `is_free_preview` flag counts.
        try:
            count = getattr(obj, '_question_count', None)
            if count is None:
                count = obj.questions.count()
            return int(count or 0) <= FREE_TEST_MAX_QUESTIONS
        except (TypeError, ValueError):
            return False


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
