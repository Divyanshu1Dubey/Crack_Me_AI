"""Engine Protocol contracts for the Medical Content Engine.

Every replaceable engine in the MCE pipeline implements one of these
Protocols. The default implementations live alongside:

    engines/layout_heuristic.py   LayoutEngine   (Stage 2)
    engines/ocr_tesseract.py      OCREngine      (Stage 6)
    engines/table_camelot.py      TableEngine    (Stage 4)
    engines/caption_ocr_llm.py    CaptionEngine  (Stage 3)

Swapping engines is a registry lookup (see ``mce/engines/registry.py``);
no stage code changes.

Why Protocols not ABCs:
* Duck-typed — no inheritance required.
* Easy to mock in tests.
* IDE-friendly (Pyright / mypy strict-mode compliant).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


# ----------------------------------------------------------------- shared types


@dataclass
class WordSpan:
    """A single word with its bbox + font metadata (from pdfminer / pdfplumber)."""

    text: str
    bbox: tuple[float, ...]               # (x0, y0, x1, y1) in PDF points
    font_name: str = ""
    font_size: float = 0.0
    font_flags: int = 0                   # bold / italic bitmask (pdfplumber)
    page_number: int = 0


@dataclass
class TextLine:
    """A line of text reconstructed from WordSpans on the same y-band."""

    text: str
    bbox: tuple[float, ...]               # (x0, y0, x1, y1) in PDF points
    spans: list[WordSpan] = field(default_factory=list)
    page_number: int = 0

    @property
    def x0(self) -> float:
        return self.bbox[0]

    @property
    def y0(self) -> float:
        return self.bbox[1]

    @property
    def x1(self) -> float:
        return self.bbox[2]

    @property
    def y1(self) -> float:
        return self.bbox[3]

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0


# ----------------------------------------------------------------- LayoutEngine


@runtime_checkable
class LayoutEngine(Protocol):
    """Detect typed regions on a PDF page.

    Inputs:
        page_number           — 1-indexed
        page_png_path         — file path to the Stage-1 render
        page_width_pt         — page width in PDF points
        page_height_pt        — page height in PDF points
        lines                 — pre-extracted TextLines (pdfminer / pdfplumber)
        images                — list of (image_id, bbox) anchors from Stage 3

    Output:
        A list of dict-shaped regions (so engine JSON can round-trip):
            {"type": str, "bbox": [x0,y0,x1,y1], "confidence": float, "label"?: str}

    The default engine uses heuristic line clustering + font-weight inference.
    """

    name: str

    def detect(
        self,
        *,
        page_number: int,
        page_png_path: Path,
        page_width_pt: float,
        page_height_pt: float,
        lines: list[TextLine],
        images: list[tuple[str, tuple[float, ...]]],
    ) -> list[dict[str, Any]]: ...

    def is_available(self) -> bool: ...


# ----------------------------------------------------------------- OCREngine


@runtime_checkable
class OCREngine(Protocol):
    """Run OCR on an image file or region crop, returning text + confidence."""

    name: str

    def ocr(self, image_path: Path, *, lang: str = "eng") -> tuple[str, float]: ...

    def ocr_region(
        self,
        image_path: Path,
        bbox: tuple[float, ...],
        *,
        page_width_px: int,
        page_height_px: int,
        lang: str = "eng",
    ) -> tuple[str, float]: ...

    def is_available(self) -> bool: ...


# ----------------------------------------------------------------- TableEngine


@runtime_checkable
class TableEngine(Protocol):
    """Detect + extract tables from a page render.

    Returns a list of dict-shaped table blocks:
        {
          "type": "table" | "algorithm" | "flowchart" | "drug_chart",
          "bbox": [x0,y0,x1,y1],
          "cells": [[str, ...], ...],   # rows of cell strings
          "preview_png": str | None,     # path to the cropped preview
          "confidence": float,
        }
    """

    name: str

    def extract(
        self,
        *,
        page_number: int,
        page_png_path: Path,
        page_width_pt: float,
        page_height_pt: float,
        lines: list[TextLine],
    ) -> list[dict[str, Any]]: ...

    def is_available(self) -> bool: ...


# ----------------------------------------------------------------- CaptionEngine


@runtime_checkable
class CaptionEngine(Protocol):
    """Generate captions for extracted images.

    Two-phase: (1) cheap OCR on the image; (2) optional LLM polish using
    the OCR text + a modality hint. Always returns a confidence.
    """

    name: str

    def caption(
        self,
        image_path: Path,
        *,
        modality_hint: str = "other",
        context_text: str = "",
    ) -> tuple[str, float, str]:
        """Return (caption_text, confidence 0..1, source_tag).

        source_tag is one of: "ocr_only", "ocr_plus_llm", "llm_only", "none".
        """
        ...

    def is_available(self) -> bool: ...


__all__ = [
    "WordSpan",
    "TextLine",
    "LayoutEngine",
    "OCREngine",
    "TableEngine",
    "CaptionEngine",
]
