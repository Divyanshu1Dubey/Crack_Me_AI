from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html
from .models import Subject, Topic, Question, QuestionBookmark, QuestionFeedback, Discussion, Note, Flashcard, QuestionImportJob, QuestionExtractionItem, AdminAIPromptVersion, QuestionAIOperationLog, QuestionRevisionSnapshot


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'paper', 'question_count']
    list_filter = ['paper']
    search_fields = ['name', 'code']
    
    def question_count(self, obj):
        count = obj.questions.count()
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>',
                         '#28a745' if count > 100 else '#dc3545' if count < 50 else '#ffc107', count)
    question_count.short_description = 'Questions'


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ['name', 'subject', 'importance', 'question_count']
    list_filter = ['subject', 'importance']
    search_fields = ['name', 'subject__name']
    
    def question_count(self, obj):
        count = obj.questions.count()
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>',
                         '#28a745' if count > 10 else '#dc3545' if count < 5 else '#ffc107', count)
    question_count.short_description = 'Questions'


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['id', 'year', 'subject', 'topic_display', 'difficulty', 'has_explanation', 'has_topic', 'is_verified_by_admin', 'correct_answer']
    list_filter = ['year', 'subject', 'difficulty', 'exam_source', 'is_active']
    search_fields = ['question_text', 'explanation']
    filter_horizontal = ['similar_questions']
    readonly_fields = ['created_at', 'updated_at']
    actions = ['add_explanations', 'assign_topics', 'activate_questions', 'deactivate_questions', 'mark_verified', 'mark_unverified']
    
    def topic_display(self, obj):
        if obj.topic:
            return format_html('<span style="color: #28a745;">{}</span>', obj.topic.name)
        else:
            return format_html('<span style="color: #dc3545; font-weight: bold;">No Topic</span>')
    topic_display.short_description = 'Topic'
    
    def has_explanation(self, obj):
        if obj.explanation:
            return format_html('<span style="color: #28a745;">✓</span>')
        else:
            return format_html('<span style="color: #dc3545; font-weight: bold;">✗</span>')
    has_explanation.short_description = 'Explanation'
    
    def has_topic(self, obj):
        if obj.topic:
            return format_html('<span style="color: #28a745;">✓</span>')
        else:
            return format_html('<span style="color: #dc3545; font-weight: bold;">✗</span>')
    has_topic.short_description = 'Topic'
    
    def add_explanations(self, request, queryset):
        count = queryset.filter(explanation='').count()
        self.message_user(request, f'{count} questions need explanations. Please edit them individually.')
    add_explanations.short_description = 'Check questions without explanations'
    
    def assign_topics(self, request, queryset):
        count = queryset.filter(topic__isnull=True).count()
        self.message_user(request, f'{count} questions need topics. Please edit them individually.')
    assign_topics.short_description = 'Check questions without topics'
    
    def activate_questions(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} questions activated.')
    activate_questions.short_description = 'Activate selected questions'
    
    def deactivate_questions(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} questions deactivated.')
    deactivate_questions.short_description = 'Deactivate selected questions'

    def mark_verified(self, request, queryset):
        updated = queryset.update(is_verified_by_admin=True)
        self.message_user(request, f'{updated} questions marked as verified by admin.')
    mark_verified.short_description = 'Mark selected as verified'

    def mark_unverified(self, request, queryset):
        updated = queryset.update(is_verified_by_admin=False)
        self.message_user(request, f'{updated} questions marked as unverified.')
    mark_unverified.short_description = 'Mark selected as unverified'
    
    fieldsets = (
        ('Question', {
            'fields': ('question_text', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_answer')
        }),
        ('Classification', {
            'fields': ('year', 'subject', 'topic', 'difficulty', 'concept_tags', 'exam_source')
        }),
        ('Explanation', {
            'fields': ('explanation', 'concept_explanation', 'mnemonic'),
            'description': 'Add detailed explanations to improve learning value'
        }),
        ('Textbook Reference', {
            'fields': ('book_name', 'chapter', 'page_number', 'reference_text'),
            'description': 'Reference textbooks for additional study'
        }),
        ('Relations', {
            'fields': ('similar_questions',)
        }),
        ('Meta', {
            'fields': ('is_active', 'times_asked', 'created_at', 'updated_at')
        }),
    )
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('subject', 'topic')


@admin.register(QuestionBookmark)
class QuestionBookmarkAdmin(admin.ModelAdmin):
    list_display = ['user', 'question_preview', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username', 'question__question_text']
    
    def question_preview(self, obj):
        return obj.question.question_text[:50] + '...' if len(obj.question.question_text) > 50 else obj.question.question_text
    question_preview.short_description = 'Question'


@admin.register(QuestionFeedback)
class QuestionFeedbackAdmin(admin.ModelAdmin):
    list_display = ['id', 'question', 'user', 'category', 'status', 'is_resolved', 'notified_user', 'created_at']
    list_filter = ['category', 'status', 'is_resolved', 'notified_user']
    search_fields = ['question__question_text', 'user__username', 'comment', 'resolution_note']
    readonly_fields = ['created_at', 'resolved_at']


@admin.register(Discussion)
class DiscussionAdmin(admin.ModelAdmin):
    list_display = ['user', 'question', 'text_preview', 'upvotes', 'is_pinned', 'created_at']
    list_filter = ['is_pinned']
    search_fields = ['text', 'user__username']
    actions = ['pin_discussions', 'unpin_discussions']

    def text_preview(self, obj):
        return obj.text[:60]
    text_preview.short_description = 'Text'

    def pin_discussions(self, request, queryset):
        queryset.update(is_pinned=True)
    pin_discussions.short_description = 'Pin selected discussions'

    def unpin_discussions(self, request, queryset):
        queryset.update(is_pinned=False)
    unpin_discussions.short_description = 'Unpin selected discussions'


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ['user', 'title', 'question', 'topic', 'updated_at']
    search_fields = ['title', 'content', 'user__username']


@admin.register(Flashcard)
class FlashcardAdmin(admin.ModelAdmin):
    list_display = ['user', 'front_preview', 'difficulty', 'review_count', 'next_review']
    list_filter = ['difficulty']
    search_fields = ['front', 'back', 'user__username']

    def front_preview(self, obj):
        return obj.front[:50]
    front_preview.short_description = 'Front'


@admin.register(QuestionImportJob)
class QuestionImportJobAdmin(admin.ModelAdmin):
    list_display = ['id', 'job_type', 'status', 'source_filename', 'created_by', 'created_at']
    list_filter = ['job_type', 'status', 'created_at']
    search_fields = ['source_filename', 'created_by__username']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(QuestionExtractionItem)
class QuestionExtractionItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'job', 'status', 'year', 'paper', 'subject', 'topic', 'published_question']
    list_filter = ['status', 'year', 'paper', 'subject']
    search_fields = ['question_text', 'raw_text', 'review_note']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(AdminAIPromptVersion)
class AdminAIPromptVersionAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'is_active', 'created_by', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'prompt_text']


@admin.register(QuestionAIOperationLog)
class QuestionAIOperationLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'question', 'operation_type', 'provider', 'tokens_used', 'created_at']
    list_filter = ['operation_type', 'provider', 'created_at']
    search_fields = ['question__question_text', 'response_excerpt']


@admin.register(QuestionRevisionSnapshot)
class QuestionRevisionSnapshotAdmin(admin.ModelAdmin):
    list_display = ['id', 'question', 'changed_by', 'reason', 'created_at']
    list_filter = ['created_at']
    search_fields = ['question__question_text', 'changed_by__username', 'reason']
    readonly_fields = ['created_at']
