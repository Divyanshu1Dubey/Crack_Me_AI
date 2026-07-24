"""Shared types for the Medical Content Engine (MCE).

The platform-wide content pipeline. Every extracted object in the MCE is
described by one of the dataclasses in this file — Question, Asset,
Image, Pearl, Reference, Concept, Chunk — and every one of them carries
a `SourceTrace` so the platform can always answer
"where exactly did this content come from?".
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Optional

# ----------------------------------------------------------------- enums


# Region types emitted by the layout engine.
RegionType = Literal[
    "stem",
    "option",
    "explanation",
    "clinical_pearl",
    "high_yield",
    "mnemonic",
    "reference",
    "table",
    "algorithm",
    "flowchart",
    "drug_chart",
    "caption",
    "image",
    "header",
    "footer",
    "answer_key",
    "footnote",
    "unclassified",
]

# Image role on a Question.
ImageRole = Literal[
    "stem",
    "option",
    "explanation",
    "table",
    "cover",
    "watermark",
    "logo",
    "other",
]

# Image modality.
ImageModality = Literal[
    "radiograph",
    "ct",
    "mri",
    "ultrasound",
    "ecg",
    "echo",
    "fundus",
    "pathology_gross",
    "pathology_micro",
    "dermatology",
    "histology",
    "hematology",
    "blood_smear",
    "embryology",
    "anatomy_diagram",
    "flow_chart",
    "table",
    "drug_chart",
    "clinical_photo",
    "generic",
    "other",
]

# Caption provenance.
CaptionSource = Literal["none", "pdf_text_near_image", "ocr_on_image", "llm", "admin"]

# Pearl type.
PearlType = Literal[
    "clinical_pearl",
    "high_yield",
    "mnemonic",
    "memory_trick",
    "pitfall",
]

# Reference source type.
ReferenceSourceType = Literal["textbook", "journal", "guideline", "official_key", "other"]

# Asset type.
AssetType = Literal["table", "algorithm", "flowchart", "drug_chart", "box"]


# ----------------------------------------------------------------- trace


@dataclass(frozen=True)
class SourceTrace:
    """Immutable provenance attached to every extracted object.

    Frozen so it can be hashed + cached; hashable so it can be used as a
    dict key in dedup clusters.
    """

    pdf_filename: str
    pdf_sha256: str
    pdf_sha256_short: str
    page_number: int                       # 1-indexed
    bbox: tuple[float, ...]                # (x0, y0, x1, y1) in PDF points
    extraction_engine: str                 # "layout_heuristic", "ocr_tesseract", "table_camelot", ...
    confidence: float                      # stage-specific 0.0-1.0
    pipeline_stage: str                    # "stage_2_layout", "stage_3_images", ...
    extracted_at: str                      # ISO 8601 UTC

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    @staticmethod
    def make(
        *,
        pdf_filename: str,
        pdf_sha256: str,
        pdf_sha256_short: str,
        page_number: int,
        bbox: tuple[float, ...] | list[float],
        extraction_engine: str,
        pipeline_stage: str,
        confidence: float,
    ) -> "SourceTrace":
        return SourceTrace(
            pdf_filename=pdf_filename,
            pdf_sha256=pdf_sha256,
            pdf_sha256_short=pdf_sha256_short,
            page_number=page_number,
            bbox=tuple(float(b) for b in bbox),
            extraction_engine=extraction_engine,
            pipeline_stage=pipeline_stage,
            confidence=max(0.0, min(1.0, float(confidence))),
            extracted_at=SourceTrace.now_iso(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "pdf_filename": self.pdf_filename,
            "pdf_sha256": self.pdf_sha256,
            "pdf_sha256_short": self.pdf_sha256_short,
            "page_number": self.page_number,
            "bbox": list(self.bbox),
            "extraction_engine": self.extraction_engine,
            "confidence": self.confidence,
            "pipeline_stage": self.pipeline_stage,
            "extracted_at": self.extracted_at,
        }


# ----------------------------------------------------------------- typed regions


@dataclass
class Region:
    """A typed region detected on a page by Stage 2 / Stage 4 / Stage 6."""

    id: str                                # e.g. "p038.b7"
    type: RegionType
    page_number: int
    bbox: tuple[float, ...]
    text: str = ""
    confidence: float = 1.0
    source_trace: Optional[SourceTrace] = None

    # When type == "option"
    label: Optional[str] = None            # "A" / "B" / ...

    # When type == "image"
    image_id: Optional[str] = None         # points to an ImageRecord

    # When type == "table" / "algorithm" / "flowchart" / "drug_chart"
    asset_id: Optional[str] = None

    # When type == "unclassified"
    candidate_types: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = {
            "id": self.id,
            "type": self.type,
            "page_number": self.page_number,
            "bbox": list(self.bbox),
            "text": self.text,
            "confidence": self.confidence,
        }
        if self.label is not None:
            d["label"] = self.label
        if self.image_id is not None:
            d["image_id"] = self.image_id
        if self.asset_id is not None:
            d["asset_id"] = self.asset_id
        if self.candidate_types:
            d["candidate_types"] = list(self.candidate_types)
        if self.warnings:
            d["warnings"] = list(self.warnings)
        if self.source_trace is not None:
            d["source_trace"] = self.source_trace.to_dict()
        return d


# ----------------------------------------------------------------- image record


@dataclass
class ImageRecord:
    """An extracted image with role + modality + caption + bbox + trace."""

    id: str                                # "p038_img03"
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

    role: ImageRole = "other"
    modality: ImageModality = "other"
    modality_subtype: str = ""
    body_region: str = ""

    ocr_text: str = ""
    caption: str = ""
    caption_source: CaptionSource = "none"
    ocr_confidence: float = 0.0
    extraction_confidence: float = 0.0

    # Spatial anchor — bbox on the source page, in PDF points.
    bbox: tuple[float, ...] = ()
    page_spans: list[tuple[int, tuple[float, ...]]] = field(default_factory=list)
    rotation_deg: int = 0                  # 0 / 90 / 180 / 270 — applied before save

    has_diagram: bool = False
    has_table: bool = False
    is_watermarked: bool = False

    source_trace: Optional[SourceTrace] = None

    def to_dict(self) -> dict[str, Any]:
        # Manual build — `asdict()` would flatten tuples to lists and
        # then we'd have to convert back, so just write it out.
        d: dict[str, Any] = {
            "id": self.id,
            "source_sha16": self.source_sha16,
            "page_number": self.page_number,
            "image_index_in_page": self.image_index_in_page,
            "file_path": self.file_path,
            "mime": self.mime,
            "width": self.width,
            "height": self.height,
            "bytes": self.bytes,
            "sha256": self.sha256,
            "sha256_short": self.sha256_short,
            "phash": self.phash,
            "dhash": self.dhash,
            "role": self.role,
            "modality": self.modality,
            "modality_subtype": self.modality_subtype,
            "body_region": self.body_region,
            "ocr_text": self.ocr_text,
            "caption": self.caption,
            "caption_source": self.caption_source,
            "ocr_confidence": self.ocr_confidence,
            "extraction_confidence": self.extraction_confidence,
            "bbox": list(self.bbox),
            "page_spans": [(p, list(b)) for p, b in self.page_spans],
            "rotation_deg": self.rotation_deg,
            "has_diagram": self.has_diagram,
            "has_table": self.has_table,
            "is_watermarked": self.is_watermarked,
        }
        if self.source_trace is not None:
            d["source_trace"] = self.source_trace.to_dict()
        return d


# ----------------------------------------------------------------- asset record


@dataclass
class AssetRecord:
    """Structured table / algorithm / flowchart / drug chart."""

    id: str                                # "p038_tbl01"
    source_sha16: str
    page_number: int
    asset_type: AssetType
    payload: dict[str, Any]                # cells / steps / nodes — structured
    preview_image: str = ""                # path to the PNG preview
    bbox: tuple[float, ...] = ()
    confidence: float = 0.0
    extraction_engine: str = ""
    source_trace: Optional[SourceTrace] = None

    def to_dict(self) -> dict[str, Any]:
        d = {
            "id": self.id,
            "source_sha16": self.source_sha16,
            "page_number": self.page_number,
            "asset_type": self.asset_type,
            "payload": self.payload,
            "preview_image": self.preview_image,
            "bbox": list(self.bbox),
            "confidence": self.confidence,
            "extraction_engine": self.extraction_engine,
        }
        if self.source_trace is not None:
            d["source_trace"] = self.source_trace.to_dict()
        return d


# ----------------------------------------------------------------- pearl record


@dataclass
class PearlRecord:
    """A clinical pearl / high-yield box / mnemonic / memory trick / pitfall."""

    id: str
    source_sha16: str
    page_number: int
    pearl_type: PearlType
    body: str
    confidence: float = 0.0
    source: Literal["pdf", "llm", "admin"] = "pdf"
    bbox: tuple[float, ...] = ()
    source_trace: Optional[SourceTrace] = None

    def to_dict(self) -> dict[str, Any]:
        d = {
            "id": self.id,
            "source_sha16": self.source_sha16,
            "page_number": self.page_number,
            "pearl_type": self.pearl_type,
            "body": self.body,
            "confidence": self.confidence,
            "source": self.source,
            "bbox": list(self.bbox),
        }
        if self.source_trace is not None:
            d["source_trace"] = self.source_trace.to_dict()
        return d


# ----------------------------------------------------------------- reference record


@dataclass
class ReferenceRecord:
    """A citation extracted from the explanation (Harrison, Robbins, NEET-PG key, etc.)."""

    id: str
    source_sha16: str
    page_number: int
    citation_text: str
    source_type: ReferenceSourceType = "other"
    locator: str = ""
    confidence: float = 0.0
    bbox: tuple[float, ...] = ()
    source_trace: Optional[SourceTrace] = None

    def to_dict(self) -> dict[str, Any]:
        d = {
            "id": self.id,
            "source_sha16": self.source_sha16,
            "page_number": self.page_number,
            "citation_text": self.citation_text,
            "source_type": self.source_type,
            "locator": self.locator,
            "confidence": self.confidence,
            "bbox": list(self.bbox),
        }
        if self.source_trace is not None:
            d["source_trace"] = self.source_trace.to_dict()
        return d


# ----------------------------------------------------------------- question


@dataclass
class ParsedQuestion:
    """One reconstructed question with everything the platform needs to render it."""

    id: str
    source_sha16: str
    page_number: int
    page_numbers: list[int] = field(default_factory=list)   # for multi-page questions
    question_number_in_pdf: Optional[int] = None

    stem: str = ""
    stem_raw: str = ""
    options: list[dict[str, Any]] = field(default_factory=list)   # [{label, text, image_ids, is_correct}]
    answer_labels: list[str] = field(default_factory=list)
    answer_text: Optional[str] = None
    explanation: Optional[str] = None

    # Educational structure (Phase 1.5 §1).
    clinical_pearl: Optional[str] = None
    high_yield_points: list[str] = field(default_factory=list)
    mnemonic: Optional[str] = None
    references: list[ReferenceRecord] = field(default_factory=list)

    # Content refs.
    image_ids: list[str] = field(default_factory=list)
    asset_ids: list[str] = field(default_factory=list)
    pearl_ids: list[str] = field(default_factory=list)
    captions: list[str] = field(default_factory=list)

    # Unclassified blocks attached to this question — never silently dropped.
    unclassified_blocks: list[Region] = field(default_factory=list)

    # Categorisation.
    subject: Optional[str] = None
    topic: Optional[str] = None
    subtopic: Optional[str] = None
    question_type: str = "single_best"   # single_best / multiple_correct / assertion_reason / match / image_based / numerical
    clinical_category: str = "clinical"  # clinical / preclinical / paraclinical
    difficulty: str = "medium"          # easy / medium / hard / expert
    language: str = "en"

    # Confidence (Phase 1.5 §4).
    ocr_confidence: float = 1.0
    layout_confidence: float = 1.0
    image_mapping_confidence: float = 1.0
    question_reconstruction_confidence: float = 1.0

    # Flags.
    is_image_based: bool = False
    needs_review: bool = False
    review_reason: str = ""

    # Bbox of the stem on the page (origin block, not the whole question block).
    bbox: tuple[float, ...] = ()
    source_trace: Optional[SourceTrace] = None

    # Provenance.
    exam_type: str = ""
    exam_source: str = ""
    recall_status: str = "recall"

    raw: str = ""
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = {
            "id": self.id,
            "source_sha16": self.source_sha16,
            "page_number": self.page_number,
            "page_numbers": list(self.page_numbers),
            "question_number_in_pdf": self.question_number_in_pdf,
            "stem": self.stem,
            "stem_raw": self.stem_raw,
            "options": list(self.options),
            "answer_labels": list(self.answer_labels),
            "answer_text": self.answer_text,
            "explanation": self.explanation,
            "clinical_pearl": self.clinical_pearl,
            "high_yield_points": list(self.high_yield_points),
            "mnemonic": self.mnemonic,
            "references": [r.to_dict() for r in self.references],
            "image_ids": list(self.image_ids),
            "asset_ids": list(self.asset_ids),
            "pearl_ids": list(self.pearl_ids),
            "captions": list(self.captions),
            "unclassified_blocks": [b.to_dict() for b in self.unclassified_blocks],
            "subject": self.subject,
            "topic": self.topic,
            "subtopic": self.subtopic,
            "question_type": self.question_type,
            "clinical_category": self.clinical_category,
            "difficulty": self.difficulty,
            "language": self.language,
            "ocr_confidence": self.ocr_confidence,
            "layout_confidence": self.layout_confidence,
            "image_mapping_confidence": self.image_mapping_confidence,
            "question_reconstruction_confidence": self.question_reconstruction_confidence,
            "is_image_based": self.is_image_based,
            "needs_review": self.needs_review,
            "review_reason": self.review_reason,
            "bbox": list(self.bbox),
            "exam_type": self.exam_type,
            "exam_source": self.exam_source,
            "recall_status": self.recall_status,
            "raw": self.raw,
            "notes": list(self.notes),
        }
        if self.source_trace is not None:
            d["source_trace"] = self.source_trace.to_dict()
        return d


# ----------------------------------------------------------------- helpers


def stable_id(prefix: str, parts: list[Any], length: int = 12) -> str:
    """Stable short id from a prefix + arbitrary hashable parts."""
    raw = json.dumps(parts, sort_keys=True, default=str, ensure_ascii=False)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:length]
    return f"{prefix}_{digest}"


__all__ = [
    "RegionType",
    "ImageRole",
    "ImageModality",
    "CaptionSource",
    "PearlType",
    "ReferenceSourceType",
    "AssetType",
    "SourceTrace",
    "Region",
    "ImageRecord",
    "AssetRecord",
    "PearlRecord",
    "ReferenceRecord",
    "ParsedQuestion",
    "stable_id",
]
