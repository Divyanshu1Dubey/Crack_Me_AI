from rest_framework import serializers
from .models import Textbook, Chapter, PDFUpload


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
