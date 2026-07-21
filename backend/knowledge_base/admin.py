from django.contrib import admin
from django.utils.html import format_html

from .models import (
    KnowledgeSource, KnowledgeChunk, KnowledgeEmbedding,
    KnowledgeEntity, KnowledgeRelation, IngestionJob,
    GoldenTestCase, EvalRun, UserUploadAttestation,
)


@admin.register(KnowledgeSource)
class KnowledgeSourceAdmin(admin.ModelAdmin):
    list_display = ("slug", "name", "license", "is_active",
                    "chunk_count", "last_ingestion_status",
                    "last_ingested_at")
    list_filter = ("is_active", "license")
    search_fields = ("slug", "name", "attribution")
    readonly_fields = ("chunk_count", "entity_count",
                       "last_ingested_at", "last_ingestion_status",
                       "created_at", "updated_at")


@admin.register(KnowledgeChunk)
class KnowledgeChunkAdmin(admin.ModelAdmin):
    list_display = ("id", "source", "subject", "topic", "license",
                    "approval_state", "is_active", "version",
                    "quality_score", "created_at")
    list_filter = ("approval_state", "is_active", "license", "source")
    search_fields = ("text", "locator", "topic", "tags")
    readonly_fields = ("text_hash", "created_at", "updated_at")
    actions = ["approve_chunks", "reject_chunks"]

    def approve_chunks(self, request, queryset):
        from django.utils import timezone
        n = queryset.update(
            approval_state="admin",
            approved_at=timezone.now(),
            approved_by=request.user,
        )
        self.message_user(request, f"Approved {n} chunks")

    def reject_chunks(self, request, queryset):
        n = queryset.update(approval_state="rejected", is_active=False)
        self.message_user(request, f"Rejected {n} chunks")


@admin.register(KnowledgeEmbedding)
class KnowledgeEmbeddingAdmin(admin.ModelAdmin):
    list_display = ("id", "chunk", "model", "dim", "created_at")
    list_filter = ("model", "dim")
    readonly_fields = ("vector", "created_at")


@admin.register(KnowledgeEntity)
class KnowledgeEntityAdmin(admin.ModelAdmin):
    list_display = ("name", "entity_type", "subject", "curated", "canonical_id")
    list_filter = ("entity_type", "subject", "curated")
    search_fields = ("name", "synonyms", "canonical_id")


@admin.register(KnowledgeRelation)
class KnowledgeRelationAdmin(admin.ModelAdmin):
    list_display = ("source_entity", "relation", "target_entity",
                    "weight", "curated")
    list_filter = ("relation", "curated")
    search_fields = ("source_entity__name", "target_entity__name")


@admin.register(IngestionJob)
class IngestionJobAdmin(admin.ModelAdmin):
    list_display = ("id", "connector", "source", "status",
                    "chunks_added", "chunks_updated", "chunks_rejected",
                    "started_at", "finished_at")
    list_filter = ("status", "connector")
    readonly_fields = ("created_at", "finished_at")


@admin.register(GoldenTestCase)
class GoldenTestCaseAdmin(admin.ModelAdmin):
    list_display = ("id", "query", "expected_subject", "is_active", "created_at")
    list_filter = ("is_active", "expected_subject")
    search_fields = ("query", "expected_keywords")


@admin.register(EvalRun)
class EvalRunAdmin(admin.ModelAdmin):
    list_display = ("id", "started_at", "testcases_total",
                    "recall_at_5", "recall_at_10", "mrr",
                    "citation_accuracy")
    readonly_fields = ("started_at", "finished_at")


@admin.register(UserUploadAttestation)
class UserUploadAttestationAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "user", "decision",
                    "rights_attested", "created_at")
    list_filter = ("decision", "rights_attested")
    search_fields = ("title", "source_description")
    actions = ["approve_uploads", "reject_uploads"]

    def approve_uploads(self, request, queryset):
        from django.utils import timezone
        n = queryset.update(
            decision="approved",
            reviewed_at=timezone.now(),
            reviewed_by=request.user,
        )
        self.message_user(request, f"Approved {n} uploads")

    def reject_uploads(self, request, queryset):
        from django.utils import timezone
        n = queryset.update(
            decision="rejected",
            reviewed_at=timezone.now(),
            reviewed_by=request.user,
        )
        self.message_user(request, f"Rejected {n} uploads")