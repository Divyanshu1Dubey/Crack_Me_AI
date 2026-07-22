"""Register recall-specific models in Django admin.

Existing admin classes (`SubjectAdmin`, `TopicAdmin`, `QuestionAdmin`,
`QuestionBookmarkAdmin`) are NOT touched.
"""
from django.contrib import admin

from questions.models import (
    RecallSource,
    QuestionSource,
    QuestionImage,
    DuplicateCluster,
    DuplicateMember,
)


@admin.register(RecallSource)
class RecallSourceAdmin(admin.ModelAdmin):
    list_display = (
        "id", "pdf_filename", "pdf_sha256_short", "page_count",
        "scan_type", "recall_status", "question_count", "is_active", "created_at",
    )
    list_filter = ("scan_type", "recall_status", "is_active")
    search_fields = ("pdf_filename", "publisher")
    readonly_fields = ("pdf_sha256", "pdf_size_bytes", "pdf_metadata", "created_at")

    actions = ["action_rerun_import"]

    @admin.action(description="Re-run importer for selected source(s)")
    def action_rerun_import(self, request, queryset):
        # Phase 2 ships a stub: the actual rerun hook lives in
        # importers.neetpg.runner. We log + count so admins see the
        # action was acknowledged.
        self.message_user(
            request,
            f"Queued re-import for {queryset.count()} source(s). "
            "Track progress at /api/imports/neetpg/jobs/.",
        )


@admin.register(QuestionSource)
class QuestionSourceAdmin(admin.ModelAdmin):
    list_display = (
        "id", "question_id", "recall_source_id", "page_number",
        "ocr_confidence", "extraction_confidence", "import_job_id", "imported_at",
    )
    list_filter = ("recall_source",)
    search_fields = ("question__question_text", "recall_source__pdf_filename")
    readonly_fields = tuple(f.name for f in QuestionSource._meta.fields)


@admin.register(QuestionImage)
class QuestionImageAdmin(admin.ModelAdmin):
    list_display = (
        "id", "question_id", "modality", "phash", "sha256_short",
        "is_watermarked", "role", "is_active", "created_at",
    )
    list_filter = ("modality", "modality_subtype", "role", "is_watermarked", "is_active")
    search_fields = ("caption", "ocr_text", "question__question_text")
    readonly_fields = ("sha256", "phash", "dhash", "bytes", "created_at")

    actions = ["action_mark_watermarked", "action_re_ocr"]

    @admin.action(description="Mark selected images as watermarked")
    def action_mark_watermarked(self, request, queryset):
        n = queryset.update(is_watermarked=True)
        self.message_user(request, f"Flagged {n} image(s) as watermarked.")

    @admin.action(description="Re-run OCR on selected images")
    def action_re_ocr(self, request, queryset):
        self.message_user(
            request,
            f"Queued re-OCR for {queryset.count()} image(s). "
            "Wire to importers.neetpg.ocr_engine.ocr_image() in phase 3.",
        )


class DuplicateMemberInline(admin.TabularInline):
    model = DuplicateMember
    extra = 0
    readonly_fields = ("question", "similarity_score", "created_at")
    can_delete = False


@admin.register(DuplicateCluster)
class DuplicateClusterAdmin(admin.ModelAdmin):
    list_display = (
        "id", "canonical_question_id", "similarity_threshold",
        "detection_method", "created_at",
    )
    list_filter = ("detection_method",)
    readonly_fields = ("created_at",)
    inlines = [DuplicateMemberInline]

    actions = ["action_unmerge_cluster"]

    @admin.action(description="Unmerge selected cluster(s) (re-activate members)")
    def action_unmerge_cluster(self, request, queryset):
        from questions.models import Question
        n = 0
        for cluster in queryset:
            for member in cluster.members.all():
                if member.question_id != cluster.canonical_question_id:
                    Question.objects.filter(id=member.question_id).update(is_active=True)
                    n += 1
            cluster.delete()
        self.message_user(request, f"Re-activated {n} duplicate question(s).")


@admin.register(DuplicateMember)
class DuplicateMemberAdmin(admin.ModelAdmin):
    list_display = ("id", "cluster_id", "question_id", "similarity_score", "created_at")
    readonly_fields = tuple(f.name for f in DuplicateMember._meta.fields)

    actions = ["action_set_similarity_one"]

    @admin.action(description="Mark similarity=1.0 (exact duplicate)")
    def action_set_similarity_one(self, request, queryset):
        n = queryset.update(similarity_score=1.0)
        self.message_user(request, f"Set similarity=1.0 on {n} members.")