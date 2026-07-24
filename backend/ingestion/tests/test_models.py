"""Regression tests for the ingestion data model.

Six tests covering:

  1. MaterialAsset is idempotent on sha256
  2. ImportJob state-machine allows queued→processing→completed
  3. ImportJob state-machine rejects queued→completed (skip)
  4. ImportCheckpoint upserts on (job) — only one row per job
  5. StagedQuestion.published_question FK is SET_NULL (UPSC safe)
  6. ImportLog returns newest-first
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from ingestion.constants import (
    JOB_COMPLETED,
    JOB_PROCESSING,
    JOB_QUEUED,
    QA_NEEDS_REVIEW,
    REVIEW_PENDING,
)
from ingestion.exceptions import InvalidJobTransitionError
from ingestion.models import (
    ImportCheckpoint,
    ImportJob,
    ImportLog,
    MaterialAsset,
    StagedQuestion,
)
from ingestion.orchestrator import _transition

User = get_user_model()


class TestMaterialAssetIdempotent(TestCase):
    def test_upload_same_sha_does_not_duplicate(self):
        m = MaterialAsset.objects.create(
            sha256="a" * 64,
            sha256_short="a" * 16,
            original_filename="x.pdf",
            storage_path="/tmp/x.pdf",
            file_size=10,
            page_count=1,
        )
        # Re-create with same sha256 + new defaults — should update.
        m2, created = MaterialAsset.objects.update_or_create(
            sha256="a" * 64,
            defaults={
                "sha256_short": "a" * 16,
                "original_filename": "x.pdf",
                "storage_path": "/tmp/x.pdf",
                "file_size": 99,
                "page_count": 1,
            },
        )
        self.assertFalse(created)
        self.assertEqual(m2.pk, m.pk)
        self.assertEqual(m2.file_size, 99)
        self.assertEqual(MaterialAsset.objects.count(), 1)


class TestImportJobStateMachine(TestCase):
    def setUp(self):
        self.material = MaterialAsset.objects.create(
            sha256="b" * 64,
            sha256_short="b" * 16,
            original_filename="y.pdf",
            storage_path="/tmp/y.pdf",
            file_size=1,
            page_count=1,
        )
        self.job = ImportJob.objects.create(
            material_asset=self.material,
            parent_exam="neet_pg",
            status=JOB_QUEUED,
        )

    def test_queued_processing_completed_is_valid(self):
        _transition(self.job, to_status=JOB_PROCESSING, started_at=None)
        _transition(self.job, to_status=JOB_COMPLETED)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, JOB_COMPLETED)

    def test_queued_to_completed_invalid_skip(self):
        with self.assertRaises(InvalidJobTransitionError):
            _transition(self.job, to_status=JOB_COMPLETED)


class TestCheckpointUnique(TestCase):
    def setUp(self):
        self.material = MaterialAsset.objects.create(
            sha256="c" * 64,
            sha256_short="c" * 16,
            original_filename="z.pdf",
            storage_path="/tmp/z.pdf",
            file_size=1,
            page_count=1,
        )
        self.job = ImportJob.objects.create(
            material_asset=self.material,
            parent_exam="neet_pg",
            status=JOB_PROCESSING,
        )

    def test_two_checkpoints_upsert_to_one_row(self):
        from ingestion.checkpoint import save_checkpoint
        from pathlib import Path

        save_checkpoint(
            job=self.job, material=self.material,
            last_completed_stage="1_render",
            last_processed_page=10, current_page=10,
            artifact_root=Path("/tmp/a"),
            artifact_sha16=self.material.sha256_short,
        )
        save_checkpoint(
            job=self.job, material=self.material,
            last_completed_stage="2_layout",
            last_processed_page=10, current_page=10,
            artifact_root=Path("/tmp/a"),
            artifact_sha16=self.material.sha256_short,
        )
        rows = list(ImportCheckpoint.objects.filter(job=self.job))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].last_completed_stage, "2_layout")


class TestStagedQuestionSetNull(TestCase):
    def test_published_question_fk_is_set_null(self):
        """The published_question FK must be SET_NULL so deletion of a
        MaterialAsset does NOT cascade-delete the Question row."""
        material = MaterialAsset.objects.create(
            sha256="d" * 64,
            sha256_short="d" * 16,
            original_filename="q.pdf",
            storage_path="/tmp/q.pdf",
            file_size=1,
            page_count=1,
        )
        job = ImportJob.objects.create(
            material_asset=material,
            parent_exam="neet_pg",
            status=JOB_QUEUED,
        )
        sq = StagedQuestion.objects.create(
            job=job,
            material_asset=material,
            qa_status=QA_NEEDS_REVIEW,
            review_status=REVIEW_PENDING,
            page_number=1,
            question_number_in_pdf=1,
        )
        # Confirm FK behavior
        fk = StagedQuestion._meta.get_field("published_question")
        self.assertEqual(fk.remote_field.on_delete.__name__, "SET_NULL")


class TestImportLogOrdering(TestCase):
    def test_logs_returned_newest_first(self):
        material = MaterialAsset.objects.create(
            sha256="e" * 64,
            sha256_short="e" * 16,
            original_filename="l.pdf",
            storage_path="/tmp/l.pdf",
            file_size=1,
            page_count=1,
        )
        job = ImportJob.objects.create(
            material_asset=material,
            parent_exam="neet_pg",
            status=JOB_QUEUED,
        )
        ImportLog.objects.create(job=job, level="INFO", message="first")
        ImportLog.objects.create(job=job, level="INFO", message="second")
        ImportLog.objects.create(job=job, level="INFO", message="third")
        logs = list(ImportLog.objects.filter(job=job))
        self.assertEqual(logs[0].message, "third")
        self.assertEqual(logs[1].message, "second")
        self.assertEqual(logs[2].message, "first")
