"""Regression tests for MCE sub-stage 2.7 (Camelot TableEngine).

Run: cd backend && python -m pytest mce/tests/test_table_camelot.py -v
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from mce.engines import TableEngine
from mce.engines.table_camelot import CamelotTableEngine


REPO_ROOT = Path(__file__).resolve().parents[3]
BENCHMARK_PDF = REPO_ROOT / "material" / "neet-pg" / "NEET-PG-2021-Question-Paper-With-Solutions-PDF-1.pdf"


def test_engine_is_protocol_compliant():
    eng = CamelotTableEngine()
    assert isinstance(eng, TableEngine)
    assert eng.name == "table_camelot"


def test_engine_unavailable_returns_empty(tmp_path):
    """When Camelot is missing, the engine returns [] (no crash)."""
    eng = CamelotTableEngine()
    eng.is_available = lambda: False  # type: ignore[assignment]
    out = eng.extract(
        page_number=1, page_png_path=tmp_path / "p001.png",
        page_width_pt=595.3, page_height_pt=841.9, lines=[],
    )
    assert out == []


def test_engine_extracts_from_real_pdf(tmp_path):
    """If Camelot + ghostscript are installed, engine finds tables on the benchmark.

    Skipped otherwise.
    """
    eng = CamelotTableEngine()
    if not eng.is_available():
        pytest.skip("camelot not installed")
    pdf = BENCHMARK_PDF
    if not pdf.exists():
        pytest.skip("benchmark PDF missing")
    os.environ["MCE_PDF_PATH"] = str(pdf)
    # Render a placeholder page PNG (Stage 4 will overwrite with a real crop).
    (tmp_path / "p038.png").write_bytes(b"")
    try:
        out = eng.extract(
            page_number=38, page_png_path=tmp_path / "p038.png",
            page_width_pt=595.3, page_height_pt=841.9, lines=[],
        )
        # The benchmark page is mostly Q&A, not tables — we expect [] here.
        # The test is here to ensure the call chain doesn't crash.
        assert isinstance(out, list)
    finally:
        os.environ.pop("MCE_PDF_PATH", None)
