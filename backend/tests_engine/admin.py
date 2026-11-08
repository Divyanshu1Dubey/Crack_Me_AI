from django.contrib import admin
from .models import AttemptRescore, Test, TestAttempt, QuestionResponse

@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    list_display = ['title', 'test_type', 'subject', 'num_questions', 'is_published', 'version']
    list_filter = ['test_type', 'subject', 'is_published']
    search_fields = ['title']
    filter_horizontal = ['questions']
    # Retired flag: the start gate ignores it (free users may start any test
    # of at most 20 questions and no others), so it is not editable here.
    readonly_fields = ['is_free_preview']

@admin.register(TestAttempt)
class TestAttemptAdmin(admin.ModelAdmin):
    list_display = ['user', 'test', 'score', 'correct_count', 'is_completed', 'is_late', 'started_at']
    list_filter = ['is_completed', 'is_late']

@admin.register(QuestionResponse)
class QuestionResponseAdmin(admin.ModelAdmin):
    list_display = ['attempt', 'question', 'selected_answer', 'is_correct']


@admin.register(AttemptRescore)
class AttemptRescoreAdmin(admin.ModelAdmin):
    """The audit trail of re-scored attempts (tests_engine.scoring): read-only."""
    list_display = ['attempt', 'created_at', 'old_score', 'new_score', 'old_total_marks', 'new_total_marks', 'reason']
    search_fields = ['attempt__id', 'reason']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
