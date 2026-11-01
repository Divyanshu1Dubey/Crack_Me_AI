from rest_framework import serializers
from .entitlement import has_locked_questions, lock_answer
from .models import FREE_TEST_MAX_QUESTIONS, Test, TestAttempt, QuestionResponse
from questions.serializers import QuestionListSerializer


class TestSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True, default='')
    topic_name = serializers.CharField(source='topic.name', read_only=True, default='')
    attempt_count = serializers.SerializerMethodField()
    # Derived flag (2026-08-04): a test is free for the current user if it
    # has at most FREE_TEST_MAX_QUESTIONS questions, all of them questions
    # whose answers the user may see (tests_engine.entitlement). Mirrors the
    # gates in views.start_attempt so the UI badge matches the server.
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
            if int(count or 0) > FREE_TEST_MAX_QUESTIONS:
                return False
        except (TypeError, ValueError):
            return False
        # ... and every question must be one whose answer the user may see
        # (staff see every answer; others only the free showcase).
        if getattr(user, 'is_staff', False):
            return True
        return not has_locked_questions(user, obj, full_access=False)


class TestDetailSerializer(serializers.ModelSerializer):
    questions = QuestionListSerializer(many=True, read_only=True)

    class Meta:
        model = Test
        fields = '__all__'


class QuestionResponseSerializer(serializers.ModelSerializer):
    """One answered question of an attempt (GET /api/tests/attempts/<id>/).

    ``question_detail`` is a slim snapshot of the question. It used to nest
    the full QuestionDetailSerializer: about five queries per response, and
    the answer key and explanations of every question whatever the viewer's
    plan. The answer parts now follow tests_engine.entitlement: the view
    puts ``answer_visibility`` ({question_id: bool}) in the context, and
    without it every answer is locked.
    """
    question_detail = serializers.SerializerMethodField()

    class Meta:
        model = QuestionResponse
        fields = ['id', 'question', 'question_detail', 'selected_answer',
                  'is_correct', 'time_taken_seconds', 'is_marked_for_review',
                  'confidence_level']
        read_only_fields = ['is_correct']

    def get_question_detail(self, obj):
        q = obj.question
        subject_name = q.subject.name if q.subject_id else ''
        if subject_name == 'Imported':  # loader bucket, shown as in the question bank
            subject_name = 'Expert Curated'
        row = {
            'id': q.id,
            'question_text': q.question_text,
            'option_a': q.option_a,
            'option_b': q.option_b,
            'option_c': q.option_c,
            'option_d': q.option_d,
            'subject': q.subject_id,
            'subject_name': subject_name,
            'topic': q.topic_id,
            'topic_name': q.topic.name if q.topic_id else '',
            'year': q.year,
            'paper': q.paper,
            'difficulty': q.difficulty,
            'exam_source': q.exam_source,
            'correct_answer': q.correct_answer,
            'explanation': q.explanation or q.ai_explanation or '',
            'mnemonic': q.mnemonic or '',
            'concept_explanation': q.concept_explanation or '',
            'textbook_references': q.textbook_references or [],
            'answer_locked': False,
        }
        if not (self.context.get('answer_visibility') or {}).get(q.pk, False):
            lock_answer(row)
        return row


class TestAttemptSerializer(serializers.ModelSerializer):
    test_title = serializers.CharField(source='test.title', read_only=True)
    accuracy = serializers.ReadOnlyField()

    class Meta:
        model = TestAttempt
        fields = ['id', 'test', 'test_title', 'started_at', 'completed_at',
                  'score', 'total_marks', 'correct_count', 'incorrect_count',
                  'unanswered_count', 'time_taken_seconds', 'is_completed',
                  'is_late', 'accuracy']
        read_only_fields = ['id', 'started_at', 'score', 'total_marks',
                            'correct_count', 'incorrect_count', 'unanswered_count',
                            'is_late']


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
