"""Read-only Django admin for evidence. All writes go through evidence.services (the review API and
the admin evidence page), which keep the snippet check, staleness and the review log intact."""
from django.contrib import admin

from .models import EvidenceFigure, EvidenceReviewLog, EvidenceSource, QuestionEvidence


class _ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EvidenceSource)
class EvidenceSourceAdmin(_ReadOnlyAdmin):
    list_display = ('id', 'title', 'edition', 'year', 'kind', 'tier', 'student_display', 'is_active')
    list_filter = ('tier', 'kind', 'student_display', 'is_active', 'metadata_source')
    search_fields = ('title', 'sha256')


@admin.register(EvidenceFigure)
class EvidenceFigureAdmin(_ReadOnlyAdmin):
    list_display = ('id', 'source', 'page_no', 'width', 'height', 'created_at')
    raw_id_fields = ('source', 'created_by')


@admin.register(QuestionEvidence)
class QuestionEvidenceAdmin(_ReadOnlyAdmin):
    list_display = ('id', 'question_id', 'source', 'page_start', 'page_label', 'option_letter', 'stance', 'origin',
                    'review_status', 'student_visible')
    list_filter = ('review_status', 'origin', 'stance', 'student_visible', 'source__tier')
    search_fields = ('=question__id', 'snippet', 'source__title')
    raw_id_fields = ('question', 'question_image', 'source', 'figure', 'created_by', 'reviewed_by')
    list_select_related = ('source',)


@admin.register(EvidenceReviewLog)
class EvidenceReviewLogAdmin(_ReadOnlyAdmin):
    list_display = ('id', 'evidence_id', 'action', 'actor_id', 'created_at')
    list_filter = ('action',)
    raw_id_fields = ('evidence', 'actor')
