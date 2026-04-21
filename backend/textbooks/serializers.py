from rest_framework import serializers
from .models import Textbook, Chapter, PDFUpload, TextbookChunk, QuestionReferenceOverride


class ChapterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chapter
        fields = ['id', 'number', 'title', 'textbook']


class TextbookSerializer(serializers.ModelSerializer):
    chapters = ChapterSerializer(many=True, read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)

    class Meta:
        model = Textbook
        fields = ['id', 'name', 'author', 'edition', 'subject',
                  'subject_name', 'description', 'chapters']


class PDFUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = PDFUpload
        fields = ['id', 'title', 'file', 'textbook', 'subject', 'is_processed', 'uploaded_at']
        read_only_fields = ['is_processed', 'uploaded_at']


class TextbookChunkSerializer(serializers.ModelSerializer):
    textbook_name = serializers.CharField(source='textbook.name', read_only=True, default='')
    upload_title = serializers.CharField(source='upload.title', read_only=True, default='')

    class Meta:
        model = TextbookChunk
        fields = [
            'id', 'textbook', 'textbook_name', 'upload', 'upload_title', 'book_name', 'page_number',
            'chunk_text', 'quality_score', 'is_approved', 'is_rejected', 'merged_from_ids', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'merged_from_ids', 'textbook_name', 'upload_title']


class QuestionReferenceOverrideSerializer(serializers.ModelSerializer):
    textbook_name = serializers.CharField(source='textbook.name', read_only=True, default='')
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, default='')
    screenshot_url = serializers.SerializerMethodField()

    class Meta:
        model = QuestionReferenceOverride
        fields = [
            'id', 'question', 'textbook', 'textbook_name', 'chapter', 'page_number', 'excerpt',
            'screenshot', 'screenshot_url', 'is_active', 'created_by', 'created_by_username',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'created_by_username', 'created_at', 'updated_at', 'textbook_name', 'screenshot_url']

    def get_screenshot_url(self, obj):
        if obj.screenshot:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.screenshot.url)
            return obj.screenshot.url
        return ''
