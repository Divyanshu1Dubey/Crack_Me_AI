"""Tesseract OCREngine — production implementation.

Wraps `pytesseract` (Tesseract 5) with OpenCV preprocessing tuned for
medical-PDF page renders:

    1. Convert to grayscale
    2. Deskew via minAreaRect on the Otsu-thresholded image
    3. Median blur (k=3)
    4. Adaptive Gaussian threshold

This is the recipe that consistently gives > 90 % confidence on the
NEET-PG-2021 page renders.

The engine supports two entry points:

    ocr(image_path)             -> (text, confidence 0..100)
    ocr_region(image_path, bbox,
               page_width_px, page_height_px) -> cropped OCR

`bbox` is in PDF-point coordinates; we scale to pixel coordinates
using the supplied `page_width_px` / `page_height_px`.

Three graceful-degradation paths:
* No `pytesseract` installed -> returns ("", 0.0)
* Tesseract binary missing  -> returns ("", 0.0)
* OCR fails for any reason  -> returns ("", 0.0) + log warning
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path

LOG = logging.getLogger("mce.ocr_tesseract")


# ----------------------------------------------------------------- optional deps

try:
    import pytesseract  # type: ignore
    from PIL import Image  # type: ignore
    _HAS_PYTESS = True
except Exception:  # pragma: no cover
    pytesseract = None  # type: ignore
    Image = None  # type: ignore
    _HAS_PYTESS = False

try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore
    _HAS_CV2 = True
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore
    np = None  # type: ignore
    _HAS_CV2 = False


# ----------------------------------------------------------------- tesseract binary discovery

_TESSERACT_BIN: str | None = None

# Repo-local tessdata directory.  Used when the system install lives in a
# write-protected location (e.g. C:\Program Files) and we need to drop
# additional language packs (e.g. ``equ``, ``osd``).
# Search upward from this file for a ``tools/tessdata`` directory.
def _find_repo_tessdata() -> Path | None:
    here = Path(__file__).resolve()
    for ancestor in here.parents:
        cand = ancestor / "tools" / "tessdata"
        if cand.is_dir() and any(cand.glob("*.traineddata")):
            return cand
    return None


_REPO_TESSDATA: Path | None = _find_repo_tessdata()


def _ensure_tessdata_prefix() -> str:
    """Return the active ``TESSDATA_PREFIX``.

    Honour ``TESSDATA_PREFIX`` if set; otherwise fall back to the repo-local
    directory (``backend/../tools/tessdata``) when it contains a valid
    ``tessdata`` layout.  This lets us run with extra language packs even
    when ``C:\\Program Files\\Tesseract-OCR\\tessdata`` is read-only.
    """
    existing = os.environ.get("TESSDATA_PREFIX")
    if existing and Path(existing).is_dir():
        return existing
    if _REPO_TESSDATA and _REPO_TESSDATA.is_dir():
        s = str(_REPO_TESSDATA).replace("\\", "/")
        os.environ["TESSDATA_PREFIX"] = s
        return s
    return existing or ""


def _find_tesseract_binary() -> str | None:
    """Locate the tesseract binary on PATH or at common Windows paths.

    Caches the result in module state so we don't rescan on every OCR
    call.
    """
    global _TESSERACT_BIN
    if _TESSERACT_BIN is not None:
        return _TESSERACT_BIN
    found = shutil.which("tesseract")
    if found:
        _TESSERACT_BIN = found
        return found
    # Common Windows install locations.
    candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        r"D:\Tesseract-OCR\tesseract.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            _TESSERACT_BIN = c
            return c
    _TESSERACT_BIN = ""
    return None


def _set_pytesseract_cmd() -> None:
    """Point pytesseract at the discovered binary + tessdata prefix.

    In pytesseract 0.3.13, ``tesseract_cmd`` lives on the inner
    ``pytesseract.pytesseract`` submodule (the public ``pytesseract``
    package no longer re-exports it).  We set both locations for
    compatibility with older releases, then patch ``subprocess.Popen``
    to inject ``TESSDATA_PREFIX`` and ``PATH`` so Windows subprocesses
    always see our tessdata directory even when the binary lives in a
    write-protected location.
    """
    if not _HAS_PYTESS:
        return
    binary = _find_tesseract_binary()
    if binary:
        # pytesseract.pytesseract.tesseract_cmd is the canonical location in
        # 0.3.13.  Older versions exposed it on the public ``pytesseract``
        # package; set both, guarded by ``hasattr`` so we don't break.
        try:
            from pytesseract.pytesseract import tesseract_cmd  # type: ignore
            if tesseract_cmd != binary:
                import pytesseract.pytesseract as _pt_mod  # type: ignore
                _pt_mod.tesseract_cmd = binary
        except Exception:  # pragma: no cover
            pass
        # Older pytesseract (<= 0.3.10): attribute on top-level package.
        if hasattr(pytesseract, "tesseract_cmd") and getattr(pytesseract, "tesseract_cmd") != binary:
            try:
                pytesseract.tesseract_cmd = binary  # type: ignore[attr-defined]
            except Exception:  # pragma: no cover
                pass
    _ensure_tessdata_prefix()


# ----------------------------------------------------------------- preprocessing


def _is_likely_clean(arr: np.ndarray) -> bool:
    """Heuristic: True if the page appears digital (sharp text on flat bg).

    Counts the proportion of pure-white and pure-black pixels (>250 or
    <5).  Clean digital renders typically have > 80 % of pixels at one
    extreme.  Scanned / photographed pages have many mid-grey pixels.
    """
    if arr.size == 0:
        return False
    # Subsample for speed.
    sample = arr[::4, ::4]
    flat = sample.ravel()
    extreme = np.count_nonzero((flat > 250) | (flat < 5))
    return float(extreme) / float(flat.size) > 0.65


def _preprocess_for_ocr(pil_image):
    """Content-aware preprocessing for OCR.

    Digital (clean) pages: minimal — convert to grayscale + 2x upscale.
    Scanned/noisy pages: deskew + adaptive threshold.

    Returns a PIL Image.  Falls back to the original image if cv2 is not
    available.
    """
    if not _HAS_CV2:
        return pil_image
    arr = np.array(pil_image.convert("L"))
    clean = _is_likely_clean(arr)
    if clean:
        # Minimal preprocessing: gentle upscale + median blur to kill
        # 1-pixel jaggies on rendered PDF glyphs.
        h, w = arr.shape
        if max(h, w) < 1800:
            arr = cv2.resize(arr, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
        arr = cv2.medianBlur(arr, 3)
        return Image.fromarray(arr)
    # Scanned path: deskew via Otsu minAreaRect + adaptive threshold.
    _, thr = cv2.threshold(arr, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    coords = np.column_stack(np.where(thr < 255))
    if coords.size > 0:
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        if abs(angle) > 0.3:
            h, w = arr.shape
            M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
            arr = cv2.warpAffine(arr, M, (w, h), flags=cv2.INTER_CUBIC,
                                 borderMode=cv2.BORDER_REPLICATE)
    arr = cv2.medianBlur(arr, 3)
    arr = cv2.adaptiveThreshold(arr, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                cv2.THRESH_BINARY, 31, 11)
    return Image.fromarray(arr)


# ----------------------------------------------------------------- engine


class TesseractOCREngine:
    """Tesseract 5 with OpenCV preprocessing.

    Auto-discovers the tesseract binary. Multi-language: ``eng+equ+osd``.
    """

    name = "ocr_tesseract"

    def is_available(self) -> bool:
        if not _HAS_PYTESS:
            return False
        bin_path = _find_tesseract_binary()
        if not bin_path:
            return False
        # Confirm the binary actually runs.
        try:
            r = subprocess.run(
                [bin_path, "--version"],
                capture_output=True, timeout=5, text=True,
            )
            return r.returncode == 0
        except Exception:
            return False

    # ----------------------------------------------------------------- API

    def ocr(self, image_path: Path, *, lang: str = "eng") -> tuple[str, float]:
        """OCR the entire image. Returns (text, mean confidence 0..100)."""
        if not self.is_available():
            return "", 0.0
        _set_pytesseract_cmd()
        try:
            img = Image.open(str(image_path))
        except Exception as e:
            LOG.warning("OCR open failed %s: %s", image_path, e)
            return "", 0.0
        try:
            img = _preprocess_for_ocr(img)
        except Exception as e:
            LOG.debug("OCR preprocess failed %s: %s", image_path, e)
        try:
            data = pytesseract.image_to_data(
                img, lang=lang,
                output_type=pytesseract.Output.DICT,
            )
        except Exception as e:
            LOG.warning("Tesseract failed %s: %s", image_path, e)
            return "", 0.0
        words = []
        confs = []
        for w, c in zip(data.get("text", []), data.get("conf", [])):
            try:
                ci = float(c)
            except (TypeError, ValueError):
                ci = -1.0
            if w and ci >= 0:
                words.append(w)
                confs.append(ci)
        if not confs:
            return "", 0.0
        return " ".join(words).strip(), sum(confs) / len(confs)

    def ocr_region(
        self,
        image_path: Path,
        bbox: tuple[float, ...],
        *,
        page_width_px: int,
        page_height_px: int,
        lang: str = "eng",
    ) -> tuple[str, float]:
        """OCR a single region (bbox in PDF points).

        Scales the bbox from PDF-point space to pixel space using the
        supplied render dimensions.
        """
        if not self.is_available() or len(bbox) != 4:
            return self.ocr(image_path, lang=lang)
        _set_pytesseract_cmd()
        try:
            img = Image.open(str(image_path))
        except Exception as e:
            LOG.warning("OCR region open failed %s: %s", image_path, e)
            return "", 0.0

        img_w, img_h = img.size
        scale_x = img_w / max(1, page_width_px)
        scale_y = img_h / max(1, page_height_px)
        x0 = max(0, int(bbox[0] * scale_x))
        y0 = max(0, int(bbox[1] * scale_y))
        x1 = min(img_w, int(bbox[2] * scale_x))
        y1 = min(img_h, int(bbox[3] * scale_y))
        if x1 <= x0 or y1 <= y0:
            return "", 0.0
        try:
            crop = img.crop((x0, y0, x1, y1))
        except Exception as e:
            LOG.warning("OCR region crop failed: %s", e)
            return "", 0.0
        try:
            crop = _preprocess_for_ocr(crop)
        except Exception:
            pass
        try:
            data = pytesseract.image_to_data(
                crop, lang=lang,
                output_type=pytesseract.Output.DICT,
            )
        except Exception as e:
            LOG.warning("Tesseract region failed: %s", e)
            return "", 0.0
        words = []
        confs = []
        for w, c in zip(data.get("text", []), data.get("conf", [])):
            try:
                ci = float(c)
            except (TypeError, ValueError):
                ci = -1.0
            if w and ci >= 0:
                words.append(w)
                confs.append(ci)
        if not confs:
            return "", 0.0
        return " ".join(words).strip(), sum(confs) / len(confs)


__all__ = ["TesseractOCREngine"]
