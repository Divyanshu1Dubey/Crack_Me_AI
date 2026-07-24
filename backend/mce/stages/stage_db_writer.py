"""DB writer — writes Stage 7 structured output into the existing schema.

What we write today (no migrations required):

    RecallSource     — one row per source PDF (keyed on sha256 + page range).
    Question         — one row per extracted question.
    QuestionSource   — one row per question bridging to RecallSource.
    QuestionImage    — one row per extracted image attached to a question.

Rows gated by Stage 8 PASS verdict — FAIL pages are queued in
``db_pending.jsonl`` for later review, never written to the live DB.

New-table rows (Phase 3 deferred):

    QuestionAsset, QuestionPearl, QuestionReference, Concept,
    QuestionConcept, ConceptEdge

These go to ``db_new_tables_queue.jsonl`` so Phase 3 has the data ready
when the migrations land. The queue file is committed to source so the
Phase 3 writer can ingest it without re-running the pipeline.

This stage is intentionally idempotent: re-running the same source over
the same questions is a no-op (we key on the existing unique hash).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from mce.stages import MceContext, StageResult


LOG = logging.getLogger("mce.stage_db_writer")


@dataclass
class DbWriterStats:
    recall_sources_created: int = 0
    questions_created: int = 0
    questions_updated: int = 0
    images_created: int = 0
    images_deduped: int = 0
    question_sources_created: int = 0
    pending_for_phase3: int = 0
    skipped_due_to_qa: int = 0


def _normalize_text(text: str) -> str:
    """Lightweight normalisation for dedup hashes — matches the legacy
    `backend/questions/text_encoding.py.normalize_text` contract."""
    import re
    text = (text or "").lower()
    text = re.sub(r"\[(?:image|fig|figure)[^\]]*\]|\b(?:q|question|ans|answer|exp|explanation)\s*[:\-\.]?\s*", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _text_sha256(text: str) -> str:
    return hashlib.sha256(_normalize_text(text).encode("utf-8")).hexdigest()


def _pass_pages_for_pdf(artefact_root: Path) -> set[int]:
    summary = artefact_root / "08_qa" / "summary.json"
    if not summary.exists():
        return set()
    rep = (artefact_root / "08_qa" / "per_page_report.json")
    if not rep.exists():
        return set()
    try:
        per_page = json.loads(rep.read_text(encoding="utf-8"))
    except Exception:
        return set()
    return {int(pn) for pn, info in per_page.items() if info.get("status") == "PASS"}


def _load_stage3_images(stage3_dir: Path, page_number: int) -> list[dict[str, Any]]:
    p = stage3_dir / f"p{page_number:03d}.json"
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("images", [])
    except Exception:
        return []


def run(ctx: MceContext, *, pages: Optional[list[int]] = None,
        force: bool = False) -> StageResult:
    """Idempotent DB write gated by Stage 8 PASS verdict."""
    res = StageResult(stage="stage_db_writer")
    stats = DbWriterStats()
    artefact_root = ctx.artefact_root

    # Stage 8 gate (only blocks ORM writes, not the queue file).
    pass_pages = _pass_pages_for_pdf(artefact_root)
    if not pass_pages:
        res.warnings.append(
            "No pages in PASS — skipping ORM writes. "
            "Phase-3 queue rows will still be emitted. "
            "Run Stage 8 first; ORM writer only persists PASS rows."
        )

    stage7_index = ctx.stage_dir("07_structured") / "_index.json"
    if not stage7_index.exists():
        res.errors.append("Stage 7 index missing")
        return res
    try:
        s7 = json.loads(stage7_index.read_text(encoding="utf-8"))
        questions = s7.get("questions", [])
    except Exception as e:
        res.errors.append(f"stage 7 read failed: {e}")
        return res

    if pages:
        pages_set = set(pages)
        questions = [q for q in questions if int(q["page_number"]) in pages_set]

    # Initialise Django (must happen before any ORM call).
    try:
        import django  # type: ignore
        if not os.environ.get("DJANGO_SETTINGS_MODULE"):
            os.environ["DJANGO_SETTINGS_MODULE"] = "crack_cms.settings"
        django.setup()
        from questions.models import (  # type: ignore
            Question, QuestionImage, QuestionSource, RecallSource,
            Subject, Topic, QuestionImportJob,
        )
        from questions.text_encoding import normalize_text  # type: ignore
        from django.db import transaction, IntegrityError
        from django.utils import timezone
        django_ready = True
    except Exception as e:
        LOG.warning("Django not importable — DB writes disabled: %s", e)
        django_ready = False

    if django_ready:
        # ---- RecallSource (one row per PDF). ----
        try:
            with transaction.atomic():
                rs, created = RecallSource.objects.get_or_create(
                    pdf_sha256=ctx.pdf_sha256,
                    defaults={
                        "pdf_filename": ctx.pdf_filename,
                        "pdf_path": str(ctx.pdf_path),
                        "pdf_sha256_short": ctx.pdf_sha256_short,
                        "pdf_size_bytes": ctx.pdf_path.stat().st_size,
                        "page_count": ctx.page_count,
                        "scan_type": "digital",
                        "recall_status": "recall",
                        "publisher": "",
                        "pdf_metadata": {},
                        "is_active": True,
                    },
                )
                if created:
                    stats.recall_sources_created += 1
        except Exception as e:
            LOG.warning("RecallSource upsert failed: %s", e)

    # ---- New-table queue file (Phase 3 deferred). ----
    queue_path = artefact_root / "00_meta" / "db_new_tables_queue.jsonl"
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    if force or not queue_path.exists():
        queue_path.write_text("", encoding="utf-8")

    # ---- Per-question writes. ----
    for q in questions:
        page = int(q.get("page_number", 0))

        # Always emit the Phase-3 queue row (assets / pearls / references).
        # These rows are the input for the Phase-3 migrations + writer.
        with queue_path.open("a", encoding="utf-8") as qf:
            qf.write(json.dumps({
                "kind": "phase3_assets",
                "question_id": q["id"],
                "page_number": page,
                "clinical_pearl": q.get("clinical_pearl"),
                "high_yield_points": q.get("high_yield_points", []),
                "mnemonic": q.get("mnemonic"),
                "references": q.get("references", []),
                "asset_ids": q.get("asset_ids", []),
                "captions": q.get("captions", []),
                "is_image_based": bool(q.get("image_ids")),
                "needs_review": bool(q.get("needs_review")),
                "source_trace": q.get("source_trace"),
            }, ensure_ascii=False) + "\n")
            stats.pending_for_phase3 += 1

        if page not in pass_pages:
            stats.skipped_due_to_qa += 1
            continue

        if not django_ready:
            continue

        try:
            with transaction.atomic():
                text_hash = _text_sha256(q.get("stem", ""))
                stem_text = normalize_text(q.get("stem", "") or "")
                if not stem_text:
                    continue
                # Try to find an existing row by (text_hash, exam_type).
                try:
                    existing = Question.objects.get(
                        recall_text_hash=text_hash, exam_type=ctx.profile.exam_type,
                    )
                    question = existing
                    created = False
                except Question.DoesNotExist:
                    # Resolve subject.
                    subject = None
                    if q.get("subject"):
                        subject = Subject.objects.filter(
                            name__iexact=q["subject"]
                        ).first()
                    if subject is None:
                        subject = Subject.objects.first()
                    question = Question.objects.create(
                        question_text=stem_text,
                        option_a=normalize_text((q.get("options") or [{}])[0].get("text", "") if len(q.get("options") or []) > 0 else ""),
                        option_b=normalize_text((q.get("options") or [{}])[1].get("text", "") if len(q.get("options") or []) > 1 else ""),
                        option_c=normalize_text((q.get("options") or [{}])[2].get("text", "") if len(q.get("options") or []) > 2 else ""),
                        option_d=normalize_text((q.get("options") or [{}])[3].get("text", "") if len(q.get("options") or []) > 3 else ""),
                        correct_answer=(q.get("answer_labels") or ["A"])[0],
                        explanation=normalize_text(q.get("explanation") or ""),
                        question_type="single_best",
                        exam_type=ctx.profile.exam_type,
                        exam_source=ctx.profile.exam_source,
                        recall_status="recall",
                        is_image_based=bool(q.get("image_ids")),
                        is_active=True,
                        recall_text_hash=text_hash,
                        needs_review=q.get("needs_review", False),
                        source=ctx.pdf_filename,
                        page_number=str(page),
                        subject=subject,
                        year=_guess_year(ctx.pdf_filename),
                    )
                    created = True
                if created:
                    stats.questions_created += 1
                else:
                    stats.questions_updated += 1

                # QuestionSource bridge.
                try:
                    QuestionSource.objects.get_or_create(
                        question=question, recall_source=rs,
                        page_number=page,
                        question_number_in_pdf=q.get("question_number_in_pdf"),
                        defaults={
                            "original_text": q.get("raw", ""),
                            "extracted_text": q.get("stem", ""),
                            "ocr_confidence": None,
                            "extraction_confidence": None,
                        },
                    )
                    stats.question_sources_created += 1
                except IntegrityError:
                    pass

                # QuestionImage rows for every attached image id.
                for iid in q.get("image_ids", []):
                    im = next((im for im in _load_stage3_images(
                        ctx.stage_dir("03_images"), page) if im.get("id") == iid), None)
                    if not im:
                        continue
                    existing_im = QuestionImage.objects.filter(sha256_short=im.get("sha256_short", "")).first()
                    if existing_im:
                        stats.images_deduped += 1
                        continue
                    QuestionImage.objects.create(
                        question=question,
                        page_number=page,
                        image_index_in_page=int(im.get("image_index_in_page", 0)),
                        mime=im.get("mime", "image/png"),
                        width=int(im.get("width", 0)),
                        height=int(im.get("height", 0)),
                        bytes=int(im.get("bytes", 0)),
                        sha256=im.get("sha256", ""),
                        sha256_short=im.get("sha256_short", ""),
                        phash=im.get("phash", ""),
                        dhash=im.get("dhash", ""),
                        modality=im.get("modality", "other"),
                        modality_subtype=im.get("modality_subtype", ""),
                        body_region=im.get("body_region", ""),
                        ocr_text=im.get("ocr_text", ""),
                        caption=im.get("caption", ""),
                        caption_source=im.get("caption_source", "none"),
                        extraction_confidence=im.get("extraction_confidence"),
                        role=im.get("role", "other"),
                        is_active=True,
                    )
                    stats.images_created += 1
        except Exception as e:
            LOG.warning("DB write failed for %s: %s", q.get("id"), e)

    res.metrics = stats.__dict__
    LOG.info(
        "stage_db_writer: %d q_created, %d q_updated, %d imgs_created, %d imgs_deduped, "
        "%d skipped (QA), %d queued for Phase 3",
        stats.questions_created, stats.questions_updated, stats.images_created,
        stats.images_deduped, stats.skipped_due_to_qa, stats.pending_for_phase3,
    )
    return res


def _guess_year(filename: str) -> int:
    import re
    m = re.search(r"\b(20\d{2})\b", filename or "")
    return int(m.group(1)) if m else 0


__all__ = ["run", "DbWriterStats"]
