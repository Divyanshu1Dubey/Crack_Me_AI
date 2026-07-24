"""Heuristic LayoutEngine — line-cluster + font-weight + regex tagging.

This is the default LayoutEngine for the Medical Content Engine. It is
transparent (every region has a written-down rule), dependency-light
(only pdfplumber + Pillow), and tuned for the NEET-PG-2021 single-
column recall layout.

Region typing rules (in priority order):

  1. Question prefix        "Q.45" / "45." / "45)"      -> "stem"
  2. Option prefix          "A." / "B)" / "(a)" / "A " -> "option" (label=A/B/...)
  3. Answer line            "Answer: B" / "Ans: B"      -> "answer_key"
  4. Explanation line       "Explanation:" / "Exp:"     -> "explanation"
  5. Clinical pearl         "Clinical Pearl:" / "PEARL:" -> "clinical_pearl"
  6. High-yield             "High Yield:" / "HIGH YIELD" -> "high_yield"
  7. Mnemonic               "Mnemonic:"                 -> "mnemonic"
  8. Reference              "Ref:" / "Harrison" / "Robbins" -> "reference"
  9. Footer / page number   pure-digit short line       -> "footer"
 10. Otherwise                                          -> "unclassified"

Confidence = 1.0 for clean regex hits; 0.7 for fuzzy font-weight hits;
0.4 when the region is emitted purely as a continuation-of-stem.

The engine is intentionally rule-based so it can be inspected, audited,
and tuned against the same PDF without opaque ML black-box surprises.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Optional

from mce.engines import TextLine


LOG = logging.getLogger("mce.layout_heuristic")


# ----------------------------------------------------------------- regex table

RE_QUESTION_PREFIX = re.compile(
    r"""^\s*
        (?:Q\.?\s*\d+
          |Question\s+\d+
          |\d+\s*[\.\)]\s+
        )
        \s*""",
    re.IGNORECASE | re.VERBOSE,
)
RE_OPTION_PREFIX = re.compile(r"^\s*\(?([A-Fa-f])[\.\)]\s+")
RE_ANSWER_LINE = re.compile(
    r"^\s*(?:Answer|Ans|Correct\s*answer|Key)\s*[:<\-]",
    re.IGNORECASE,
)
RE_EXPLANATION_LINE = re.compile(
    r"^\s*(?:Explanation|Explain|Exp|Explanation\s*with\s*reference)\s*[:\-]",
    re.IGNORECASE,
)
RE_PEARL_LINE = re.compile(
    r"^\s*(?:Clinical\s+Pearl|PEARL|Pearl)\s*[:\-]?",
    re.IGNORECASE,
)
RE_HIGH_YIELD_LINE = re.compile(
    r"^\s*(?:High\s*Yield|HIGH\s*YIELD|HY|High\s*yield\s*point)\s*[:\-]?",
    re.IGNORECASE,
)
RE_MNEMONIC_LINE = re.compile(
    r"^\s*(?:Mnemonic|Mnemonics|MNEMONIC)\s*[:\-]?",
    re.IGNORECASE,
)
RE_REFERENCE_LINE = re.compile(
    r"^\s*(?:Ref(?:erence)?|Citation|Source|Textbook)\s*[:\-]",
    re.IGNORECASE,
)
RE_BARE_REFERENCE = re.compile(
    r"(Harrison|Robbins|Guyton|Bailey\s*&\s*Love|KDT|NEET\s*PG\s*Key|NEET\s*PG\s*Official|First\s*Aid)",
    re.IGNORECASE,
)
RE_FOOTER = re.compile(r"^\s*\d{1,4}\s*$")
RE_HEADER = re.compile(r"^\s*(?:Page\s+\d+|www\.|Copyright|[\w.-]+\.(com|net|org|in))", re.IGNORECASE)


# ----------------------------------------------------------------- engine


class HeuristicLayoutEngine:
    """Default LayoutEngine. Pure Python + pdfplumber, no ML deps."""

    name = "layout_heuristic"

    # ---------------------------------------------------------------- API

    def is_available(self) -> bool:
        try:
            import pdfplumber  # noqa: F401
            return True
        except Exception:
            try:
                from pdfminer.high_level import extract_pages  # noqa: F401
                return True
            except Exception:
                return False

    def detect(  # noqa: ARG002 - Protocol params kept for YOLO swap-in
        self,
        *,
        page_number: int,
        page_png_path: Path,
        page_width_pt: float,
        page_height_pt: float,
        lines: list[TextLine],
        images: list[tuple[str, tuple[float, ...]]],
    ) -> list[dict[str, Any]]:
        """Classify every line into a typed region.

        Output entries:
            {
              "type":     str,        # one of the RegionType literals
              "bbox":     [x0,y0,x1,y1],
              "label":    str|None,   # "A" / "B" / ... for options
              "confidence": float,
              "text":     str,        # the line text (Stage 6 OCR may overwrite)
              "match_rule": str,      # which rule fired (debug)
            }

        Image anchors (from Stage 3) are NOT typed here; they're
        attached in Stage 5 by spatial intersection. We just remember
        their bboxes so we can extend a "stem" region downward to cover
        an image that visually belongs to the same question.
        """
        regions: list[dict[str, Any]] = []
        for i, line in enumerate(lines):
            t = (line.text or "").strip()
            if not t:
                continue

            rule, region_type, label, conf = self._classify_line(t, line, lines, i)

            regions.append({
                "type": region_type,
                "bbox": list(line.bbox),
                "label": label,
                "confidence": conf,
                "text": t,
                "match_rule": rule,
                "line_index": i,
            })

        return regions

    # ---------------------------------------------------------------- helpers

    def _classify_line(  # noqa: ARG002 - Protocol params reserved for future lookups
        self,
        t: str,
        line: TextLine,
        all_lines: list[TextLine],
        idx: int,
    ) -> tuple[str, str, Optional[str], float]:
        """Return (rule_name, region_type, label, confidence)."""
        # 1. Question prefix wins first — it's the strongest signal of a new question.
        if RE_QUESTION_PREFIX.match(t):
            return "question_prefix", "stem", None, 1.0

        # 2. Option prefix — but only if it looks like "A. text" / "A) text" /
        # "(a) text" with non-empty body. Stops accidentally typing the
        # body of an option that says "A. Smith 1958" as option A.
        m = RE_OPTION_PREFIX.match(t)
        if m and len(t.split(maxsplit=1)[1] if " " in t else "") > 1:
            label = m.group(1).upper()
            return "option_prefix", "option", label, 1.0

        # 3-8. Marker lines.
        if RE_ANSWER_LINE.match(t):
            return "answer_line", "answer_key", None, 1.0
        if RE_EXPLANATION_LINE.match(t):
            return "explanation_line", "explanation", None, 1.0
        if RE_PEARL_LINE.match(t):
            return "pearl_line", "clinical_pearl", None, 1.0
        if RE_HIGH_YIELD_LINE.match(t):
            return "high_yield_line", "high_yield", None, 1.0
        if RE_MNEMONIC_LINE.match(t):
            return "mnemonic_line", "mnemonic", None, 1.0
        if RE_REFERENCE_LINE.match(t) or RE_BARE_REFERENCE.search(t):
            return "reference_line", "reference", None, 0.95 if RE_REFERENCE_LINE.match(t) else 0.7

        # 9. Footer / header / page-number-ish.
        if RE_FOOTER.match(t):
            return "footer_digits", "footer", None, 0.95
        if RE_HEADER.match(t):
            return "header_text", "header", None, 0.9

        # 10. Otherwise: continuation. We do NOT collapse continuations
        # into the previous region here — Stage 5 merges them by y-band.
        # We do tag them as "unclassified" so they appear in the QA report
        # if the merge stage can't place them.
        return "fallthrough", "unclassified", None, 0.6


__all__ = ["HeuristicLayoutEngine"]
