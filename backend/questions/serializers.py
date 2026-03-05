from rest_framework import serializers
from .models import Subject, Topic, Question, QuestionBookmark


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

    class Meta:
        model = Question
        fields = ['id', 'question_text', 'option_a', 'option_b', 'option_c', 'option_d',
                  'year', 'subject', 'subject_name',
                  'topic', 'topic_name', 'difficulty', 'exam_source',
                  'concept_tags', 'is_bookmarked']

    def get_is_bookmarked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.bookmarks.filter(user=request.user).exists()
        return False


class QuestionDetailSerializer(serializers.ModelSerializer):
    """Full serializer with explanations, references, similar questions."""
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    topic_name = serializers.CharField(source='topic.name', read_only=True, default='')
    similar = serializers.SerializerMethodField()
    is_bookmarked = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = '__all__'

    def get_similar(self, obj):
        similar_qs = obj.similar_questions.all()[:5]
        return QuestionListSerializer(similar_qs, many=True, context=self.context).data

    def get_is_bookmarked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.bookmarks.filter(user=request.user).exists()
        return False


class QuestionUploadSerializer(serializers.ModelSerializer):
    """Serializer for admin bulk upload."""
    class Meta:
        model = Question
        fields = ['question_text', 'option_a', 'option_b', 'option_c', 'option_d',
                  'correct_answer', 'year', 'subject', 'topic', 'difficulty',
                  'concept_tags', 'explanation', 'concept_explanation', 'mnemonic',
                  'book_name', 'chapter', 'page_number', 'reference_text',
                  'exam_source']


class BookmarkSerializer(serializers.ModelSerializer):
    question_detail = QuestionListSerializer(source='question', read_only=True)

    class Meta:
        model = QuestionBookmark
        fields = ['id', 'question', 'question_detail', 'note', 'created_at']
        read_only_fields = ['id', 'created_at']
