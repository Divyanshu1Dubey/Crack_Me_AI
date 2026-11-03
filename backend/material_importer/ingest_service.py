"""Ingest service — glue between parsers and the database.

One entry point: `ingest_path(...)`. It walks a folder, parses every
recognized file, persists staged records, and returns a summary.

The service is intentionally Django-coupled (writes to the DB) but the
parsers it uses are pure dataclasses, so you can test the parsing-side
in isolation.
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import os
from pathlib import Path
from typing import Iterable, List

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .ai_classifier import ClassificationResult, HeuristicClassifier, classify_question
from .duplicate_detector import DuplicateDetector, question_dedup_hash, question_dedup_text
from .models import (
    ExtractedQuestion,
    ExtractedTheory,
    ImportedImage,
    ImportAuditLog,
    ImportBatch,
    ImportMaterial,
)
from .parser import ParserFactory
from .parser.dataclasses import ParsedDocument

log = logging.getLogger(__name__)


def _material_format(path: str) -> str:
    ext = Path(path).suffix.lower().lstrip(".")
    return ext if ext else "unknown"


def _file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# Raster formats we accept from imported documents, keyed by Pillow format.
# Anything else (SVG, WMF/EMF, unknown blobs) is skipped: SVG can carry
# script and the public image proxy would serve it from the API origin.
_RASTER_FORMATS: dict[str, tuple[str, str]] = {
    "PNG": ("image/png", "png"),
    "JPEG": ("image/jpeg", "jpg"),
    "GIF": ("image/gif", "gif"),
    "WEBP": ("image/webp", "webp"),
}


def _sniff_raster(img_bytes: bytes) -> tuple[str, str] | None:
    """Return (mime, ext) when Pillow confirms the bytes are an allowed raster image."""
    try:
        from PIL import Image
        with Image.open(io.BytesIO(img_bytes)) as im:
            fmt = (im.format or "").upper()
            im.verify()
    except Exception:
        return None
    return _RASTER_FORMATS.get(fmt)


def _store_image(material: ImportMaterial, idx: int, img_bytes: bytes, mime: str, original_filename: str):
    """Save an extracted raster image under MEDIA_ROOT/imported/<batch>/<material>/<idx>.<ext>.

    Returns ``(storage_name, public_url, mime)`` or ``None`` when the bytes
    are not a verified PNG/JPEG/GIF/WEBP image (the claimed ``mime`` from
    the document is not trusted). ``storage_name`` is what
    ``ImportedImage.stored_path`` must hold so publishing can read the file
    back through the storage backend.
    """
    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage

    sniffed = _sniff_raster(img_bytes)
    if sniffed is None:
        return None
    real_mime, ext = sniffed
    rel = f"imported/batch_{material.batch_id}/material_{material.id}/img_{idx:03d}.{ext}"
    saved = default_storage.save(rel, ContentFile(img_bytes))
    return saved, default_storage.url(saved), real_mime


def _seed_existing_dedup(primed: DuplicateDetector) -> None:
    """Prime the detector with hashes + shingles of every existing Question.

    Tries to load a previously-serialized on-disk index first (see
    `DEDUP_CACHE_PATH`); if absent or stale (Question count changed), falls
    back to a full DB scan and writes the new index to disk. Either path
    is wrapped in try/except so a cache failure (disk full, permissions,
    file corrupted) degrades gracefully to the full-scan path — never
    blocks an ingestion.
    """
    from questions.models import Question
    from .duplicate_detector import _shingles

    cache_path = Path(getattr(settings, "MEDIA_ROOT", "/tmp")) / "_cache" / "dedup_index.json"
    fingerprint = None
    population = 0
    rows: list[tuple[str, str]] = []

    # P19 — cache schema version. Bump when the on-disk format changes; the
    # cached file is silently discarded if the version doesn't match.
    # "2": the key covers the stem AND the (sorted) options, so distinct
    # questions sharing a generic stem ("Which of the following is not
    # true?") are no longer collapsed into one.
    CACHE_SCHEMA_VERSION = "2"

    try:
        population = Question.objects.count()
        # Cheap fingerprint: count + latest pk id, so any row add/remove
        # invalidates the cache.
        max_id = (
            Question.objects.order_by("-pk").values_list("pk", flat=True).first() or 0
        )
        fingerprint = f"{population}:{max_id}"
        if cache_path.exists():
            with cache_path.open(encoding="utf-8") as f:
                payload = json.loads(f.read())
            if (
                payload.get("schema_version") == CACHE_SCHEMA_VERSION
                and payload.get("fingerprint") == fingerprint
            ):
                rows = [(h, t) for h, t in payload.get("rows", []) if t]
    except Exception:
        # Cache I/O failures are non-fatal. Reset and rebuild.
        cache_path = None
        rows = []

    if not rows:
        # Full-scan fallback. Slow but always correct.
        qs = (
            Question.objects.all()
            .only("question_text", "option_a", "option_b", "option_c", "option_d")
            .iterator(chunk_size=500)
        )
        for q in qs:
            options = [q.option_a, q.option_b, q.option_c, q.option_d]
            norm = question_dedup_text(q.question_text, options)
            if not norm:
                continue
            h = question_dedup_hash(q.question_text, options)
            primed._seen_hashes[h] = h
            sh = _shingles(norm)
            primed._seen_shingles[h] = sh
            for s in sh:
                primed._index[s].add(h)
            rows.append((h, norm))

        # Write the new index to disk (best effort).
        try:
            if cache_path is not None:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                with cache_path.open("w", encoding="utf-8") as f:
                    json.dump({
                        "schema_version": CACHE_SCHEMA_VERSION,
                        "fingerprint": fingerprint or "",
                        "rows": rows,
                    }, f)
        except Exception:
            pass
    else:
        for h, t in rows:
            primed._seen_hashes[h] = h
            sh = _shingles(t)
            primed._seen_shingles[h] = sh
            for s in sh:
                primed._index[s].add(h)


# Canonical subject-name aliases. Module-level (static, no DB call).
# Adding a new exam-specific alias here propagates to all importers.
_SUBJECT_ALIASES: dict[str, str] = {
    "medicine": "Medicine",
    "surgery": "Surgery",
    "obgy": "Obstetrics & Gynaecology",
    "obstetrics": "Obstetrics & Gynaecology",
    "obstetrics & gynaecology": "Obstetrics & Gynaecology",
    "gyne": "Obstetrics & Gynaecology",
    "gynae": "Obstetrics & Gynaecology",
    "gynaecology": "Obstetrics & Gynaecology",
    "pediatrics": "Pediatrics",
    "paediatrics": "Pediatrics",
    "psm": "Preventive & Social Medicine",
    "preventive": "Preventive & Social Medicine",
    "preventive & social medicine": "Preventive & Social Medicine",
    "community medicine": "Preventive & Social Medicine",
    "orthopaedics": "Orthopaedics",
    "orthopedics": "Orthopaedics",
    "ortho": "Orthopaedics",
    "anesthesia": "Anaesthesia",
    "anaesthesia": "Anaesthesia",
    "dermatology": "Dermatology",
    "derma": "Dermatology",
    "psychiatry": "Psychiatry",
    "ophthalmology": "Ophthalmology",
    "ent": "ENT",
}


def _resolve_subject_alias(n: str) -> str:
    """Lower-case fuzzy alias → canonical subject name. Returns input unchanged
    if no alias matches."""
    return _SUBJECT_ALIASES.get((n or "").strip().lower(), (n or "").strip())


def _resolve_subject(name: str):
    """Find a Subject by name (case-insensitive). Returns None if missing.

    Tries (in order): alias → canonical Subject.name, then the raw name as-is.
    Uses a single `iexact` query — no per-call table scan.
    """
    if not name:
        return None
    from questions.models import Subject
    canonical = _resolve_subject_alias(name)
    subj = Subject.objects.filter(name__iexact=canonical).first()
    if subj:
        return subj
    if canonical != name:
        # Final fallback: try the raw lowercase form too.
        return Subject.objects.filter(name__iexact=name.strip()).first()
    return None


def _resolve_topic(subject, topic_name: str):
    if not subject or not topic_name:
        return None
    from questions.models import Topic
    return Topic.objects.filter(subject=subject, name__iexact=topic_name).first()


def _persist_parsed_document(
    material: ImportMaterial,
    parsed: ParsedDocument,
    dedup: DuplicateDetector,
    use_ai: bool,
) -> dict:
    """Persist the parsed result into ExtractedQuestion / ExtractedTheory / ImportedImage."""
    summary = {
        "questions_saved": 0,
        "questions_rejected": 0,
        "questions_deduplicated": 0,
        "duplicates_staged": 0,
        "theory_saved": 0,
        "images_saved": 0,
        "images_duplicate": 0,
        "images_rejected": 0,
    }

    # ----- Images ----------------------------------------------------------
    image_rows: list[ImportedImage] = []
    seen_image_hashes: set[str] = set()
    for idx, img in enumerate(parsed.images):
        if not img.raw_bytes:
            continue
        try:
            sha = hashlib.sha256(img.raw_bytes).hexdigest()
        except Exception:
            sha = ""
        if not sha or sha in seen_image_hashes:
            summary["images_duplicate"] += 1
            continue
        seen_image_hashes.add(sha)
        try:
            stored = _store_image(material, idx, img.raw_bytes, img.mime_type, img.filename)
        except Exception as exc:
            log.warning("Failed to store image %s: %s", img.filename, exc)
            continue
        if stored is None:
            # Not a verified PNG/JPEG/GIF/WEBP (e.g. SVG, WMF/EMF): never stored.
            summary["images_rejected"] += 1
            log.info("Skipping non-raster image %s (%s)", img.filename, img.mime_type)
            continue
        storage_name, url, real_mime = stored
        image_rows.append(ImportedImage(
            material=material,
            original_filename=img.filename,
            stored_path=storage_name,
            public_url=url,
            mime_type=real_mime,
            width=img.width,
            height=img.height,
            size_bytes=len(img.raw_bytes),
            sha256=sha,
            ocr_status="skipped",
        ))
    if image_rows:
        ImportedImage.objects.bulk_create(image_rows, batch_size=100)
        summary["images_saved"] = len(image_rows)

    # Map filenames → ImportedImage PKs so per-question linking can use them later.
    filename_to_pk: dict[str, int] = {}
    for ir in ImportedImage.objects.filter(material=material).values_list("original_filename", "pk"):
        filename_to_pk[ir[0]] = ir[1]

    # ----- Questions -------------------------------------------------------
    classifier = HeuristicClassifier()
    pending_rows: list[ExtractedQuestion] = []
    material_hashes: set[str] = set()
    for q in parsed.questions:
        if not (q.question_text and (q.option_a or q.option_b or q.option_c or q.option_d)):
            summary["questions_rejected"] += 1
            continue
        dup = dedup.check(q)
        duplicate_meta: dict = {}
        if dup.is_duplicate:
            summary["questions_deduplicated"] += 1
            if dup.content_hash in material_hashes:
                # The same question twice in this file: nothing new to review.
                continue
            # Stage it as a visible "duplicate" row instead of dropping it, so
            # an admin can check the match (and approve it if it is wrong).
            duplicate_meta = {
                "of_hash": dup.duplicate_of_hash,
                "score": round(dup.similarity_score, 3),
                "reason": dup.reason,
            }
        material_hashes.add(dup.content_hash)
        classification = classify_question(q, use_ai=use_ai) if use_ai else classifier.classify(q)
        subject = _resolve_subject(classification.subject)
        topic = _resolve_topic(subject, classification.topic) if subject else None
        # Compute provenance_checksum (P4): sha256(question_text + correct_answer + explanation).
        prov_h = hashlib.sha256()
        prov_h.update((q.question_text or "").encode("utf-8", errors="ignore")); prov_h.update(b"\x1f")
        prov_h.update((q.correct_answer or "").encode("utf-8", errors="ignore")); prov_h.update(b"\x1f")
        prov_h.update((q.explanation or "").encode("utf-8", errors="ignore"))
        provenance_checksum = prov_h.hexdigest()
        # P17 — needs_review flag for ambiguous cases (missing correct marker
        # but otherwise OK). NB: ``"" in "ABCD"`` is True, so the old substring
        # test let rows with NO answer through as plain "pending".
        needs_review = (q.correct_answer or "").strip().upper() not in {"A", "B", "C", "D"}
        if duplicate_meta:
            row_status = "duplicate"
        else:
            row_status = "needs_review" if needs_review else "pending"
        classification_meta = dict(classification.raw or {})
        duplicate_of = None
        if duplicate_meta:
            classification_meta["duplicate"] = duplicate_meta
            duplicate_of = (
                ExtractedQuestion.objects.filter(content_hash=dup.duplicate_of_hash)
                .exclude(status="duplicate").order_by("id").first()
            )
        pending_rows.append(ExtractedQuestion(
            material=material,
            position_index=q.position_index,
            paragraph_index=q.paragraph_index,
            raw_text=q.raw_text,
            question_text=q.question_text,
            option_a=q.option_a,
            option_b=q.option_b,
            option_c=q.option_c,
            option_d=q.option_d,
            correct_answer=q.correct_answer or "",
            explanation=q.explanation,
            marks=q.marks or 1,
            negative_marks=q.negative_marks or 0.0,
            inferred_subject=classification.subject or "",
            inferred_topic=classification.topic or "",
            inferred_difficulty=classification.difficulty or "medium",
            inferred_bloom_level=classification.bloom_level or "",
            classification_confidence=classification.confidence or 0.0,
            classification_meta=classification_meta,
            subject=subject,
            topic=topic,
            content_hash=dup.content_hash,
            duplicate_of=duplicate_of,
            review_note=(f"Possible duplicate ({dup.reason})" if duplicate_meta else ""),
            provenance_checksum=provenance_checksum,
            image_refs=q.image_refs or [],
            status=row_status,
        ))
    if pending_rows:
        ExtractedQuestion.objects.bulk_create(pending_rows, batch_size=200)
        summary["duplicates_staged"] = sum(1 for r in pending_rows if r.status == "duplicate")
        summary["questions_saved"] = len(pending_rows) - summary["duplicates_staged"]
        # P3 — per-question image linking via the M2M.
        # Each ExtractedQuestion's image_refs is the list of filenames that
        # belong to it (set by the fidelity extractor). Map those to
        # ImportedImage PKs and add to linked_questions M2M.
        eq_pk_by_position = {eq.position_index: eq.pk for eq in ExtractedQuestion.objects.filter(material=material).only("pk", "position_index", "image_refs")}
        for eq_pos, eq_pk in eq_pk_by_position.items():
            eq = next((p for p in pending_rows if p.position_index == eq_pos), None)
            if not eq or not eq.image_refs:
                continue
            img_pks = [filename_to_pk[fn] for fn in eq.image_refs if fn in filename_to_pk]
            if img_pks:
                Through = ImportedImage.linked_questions.through
                rows = []
                for ipk in img_pks:
                    rows.append(Through(importedimage_id=ipk, extractedquestion_id=eq_pk))
                Through.objects.bulk_create(rows, ignore_conflicts=True)

    # ----- Theory ----------------------------------------------------------
    theory_rows: list[ExtractedTheory] = []
    for t in parsed.theory_blocks:
        if not t.body_text and not t.heading:
            continue
        theory_rows.append(ExtractedTheory(
            material=material,
            position_index=t.position_index,
            heading=t.heading,
            subheading=t.subheading,
            body_text=t.body_text,
            block_type=t.block_type,
            keywords=t.keywords or [],
            classification_meta=t.extra or {},
            content_hash=hashlib.sha256((t.body_text or "").encode("utf-8", errors="ignore")).hexdigest(),
        ))
    if theory_rows:
        ExtractedTheory.objects.bulk_create(theory_rows, batch_size=200)
        summary["theory_saved"] = len(theory_rows)

    return summary


def ingest_path(
    path: str,
    source_label: str = "",
    created_by=None,
    use_ai: bool = False,
    max_files: int | None = None,
    force: bool = False,
    batch: ImportBatch | None = None,
) -> ImportBatch:
    """Ingest a single file or an entire folder. Returns the ImportBatch.

    ``batch``: an existing (normally ``queued``) ImportBatch to fill — the
    Import Center upload view creates the batch up front so it can return
    its id, and the background ingest must report into THAT batch. Without
    it a new batch is created (CLI / admin re-run behaviour).

    A batch whose status becomes ``cancelled`` (Import Center "Cancel") is
    honoured between files: the loop stops and the status stays cancelled.

    ``force=True`` bypasses the cross-batch dedup check (P1 escape hatch) so
    a fidelity upgrade or a deliberately re-imported fixture always lands new
    staging rows. Production-grade imports should keep dedup ON; this is a
    verification / migration aid only.
    """
    path = os.path.abspath(path)
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    factory = ParserFactory()

    if batch is None:
        batch = ImportBatch.objects.create(
            source_label=source_label or Path(path).name,
            root_path=path,
            status="processing",
            started_at=timezone.now(),
            created_by=created_by,
        )
    else:
        batch.refresh_from_db()
        if batch.status == "cancelled":
            log.info("ingest_path: batch %s was cancelled before it started", batch.id)
            return batch
        batch.status = "processing"
        batch.started_at = batch.started_at or timezone.now()
        batch.root_path = batch.root_path or path
        if created_by is not None and batch.created_by_id is None:
            batch.created_by = created_by
        batch.save(update_fields=["status", "started_at", "root_path", "created_by", "updated_at"])

    # Decide which files to process.
    if os.path.isfile(path):
        files = [path]
    else:
        files = []
        for dirpath, _dirnames, filenames in os.walk(path):
            for fn in filenames:
                fp = os.path.join(dirpath, fn)
                if factory.parser_for(fp) is not None:
                    files.append(fp)
        files.sort()
    batch.total_files = min(len(files), max_files) if max_files else len(files)
    batch.save(update_fields=["total_files"])

    # Prime dedup with existing questions. ``force=True`` (P1 escape hatch)
    # skips the priming + dedup check so fidelity upgrades / re-imports always
    # land new staging rows; otherwise the shingle-similarity detector marks
    # the new rows as duplicates of the older plain-text versions.
    dedup = DuplicateDetector()
    if not force:
        _seed_existing_dedup(dedup)
    else:
        log.warning("ingest_path(force=True) — dedup bypass active; staging rows may overlap existing Questions")

    summary_total = {
        "questions_found": 0,
        "questions_saved": 0,
        "questions_rejected": 0,
        "questions_deduplicated": 0,
        "duplicates_staged": 0,
        "theory_saved": 0,
        "images_saved": 0,
        "images_duplicate": 0,
        "images_rejected": 0,
    }
    error_log: list[dict] = []
    files_failed = 0
    cancelled = False

    for idx, fp in enumerate(files):
        if max_files and idx >= max_files:
            break
        # Honour an admin "Cancel" between files.
        if ImportBatch.objects.filter(pk=batch.pk, status="cancelled").exists():
            cancelled = True
            ImportAuditLog.objects.create(
                batch=batch, level="warning", code="cancel_honoured",
                message=f"Stopped after {idx} of {len(files)} file(s): batch was cancelled.",
            )
            break
        rel = os.path.relpath(fp, path)
        try:
            material = ImportMaterial.objects.create(
                batch=batch,
                original_filename=os.path.basename(fp),
                stored_path=fp,
                file_format=_material_format(fp),
                file_size_bytes=os.path.getsize(fp),
                file_sha256=_file_sha256(fp),
            )
            parsed = factory.parse(fp)
            # Track found counts BEFORE dedup / persistence.
            material.questions_found = len(parsed.questions)
            summary_total["questions_found"] += len(parsed.questions)
            # P1 — per-question image refs were set by the fidelity extractor in
            # the parser. Do NOT clobber them here with the document-wide image
            # list (that was the old global-assignment bug).
            material.detected_type = parsed.detected_type
            material.parser_used = parsed.parser_used
            material.duration_ms = parsed.duration_ms
            material.parse_warnings = parsed.warnings[:50]
            material.parse_errors = parsed.errors[:50]
            material.parse_status = "parsed" if not parsed.errors else "failed"
            summary = _persist_parsed_document(material, parsed, dedup, use_ai=use_ai)
            material.question_count = summary["questions_saved"]
            material.questions_rejected = summary["questions_rejected"]
            material.theory_block_count = summary["theory_saved"]
            material.image_count = summary["images_saved"]
            material.duplicate_count = summary["questions_deduplicated"]
            material.parsed_at = timezone.now()
            material.save()
            for k, v in summary.items():
                summary_total[k] = summary_total.get(k, 0) + v
            if parsed.errors:
                files_failed += 1
                for err in parsed.errors[:5]:
                    error_log.append({"file": rel, "error": err})
                    ImportAuditLog.objects.create(
                        batch=batch, material=material, level="error",
                        code="parse_error", message=err,
                    )
            else:
                ImportAuditLog.objects.create(
                    batch=batch, material=material, level="info",
                    code="parsed", message=f"Parsed {parsed.detected_type} with {parsed.parser_used}",
                    details=parsed.counts(),
                )
        except Exception as exc:
            log.exception("Failed to ingest %s", fp)
            files_failed += 1
            error_log.append({"file": rel, "error": str(exc)})
            try:
                ImportAuditLog.objects.create(
                    batch=batch, level="error", code="ingest_failure",
                    message=f"{rel}: {exc}",
                )
            except Exception:
                pass
        batch.files_processed = idx + 1
        batch.files_failed = files_failed
        batch.questions_extracted = summary_total["questions_saved"]
        batch.questions_found = summary_total["questions_found"]
        batch.questions_rejected = summary_total["questions_rejected"]
        batch.theory_blocks_extracted = summary_total["theory_saved"]
        batch.images_extracted = summary_total["images_saved"]
        batch.duplicates_skipped = summary_total["questions_deduplicated"]
        batch.save(update_fields=[
            "files_processed", "files_failed", "questions_extracted", "questions_found",
            "questions_rejected", "theory_blocks_extracted",
            "images_extracted", "duplicates_skipped", "updated_at",
        ])

    # Re-read the status: a Cancel that arrived during the last file wins.
    if cancelled or ImportBatch.objects.filter(pk=batch.pk, status="cancelled").exists():
        batch.status = "cancelled"
    else:
        batch.status = "partial" if error_log else "completed"
    batch.finished_at = timezone.now()
    # Merge, never replace, under the batch row lock: the upload view stores
    # uploaded_files here and the publish / test builder keep their own keys
    # in the same dict (a cancelled batch may already be publishing).
    from .batch_state import update_batch_summary
    update_batch_summary(batch.pk, lambda summary: summary.update(summary_total))
    batch.error_report = error_log[:200]
    batch.save(update_fields=["status", "finished_at", "error_report", "updated_at"])
    batch.refresh_from_db(fields=["summary"])
    return batch
