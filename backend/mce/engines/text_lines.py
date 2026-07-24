"""Char / word / line extraction from PDF pages.

Two backends, used as a fallback chain:

    1. pdfplumber  — word-level bbox + fontname. Modern, well-maintained.
    2. pdfminer.six — line-level fallback when pdfplumber returns nothing
                      (very rare with NEET-PG-2021's digital text layer).

The output is a list of `TextLine` objects (one per visual line) with
per-word `WordSpan` data. Every later engine (LayoutEngine, TableEngine)
consumes these — never raw PDF — so the heuristic logic is clean.
"""
from __future__ import annotations

import logging
from typing import Iterable, Optional

from mce.engines import TextLine, WordSpan


LOG = logging.getLogger("mce.text_lines")


def _try_pdfplumber():
    try:
        import pdfplumber  # type: ignore
        return pdfplumber
    except Exception:  # pragma: no cover - optional dep
        return None


def _try_pdfminer():
    try:
        from pdfminer.high_level import extract_pages  # type: ignore
        from pdfminer.layout import LTTextLineHorizontal  # type: ignore
        return extract_pages, LTTextLineHorizontal
    except Exception:  # pragma: no cover - optional dep
        return None, None


def _words_to_lines(words: Iterable) -> list[TextLine]:
    """Group pdfplumber `words` into TextLines by y-band proximity.

    pdfplumber's ``extract_words()`` gives a flat list of words each with
    (x0, top, x1, bottom). We cluster words whose vertical midpoints are
    within ``y_tolerance`` (≈ 25 % of median font height) on the same
    horizontal band.

    Returns a stable top-to-bottom list (PDF coordinate space, y grows
    downward).
    """
    words = list(words)
    if not words:
        return []

    # Compute a y-tolerance from the median word height.
    heights = sorted((float(w["bottom"]) - float(w["top"])) for w in words)
    median_h = heights[len(heights) // 2] if heights else 10.0
    y_tol = max(2.0, median_h * 0.5)

    # Sort top-to-bottom; tiebreak on x0.
    words.sort(key=lambda w: (float(w["top"]), float(w["x0"])))

    lines: list[list] = []
    for w in words:
        cy = (float(w["top"]) + float(w["bottom"])) / 2.0
        if lines and abs(cy - lines[-1][0]["cy"]) <= y_tol:
            lines[-1].append(w)
        else:
            lines.append([w])
        lines[-1][-1] = {**w, "cy": cy}

    out: list[TextLine] = []
    for ln in lines:
        x0 = min(float(w["x0"]) for w in ln)
        top = min(float(w["top"]) for w in ln)
        x1 = max(float(w["x1"]) for w in ln)
        bottom = max(float(w["bottom"]) for w in ln)
        text = " ".join(str(w["text"]) for w in ln)
        spans = [
            WordSpan(
                text=str(w["text"]),
                bbox=(float(w["x0"]), float(w["top"]), float(w["x1"]), float(w["bottom"])),
                font_name=str(w.get("fontname", "")),
                font_size=float(w.get("size", 0.0) or 0.0),
                page_number=int(w.get("page_number", 0)),
            )
            for w in ln
        ]
        out.append(TextLine(
            text=text, bbox=(x0, top, x1, bottom), spans=spans,
            page_number=int(ln[0].get("page_number", 0)) if ln else 0,
        ))
    return out


def extract_text_lines(pdf_path: str, page_number: int) -> list[TextLine]:
    """Return TextLines for one page (1-indexed).

    Tries pdfplumber first; falls back to pdfminer.six on any failure.
    Returns an empty list if both backends are missing or both fail.
    """
    pdfplumber = _try_pdfplumber()
    if pdfplumber is not None:
        try:
            with pdfplumber.open(pdf_path) as pdf:
                page = pdf.pages[page_number - 1]
                words = page.extract_words(
                    use_text_flow=True, keep_blank_chars=False,
                    extra_attrs=["fontname", "size"],
                )
                for w in words:
                    w["page_number"] = page_number
                return _words_to_lines(words)
        except Exception as e:  # pragma: no cover - filesystem / parsing
            LOG.debug("pdfplumber failed for page %s: %s", page_number, e)

    extract_pages, LTTextLineHorizontal = _try_pdfminer()
    if extract_pages is not None:
        try:
            out: list[TextLine] = []
            pages_iter = extract_pages(pdf_path, page_numbers=[page_number - 1])
            for page_layout in pages_iter:
                for elem in page_layout:
                    if isinstance(elem, LTTextLineHorizontal):
                        spans = [
                            WordSpan(
                                text=ch.get_text().strip(),
                                bbox=(float(ch.x0), float(ch.y0), float(ch.x1), float(ch.y1)),
                                font_name=ch.font[0] if hasattr(ch, "font") and ch.font else "",
                                font_size=float(ch.height) if hasattr(ch, "height") else 0.0,
                                page_number=page_number,
                            )
                            for ch in (elem.__iter__() if hasattr(elem, "__iter__") else [])
                            if ch.get_text().strip()
                        ]
                        text = " ".join(s.text for s in spans)
                        if text.strip():
                            out.append(TextLine(
                                text=text,
                                bbox=(float(elem.x0), float(elem.y0), float(elem.x1), float(elem.y1)),
                                spans=spans, page_number=page_number,
                            ))
            return out
        except Exception as e:  # pragma: no cover - filesystem / parsing
            LOG.debug("pdfminer fallback failed for page %s: %s", page_number, e)

    return []


__all__ = ["extract_text_lines"]
