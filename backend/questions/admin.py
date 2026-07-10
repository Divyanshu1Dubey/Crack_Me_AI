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





@admin.action(description='Generate AI Cache for selected questions')
def generate_ai_cache(modeladmin, request, queryset):
    from django_q.tasks import async_task
    for q in queryset:
        async_task('questions.tasks.generate_ai_task', q.id)
    modeladmin.message_user(request, f"Queued AI generation for {queryset.count()} questions.")

@admin.action(description='Generate Video for selected questions')
def generate_video(modeladmin, request, queryset):
    from django_q.tasks import async_task
    for q in queryset:
        async_task('video_engine.tasks.generate_video_task', q.id)
    modeladmin.message_user(request, f"Queued video generation for {queryset.count()} questions.")


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['id', 'year', 'subject', 'topic', 'difficulty', 'video_status', 'video_duration', 'ai_generated_at']
    list_filter = ['year', 'subject', 'video_status', 'difficulty']
    search_fields = ['question_text', 'explanation']
    filter_horizontal = ['similar_questions']
    readonly_fields = ['created_at', 'updated_at', 'ai_generated_at', 'video_generated_at', 'video_version', 'video_error']
    actions = [generate_ai_cache, generate_video]

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
        ('AI Video', {

            'fields': ('video_url', 'video_thumbnail', 'video_status', 'video_duration', 'video_generated_at', 'video_version', 'video_error')

        }),

        ('Meta', {

            'fields': ('is_active', 'times_asked', 'created_at', 'updated_at')

        }),

    )





@admin.register(QuestionBookmark)

class QuestionBookmarkAdmin(admin.ModelAdmin):

    list_display = ['user', 'question', 'created_at']

