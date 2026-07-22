"""Per-page classifier — digital / scanned / hybrid.

Heuristic decisions are deliberately conservative: when in doubt we tag
the page as `hybrid` and let downstream stages fall back to OCR if the
regex parser finds no question structure.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


# Heuristics — tuned for English medical recall PDFs.
MIN_DIGITAL_TEXT_CHARS = 50       # below this we treat as scanned.
MAX_GARBLED_GLYPH_RATIO = 0.30    # fraction of non-printable / control chars.
HYBRID_TEXT_CHARS = 250           # at this size we accept text but verify structure.


@dataclass
class PageFeatures:
    page_number: int
    text: str
    text_chars: int
    image_count: int
    garbled_ratio: float


def garbled_ratio(text: str) -> float:
    """Fraction of characters that are non-printable / control glyphs."""
    if not text:
        return 0.0
    bad = sum(1 for c in text if ord(c) < 32 and c not in ("\n", "\r", "\t"))
    return bad / max(1, len(text))


def features_for(page_number: int, text: str, image_count: int) -> PageFeatures:
    return PageFeatures(
        page_number=page_number,
        text=text or "",
        text_chars=len(text or ""),
        image_count=image_count,
        garbled_ratio=garbled_ratio(text or ""),
    )


def classify(features: PageFeatures) -> str:
    """Return one of: 'digital', 'scanned', 'hybrid', 'blank'."""
    if features.text_chars == 0 and features.image_count == 0:
        return "blank"
    if features.text_chars < MIN_DIGITAL_TEXT_CHARS and features.image_count > 0:
        return "scanned"
    if features.garbled_ratio > MAX_GARBLED_GLYPH_RATIO:
        return "hybrid"
    if features.text_chars >= HYBRID_TEXT_CHARS:
        return "digital"
    return "hybrid"


def aggregate(pages: Iterable[PageFeatures]) -> dict:
    pages = list(pages)
    by_class: dict[str, int] = {"digital": 0, "scanned": 0, "hybrid": 0, "blank": 0}
    for p in pages:
        by_class[classify(p)] += 1
    total = max(1, sum(by_class.values()))
    return {
        "total_pages": total,
        "pages_digital": by_class["digital"],
        "pages_scanned": by_class["scanned"],
        "pages_hybrid": by_class["hybrid"],
        "pages_blank": by_class["blank"],
        "scanned_ratio": by_class["scanned"] / total,
        "digital_ratio": by_class["digital"] / total,
    }


__all__ = ["PageFeatures", "features_for", "classify", "aggregate"]