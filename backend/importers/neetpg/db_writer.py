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

from django.db import IntegrityError, transaction
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
    RemovedQuestion,
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
                 batch_size: int = 500, exam_type: str = "neet_pg"):
        self.import_job = import_job
        self.batch_size = batch_size
        self.exam_type = exam_type
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

        # Honor admin "Remove from bank" tombstones — the canonical stem
        # hash (lowercase + noise-stripped + whitespace-collapsed) matches
        # what `compute_stem_hash` produces in the admin endpoint, so a
        # previously removed question will be silently skipped here.
        if text_hash and RemovedQuestion.objects.filter(
            question_text_hash=text_hash,
        ).exists():
            LOG.info(
                "Skipping NEET PG (recall) Q hash=%s — admin-removed tombstone",
                text_hash[:12],
            )
            return None

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

        # Pull year from (in order): recall_source.pdf_filename (e.g.
        # NEET-PG-2021-...) → recall_source PDF metadata creationDate →
        # 0 (frontend year filter just hides those rows).
        guessed_year = self._guess_year(recall_source.pdf_filename or "")
        if not guessed_year:
            try:
                meta = getattr(recall_source, "pdf_metadata", {}) or {}
                # PyMuPDF dates look like "D:20210315..."; normalise to YYYY.
                import re as _re
                m = _re.search(r"(20\d{2})", str(meta.get("creationDate") or meta.get("modDate") or ""))
                if m:
                    guessed_year = int(m.group(1))
            except Exception:
                guessed_year = 0

        defaults = {
            "question_text": normalize_text(q.stem or q.stem_raw),
            "option_a": normalize_text(options_text[0] or ""),
            "option_b": normalize_text(options_text[1] or ""),
            "option_c": normalize_text(options_text[2] or ""),
            "option_d": normalize_text(options_text[3] or ""),
            "correct_answer": correct_answer or "A",
            "year": guessed_year,
            "subject": subject or self._subject_row_for(q.subject) or self._default_subject(),
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
                exam_type=self.exam_type,
                defaults=defaults,
            )

            try:
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
            except IntegrityError:
                # Mid-PDF re-import can collide on
                # uniq_question_source_page_qno. The question text is already
                # saved (above), so skip the source link rather than abort
                # the entire transaction.
                LOG.warning(
                    "Duplicate QuestionSource for %s p%s q%s — skipping source link",
                    recall_source,
                    q.page_number,
                    q.question_number_in_pdf,
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
        we link to the existing one (no duplicate row).  Also writes
        the raw bytes into ``MEDIA_ROOT/<recall_path>`` so the image
        is served by Django at MEDIA_URL.
        """
        if not img.sha256_short:
            return None

        existing = QuestionImage.objects.filter(sha256_short=img.sha256_short).first()
        if existing:
            return existing

        # Copy the bytes into MEDIA_ROOT so the browser can fetch them.
        # We persist under ``recall_images/<sha16>/<sha16>.<ext>`` — a
        # stable path that dedup against existing rows works against.
        media_rel = None
        if img.file_path:
            try:
                from django.core.files import File
                from django.conf import settings

                src = Path(img.file_path)
                if src.exists():
                    ext = src.suffix.lstrip(".") or "png"
                    rel = Path("recall_images") / img.sha256_short[:2] / f"{img.sha256_short}.{ext}"
                    full = Path(settings.MEDIA_ROOT) / rel
                    full.parent.mkdir(parents=True, exist_ok=True)
                    if not full.exists():
                        with open(src, "rb") as r, open(full, "wb") as w:
                            w.write(r.read())
                    media_rel = str(rel).replace("\\", "/")
            except Exception as e:  # pragma: no cover
                LOG.warning("failed to persist image to MEDIA_ROOT: %s", e)

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
        if media_rel:
            # Use the FileField API so Django stores the relative path.
            # IMPORTANT: delete any previously-attached file before saving,
            # otherwise Django rejects the write with SuspiciousFileOperation
            # when an image with the same relative path already exists on disk.
            from django.core.files import File
            from django.conf import settings

            full = Path(settings.MEDIA_ROOT) / media_rel
            # Idempotency: if an old file is attached, drop it from the
            # underlying storage so re-imports can write the same path again.
            if qi.file:
                try:
                    qi.file.delete(save=False)
                except Exception as e:  # pragma: no cover
                    LOG.warning("failed to drop previous file before resave: %s", e)
            with open(full, "rb") as f:
                qi.file.save(media_rel, File(f), save=True)
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
        # When `self.import_job` is None (CLI one-shots that run without
        # a QuestionImportJob), fall back to a "system" job so the FK is
        # satisfied. Without this the IntegrityError fires when no PDF
        # gets a parent job.
        if self.import_job is None:
            try:
                self.import_job = QuestionImportJob.objects.create(
                    job_type="pdf",
                    status="running",
                    source_filename=source.pdf_filename or "unknown",
                    stored_file_path=source.pdf_path or "",
                    summary={"triggered_via": "_emit_extraction_item fallback"},
                )
            except Exception:
                # If even the fallback fails, swallow it — the import is
                # best-effort and the main Question row is what matters.
                return
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
        out: list[str] = [""] * len(labels)
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

    # Map topic_mapper output strings to Subject rows in the catalogue.
    # Some NEET PG subject names don't exactly match the catalogue
    # (e.g. "General Medicine" → "General Medicine", "OBG" → "Obstetrics &
    # Gynecology", "Forensic Medicine" → "FMT"). This table is the bridge.
    _SUBJECT_NAME_MAP = {
        "anatomy": "Anatomy",
        "physiology": "Physiology",
        "biochemistry": "Biochemistry",
        "pathology": "Pathology",
        "microbiology": "Microbiology",
        "pharmacology": "Pharmacology",
        "forensic medicine": "Forensic Medicine",
        "fmt": "Forensic Medicine",
        "psm": "PSM",
        "preventive & social medicine": "PSM",
        "ophthalmology": "Ophthalmology",
        "ent": "ENT",
        "general medicine": "General Medicine",
        "medicine": "General Medicine",
        "general surgery": "Surgery",
        "surgery": "Surgery",
        "obg": "Obstetrics & Gynecology",
        "obstetrics & gynaecology": "Obstetrics & Gynecology",
        "obstetrics & gynecology": "Obstetrics & Gynecology",
        "paediatrics": "Pediatrics",
        "pediatrics": "Pediatrics",
        "dermatology": "Dermatology",
        "orthopaedics": "Orthopaedics",
        "orthopedics": "Orthopaedics",
        "anaesthesia": "Anaesthesia",
        "anesthesia": "Anaesthesia",
        "radiodiagnosis": "Radiodiagnosis",
        "radiology": "Radiodiagnosis",
        "psychiatry": "Psychiatry",
    }

    @classmethod
    def _subject_row_for(cls, name: Optional[str]) -> Optional[Subject]:
        """Translate a topic_mapper string → Subject row. Cached per process."""
        if not name:
            return None
        norm = name.strip().lower()
        target = cls._SUBJECT_NAME_MAP.get(norm, name.strip())
        if not hasattr(cls, "_SUBJECT_CACHE"):
            cls._SUBJECT_CACHE = {s.name.lower(): s for s in Subject.objects.all()}
        # Try direct name first, then case-insensitive lookup, then catalog match.
        if target.lower() in cls._SUBJECT_CACHE:
            return cls._SUBJECT_CACHE[target.lower()]
        # Final fallback: fuzzy contains-match in catalogue.
        for cat_name, subj in cls._SUBJECT_CACHE.items():
            if target.lower() in cat_name or cat_name in target.lower():
                return subj
        return None

    def _maybe_form_cluster(self, question: Question, text_hash: str) -> None:
        """If another Question already has the same recall_text_hash, form a cluster."""
        existing = (
            Question.objects
            .filter(recall_text_hash=text_hash, exam_type=self.exam_type)
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