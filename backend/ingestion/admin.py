"""Django admin registration for the ingestion app.

Read-only surface — UPSC's ``/admin/`` pages keep working unchanged.
This is purely so a Django superuser can inspect the production
ingestion ledger from the existing admin panel if they want to.
"""
from django.contrib import admin

from .models import (
    BatchRun,
    ImportArtifact,
    ImportCheckpoint,
    ImportJob,
    ImportJobStage,
    ImportLog,
    MaterialAsset,
    StagedQuestion,
)


@admin.register(MaterialAsset)
class MaterialAssetAdmin(admin.ModelAdmin):
    list_display = ("sha256_short", "original_filename", "file_size", "page_count",
                    "exam_hint", "is_active", "uploaded_at")
    search_fields = ("sha256", "sha256_short", "original_filename")
    readonly_fields = ("sha256", "sha256_short", "uploaded_at", "updated_at")


@admin.register(BatchRun)
class BatchRunAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "status", "total_jobs", "completed_jobs",
                    "failed_jobs", "created_at")
    search_fields = ("name",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(ImportJob)
class ImportJobAdmin(admin.ModelAdmin):
    list_display = ("id", "parent_exam", "version", "status", "current_stage",
                    "qa_v2_production_ready_pct", "qa_v2_needs_review_pct",
                    "qa_v2_extraction_failure_pct", "created_at")
    list_filter = ("status", "parent_exam")
    search_fields = ("material_asset__sha256_short",)
    readonly_fields = ("created_at", "updated_at", "started_at", "completed_at",
                       "qa_v2_production_ready_pct", "qa_v2_needs_review_pct",
                       "qa_v2_extraction_failure_pct")


@admin.register(ImportJobStage)
class ImportJobStageAdmin(admin.ModelAdmin):
    list_display = ("id", "job", "stage_name", "status", "pages_processed",
                    "started_at", "completed_at")
    list_filter = ("stage_name", "status")


@admin.register(ImportCheckpoint)
class ImportCheckpointAdmin(admin.ModelAdmin):
    list_display = ("id", "job", "last_completed_stage", "last_processed_page",
                    "current_page", "version", "created_at")
    list_filter = ("last_completed_stage",)


@admin.register(ImportArtifact)
class ImportArtifactAdmin(admin.ModelAdmin):
    list_display = ("id", "job", "kind", "sha16_short", "bytes", "created_at")
    list_filter = ("kind",)


@admin.register(ImportLog)
class ImportLogAdmin(admin.ModelAdmin):
    list_display = ("id", "job", "level", "stage_name", "created_at")
    list_filter = ("level", "stage_name")


@admin.register(StagedQuestion)
class StagedQuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "job", "qa_status", "review_status", "page_number",
                    "question_number_in_pdf", "created_at")
    list_filter = ("qa_status", "review_status")
    search_fields = ("question_payload__stem",)
    actions = ["publish_to_live"]

    @admin.action(description="Approve and Publish to Live Question Bank")
    def publish_to_live(self, request, queryset):
        from .conservative_gate import _import_production_ready
        
        # Group by job for batching
        jobs = {}
        for sq in queryset:
            if sq.job_id not in jobs:
                jobs[sq.job_id] = {"job": sq.job, "payloads": [], "sq_objs": []}
            jobs[sq.job_id]["payloads"].append(sq.question_payload)
            jobs[sq.job_id]["sq_objs"].append(sq)
            
        total_created = 0
        total_updated = 0
        for job_data in jobs.values():
            c, u, _ = _import_production_ready(
                job=job_data["job"],
                pr_payloads=job_data["payloads"]
            )
            total_created += c
            total_updated += u
            for sq in job_data["sq_objs"]:
                sq.review_status = "approved"
                sq.save(update_fields=["review_status"])
                
        self.message_user(request, f"Published {total_created} new questions, updated {total_updated} existing questions.")
