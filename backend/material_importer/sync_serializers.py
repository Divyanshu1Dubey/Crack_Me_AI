"""DRF serializers for the Admin Import Center API.

These wrap the staging models (ImportBatch, ImportMaterial, ExtractedQuestion,
ImportAuditLog) so the browser UI can fetch batches, list materials, page
through preview/parsed questions, and approve/reject without ever touching
the ORM directly. All serializers are read-only unless explicitly marked
writable — approvals/deletes go through action methods on the viewset
so we keep an audit log entry per state change.
"""
from __future__ import annotations

from rest_framework import serializers

from .models import (
    ExtractedQuestion,
    ImportAuditLog,
    ImportBatch,
    ImportMaterial,
)


class ImportAuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportAuditLog
        fields = ("id", "level", "code", "message", "details", "created_at")
        read_only_fields = fields


class ImportMaterialSerializer(serializers.ModelSerializer):
    """Per-file status row inside an import batch."""

    parse_warnings_count = serializers.SerializerMethodField()
    parse_errors_count = serializers.SerializerMethodField()

    class Meta:
        model = ImportMaterial
        fields = (
            "id",
            "batch",
            "original_filename",
            "stored_path",
            "file_format",
            "file_size_bytes",
            "file_sha256",
            "detected_type",
            "parse_status",
            "question_count",
            "questions_found",
            "questions_rejected",
            "theory_block_count",
            "image_count",
            "duplicate_count",
            "parser_used",
            "duration_ms",
            "parse_warnings",
            "parse_errors",
            "parse_warnings_count",
            "parse_errors_count",
            "parsed_at",
            "created_at",
        )
        read_only_fields = fields

    def get_parse_warnings_count(self, obj: ImportMaterial) -> int:
        return len(obj.parse_warnings or [])

    def get_parse_errors_count(self, obj: ImportMaterial) -> int:
        return len(obj.parse_errors or [])


class ExtractedQuestionListSerializer(serializers.ModelSerializer):
    """Lightweight row for the review queue table view."""

    subject_name = serializers.CharField(source="subject.name", read_only=True, default="")
    topic_name = serializers.CharField(source="topic.name", read_only=True, default="")
    material_filename = serializers.CharField(source="material.original_filename", read_only=True)
    image_count = serializers.SerializerMethodField()
    needs_review_marker = serializers.SerializerMethodField()

    class Meta:
        model = ExtractedQuestion
        fields = (
            "id",
            "material",
            "material_filename",
            "position_index",
            "question_text",
            "option_a",
            "option_b",
            "option_c",
            "option_d",
            "correct_answer",
            "status",
            "inferred_subject",
            "subject_name",
            "inferred_topic",
            "topic_name",
            "inferred_difficulty",
            "classification_confidence",
            "needs_review_marker",
            "image_count",
            "content_hash",
            "created_at",
        )
        read_only_fields = fields

    def get_image_count(self, obj: ExtractedQuestion) -> int:
        return len(obj.image_refs or [])

    def get_needs_review_marker(self, obj: ExtractedQuestion) -> bool:
        return obj.status == "needs_review"


class ExtractedQuestionDetailSerializer(ExtractedQuestionListSerializer):
    """Full preview row incl. explanation + raw text + review note."""

    class Meta(ExtractedQuestionListSerializer.Meta):
        fields = ExtractedQuestionListSerializer.Meta.fields + (
            "explanation",
            "marks",
            "negative_marks",
            "inferred_bloom_level",
            "classification_meta",
            "raw_text",
            "image_refs",
            "provenance_checksum",
            "duplicate_of",
            "published_question",
            "review_note",
        )
        read_only_fields = fields


class ImportBatchListSerializer(serializers.ModelSerializer):
    """Top-level dashboard card view."""

    materials_count = serializers.SerializerMethodField()
    needs_review_count = serializers.SerializerMethodField()

    class Meta:
        model = ImportBatch
        fields = (
            "id",
            "status",
            "source_label",
            "root_path",
            "total_files",
            "files_processed",
            "files_failed",
            "questions_extracted",
            "questions_found",
            "questions_rejected",
            "theory_blocks_extracted",
            "images_extracted",
            "duplicates_skipped",
            "ai_enrichment_queued",
            "started_at",
            "finished_at",
            "created_at",
            "created_by",
            "materials_count",
            "needs_review_count",
            "summary",
        )
        read_only_fields = fields

    def get_materials_count(self, obj: ImportBatch) -> int:
        return obj.materials.count()

    def get_needs_review_count(self, obj: ImportBatch) -> int:
        return ExtractedQuestion.objects.filter(
            material__batch_id=obj.id, status="needs_review"
        ).count()


class ImportBatchDetailSerializer(ImportBatchListSerializer):
    """Detail includes error_report + audit log tail."""

    recent_audit_logs = serializers.SerializerMethodField()

    class Meta(ImportBatchListSerializer.Meta):
        fields = ImportBatchListSerializer.Meta.fields + (
            "error_report",
            "recent_audit_logs",
        )
        read_only_fields = fields

    def get_recent_audit_logs(self, obj: ImportBatch):
        logs = obj.audit_logs.order_by("-created_at")[:25]
        return ImportAuditLogSerializer(logs, many=True).data


# ----- Writable serializers ------------------------------------------------


class BatchPublishSerializer(serializers.Serializer):
    """Input for POST /api/admin/import/batch/<id>/publish/."""

    max_per_test = serializers.IntegerField(default=100, min_value=1, max_value=1000)
    build_tests = serializers.BooleanField(default=True)
    only_publish = serializers.BooleanField(default=False)


class BatchRollbackSerializer(serializers.Serializer):
    """Input for POST /api/admin/import/batch/<id>/rollback/."""

    delete_published = serializers.BooleanField(default=False)
    confirm = serializers.BooleanField(required=True)


class QuestionDecisionSerializer(serializers.Serializer):
    """Input for POST /api/admin/import/questions/<id>/decision/."""

    decision = serializers.ChoiceField(choices=["approve", "reject", "reset"])
    note = serializers.CharField(required=False, allow_blank=True, default="")


class BulkDecisionSerializer(serializers.Serializer):
    """Input for POST /api/admin/import/questions/bulk-decision/."""

    ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)
    decision = serializers.ChoiceField(choices=["approve", "reject", "reset"])
    note = serializers.CharField(required=False, allow_blank=True, default="")


class MockTestGenerationSerializer(serializers.Serializer):
    """Input for POST /api/admin/import/batch/<id>/generate-mock/."""

    strategy = serializers.ChoiceField(choices=[
        "entire_file", "by_subject", "by_chapter", "by_topic", "by_difficulty",
        "random", "image_based", "grand", "revision", "weekly",
    ])
    question_count = serializers.IntegerField(default=50, min_value=1, max_value=2000)
    difficulty = serializers.ChoiceField(
        choices=["easy", "medium", "hard", "mixed"], default="mixed", required=False
    )
    subject_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    topic_id = serializers.IntegerField(required=False, allow_null=True, default=None)


class AIClassifySerializer(serializers.Serializer):
    """Input for POST /api/admin/import/questions/<id>/classify-ai/."""

    use_ai = serializers.BooleanField(default=True)


class DashboardStatsSerializer(serializers.Serializer):
    """Computed stats for /api/admin/import/dashboard/."""

    total_batches = serializers.IntegerField()
    total_questions_imported = serializers.IntegerField()
    total_questions_published = serializers.IntegerField()
    total_needs_review = serializers.IntegerField()
    duplicate_rate = serializers.FloatField()
    image_questions = serializers.IntegerField()
    subjects_count = serializers.IntegerField()
    topics_count = serializers.IntegerField()
    pending_reviews = serializers.IntegerField()
    recent_uploads = serializers.ListField(child=serializers.DictField())
