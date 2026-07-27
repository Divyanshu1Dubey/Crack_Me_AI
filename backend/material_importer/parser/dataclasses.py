"""Shared dataclasses returned by the parser layer.

These are intentionally framework-free (no Django imports) so the parser
package can be unit-tested in isolation and reused for non-Django call
sites (e.g. a future CLI consumer).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ParsedImage:
    """An image blob recovered from the source file."""

    filename: str
    raw_bytes: bytes
    mime_type: str = ""
    width: int = 0
    height: int = 0
    source_ref: str = ""
    """Location inside the document (e.g. "section:body, paragraph:42")."""


@dataclass
class ParsedQuestion:
    """One MCQ recovered from a source file."""

    position_index: int
    question_text: str
    option_a: str = ""
    option_b: str = ""
    option_c: str = ""
    option_d: str = ""
    correct_answer: str = ""           # 'A'/'B'/'C'/'D' or '' if unknown
    explanation: str = ""
    marks: int = 1
    negative_marks: float = 0.0
    raw_text: str = ""                 # original slice, for debug/QA
    image_refs: List[str] = field(default_factory=list)
    paragraph_index: int = -1
    """Index of the source paragraph in the document (-1 if unknown)."""
    extra: dict = field(default_factory=dict)
    """Extractor-specific metadata (e.g. paper, year, year of PYQ)."""


@dataclass
class ParsedTheory:
    """One theory/note block from a theory-style document."""

    position_index: int
    heading: str = ""
    subheading: str = ""
    body_text: str = ""
    block_type: str = "paragraph"      # heading|paragraph|list|table|callout|index|image_caption|mixed
    keywords: List[str] = field(default_factory=list)
    raw_text: str = ""
    image_refs: List[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)


@dataclass
class ParsedDocument:
    """The full result of parsing one source file."""

    source_filename: str
    file_format: str                   # docx | pdf | pptx | txt | md | unknown
    detected_type: str                 # mcq_classic | mcq_boxed | mcq_statement | theory | hybrid | unknown
    parser_used: str = ""
    questions: List[ParsedQuestion] = field(default_factory=list)
    theory_blocks: List[ParsedTheory] = field(default_factory=list)
    images: List[ParsedImage] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    duration_ms: int = 0
    meta: dict = field(default_factory=dict)
    """Top-level metadata (title, subject hint, year range, etc.)."""

    def is_empty(self) -> bool:
        return not (self.questions or self.theory_blocks or self.images)

    def counts(self) -> dict:
        return {
            "questions": len(self.questions),
            "theory_blocks": len(self.theory_blocks),
            "images": len(self.images),
            "warnings": len(self.warnings),
            "errors": len(self.errors),
        }
