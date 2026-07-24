"""Regression tests for the conservative import gate.

Three tests covering:

  1. Production Ready verdict → ``DjangoWriter.write_question`` is
     called and a ``Question`` row is created.
  2. Needs Review verdict → zero Question rows, one ``StagedQuestion``
     row with ``review_status='pending'``.
  3. Extraction Failure verdict → zero Question rows, one
     ``StagedQuestion`` row with ``review_status='blocked'`` and a
     populated ``failure_reason``.

We mock the legacy ``DjangoWriter`` and the artefact-root reader so
the gate runs without PyMuPDF / Tesseract / the real benchmark PDF.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from ingestion.constants import (
    QA_EXTRACTION_FAILURE,
    QA_NEEDS_REVIEW,
    QA_PRODUCTION_READY,
    REVIEW_BLOCKED,
    REVIEW_PENDING,
)
from ingestion.models import ImportJob, MaterialAsset, StagedQuestion


def _write_per_q(artefact_root: Path, rows: list[dict]) -> None:
    p = artefact_root / "08_qa"
    p.mkdir(parents=True, exist_ok=True)
    (p / "per_question_qa.json").write_text(json.dumps(rows), encoding="utf-8")
    (p / "summary.json").write_text(json.dumps({"ok": True}), encoding="utf-8")


@override_settings(INGESTION_ARTEFACT_ROOT=Path("/tmp/_artifacts_gate_test_pr"))
class TestGatePRWritesQuestion(TestCase):
    def setUp(self):
        self.material = MaterialAsset.objects.create(
            sha256="4" * 64,
            sha256_short="4" * 16,
            original_filename="p.pdf",
            storage_path="/tmp/p.pdf",
            file_size=1,
            page_count=1,
        )
        self.job = ImportJob.objects.create(
            material_asset=self.material,
            parent_exam="neet_pg",
            status="processing",
        )
        artefact_root = Path("/tmp/_artifacts_gate_test_pr/4" * 16)
        _write_per_q(artefact_root, [
            {
                "status": QA_PRODUCTION_READY,
                "page_number": 1,
                "question_number_in_pdf": 1,
                "failing_axes": [],
                "payload": {
                    "stem": "Which nerve does the Pen Test evaluate?",
                    "stem_raw": "Pen Test is for which nerve",
                    "options": [
                        {"label": "A", "text": "Median Nerve"},
                        {"label": "B", "text": "Ulnar Nerve"},
                        {"label": "C", "text": "Radial Nerve"},
                        {"label": "D", "text": "Musculocutaneous Nerve"},
                    ],
                    "answer_labels": ["A"],
                    "explanation": "Pen Test assesses the median nerve by sensation over the palmar aspect.",
                    "page_number": 1,
                    "question_number_in_pdf": 1,
                    "confidence_score": 0.95,
                },
            },
        ])
        self.artefact_root = artefact_root

    def test_pr_payload_runs_writer_and_creates_question(self):
        # Use a plain dataclass-like object so the gate can diff
        # .stats.questions_created cleanly (MagicMock attributes return
        # MagicMock on += 1 which breaks integer subtraction).
        class _FakeStats:
            questions_created = 0
            questions_updated = 0

        class _FakeWriter:
            def __init__(self, import_job=None):
                self.stats = _FakeStats()
                self._rs = MagicMock()
            def upsert_recall_source(self, *a, **kw):
                return self._rs
            def write_question(self, pq, rs):
                self.stats.questions_created += 1
                return MagicMock(pk=12345)

        with patch("ingestion.conservative_gate._authorise_writer",
                   return_value=_FakeWriter):
            from ingestion.conservative_gate import apply_qa_v2_verdict
            counts = apply_qa_v2_verdict(job=self.job, artefact_root=self.artefact_root)

        self.assertEqual(counts["pr"], 1)
        self.assertEqual(counts["nr"], 0)
        self.assertEqual(counts["ef"], 0)
        self.assertGreaterEqual(counts["imported"], 1)


@override_settings(INGESTION_ARTEFACT_ROOT=Path("/tmp/_artifacts_gate_test_nr"))
class TestGateNRStagesNoQuestion(TestCase):
    def setUp(self):
        self.material = MaterialAsset.objects.create(
            sha256="5" * 64,
            sha256_short="5" * 16,
            original_filename="n.pdf",
            storage_path="/tmp/n.pdf",
            file_size=1,
            page_count=1,
        )
        self.job = ImportJob.objects.create(
            material_asset=self.material,
            parent_exam="neet_pg",
            status="processing",
        )
        self.artefact_root = Path("/tmp/_artifacts_gate_test_nr/5" * 16)
        _write_per_q(self.artefact_root, [
            {
                "status": QA_NEEDS_REVIEW,
                "page_number": 1,
                "question_number_in_pdf": 1,
                "failing_axes": ["explanation_complete"],
                "payload": {
                    "stem": "Long stem...",
                    "options": [],
                    "answer_labels": [],
                    "explanation": "",
                    "page_number": 1,
                    "question_number_in_pdf": 1,
                    "confidence_score": 0.5,
                },
            },
        ])

    def test_nr_payload_creates_staged_row_no_question(self):
        from ingestion.conservative_gate import apply_qa_v2_verdict
        counts = apply_qa_v2_verdict(job=self.job, artefact_root=self.artefact_root)

        self.assertEqual(counts["pr"], 0)
        self.assertEqual(counts["nr"], 1)
        self.assertEqual(counts["ef"], 0)
        self.assertEqual(counts["imported"], 0)

        sq = StagedQuestion.objects.get(job=self.job)
        self.assertEqual(sq.qa_status, QA_NEEDS_REVIEW)
        self.assertEqual(sq.review_status, REVIEW_PENDING)
        self.assertIn("explanation_complete", sq.failing_axes)


@override_settings(INGESTION_ARTEFACT_ROOT=Path("/tmp/_artifacts_gate_test_ef"))
class TestGateEFBlocksWithDiagnostics(TestCase):
    def setUp(self):
        self.material = MaterialAsset.objects.create(
            sha256="6" * 64,
            sha256_short="6" * 16,
            original_filename="e.pdf",
            storage_path="/tmp/e.pdf",
            file_size=1,
            page_count=1,
        )
        self.job = ImportJob.objects.create(
            material_asset=self.material,
            parent_exam="neet_pg",
            status="processing",
        )
        self.artefact_root = Path("/tmp/_artifacts_gate_test_ef/6" * 16)
        _write_per_q(self.artefact_root, [
            {
                "status": QA_EXTRACTION_FAILURE,
                "page_number": 7,
                "question_number_in_pdf": 2,
                "failing_axes": ["options_complete", "answer_correct",
                                 "explanation_complete"],
                "payload": {
                    "stem": "",
                    "options": [],
                    "answer_labels": [],
                    "explanation": "",
                    "page_number": 7,
                    "question_number_in_pdf": 2,
                    "confidence_score": 0.1,
                },
            },
        ])

    def test_ef_payload_blocks_with_failure_reason(self):
        from ingestion.conservative_gate import apply_qa_v2_verdict
        counts = apply_qa_v2_verdict(job=self.job, artefact_root=self.artefact_root)

        self.assertEqual(counts["pr"], 0)
        self.assertEqual(counts["nr"], 0)
        self.assertEqual(counts["ef"], 1)
        self.assertEqual(counts["imported"], 0)

        sq = StagedQuestion.objects.get(job=self.job)
        self.assertEqual(sq.qa_status, QA_EXTRACTION_FAILURE)
        self.assertEqual(sq.review_status, REVIEW_BLOCKED)
        self.assertIn("Extraction Failure", sq.failure_reason)
        self.assertEqual(len(sq.failure_log_paths), 1)
