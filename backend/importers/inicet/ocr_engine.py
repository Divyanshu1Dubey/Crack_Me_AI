"""Tesseract wrapper with OpenCV preprocessing.

Returns (text, confidence). Falls back to empty string when tesseract
is missing — callers should treat empty + ocr_confidence=0 as "OCR
unavailable" and log a warning.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Tuple

LOG = logging.getLogger(__name__)

try:
    import pytesseract  # type: ignore
    from PIL import Image  # type: ignore
    _HAS_TESSERACT = True
except Exception:  # pragma: no cover
    pytesseract = None  # type: ignore
    Image = None  # type: ignore
    _HAS_TESSERACT = False

try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore
    _HAS_CV2 = True
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore
    np = None  # type: ignore
    _HAS_CV2 = False


def is_available() -> bool:
    return _HAS_TESSERACT


def ocr_image(image_path: Path, lang: str = "eng") -> Tuple[str, float]:
    """OCR an image file; return (text, confidence 0..100)."""
    if not _HAS_TESSERACT:
        return "", 0.0
    try:
        img = Image.open(image_path)
    except Exception as e:  # pragma: no cover - filesystem errors
        LOG.warning("Failed to open image %s: %s", image_path, e)
        return "", 0.0

    if _HAS_CV2:
        try:
            img = _preprocess(img)
        except Exception as e:  # pragma: no cover - cv2 quirk
            LOG.debug("Preprocess failed for %s: %s", image_path, e)

    try:
        data = pytesseract.image_to_data(
            img, lang=lang, output_type=pytesseract.Output.DICT
        )
    except Exception as e:  # pragma: no cover - tesseract binary missing
        LOG.warning("Tesseract failed for %s: %s", image_path, e)
        return "", 0.0

    words = []
    confidences = []
    for w, c in zip(data.get("text", []), data.get("conf", [])):
        try:
            ci = float(c)
        except (TypeError, ValueError):
            ci = -1.0
        if w and ci >= 0:
            words.append(w)
            confidences.append(ci)

    if not confidences:
        return "", 0.0

    text = " ".join(words).strip()
    avg_conf = sum(confidences) / len(confidences)
    return text, avg_conf


def _preprocess(pil_image):
    """Deskew + adaptive threshold. Improves OCR on scanned pages."""
    arr = np.array(pil_image.convert("L"))
    # Deskew via minAreaRect on the thresholded image.
    _, thr = cv2.threshold(arr, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    coords = np.column_stack(np.where(thr < 255))
    if coords.size == 0:
        return pil_image
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    if abs(angle) > 0.5:
        h, w = arr.shape
        M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        arr = cv2.warpAffine(arr, M, (w, h), flags=cv2.INTER_CUBIC,
                             borderMode=cv2.BORDER_REPLICATE)
    arr = cv2.medianBlur(arr, 3)
    return Image.fromarray(arr)


__all__ = ["is_available", "ocr_image"]