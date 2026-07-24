"""OCR + LLM caption engine — filled in later (Phase 4 / sub-stage 2.12).

Stub for now so the registry can be imported during 2.3 smoke tests.
"""
from __future__ import annotations

from pathlib import Path


class OCRPlusLLMCaptionEngine:
    name = "caption_ocr_llm"

    def is_available(self) -> bool:
        # True even without LLM — the engine degrades to OCR-only captions.
        return True

    def caption(self, image_path: Path, *, modality_hint: str = "other",
                context_text: str = ""):  # pragma: no cover - stub
        # Returns (caption_text, confidence, source_tag).
        # Until sub-stage 2.6 wires the real OCR path, we return empty.
        return "", 0.0, "none"
