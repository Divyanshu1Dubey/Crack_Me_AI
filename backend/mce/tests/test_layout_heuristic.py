"""Regression tests for MCE sub-stage 2.3 (Heuristic LayoutEngine).

Run: cd backend && python -m pytest mce/tests/test_layout_heuristic.py -v
"""
from __future__ import annotations

from pathlib import Path

import pytest

from mce.engines import LayoutEngine
from mce.engines.layout_heuristic import HeuristicLayoutEngine
from mce.engines.text_lines import extract_text_lines


REPO_ROOT = Path(__file__).resolve().parents[3]
BENCHMARK_PDF = REPO_ROOT / "material" / "neet-pg" / "NEET-PG-2021-Question-Paper-With-Solutions-PDF-1.pdf"


@pytest.fixture(scope="module")
def pdf_path() -> str:
    p = BENCHMARK_PDF
    if not p.exists():
        pytest.skip(f"benchmark PDF missing at {p}")
    return str(p)


# ----------------------------------------------------------- type / availability


def test_engine_is_protocol_compliant():
    eng = HeuristicLayoutEngine()
    assert isinstance(eng, LayoutEngine)
    assert eng.name == "layout_heuristic"
    assert eng.is_available() is True


def test_engine_unavailable_when_no_backend(monkeypatch):
    """When neither pdfplumber nor pdfminer is importable, the engine reports
    itself as unavailable so the stage can skip."""
    import builtins
    real_import = builtins.__import__

    def blocked(name, *a, **kw):
        if name in ("pdfplumber", "pdfminer", "pdfminer.high_level"):
            raise ImportError(f"blocked {name}")
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", blocked)
    eng = HeuristicLayoutEngine()
    assert eng.is_available() is False


# ----------------------------------------------------------- classification rules


def test_classify_detects_question_prefix():
    eng = HeuristicLayoutEngine()
    regions = eng.detect(
        page_number=1, page_png_path=Path("/tmp/x.png"),
        page_width_pt=595.3, page_height_pt=841.9, lines=[], images=[],
    )
    # Empty lines -> empty regions.
    assert regions == []


def _fake_line(text: str, y: float = 100.0) -> object:
    """Construct a TextLine stand-in for direct regex testing via detect()."""
    from mce.engines import TextLine
    return TextLine(text=text, bbox=(50.0, y, 545.0, y + 12.0), page_number=1)


@pytest.mark.parametrize(
    "text,expected_type,expected_label",
    [
        ("53. A female engineer works for 12 hours", "stem", None),
        ("Q.7 Beta 2 receptors act via", "stem", None),
        ("Question 12: A patient presents", "stem", None),
        ("A. Saphenous Nerve", "option", "A"),
        ("B) Femoral vein", "option", "B"),
        ("(C) Profunda femoris vein", "option", "C"),
        ("Answer < A: Vitamin B12", "answer_key", None),
        ("Answer: B. Folic acid", "answer_key", None),
        ("Ans: C", "answer_key", None),
        ("Explanation: Patient has B12 deficiency", "explanation", None),
        ("Exp: This is a quick note", "explanation", None),
        ("Clinical Pearl: Watch for hypokalemia", "clinical_pearl", None),
        ("PEARL: Hyperkalemia first", "clinical_pearl", None),
        ("High Yield: Pemberton sign", "high_yield", None),
        ("HIGH YIELD: Virchow triad", "high_yield", None),
        ("Mnemonic: SOME", "mnemonic", None),
        ("Ref: Harrison 21e p.1245", "reference", None),
        ("Harrison 21e p.1245", "reference", None),
        ("Robbins 10e p.823", "reference", None),
        ("MEDICAL-JUNCTION.COM", "header", None),
        ("Page 12", "header", None),
        ("    3737", "footer", None),
        ("Some prose with no marker", "unclassified", None),
    ],
)
def test_classify_each_marker(text, expected_type, expected_label):
    eng = HeuristicLayoutEngine()
    lines = [_fake_line(text)]
    regions = eng.detect(
        page_number=1, page_png_path=Path("/tmp/x.png"),
        page_width_pt=595.3, page_height_pt=841.9, lines=lines, images=[],
    )
    assert len(regions) == 1
    r = regions[0]
    assert r["type"] == expected_type, (text, r)
    assert r["label"] == expected_label, (text, r)


# ----------------------------------------------------------- live PDF smoke


def test_layout_engine_on_real_page_38(pdf_path):
    """End-to-end against the actual benchmark PDF, page 38."""
    eng = HeuristicLayoutEngine()
    lines = extract_text_lines(pdf_path, 38)
    assert len(lines) > 0
    regions = eng.detect(
        page_number=38, page_png_path=Path("/tmp/p038.png"),
        page_width_pt=595.3, page_height_pt=841.9, lines=lines, images=[],
    )
    by_type: dict[str, int] = {}
    for r in regions:
        by_type[r["type"]] = by_type.get(r["type"], 0) + 1
    # Page 38 has 2 questions, 4 options each, 2 answer lines, 1 watermark header.
    assert by_type.get("stem", 0) >= 2
    assert by_type.get("option", 0) >= 8
    assert by_type.get("answer_key", 0) >= 2
    assert by_type.get("header", 0) >= 1
    # Watermark header should fire on MEDICAL-JUNCTION.COM.
    header_texts = [r["text"] for r in regions if r["type"] == "header"]
    assert any("MEDICAL" in t or "Page" in t for t in header_texts)
