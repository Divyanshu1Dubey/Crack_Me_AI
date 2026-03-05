from django.contrib import admin
from .models import Textbook, Chapter, PDFUpload

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
