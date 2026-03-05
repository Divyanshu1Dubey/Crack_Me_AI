from django.contrib import admin
from .models import Test, TestAttempt, QuestionResponse

@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    list_display = ['title', 'test_type', 'subject', 'num_questions', 'is_published']
    list_filter = ['test_type', 'subject', 'is_published']
    filter_horizontal = ['questions']

@admin.register(TestAttempt)
class TestAttemptAdmin(admin.ModelAdmin):
    list_display = ['user', 'test', 'score', 'correct_count', 'is_completed', 'started_at']
    list_filter = ['is_completed']

@admin.register(QuestionResponse)
class QuestionResponseAdmin(admin.ModelAdmin):
    list_display = ['attempt', 'question', 'selected_answer', 'is_correct']
