from django.contrib import admin
from .models import Textbook, Chapter, PDFUpload, TextbookChunk, QuestionReferenceOverride

@admin.register(Textbook)
class TextbookAdmin(admin.ModelAdmin):
    list_display = ['name', 'author', 'subject', 'edition']
    list_filter = ['subject']

@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    list_display = ['textbook', 'number', 'title']

@admin.register(PDFUpload)
class PDFUploadAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'is_processed', 'uploaded_at']


@admin.register(TextbookChunk)
class TextbookChunkAdmin(admin.ModelAdmin):
    list_display = ['id', 'book_name', 'page_number', 'quality_score', 'is_approved', 'is_rejected', 'updated_at']
    list_filter = ['is_approved', 'is_rejected', 'book_name']
    search_fields = ['book_name', 'chunk_text']


@admin.register(QuestionReferenceOverride)
class QuestionReferenceOverrideAdmin(admin.ModelAdmin):
    list_display = ['id', 'question', 'textbook', 'page_number', 'is_active', 'created_by', 'updated_at']
    list_filter = ['is_active', 'textbook', 'page_number']
    search_fields = ['question__question_text', 'excerpt']
    list_display_links = ['id', 'question']
