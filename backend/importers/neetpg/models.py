"""Dataclass definitions for Question, Option, Image, Source.

These are JSON-serialisable dataclasses used by the importer to pass
structured data between stages and to write JSONL output. They are
intentionally separate from any Django model so the importer stays
standalone until phase 2.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class SourceRecord:
    """Identity of a source PDF."""
    pdf_filename: str
    pdf_path: str
    pdf_sha256: str
    pdf_sha256_short: str
    pdf_size_bytes: int
    page_count: int
    is_encrypted: bool = False
    recall_status: str = "recall"  # recall / coaching_compiled / official_compiled
    scan_type: str = "hybrid"      # digital / scanned / hybrid
    publisher: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    import_job_id: Optional[str] = None
    imported_at: Optional[str] = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


@dataclass
class ParsedOption:
    label: str           # A / B / C / D / E / F
    text: str
    is_correct: bool = False
    image_refs: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ParsedQuestion:
    """A single parsed question with options, answer, explanation, image refs."""
    source_sha16: str
    page_number: int
    question_number_in_pdf: Optional[int] = None
    stem: str = ""
    stem_raw: str = ""
    options: list[ParsedOption] = field(default_factory=list)
    answer_labels: list[str] = field(default_factory=list)  # e.g. ["B"]
    answer_text: Optional[str] = None
    explanation: Optional[str] = None
    question_type: str = "single_best"  # single_best / multiple_correct / assertion_reason / match / image_based / numerical
    clinical_category: str = "clinical"  # clinical / preclinical / paraclinical
    difficulty: str = "medium"           # easy / medium / hard / expert
    language: str = "en"
    image_refs: list[dict[str, Any]] = field(default_factory=list)
    subject: Optional[str] = None
    topic: Optional[str] = None
    subtopic: Optional[str] = None
    recall_status: str = "recall"
    ocr_confidence: float = 1.0
    extraction_confidence: float = 1.0
    confidence_score: float = 1.0
    is_image_based: bool = False
    raw: str = ""
    notes: list[str] = field(default_factory=list)
    import_job_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


@dataclass
class ImageRecord:
    """An extracted image with provenance + hashes + OCR + caption."""
    source_sha16: str
    page_number: int
    image_index_in_page: int
    file_path: str
    mime: str = "image/png"
    width: int = 0
    height: int = 0
    bytes: int = 0
    sha256: str = ""
    sha256_short: str = ""
    phash: str = ""
    dhash: str = ""
    modality: str = "other"
    modality_subtype: Optional[str] = None
    body_region: Optional[str] = None
    ocr_text: str = ""
    caption: Optional[str] = None
    caption_source: str = "none"
    ocr_confidence: float = 0.0
    extraction_confidence: float = 0.0
    has_diagram: bool = False
    has_table: bool = False
    is_watermarked: bool = False

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


@dataclass
class QualityIssue:
    source_sha16: str
    page_number: int
    issue_type: str   # empty_stem / missing_options / ambiguous_answer / low_ocr / broken_image / etc.
    severity: str     # warn / error
    message: str
    question_number_in_pdf: Optional[int] = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


__all__ = [
    "SourceRecord",
    "ParsedOption",
    "ParsedQuestion",
    "ImageRecord",
    "QualityIssue",
]
