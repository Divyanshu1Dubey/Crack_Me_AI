"""Database models for the production ingestion platform (Phase 1).

Eight tables, all under the ``ingestion_`` prefix:

  - MaterialAsset     : one row per uploaded PDF (keyed by sha256)
  - BatchRun          : one row per admin-initiated batch of jobs
  - ImportJob         : one row per (material, attempt) pair
  - ImportJobStage    : one row per (job, stage) execution
  - ImportCheckpoint  : one row per checkpoint save (the resume ledger)
  - ImportArtifact    : pointer rows to on-disk MCE artefacts
  - ImportLog         : structured logs bound to a job
  - StagedQuestion    : NR + EF holding (Phase 2 reads from this; Phase 1 writes here)

No FK to UPSC CMS tables except ``Question`` (nullable + SET_NULL),
which guarantees UPSC schema is untouched when an ingestion row is
deleted.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from .constants import (
    ARTIFACT_KIND_CHOICES,
    BATCH_STATUS_CHOICES,
    EXAM_CHOICES,
    JOB_STATUS_CHOICES,
    LOG_LEVEL_CHOICES,
    PIPELINE_ORDER,
    QA_STATUS_CHOICES,
    REVIEW_STATUS_CHOICES,
    STAGE_CHOICES,
    STAGE_STATUS_CHOICES,
)


def _default_config() -> dict:
    """Conservative-default per-job config (Strategy: auto-PR-only)."""
    return {"strategy": "auto-pr-only", "force": False}


class MaterialAsset(models.Model):
    """An uploaded PDF ready to be processed by the MCE pipeline.

    Idempotent on sha256 — re-uploading the same PDF returns the
    existing row (so retried uploads don't pollute the catalogue).
    """

    sha256 = models.CharField(max_length=64, unique=True)
    sha256_short = models.CharField(max_length=16, db_index=True)
    original_filename = models.CharField(max_length=255)
    storage_path = models.CharField(max_length=600, help_text="absolute path on disk")
    file_size = models.BigIntegerField(default=0)
    page_count = models.IntegerField(default=0)
    exam_hint = models.CharField(max_length=20, choices=EXAM_CHOICES, blank=True)
    meta = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="ingestion_uploaded_materials",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-uploaded_at"]
        indexes = [
            models.Index(fields=["sha256_short"]),
            models.Index(fields=["exam_hint", "uploaded_at"]),
        ]

    def __str__(self) -> str:
        return f"Material[{self.sha256_short}] {self.original_filename}"


class BatchRun(models.Model):
    """A user-initiated batch of one or more import jobs.

    Allows the dashboard to render a single status grid for an entire
    'upload the 6 NEET PG PDFs' operation rather than polling per-job.
    """

    name = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=BATCH_STATUS_CHOICES, default="open")
    total_jobs = models.IntegerField(default=0)
    completed_jobs = models.IntegerField(default=0)
    failed_jobs = models.IntegerField(default=0)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="ingestion_created_batches",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Batch[{self.id}] {self.name} ({self.status})"


class ImportJob(models.Model):
    """One ingestion attempt for one MaterialAsset.

    A retry creates a NEW ImportJob row with ``retry_of`` pointing at
    the previous attempt, and ``version`` incremented. This keeps the
    history immutable and easy to query for the dashboard.
    """

    material_asset = models.ForeignKey(
        MaterialAsset, on_delete=models.PROTECT, related_name="jobs",
    )
    batch_run = models.ForeignKey(
        BatchRun, on_delete=models.SET_NULL, null=True, blank=True, related_name="jobs",
    )
    retry_of = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="retries",
    )
    version = models.IntegerField(default=1)

    parent_exam = models.CharField(max_length=20, choices=EXAM_CHOICES)
    status = models.CharField(max_length=20, choices=JOB_STATUS_CHOICES, default="queued", db_index=True)

    # Pipeline progress
    current_stage = models.CharField(max_length=24, choices=STAGE_CHOICES, blank=True)
    current_page = models.IntegerField(default=0)
    total_pages = models.IntegerField(default=0)
    progress_pct = models.FloatField(default=0.0)

    # QA V2 measured percentages (set after Stage 8). Float 0..100.
    qa_v2_production_ready_pct = models.FloatField(default=0.0)
    qa_v2_needs_review_pct = models.FloatField(default=0.0)
    qa_v2_extraction_failure_pct = models.FloatField(default=0.0)
    qa_v2_total_questions = models.IntegerField(default=0)

    # Counters (cheap-to-render on the dashboard without JSON parsing).
    questions_imported = models.IntegerField(default=0)
    questions_staged_nr = models.IntegerField(default=0)
    questions_staged_ef = models.IntegerField(default=0)
    images_imported = models.IntegerField(default=0)

    summary = models.JSONField(default=dict, blank=True)
    error = models.JSONField(default=dict, blank=True)
    config = models.JSONField(default=_default_config, blank=True)

    # Wall-clock
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="ingestion_created_jobs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["material_asset", "version"]),
            models.Index(fields=["batch_run", "status"]),
            models.Index(fields=["parent_exam", "status"]),
        ]

    def __str__(self) -> str:
        return (
            f"Job[{self.id}] {self.parent_exam} v{self.version} "
            f"({self.status}) {self.material_asset.sha256_short}"
        )


class ImportJobStage(models.Model):
    """Per-stage execution record for one ImportJob.

    One row per (job, stage_name) attempt. A retry of the same job
    that re-runs Stage 5 inserts a NEW ImportJobStage row (the old
    one stays as historical evidence).
    """

    job = models.ForeignKey(ImportJob, on_delete=models.CASCADE, related_name="stages")
    stage_name = models.CharField(max_length=24, choices=STAGE_CHOICES)
    status = models.CharField(max_length=20, choices=STAGE_STATUS_CHOICES, default="running")

    pages_processed = models.IntegerField(default=0)
    pages_skipped = models.IntegerField(default=0)
    artefacts_written = models.IntegerField(default=0)
    warnings = models.JSONField(default=list, blank=True)
    errors = models.JSONField(default=list, blank=True)
    metrics = models.JSONField(default=dict, blank=True)

    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["job_id", "started_at"]
        indexes = [
            models.Index(fields=["job", "stage_name"]),
        ]

    def __str__(self) -> str:
        return f"Stage[{self.job_id}/{self.stage_name}/{self.status}]"


class ImportCheckpoint(models.Model):
    """Crash-safe ledger row that lets the orchestrator resume mid-stage.

    The checkpoint is upserted on every stage boundary (and at
    configurable in-stage sub-boundaries). When the worker restarts
    it reads the latest row, picks up at ``last_completed_stage`` /
    ``last_processed_page`` and continues.

    ``token`` is a 32-char secret that protects against stale writers
    (a worker that crashed mid-write can't have its row clobbered by
    a parallel retried worker).
    """

    job = models.ForeignKey(ImportJob, on_delete=models.CASCADE, related_name="checkpoints")
    material_asset = models.ForeignKey(MaterialAsset, on_delete=models.PROTECT, related_name="checkpoints")
    last_completed_stage = models.CharField(max_length=24, choices=STAGE_CHOICES, blank=True)
    last_processed_page = models.IntegerField(default=0)
    current_page = models.IntegerField(default=0)
    token = models.CharField(max_length=64, default="")
    artifact_root = models.CharField(max_length=600)
    artifact_sha16 = models.CharField(max_length=16)
    checkpoint_data = models.JSONField(default=dict, blank=True)
    version = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["job", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"Checkpoint[{self.job_id}@{self.last_completed_stage}/{self.last_processed_page}]"


class ImportArtifact(models.Model):
    """Pointer row to an on-disk MCE artefact.

    We DO NOT copy artefacts into the database — that would be
    wasteful. The artefact lives at the MCE-managed path; this row
    records the kind + sha for cache invalidation and for the
    dashboard / review UI.
    """

    job = models.ForeignKey(ImportJob, on_delete=models.CASCADE, related_name="artifacts")
    sha16_short = models.CharField(max_length=16, db_index=True)
    kind = models.CharField(max_length=40, choices=ARTIFACT_KIND_CHOICES)
    path_rel = models.CharField(max_length=600, help_text="path relative to artefact_root")
    bytes = models.BigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["job_id", "kind"]
        indexes = [
            models.Index(fields=["job", "kind"]),
        ]

    def __str__(self) -> str:
        return f"Artifact[{self.kind}@{self.sha16_short}]"


class ImportLog(models.Model):
    """Structured log row bound to a job.

    Cheap for the dashboard to render (no need to open files); the
    Python ``logging`` machinery also writes a parallel set of files
    under the artefact_root for grep / debugging.
    """

    job = models.ForeignKey(ImportJob, on_delete=models.CASCADE, related_name="logs")
    level = models.CharField(max_length=10, choices=LOG_LEVEL_CHOICES, default="INFO")
    stage_name = models.CharField(max_length=24, choices=STAGE_CHOICES, blank=True)
    message = models.TextField(blank=True)
    context = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["job", "level"]),
            models.Index(fields=["job", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"Log[{self.job_id}/{self.level}] {self.message[:60]}"


class StagedQuestion(models.Model):
    """A question that did NOT auto-import.

    Two flavours:
      - qa_status='Needs Review', review_status='pending' → Phase 2 UI
      - qa_status='Extraction Failure', review_status='blocked'

    Production Ready questions bypass this table entirely — they go
    straight to the legacy `questions.Question` via the existing
    `importers.neetpg.db_writer.DjangoWriter` which is already
    idempotent on `(recall_text_hash, exam_type)`.

    The FK to `questions.Question` is SET_NULL: deleting a
    MaterialAsset MUST NOT cascade delete a Question (UPSC schema
    must stay untouched).
    """

    job = models.ForeignKey(ImportJob, on_delete=models.CASCADE, related_name="staged_questions")
    material_asset = models.ForeignKey(MaterialAsset, on_delete=models.PROTECT, related_name="staged_questions")
    qa_status = models.CharField(max_length=24, choices=QA_STATUS_CHOICES, db_index=True)
    review_status = models.CharField(max_length=20, choices=REVIEW_STATUS_CHOICES, default="pending", db_index=True)

    page_number = models.IntegerField(default=0)
    question_number_in_pdf = models.IntegerField(default=0)
    question_payload = models.JSONField(default=dict, blank=True, help_text="full ParsedQuestion dict")
    failing_axes = models.JSONField(default=list, blank=True, help_text="list of failing axis names")
    failure_reason = models.TextField(blank=True, help_text="only set for Extraction Failure")
    failure_log_paths = models.JSONField(default=list, blank=True)

    review_note = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)
    published_question = models.ForeignKey(
        "questions.Question",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="staging_records",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["job_id", "page_number", "question_number_in_pdf"]
        indexes = [
            models.Index(fields=["job", "qa_status", "review_status"]),
            models.Index(fields=["material_asset", "qa_status"]),
        ]

    def __str__(self) -> str:
        return (
            f"StagedQ[{self.id}] job={self.job_id} qa={self.qa_status} "
            f"review={self.review_status}"
        )


__all__ = [
    "MaterialAsset",
    "BatchRun",
    "ImportJob",
    "ImportJobStage",
    "ImportCheckpoint",
    "ImportArtifact",
    "ImportLog",
    "StagedQuestion",
    "PIPELINE_ORDER",
]
