from rest_framework import serializers
from .models import Subject, Topic, Question, QuestionBookmark, QuestionFeedback, Discussion, Note, Flashcard, QuestionImportJob, QuestionExtractionItem, AdminAIPromptVersion, QuestionAIOperationLog, QuestionRevisionSnapshot


class SubjectSerializer(serializers.ModelSerializer):
    question_count = serializers.SerializerMethodField()

    class Meta:
        model = Subject
        fields = ['id', 'name', 'code', 'paper', 'description', 'icon', 'color', 'question_count']

    def get_question_count(self, obj):
        return obj.questions.count()


class TopicSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    question_count = serializers.SerializerMethodField()

    class Meta:
        model = Topic
        fields = ['id', 'name', 'subject', 'subject_name', 'parent',
                  'importance', 'description', 'question_count']

    def get_question_count(self, obj):
        return obj.questions.count()


class QuestionListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list view."""
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    topic_name = serializers.CharField(source='topic.name', read_only=True, default='')
    is_bookmarked = serializers.SerializerMethodField()
    verified_by_username = serializers.CharField(source='verified_by.username', read_only=True, default='')
    effective_answer = serializers.SerializerMethodField()
    effective_explanation = serializers.SerializerMethodField()
    revision_count = serializers.SerializerMethodField()
    last_revision_at = serializers.SerializerMethodField()
    related_question_ids = serializers.SerializerMethodField()
    accuracy = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = ['id', 'question_text', 'option_a', 'option_b', 'option_c', 'option_d',
                  'year', 'subject', 'subject_name',
                  'topic', 'topic_name', 'difficulty', 'exam_source',
                  'concept_tags', 'concept_id', 'book_name', 'chapter', 'page_number', 'reference_text',
                  'textbook_references', 'is_bookmarked', 'is_verified_by_admin',
                  'verified_at', 'verified_by', 'verified_by_username',
                  'effective_answer', 'effective_explanation',
                  'revision_count', 'last_revision_at', 'related_question_ids', 'accuracy']

    def get_is_bookmarked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.bookmarks.filter(user=request.user).exists()
        return False

    def get_effective_answer(self, obj):
        if obj.lock_answer:
            return obj.admin_answer_override or obj.get_correct_option_text()
        if obj.admin_answer_override:
            return obj.admin_answer_override
        return obj.ai_answer or obj.get_correct_option_text()

    def get_effective_explanation(self, obj):
        if obj.lock_explanation:
            return obj.admin_explanation_override or obj.explanation
        if obj.admin_explanation_override:
            return obj.admin_explanation_override
        return obj.ai_explanation or obj.explanation

    def get_revision_count(self, obj):
        return obj.revision_snapshots.count()

    def get_last_revision_at(self, obj):
        latest = obj.revision_snapshots.order_by('-created_at').values_list('created_at', flat=True).first()
        return latest

    def get_related_question_ids(self, obj):
        return list(obj.similar_questions.values_list('id', flat=True)[:50])

    def get_accuracy(self, obj):
        value = getattr(obj, 'accuracy', None)
        if value is None:
            return None
        try:
            return round(float(value), 2)
        except (TypeError, ValueError):
            return None


class QuestionAdminListSerializer(QuestionListSerializer):
    """Admin list serializer that exposes lock controls."""

    class Meta(QuestionListSerializer.Meta):
        fields = QuestionListSerializer.Meta.fields + ['lock_answer', 'lock_explanation']


class QuestionDetailSerializer(serializers.ModelSerializer):
    """Full serializer with explanations, references, similar questions."""
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    topic_name = serializers.CharField(source='topic.name', read_only=True, default='')
    similar = serializers.SerializerMethodField()
    is_bookmarked = serializers.SerializerMethodField()
    effective_answer = serializers.SerializerMethodField()
    effective_explanation = serializers.SerializerMethodField()
    effective_mnemonic = serializers.SerializerMethodField()
    effective_references = serializers.SerializerMethodField()
    revision_count = serializers.SerializerMethodField()
    last_revision_at = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = [
            'id', 'question_text', 'option_a', 'option_b', 'option_c', 'option_d',
            'correct_answer', 'year', 'subject', 'subject_name', 'topic', 'topic_name',
            'difficulty', 'concept_tags', 'concept_id', 'explanation', 'concept_explanation',
            'mnemonic', 'book_name', 'chapter', 'page_number', 'reference_text', 'paper',
            'source', 'exam_source', 'times_asked', 'is_active', 'created_at', 'updated_at',
            'textbook_references', 'learning_technique', 'shortcut_tip', 'page_screenshot',
            'concept_keywords', 'ai_explanation', 'ai_answer', 'ai_mnemonic', 'ai_references',
            'is_verified_by_admin', 'verified_by', 'verified_at', 'verified_note',
            'similar', 'is_bookmarked', 'effective_answer', 'effective_explanation',
            'effective_mnemonic', 'effective_references', 'revision_count', 'last_revision_at',
        ]

    def get_similar(self, obj):
        similar_qs = obj.similar_questions.all()[:5]
        return QuestionListSerializer(similar_qs, many=True, context=self.context).data

    def get_is_bookmarked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.bookmarks.filter(user=request.user).exists()
        return False

    def get_effective_answer(self, obj):
        if obj.lock_answer:
            return obj.admin_answer_override or obj.get_correct_option_text()
        if obj.admin_answer_override:
            return obj.admin_answer_override
        return obj.ai_answer or obj.get_correct_option_text()

    def get_effective_explanation(self, obj):
        if obj.lock_explanation:
            return obj.admin_explanation_override or obj.explanation
        if obj.admin_explanation_override:
            return obj.admin_explanation_override
        return obj.ai_explanation or obj.explanation

    def get_effective_mnemonic(self, obj):
        if obj.admin_mnemonic_override:
            return obj.admin_mnemonic_override
        return obj.ai_mnemonic or obj.mnemonic

    def get_effective_references(self, obj):
        if obj.admin_references_override:
            return obj.admin_references_override
        return obj.ai_references or obj.textbook_references

    def get_revision_count(self, obj):
        return obj.revision_snapshots.count()

    def get_last_revision_at(self, obj):
        latest = obj.revision_snapshots.order_by('-created_at').values_list('created_at', flat=True).first()
        return latest


class QuestionUploadSerializer(serializers.ModelSerializer):
    """Serializer for admin bulk upload."""
    class Meta:
        model = Question
        fields = ['question_text', 'option_a', 'option_b', 'option_c', 'option_d',
                  'correct_answer', 'year', 'subject', 'topic', 'difficulty',
                  'concept_tags', 'explanation', 'concept_explanation', 'mnemonic',
                  'book_name', 'chapter', 'page_number', 'reference_text',
                  'textbook_references', 'concept_id', 'exam_source', 'is_verified_by_admin', 'verified_note']


class BookmarkSerializer(serializers.ModelSerializer):
    question_detail = QuestionListSerializer(source='question', read_only=True)

    class Meta:
        model = QuestionBookmark
        fields = ['id', 'question', 'question_detail', 'note', 'created_at']
        read_only_fields = ['id', 'created_at']


class QuestionFeedbackSerializer(serializers.ModelSerializer):
    question_text = serializers.CharField(source='question.question_text', read_only=True, default='')
    username = serializers.CharField(source='user.username', read_only=True, default='')

    class Meta:
        model = QuestionFeedback
        fields = [
            'id', 'question', 'question_text', 'user', 'username', 'category', 'comment',
            'status', 'is_resolved', 'resolution_note', 'resolved_by', 'resolved_at', 'notified_user', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'user', 'resolved_by', 'resolved_at', 'notified_user', 'is_resolved']


class DiscussionSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    reply_count = serializers.SerializerMethodField()
    user_vote = serializers.SerializerMethodField()

    class Meta:
        model = Discussion
        fields = ['id', 'question', 'user', 'username', 'parent', 'text',
                  'upvotes', 'downvotes', 'is_pinned', 'reply_count', 'user_vote',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'username', 'upvotes', 'downvotes',
                            'is_pinned', 'created_at', 'updated_at']

    def get_reply_count(self, obj):
        return obj.replies.count()

    def get_user_vote(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            vote = obj.votes.filter(user=request.user).first()
            return vote.vote_type if vote else None
        return None


class NoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Note
        fields = ['id', 'question', 'topic', 'title', 'content', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class FlashcardSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True, default='')

    class Meta:
        model = Flashcard
        fields = ['id', 'question', 'subject', 'subject_name', 'front', 'back',
                  'difficulty', 'next_review', 'review_count', 'ease_factor',
                  'interval_days', 'created_at']
        read_only_fields = ['id', 'review_count', 'ease_factor', 'interval_days',
                            'next_review', 'created_at']


class QuestionImportJobSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, default='')

    class Meta:
        model = QuestionImportJob
        fields = [
            'id', 'job_type', 'status', 'source_filename', 'stored_file_path',
            'summary', 'error_report', 'created_by', 'created_by_username',
            'created_at', 'updated_at'
        ]


class QuestionExtractionItemSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True, default='')
    topic_name = serializers.CharField(source='topic.name', read_only=True, default='')

    class Meta:
        model = QuestionExtractionItem
        fields = [
            'id', 'job', 'status', 'raw_text', 'question_text',
            'option_a', 'option_b', 'option_c', 'option_d',
            'correct_answer', 'explanation', 'year', 'paper',
            'subject', 'subject_name', 'topic', 'topic_name',
            'tags', 'published_question', 'review_note', 'created_at', 'updated_at'
        ]


class AdminAIPromptVersionSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, default='')

    class Meta:
        model = AdminAIPromptVersion
        fields = ['id', 'name', 'prompt_text', 'is_active', 'created_by', 'created_by_username', 'created_at']


class QuestionAIOperationLogSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, default='')
    prompt_version_name = serializers.CharField(source='prompt_version.name', read_only=True, default='')

    class Meta:
        model = QuestionAIOperationLog
        fields = [
            'id', 'question', 'operation_type', 'provider', 'prompt_version', 'prompt_version_name',
            'tokens_used', 'response_excerpt', 'created_by', 'created_by_username', 'created_at'
        ]


class QuestionRevisionSnapshotSerializer(serializers.ModelSerializer):
    changed_by_username = serializers.CharField(source='changed_by.username', read_only=True, default='')

    class Meta:
        model = QuestionRevisionSnapshot
        fields = ['id', 'question', 'changed_by', 'changed_by_username', 'reason', 'snapshot', 'created_at']
