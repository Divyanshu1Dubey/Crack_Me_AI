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


def _waiting_for_worker(job) -> bool:
    """A job still queued well after creation: no django-q worker picked it up.

    Jobs run only on the django-q cluster (``python manage.py qcluster``);
    without one they stay queued forever. The UI shows this flag instead of
    pretending the job is about to start.
    """
    from datetime import timedelta
    from django.utils import timezone

    return bool(
        job.status == "queued"
        and job.created_at
        and timezone.now() - job.created_at > timedelta(minutes=5)
    )


class _JobDisplayMixin(serializers.Serializer):
    """Readable fields for the job tables.

    ``exam`` is the job's exam code, or — for a job created without one
    (the bulk-ingestion script) — its material's exam hint; ``exam_label``
    is its display name ("INI-CET"), ``material_filename`` the source file.
    """

    exam = serializers.SerializerMethodField()
    exam_label = serializers.SerializerMethodField()
    material_filename = serializers.CharField(
        source="material_asset.original_filename", read_only=True, default="",
    )

    def get_exam(self, obj) -> str:
        from .orchestrator import effective_exam
        return effective_exam(obj)

    def get_exam_label(self, obj) -> str:
        from .constants import EXAM_NAMES
        exam = self.get_exam(obj)
        return EXAM_NAMES.get(exam, exam)


_JOB_DISPLAY_FIELDS = ["exam", "exam_label", "material_filename"]


class ImportJobSerializer(_JobDisplayMixin, serializers.ModelSerializer):
    stages = ImportJobStageSerializer(many=True, read_only=True)
    checkpoints = ImportCheckpointSerializer(many=True, read_only=True)
    waiting_for_worker = serializers.SerializerMethodField()

    def get_waiting_for_worker(self, obj) -> bool:
        return _waiting_for_worker(obj)

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
            "waiting_for_worker",
        ] + _JOB_DISPLAY_FIELDS
        read_only_fields = fields


class ImportJobListSerializer(_JobDisplayMixin, serializers.ModelSerializer):
    """Lightweight version used by /jobs/ (no nested stages/checkpoints)."""

    waiting_for_worker = serializers.SerializerMethodField()

    def get_waiting_for_worker(self, obj) -> bool:
        return _waiting_for_worker(obj)

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
            "waiting_for_worker",
        ] + _JOB_DISPLAY_FIELDS
        read_only_fields = fields


def _live_batch_counts(obj) -> dict:
    """Job counts and status of a BatchRun, computed from its jobs.

    The stored ``total_jobs`` / ``completed_jobs`` / ``failed_jobs`` /
    ``status`` were written once at creation by older code (and by the
    bulk-ingestion script) and never updated, so batches read "running ·
    0 · 0" for ever. Uses the ``n_*`` annotations of BatchRunListView when
    present, else the (prefetched) jobs. Status follows the orchestrator's
    ``_refresh_batch_counters``: a cancelled batch stays cancelled; all jobs
    finished → done (cancelled if every job was cancelled); else running.
    """
    cached = getattr(obj, "_live_counts", None)
    if cached is not None:
        return cached
    from .constants import BATCH_CANCELLED, BATCH_DONE, BATCH_RUNNING

    if getattr(obj, "n_total", None) is not None:
        total, completed = obj.n_total, obj.n_completed
        failed, cancelled = obj.n_failed, obj.n_cancelled
    else:
        statuses = [j.status for j in obj.jobs.all()]
        total = len(statuses)
        completed = sum(1 for s in statuses if s == "completed")
        failed = sum(1 for s in statuses if s in ("failed", "crashed"))
        cancelled = sum(1 for s in statuses if s == "cancelled")
    status = obj.status
    if obj.status != BATCH_CANCELLED and total:
        if completed + failed + cancelled == total:
            status = BATCH_CANCELLED if cancelled == total else BATCH_DONE
        else:
            status = BATCH_RUNNING
    counts = {"total": total, "completed": completed, "failed": failed, "status": status}
    obj._live_counts = counts
    return counts


class _LiveBatchCountsMixin(serializers.Serializer):
    status = serializers.SerializerMethodField()
    total_jobs = serializers.SerializerMethodField()
    completed_jobs = serializers.SerializerMethodField()
    failed_jobs = serializers.SerializerMethodField()

    def get_status(self, obj) -> str:
        return _live_batch_counts(obj)["status"]

    def get_total_jobs(self, obj) -> int:
        return _live_batch_counts(obj)["total"]

    def get_completed_jobs(self, obj) -> int:
        return _live_batch_counts(obj)["completed"]

    def get_failed_jobs(self, obj) -> int:
        return _live_batch_counts(obj)["failed"]


class BatchRunSerializer(_LiveBatchCountsMixin, serializers.ModelSerializer):
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


class BatchRunListSerializer(_LiveBatchCountsMixin, serializers.ModelSerializer):
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
