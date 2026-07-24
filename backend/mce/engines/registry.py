"""Default engine registry.

Loads the default implementations lazily. Stages call ``get_layout()`` /
``get_ocr()`` / etc. once at startup; tests can override by setting the
module-level ``_overrides`` dict.
"""
from __future__ import annotations

from typing import Optional


_overrides: dict[str, object] = {}


def set_override(name: str, engine: object) -> None:
    """Force a specific engine implementation (used by tests)."""
    _overrides[name] = engine


def clear_overrides() -> None:
    _overrides.clear()


def get_layout():
    from mce.engines.layout_heuristic import HeuristicLayoutEngine
    if "layout" in _overrides:
        return _overrides["layout"]
    return HeuristicLayoutEngine()


def get_ocr():
    from mce.engines.ocr_tesseract import TesseractOCREngine
    if "ocr" in _overrides:
        return _overrides["ocr"]
    return TesseractOCREngine()


def get_table():
    from mce.engines.table_camelot import CamelotTableEngine
    if "table" in _overrides:
        return _overrides["table"]
    return CamelotTableEngine()


def get_caption():
    from mce.engines.caption_ocr_llm import OCRPlusLLMCaptionEngine
    if "caption" in _overrides:
        return _overrides["caption"]
    return OCRPlusLLMCaptionEngine()


__all__ = ["get_layout", "get_ocr", "get_table", "get_caption", "set_override", "clear_overrides"]
