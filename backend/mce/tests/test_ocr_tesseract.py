"""Regression tests for MCE sub-stage 2.5 (Tesseract OCREngine).

Run: cd backend && python -m pytest mce/tests/test_ocr_tesseract.py -v

The engine is tested in two modes:

* Real mode — requires `pytesseract` + the tesseract binary + `cv2`. When
  unavailable, the engine correctly reports `is_available() == False` and
  OCR returns ("", 0.0). This is the **safety-net path** the design calls
  for so a missing binary never crashes the pipeline.

* Synthetic mode — uses a synthetic PNG with known text and a mocked
  pytesseract so we can verify the engine's preprocessing + post-processing
  pipeline works as expected.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image, ImageDraw, ImageFont

from mce.engines import OCREngine
from mce.engines.ocr_tesseract import (
    TesseractOCREngine,
    _find_tesseract_binary,
)


# ----------------------------------------------------------- availability


def test_engine_is_protocol_compliant():
    eng = TesseractOCREngine()
    assert isinstance(eng, OCREngine)
    assert eng.name == "ocr_tesseract"


def test_engine_availability_check_never_crashes():
    """Even on a machine with no tesseract binary, the engine returns a bool."""
    eng = TesseractOCREngine()
    result = eng.is_available()
    assert isinstance(result, bool)


def test_engine_unavailable_returns_empty_string(tmp_path):
    """When the engine can't run, ocr() returns the documented empty signal."""
    eng = TesseractOCREngine()
    # Force unavailable regardless of installed deps.
    eng.is_available = lambda: False  # type: ignore[assignment]
    img = tmp_path / "blank.png"
    Image.new("RGB", (100, 30), "white").save(img)
    text, conf = eng.ocr(img)
    assert text == ""
    assert conf == 0.0


# ----------------------------------------------------------- synthetic OCR


def _make_synthetic_text_png(tmp_path: Path, text: str = "HELLO WORLD") -> Path:
    """Render a synthetic PNG with the given text in a clean sans font."""
    img = Image.new("RGB", (400, 60), "white")
    drw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 32)
    except Exception:
        font = ImageFont.load_default()
    drw.text((10, 10), text, fill="black", font=font)
    p = tmp_path / "synthetic.png"
    img.save(p)
    return p


def test_engine_ocr_with_mocked_pytesseract(tmp_path):
    """With pytesseract mocked, the engine returns the mock's output verbatim."""
    img = _make_synthetic_text_png(tmp_path, "VITAMIN B12")

    fake_dict = {
        "text": ["VITAMIN", "B12"],
        "conf": ["95.5", "88.2"],
    }

    with patch("mce.engines.ocr_tesseract._HAS_PYTESS", True), \
         patch("mce.engines.ocr_tesseract._find_tesseract_binary", return_value="/fake/tesseract"), \
         patch("mce.engines.ocr_tesseract.pytesseract.image_to_data", return_value=fake_dict), \
         patch.object(TesseractOCREngine, "is_available", return_value=True):
        eng = TesseractOCREngine()
        text, conf = eng.ocr(img)
    assert text == "VITAMIN B12"
    assert abs(conf - 91.85) < 0.1


def test_engine_ocr_region_with_mocked_pytesseract(tmp_path):
    """Region OCR scales the bbox to pixels and runs tesseract on the crop."""
    img = _make_synthetic_text_png(tmp_path, "REGION_TEST")
    fake_dict = {"text": ["REGION"], "conf": ["80.0"]}

    with patch("mce.engines.ocr_tesseract._HAS_PYTESS", True), \
         patch("mce.engines.ocr_tesseract._find_tesseract_binary", return_value="/fake/tesseract"), \
         patch("mce.engines.ocr_tesseract.pytesseract.image_to_data", return_value=fake_dict), \
         patch.object(TesseractOCREngine, "is_available", return_value=True):
        eng = TesseractOCREngine()
        text, conf = eng.ocr_region(
            img,
            bbox=(10.0, 10.0, 300.0, 50.0),
            page_width_px=400,
            page_height_px=60,
        )
    assert text == "REGION"
    assert conf == 80.0


def test_engine_ocr_handles_open_errors_gracefully(tmp_path):
    """A non-existent image file -> empty (text, 0.0) + warning."""
    eng = TesseractOCREngine()
    # Force-pretend available so we exercise the open() error path.
    eng.is_available = lambda: True  # type: ignore[assignment]
    text, conf = eng.ocr(tmp_path / "does_not_exist.png")
    assert text == ""
    assert conf == 0.0


# ----------------------------------------------------------- real OCR (when available)


def test_real_tesseract_when_installed(tmp_path):
    """When pytesseract + binary + cv2 are all present, OCR works on real text.

    Skipped otherwise.
    """
    from mce.engines.ocr_tesseract import _HAS_PYTESS, _HAS_CV2
    if not (_HAS_PYTESS and _HAS_CV2 and _find_tesseract_binary()):
        pytest.skip("tesseract binary / pytesseract / cv2 not available")
    img = _make_synthetic_text_png(tmp_path, "HELLO WORLD")
    eng = TesseractOCREngine()
    text, conf = eng.ocr(img)
    assert text.strip() != ""
    assert conf > 0
    assert any(w.upper() in text.upper() for w in ("HELLO", "WORLD"))
