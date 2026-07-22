"""Database writer for the recall importer.

`DjangoWriter` translates Phase-1 `ParsedQuestion` + `ImageRecord` objects
into `Question` / `RecallSource` / `QuestionSource` / `QuestionImage` /
`DuplicateCluster` / `DuplicateMember` rows.

Design contract:
- Idempotent: re-running the same source produces the same row set.
- Soft-delete: never hard-deletes. `Question.is_active=False` is the
  rollback handle.
- Append-only provenance: `QuestionSource` rows are never updated.
- Faithful to existing schema: only Phase-2 fields + new models are
  touched. Existing fields default-fill.

Usage:
    writer = DjangoWriter(import_job=<QuestionImportJob instance>)
    for question in parsed_questions:
        writer.write_question(question)
    for image in image_records:
        writer.write_image(image)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Optional

from django.db import transaction
from django.utils import timezone

from questions.models import (
    DuplicateCluster,
    DuplicateMember,
    Question,
    QuestionExtractionItem,
    QuestionImage,
    QuestionImportJob,
    QuestionSource,
    RecallSource,
    Subject,
    Topic,
)
from questions.text_encoding import normalize_text

from . import fingerprints, deduplicator
from .models import ImageRecord, ParsedQuestion

LOG = logging.getLogger(__name__)


@dataclass
class WriterStats:
    questions_created: int = 0
    questions_updated: int = 0
    questions_soft_deleted: int = 0
    images_created: int = 0
    sources_created: int = 0
    question_sources_created: int = 0
    extraction_items_created: int = 0
    duplicate_clusters_created: int = 0


class DjangoWriter:
    """Writes parsed output into the production schema."""

    def __init__(self, import_job: Optional[QuestionImportJob] = None,
                 batch_size: int = 500):
        self.import_job = import_job
        self.batch_size = batch_size
        self.stats = WriterStats()

    # ---------------------------------------------------------------- RecallSource

    @transaction.atomic
    def upsert_recall_source(self, pdf_path: Path, fingerprint,
                             scan_type: str, recall_status: str,
                             page_start: Optional[int] = None,
                             page_end: Optional[int] = None) -> RecallSource:
        """Insert-or-fetch a RecallSource row keyed on (sha256, page_start, page_end)."""
        defaults = {
            "pdf_filename": fingerprint.pdf_filename,
            "pdf_path": fingerprint.pdf_path,
            "pdf_sha256": fingerprint.pdf_sha256,
            "pdf_sha256_short": fingerprint.pdf_sha256_short,
            "pdf_size_bytes": fingerprint.size_bytes,
            "page_count": fingerprint.page_count,
            "scan_type": scan_type,
            "recall_status": recall_status,
            "publisher": (fingerprint.metadata or {}).get("author") or "",
            "pdf_metadata": fingerprint.metadata or {},
            "import_job": self.import_job,
            "is_active": True,
        }
        if page_start is not None:
            defaults["page_start"] = page_start
        if page_end is not None:
            defaults["page_end"] = page_end

        obj, created = RecallSource.objects.get_or_create(
            pdf_sha256=fingerprint.pdf_sha256,
            page_start=page_start,
            page_end=page_end,
            defaults=defaults,
        )
        if created:
            self.stats.sources_created += 1
        return obj

    # ---------------------------------------------------------------- Question

    def write_question(self, q: ParsedQuestion,
                       recall_source: RecallSource,
                       subject: Optional[Subject] = None,
                       topic: Optional[Topic] = None) -> Optional[Question]:
        """Write or update one Question + its QuestionSource bridge row.

        Returns None when the question was sent to the extraction review
        queue (empty stem / missing options).
        """
        text_hash = deduplicator.text_sha256(q.stem or q.stem_raw)

        if not (q.stem or "").strip():
            self._emit_extraction_item(q, recall_source, status="pending",
                                       note="empty stem — admin review")
            return None
        if not q.options:
            self._emit_extraction_item(q, recall_source, status="pending",
                                       note="missing options — admin review")
            return None

        options_text = self._flatten_options(q)
        if len(options_text) < 4:
            # Need at least A/B/C/D
            options_text = (options_text + ["", "", "", ""])[:4]

        correct_answer = self._first_answer_label(q)
        confidence = Decimal(str(round(q.confidence_score, 3))).quantize(Decimal("0.001"))

        defaults = {
            "question_text": normalize_text(q.stem or q.stem_raw),
            "option_a": normalize_text(options_text[0] or ""),
            "option_b": normalize_text(options_text[1] or ""),
            "option_c": normalize_text(options_text[2] or ""),
            "option_d": normalize_text(options_text[3] or ""),
            "correct_answer": correct_answer or "A",
            "year": int(getattr(recall_source, "page_count", 0) or 0) and self._guess_year(recall_source.pdf_filename) or 0,
            "subject": subject or self._default_subject(),
            "topic": topic,
            "difficulty": q.difficulty if q.difficulty in ("easy", "medium", "hard") else "medium",
            "exam_type": "neet_pg",
            "exam_source": "NEET PG (recall)",
            "explanation": normalize_text(q.explanation or ""),
            "concept_tags": list({t for t in (q.subject, q.topic, q.subtopic) if t} or []),
            "recall_status": "recall",
            "question_type": q.question_type or "single_best",
            "clinical_category": q.clinical_category or "clinical",
            "session": "",
            "confidence_score": confidence,
            "ocr_confidence": Decimal(str(round((q.ocr_confidence or 0) * 100, 2))) if q.ocr_confidence else None,
            "extraction_confidence": Decimal(str(round(q.extraction_confidence or 0, 3))).quantize(Decimal("0.001")),
            "is_image_based": q.is_image_based,
            "recall_text_hash": text_hash,
            "needs_review": (q.confidence_score or 0) < 0.70,
            "source": recall_source.pdf_filename,
            "page_number": str(q.page_number) if q.page_number else "",
        }

        with transaction.atomic():
            question, created = Question.objects.update_or_create(
                recall_text_hash=text_hash,
                exam_type="neet_pg",
                defaults=defaults,
            )

            QuestionSource.objects.get_or_create(
                question=question,
                recall_source=recall_source,
                page_number=q.page_number or 0,
                question_number_in_pdf=q.question_number_in_pdf,
                defaults={
                    "original_text": q.raw or "",
                    "extracted_text": q.stem or q.stem_raw or "",
                    "ocr_confidence": defaults["ocr_confidence"],
                    "extraction_confidence": defaults["extraction_confidence"],
                    "import_job_id": str(self.import_job.id) if self.import_job else "",
                },
            )

        if created:
            self.stats.questions_created += 1
        else:
            self.stats.questions_updated += 1

        self._maybe_form_cluster(question, text_hash)
        return question

    # ---------------------------------------------------------------- Images

    def write_image(self, img: ImageRecord,
                    question: Question,
                    recall_source: RecallSource) -> Optional[QuestionImage]:
        """Save an extracted image into QuestionImage.

        Dedup by sha256_short — if an image with the same sha exists,
        we link to the existing one (no duplicate row).
        """
        if not img.sha256_short:
            return None

        existing = QuestionImage.objects.filter(sha256_short=img.sha256_short).first()
        if existing:
            return existing

        qi = QuestionImage.objects.create(
            question=question,
            recall_source=recall_source,
            page_number=img.page_number,
            image_index_in_page=img.image_index_in_page,
            mime=img.mime or "image/png",
            width=img.width or 0,
            height=img.height or 0,
            bytes=img.bytes or 0,
            sha256=img.sha256 or "",
            sha256_short=img.sha256_short,
            phash=img.phash or "",
            dhash=img.dhash or "",
            modality=img.modality or "other",
            modality_subtype=img.modality_subtype or "",
            body_region=img.body_region or "",
            ocr_text=img.ocr_text or "",
            caption=img.caption or "",
            caption_source=img.caption_source or "none",
            ocr_confidence=Decimal(str(round((img.ocr_confidence or 0), 2))) if img.ocr_confidence else None,
            extraction_confidence=Decimal(str(round(img.extraction_confidence or 0, 3))).quantize(Decimal("0.001")),
            has_diagram=img.has_diagram,
            has_table=img.has_table,
            is_watermarked=img.is_watermarked,
            role="illustration",
            is_active=True,
        )
        self.stats.images_created += 1
        return qi

    # ---------------------------------------------------------------- Rollback

    @transaction.atomic
    def rollback_for_job(self) -> int:
        """Soft-delete every Question whose QuestionSource.import_job_id matches."""
        if not self.import_job:
            return 0
        qs = Question.objects.filter(
            recall_sources__import_job_id=str(self.import_job.id),
            is_active=True,
        ).distinct()
        n = qs.update(is_active=False)
        self.stats.questions_soft_deleted += n
        return n

    # ---------------------------------------------------------------- helpers

    def _emit_extraction_item(self, q: ParsedQuestion, source: RecallSource,
                              status: str = "pending", note: str = "") -> None:
        QuestionExtractionItem.objects.create(
            job=self.import_job,
            status=status,
            raw_text=q.raw or "",
            question_text=q.stem or "",
            option_a=q.options[0].text if len(q.options) > 0 else "",
            option_b=q.options[1].text if len(q.options) > 1 else "",
            option_c=q.options[2].text if len(q.options) > 2 else "",
            option_d=q.options[3].text if len(q.options) > 3 else "",
            correct_answer=(q.answer_labels[0] if q.answer_labels else "")[:1] or "",
            explanation=q.explanation or "",
            year=self._guess_year(source.pdf_filename),
            subject=self._find_subject_for_stem(q.stem or ""),
            tags=[t for t in (q.subject, q.topic, q.subtopic) if t],
            review_note=note,
        )
        self.stats.extraction_items_created += 1

    @staticmethod
    def _flatten_options(q: ParsedQuestion) -> list[str]:
        labels = ["A", "B", "C", "D", "E", "F"]
        out: list[str] = [""] * 4
        for opt in q.options:
            if opt.label in labels:
                out[labels.index(opt.label)] = opt.text or ""
        return out

    @staticmethod
    def _first_answer_label(q: ParsedQuestion) -> Optional[str]:
        if q.answer_labels:
            return q.answer_labels[0]
        return None

    @staticmethod
    def _guess_year(filename: str) -> int:
        import re
        m = re.search(r"\b(20\d{2})\b", filename or "")
        return int(m.group(1)) if m else 0

    @staticmethod
    def _default_subject() -> Subject:
        """Return the first Subject in the catalogue — safe default for recall imports
        that haven't been auto-tagged yet."""
        return Subject.objects.first()

    @staticmethod
    def _find_subject_for_stem(stem: str) -> Optional[Subject]:
        """Cheap fallback — first subject whose name appears in the stem."""
        if not stem:
            return None
        text = stem.lower()
        for subj in Subject.objects.all()[:50]:
            if subj.name.lower() in text:
                return subj
        return None

    def _maybe_form_cluster(self, question: Question, text_hash: str) -> None:
        """If another Question already has the same recall_text_hash, form a cluster."""
        existing = (
            Question.objects
            .filter(recall_text_hash=text_hash, exam_type="neet_pg")
            .exclude(id=question.id)
            .order_by("-confidence_score", "created_at")
            .first()
        )
        if not existing:
            return
        canonical = existing if (existing.confidence_score or 0) >= (question.confidence_score or 0) else question
        cluster, _ = DuplicateCluster.objects.get_or_create(
            canonical_question=canonical,
            defaults={"detection_method": "sha", "similarity_threshold": Decimal("1.000")},
        )
        DuplicateMember.objects.get_or_create(
            cluster=cluster,
            question=question,
            defaults={"similarity_score": Decimal("1.000")},
        )
        DuplicateMember.objects.get_or_create(
            cluster=cluster,
            question=existing,
            defaults={"similarity_score": Decimal("1.000")},
        )
        if existing.id != canonical.id:
            existing.is_active = False
            existing.save(update_fields=["is_active"])
            self.stats.questions_soft_deleted += 1
        self.stats.duplicate_clusters_created += 1


__all__ = ["DjangoWriter", "WriterStats"]