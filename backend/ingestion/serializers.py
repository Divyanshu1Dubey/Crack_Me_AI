"""DRF serializers for the ingestion app.

These are read-mostly — the only write paths are the material upload
and the job creation / retry / cancel endpoints.
"""
from __future__ import annotations

from rest_framework import serializers

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


class MaterialAssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaterialAsset
        fields = [
            "id",
            "sha256",
            "sha256_short",
            "original_filename",
            "storage_path",
            "file_size",
            "page_count",
            "exam_hint",
            "is_active",
            "uploaded_by",
            "uploaded_at",
        ]
        read_only_fields = fields


class ImportJobStageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportJobStage
        fields = [
            "id",
            "stage_name",
            "status",
            "pages_processed",
            "pages_skipped",
            "artefacts_written",
            "warnings",
            "errors",
            "metrics",
            "started_at",
            "completed_at",
        ]
        read_only_fields = fields


class ImportCheckpointSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportCheckpoint
        fields = [
            "id",
            "last_completed_stage",
            "last_processed_page",
            "current_page",
            "token",
            "artifact_root",
            "artifact_sha16",
            "checkpoint_data",
            "version",
            "created_at",
        ]
        read_only_fields = fields


class ImportArtifactSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportArtifact
        fields = [
            "id",
            "sha16_short",
            "kind",
            "path_rel",
            "bytes",
            "sha256",
            "created_at",
        ]
        read_only_fields = fields


class ImportLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportLog
        fields = [
            "id",
            "level",
            "stage_name",
            "message",
            "context",
            "created_at",
        ]
        read_only_fields = fields


class ImportJobSerializer(serializers.ModelSerializer):
    stages = ImportJobStageSerializer(many=True, read_only=True)
    checkpoints = ImportCheckpointSerializer(many=True, read_only=True)

    class Meta:
        model = ImportJob
        fields = [
            "id",
            "material_asset",
            "batch_run",
            "retry_of",
            "version",
            "parent_exam",
            "status",
            "current_stage",
            "current_page",
            "total_pages",
            "progress_pct",
            "qa_v2_production_ready_pct",
            "qa_v2_needs_review_pct",
            "qa_v2_extraction_failure_pct",
            "qa_v2_total_questions",
            "questions_imported",
            "questions_staged_nr",
            "questions_staged_ef",
            "images_imported",
            "summary",
            "error",
            "config",
            "started_at",
            "completed_at",
            "created_by",
            "created_at",
            "updated_at",
            "stages",
            "checkpoints",
        ]
        read_only_fields = fields


class ImportJobListSerializer(serializers.ModelSerializer):
    """Lightweight version used by /jobs/ (no nested stages/checkpoints)."""

    class Meta:
        model = ImportJob
        fields = [
            "id",
            "material_asset",
            "batch_run",
            "retry_of",
            "version",
            "parent_exam",
            "status",
            "current_stage",
            "current_page",
            "total_pages",
            "progress_pct",
            "qa_v2_production_ready_pct",
            "qa_v2_needs_review_pct",
            "qa_v2_extraction_failure_pct",
            "qa_v2_total_questions",
            "questions_imported",
            "questions_staged_nr",
            "questions_staged_ef",
            "started_at",
            "completed_at",
            "created_at",
        ]
        read_only_fields = fields


class BatchRunSerializer(serializers.ModelSerializer):
    jobs = ImportJobListSerializer(many=True, read_only=True)

    class Meta:
        model = BatchRun
        fields = [
            "id",
            "name",
            "status",
            "total_jobs",
            "completed_jobs",
            "failed_jobs",
            "notes",
            "created_by",
            "created_at",
            "updated_at",
            "jobs",
        ]
        read_only_fields = fields


class BatchRunListSerializer(serializers.ModelSerializer):
    class Meta:
        model = BatchRun
        fields = [
            "id",
            "name",
            "status",
            "total_jobs",
            "completed_jobs",
            "failed_jobs",
            "created_at",
        ]
        read_only_fields = fields


class StagedQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = StagedQuestion
        fields = [
            "id",
            "job",
            "material_asset",
            "qa_status",
            "review_status",
            "page_number",
            "question_number_in_pdf",
            "question_payload",
            "failing_axes",
            "failure_reason",
            "failure_log_paths",
            "review_note",
            "retry_count",
            "published_question",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class MaterialUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    exam_hint = serializers.ChoiceField(
        choices=[c[0] for c in __import__("ingestion.constants", fromlist=["EXAM_CHOICES"]).EXAM_CHOICES],
        required=False,
        allow_blank=True,
    )


class CreateJobSerializer(serializers.Serializer):
    material_sha16 = serializers.CharField(max_length=16)
    parent_exam = serializers.ChoiceField(
        choices=[c[0] for c in __import__("ingestion.constants", fromlist=["EXAM_CHOICES"]).EXAM_CHOICES],
    )
    batch_id = serializers.IntegerField(required=False, allow_null=True)
    strategy = serializers.ChoiceField(
        choices=[c[0] for c in __import__("ingestion.constants", fromlist=["STRATEGY_CHOICES"]).STRATEGY_CHOICES],
        required=False,
    )


class CreateBatchSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    material_sha16s = serializers.ListField(child=serializers.CharField(max_length=16))
    parent_exam = serializers.ChoiceField(
        choices=[c[0] for c in __import__("ingestion.constants", fromlist=["EXAM_CHOICES"]).EXAM_CHOICES],
    )
    strategy = serializers.ChoiceField(
        choices=[c[0] for c in __import__("ingestion.constants", fromlist=["STRATEGY_CHOICES"]).STRATEGY_CHOICES],
        required=False,
    )
