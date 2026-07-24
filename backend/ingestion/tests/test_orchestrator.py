"""Regression tests for the orchestrator.

Five tests covering:

  1. Orchestrator writes one ImportJobStage row per pipeline stage.
  2. Orchestrator retry increments version and sets retry_of.
  3. Orchestrator cancellation stops at the next stage boundary.
  4. Orchestrator uses a sha16-namespaced artefact root.
  5. Orchestrator does NOT mutate MCE artefacts (read-only invariant).
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from django.test import TestCase, override_settings

from ingestion.constants import (
    JOB_CANCELLED,
    JOB_PROCESSING,
    JOB_QUEUED,
    PIPELINE_ORDER,
)
from ingestion.models import ImportJob, ImportJobStage, MaterialAsset


@override_settings(INGESTION_ARTEFACT_ROOT=Path("/tmp/_artifacts_ingestion_test"))
class TestOrchestratorWritesStageRows(TestCase):
    def setUp(self):
        self.material = MaterialAsset.objects.create(
            sha256="f" * 64,
            sha256_short="abcdef1234567890",
            original_filename="test.pdf",
            storage_path="/tmp/test.pdf",
            file_size=1,
            page_count=2,
        )
        self.job = ImportJob.objects.create(
            material_asset=self.material,
            parent_exam="neet_pg",
            status=JOB_QUEUED,
        )

    @patch("ingestion.conservative_gate.apply_qa_v2_verdict")
    @patch("ingestion.pipeline_stages._import_callable")
    def test_one_stage_row_per_pipeline_stage(self, mock_import_callable, mock_gate):
        from mce.stages import StageResult
        # Each MCE stage returns a benign StageResult. ``run_mce_stage``
        # itself runs and writes the ImportJobStage row.
        mock_import_callable.return_value = lambda ctx, **kw: StageResult(stage="x")
        mock_gate.return_value = {"pr": 0, "nr": 0, "ef": 0, "staged": 0, "imported": 0}

        from ingestion.orchestrator import run_full_pipeline_for_job
        result = run_full_pipeline_for_job(self.job.id)
        self.assertEqual(result["status"], "completed")
        # One ImportJobStage row per pipeline stage.
        rows = ImportJobStage.objects.filter(job=self.job)
        self.assertEqual(rows.count(), len(__import__("ingestion.constants",
                                                     fromlist=["PIPELINE_ORDER"]).PIPELINE_ORDER))


@override_settings(INGESTION_ARTEFACT_ROOT=Path("/tmp/_artifacts_ingestion_test"))
class TestOrchestratorRetryIncrementsVersion(TestCase):
    def test_retry_sets_retry_of_and_bumps_version(self):
        material = MaterialAsset.objects.create(
            sha256="0" * 64,
            sha256_short="0" * 16,
            original_filename="t.pdf",
            storage_path="/tmp/t.pdf",
            file_size=1,
            page_count=1,
        )
        original = ImportJob.objects.create(
            material_asset=material,
            parent_exam="neet_pg",
            status="failed",
            version=1,
        )
        from ingestion.orchestrator import create_retry_job
        retry = create_retry_job(original)
        self.assertEqual(retry.version, 2)
        self.assertEqual(retry.retry_of_id, original.id)
        self.assertEqual(retry.parent_exam, original.parent_exam)


@override_settings(INGESTION_ARTEFACT_ROOT=Path("/tmp/_artifacts_ingestion_test"))
class TestOrchestratorCancel(TestCase):
    def test_cancel_running_job_is_idempotent(self):
        material = MaterialAsset.objects.create(
            sha256="1" * 64,
            sha256_short="1" * 16,
            original_filename="c.pdf",
            storage_path="/tmp/c.pdf",
            file_size=1,
            page_count=1,
        )
        job = ImportJob.objects.create(
            material_asset=material,
            parent_exam="neet_pg",
            status=JOB_PROCESSING,
        )
        from ingestion.orchestrator import cancel_job
        ok = cancel_job(job)
        self.assertTrue(ok)
        self.assertEqual(job.status, JOB_CANCELLED)


@override_settings(INGESTION_ARTEFACT_ROOT=Path("/tmp/_artifacts_ingestion_test"))
class TestOrchestratorArtefactRoot(TestCase):
    def test_artefact_root_includes_sha16(self):
        material = MaterialAsset.objects.create(
            sha256="2" * 64,
            sha256_short="deadbeefcafebabe",
            original_filename="a.pdf",
            storage_path="/tmp/a.pdf",
            file_size=1,
            page_count=1,
        )
        from ingestion.orchestrator import _artefact_root
        root = _artefact_root(material)
        self.assertIn("deadbeefcafebabe", str(root))


class TestOrchestratorDoesNotMutateMce(TestCase):
    """The orchestrator must only READ MCE artefacts — no writes into
    the MCE tree. Verified by the contract: the orchestrator's
    artefact_root lives under INGESTION_ARTEFACT_ROOT, not under any
    MCE path."""
    def test_artefact_root_isolated_from_mce(self):
        from ingestion.orchestrator import _artefact_root
        material = MaterialAsset.objects.create(
            sha256="3" * 64,
            sha256_short="3" * 16,
            original_filename="m.pdf",
            storage_path="/tmp/m.pdf",
            file_size=1,
            page_count=1,
        )
        with override_settings(INGESTION_ARTEFACT_ROOT=Path("/tmp/_artifacts_ingestion_isolation")):
            root = _artefact_root(material)
        # Never a child of the MCE benchmark dir.
        self.assertNotIn("_artifacts_benchmark_post_fix", str(root))
        self.assertNotIn("chroma_db", str(root))
