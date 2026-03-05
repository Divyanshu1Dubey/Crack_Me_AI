from django.contrib import admin
from .models import Subject, Topic, Question, QuestionBookmark


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'paper']
    list_filter = ['paper']


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ['name', 'subject', 'importance']
    list_filter = ['subject', 'importance']
    search_fields = ['name']


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['id', 'year', 'subject', 'topic', 'difficulty', 'correct_answer']
    list_filter = ['year', 'subject', 'difficulty', 'exam_source']
    search_fields = ['question_text', 'explanation']
    filter_horizontal = ['similar_questions']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Question', {
            'fields': ('question_text', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_answer')
        }),
        ('Classification', {
            'fields': ('year', 'subject', 'topic', 'difficulty', 'concept_tags', 'exam_source')
        }),
        ('Explanation', {
            'fields': ('explanation', 'concept_explanation', 'mnemonic')
        }),
        ('Textbook Reference', {
            'fields': ('book_name', 'chapter', 'page_number', 'reference_text')
        }),
        ('Relations', {
            'fields': ('similar_questions',)
        }),
        ('Meta', {
            'fields': ('is_active', 'times_asked', 'created_at', 'updated_at')
        }),
    )


@admin.register(QuestionBookmark)
class QuestionBookmarkAdmin(admin.ModelAdmin):
    list_display = ['user', 'question', 'created_at']
