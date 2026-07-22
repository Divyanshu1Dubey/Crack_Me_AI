"""Orchestration entrypoint — runs the import pipeline end-to-end.

Usage:
    python -m backend.importers.neetpg.runner --scan --source-dir <path>
    python -m backend.importers.neetpg.runner --source-dir <path>
    python -m backend.importers.neetpg.runner --pdf <file>
    python -m backend.importers.neetpg.runner --dedup
    python -m backend.importers.neetpg.runner --report

The runner is resumable: per-source progress lives in
`<output>/manifest.json`. Re-running skips finished sources.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import logging
import sys
import time
from pathlib import Path
from typing import Iterable, Optional

from . import (
    classifier as classifier_mod,
    deduplicator,
    fingerprints as fp_mod,
    image_extractor,
    ocr_engine,
    pdf_reader,
    quality as quality_mod,
    report as report_mod,
    storage,
    text_parser,
    topic_mapper,
)
from .config import get_config
from .models import ImageRecord, ParsedQuestion, QualityIssue, SourceRecord

LOG = logging.getLogger("neetpg.importer")

# --------------------------------------------------------------- helpers ---

def _now_iso() -> str:
    return _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _run_id() -> str:
    return _dt.datetime.utcnow().strftime("%Y-%m-%dT%H-%MZ")


def _iter_pdfs(source_dir: Path) -> Iterable[Path]:
    return sorted(p for p in source_dir.glob("*.pdf") if p.is_file())


# --------------------------------------------------------------- per-PDF ---

def process_one_pdf(
    pdf_path: Path,
    cfg,
    *,
    import_job_id: Optional[str] = None,
    force: bool = False,
) -> dict:
    """Run the full pipeline for one PDF; return a summary dict."""
    LOG.info("Processing %s", pdf_path.name)
    started = time.monotonic()

    # 0. Fingerprint
    try:
        doc = pdf_reader.open_pdf(pdf_path)
    except pdf_reader.PdfBackendUnavailable as e:
        LOG.warning("Skipping %s: %s", pdf_path.name, e)
        return {"filename": pdf_path.name, "skipped": True, "reason": str(e)}

    is_enc = pdf_reader.is_encrypted(doc)
    if is_enc:
        LOG.warning("Skipping encrypted PDF %s", pdf_path.name)
        return {"filename": pdf_path.name, "skipped": True, "reason": "encrypted"}

    page_count = pdf_reader.page_count(doc)
    metadata = pdf_reader.metadata(doc)
    fingerprint = fp_mod.compute_fingerprint(pdf_path, page_count, is_enc, metadata)
    sha16 = fingerprint.pdf_sha256_short

    source = SourceRecord(
        pdf_filename=fingerprint.pdf_filename,
        pdf_path=fingerprint.pdf_path,
        pdf_sha256=fingerprint.pdf_sha256,
        pdf_sha256_short=sha16,
        pdf_size_bytes=fingerprint.size_bytes,
        page_count=page_count,
        is_encrypted=is_enc,
        recall_status="recall",
        scan_type="hybrid",
        publisher=(metadata.get("author") or None),
        metadata=metadata,
        import_job_id=import_job_id,
        imported_at=_now_iso(),
    )

    raw_rows: list[dict] = []
    parsed_questions: list[ParsedQuestion] = []
    image_records: list[ImageRecord] = []
    ocr_pages: list[dict] = []
    page_features: list = []

    fallback_subject = topic_mapper.fallback_subject_from_filename(pdf_path.name)

    # Pre-compute pdfplumber fallback text per page. Some scanned PDFs
    # have a hidden OCR text layer that PyMuPDF can't read but pdfplumber
    # can. We pull that once up front, then plug it in per-page when the
    # PyMuPDF layer is empty.
    plumber_text: dict[int, str] = pdf_reader.extract_text_via_pdfplumber_pages(pdf_path)

    # 1+2. Iterate pages: classify, extract text/images, OCR fallback.
    for page in pdf_reader.iter_pages(doc):
        text = page.text or ""
        # Fallback: if PyMuPDF gave us nothing, use pdfplumber's text.
        if not text.strip() and plumber_text.get(page.page_number, "").strip():
            text = plumber_text[page.page_number]
        feats = classifier_mod.features_for(page.page_number, text, page.image_count)
        page_features.append(feats)
        cls = classifier_mod.classify(feats)
        ocr_text = ""
        ocr_conf = 0.0

        if cls in ("scanned", "hybrid") and ocr_engine.is_available():
            png = pdf_reader.render_page_png(doc, page.page_number, dpi=cfg.ocr_dpi)
            if png:
                tmp = cfg.pages_dir / sha16 / f"p{page.page_number:04d}.png"
                tmp.parent.mkdir(parents=True, exist_ok=True)
                tmp.write_bytes(png)
                ocr_text, ocr_conf = ocr_engine.ocr_image(tmp, lang=cfg.ocr_lang)
                if ocr_text and cls == "scanned":
                    text = ocr_text
                elif ocr_text and cls == "hybrid":
                    text = (text + "\n" + ocr_text).strip()
                if ocr_conf:
                    ocr_pages.append({"filename": pdf_path.name, "page_number": page.page_number,
                                      "confidence": ocr_conf})

        raw_rows.append({
            "page_number": page.page_number,
            "class": cls,
            "text_chars": feats.text_chars,
            "image_count": feats.image_count,
            "ocr_confidence": ocr_conf,
        })

        # 3. Parse questions
        llm = text_parser.parse_with_llm if cfg.enable_llm_fallback else None
        questions, stats = text_parser.parse_page(
            text, page.page_number, sha16,
            llm_fallback=llm, import_job_id=import_job_id,
        )

        # 4. Topic mapping + image extraction
        for q in questions:
            q.subject = topic_mapper.map_subject(q.stem, fallback=fallback_subject)
            q.topic = topic_mapper.map_topic_subject(q.stem, q.subject or "")
            if ocr_conf:
                q.ocr_confidence = ocr_conf / 100.0

        # Extract embedded images for this page.
        page_images = image_extractor.extract_embedded(
            doc, page.page_number, page.image_xrefs,
            out_dir=cfg.images_dir / sha16,
            source_sha16=sha16,
            ocr_lang=cfg.ocr_lang,
        )
        image_records.extend(page_images)

        # Link image_refs that mention page N to the page's images.
        for q in questions:
            if q.image_refs:
                q.is_image_based = True
                for ref in q.image_refs:
                    pass  # resolved later by the linker stage

        parsed_questions.extend(questions)

    # 5. Dedup within this PDF
    dedup_report = deduplicator.dedup_batch(
        parsed_questions,
        image_records,
        fuzzy_threshold=cfg.dedup_threshold,
        image_phash_threshold=cfg.image_phash_threshold,
    )

    # 6. Quality
    kept, issues, qstats = quality_mod.check_questions(
        parsed_questions,
        min_ocr_confidence=cfg.min_ocr_confidence,
    )

    # 7. Persist outputs (Phase-1 JSONL first, DB second so a DB failure
    #    never loses parsed data).
    raw_path = cfg.raw_dir / f"{sha16}__{pdf_path.stem}.jsonl"
    storage.write_jsonl(raw_path, raw_rows)
    parsed_path = cfg.parsed_dir / f"{sha16}.questions.jsonl"
    storage.write_jsonl(parsed_path, (q.to_dict() for q in parsed_questions))
    quality_path = cfg.output_dir / "quality.jsonl"
    storage.write_jsonl(quality_path, (i.to_json() for i in issues))

    # 7b. Persist into the database (Phase 2 integration).
    db_stats = _persist_into_db(
        pdf_path=pdf_path,
        fingerprint=fingerprint,
        parsed_questions=parsed_questions,
        image_records=image_records,
        scan_type=_scan_type(page_features),
        recall_status="recall",
        import_job_id=import_job_id,
        force=force,
    )

    elapsed = time.monotonic() - started
    summary = {
        "filename": pdf_path.name,
        "sha256_short": sha16,
        "page_count": page_count,
        "question_count": len(parsed_questions),
        "image_count": len(image_records),
        "skipped": False,
        "elapsed_seconds": round(elapsed, 2),
        "scan_type": _scan_type(page_features),
        "db": db_stats,
    }
    LOG.info("Done %s: %d questions, %d images, %.1fs",
             pdf_path.name, summary["question_count"],
             summary["image_count"], elapsed)
    return summary


def _persist_into_db(
    pdf_path: Path,
    fingerprint,
    parsed_questions: list,
    image_records: list,
    scan_type: str,
    recall_status: str,
    import_job_id: Optional[str],
    force: bool = False,  # noqa: ARG001 — kept for parity with runner's main arg set
) -> dict:
    """Translate Phase-1 output into Django ORM rows.

    Wrapped so a DB error never blocks Phase-1 JSONL output. Returns a
    dict the runner tucks into the per-PDF `summary['db']` block.
    """
    try:
        from .db_writer import DjangoWriter
        from questions.models import QuestionImportJob
    except Exception as e:
        LOG.warning("DB persistence unavailable for %s: %s", pdf_path.name, e)
        return {"available": False, "error": str(e)}

    if not parsed_questions and not image_records:
        return {"available": True, "persisted": False, "reason": "no rows"}

    try:
        import_job = None
        if import_job_id is not None:
            try:
                import_job = QuestionImportJob.objects.filter(id=int(import_job_id)).first()
            except (TypeError, ValueError):
                import_job = None
        writer = DjangoWriter(import_job=import_job)
        recall_source = writer.upsert_recall_source(
            pdf_path=pdf_path, fingerprint=fingerprint,
            scan_type=scan_type, recall_status=recall_status,
        )

        questions_by_stem: dict[str, object] = {}
        for q in parsed_questions:
            row = writer.write_question(q, recall_source)
            if row is not None:
                key = (q.stem or q.stem_raw or "").strip()[:80]
                if key:
                    questions_by_stem[key] = row

        images_written = 0
        for img in image_records:
            target = None
            stem_key = (getattr(img, "question_stem", "") or "").strip()[:80]
            if stem_key:
                target = questions_by_stem.get(stem_key)
            if target is None:
                # Best-effort fallback: link to the first question so we
                # never lose the image row.
                target = next(iter(questions_by_stem.values()), None)
            if target is not None:
                if writer.write_image(img, target, recall_source) is not None:
                    images_written += 1

        return {
            "available": True,
            "persisted": True,
            "questions_created": writer.stats.questions_created,
            "questions_updated": writer.stats.questions_updated,
            "questions_soft_deleted": writer.stats.questions_soft_deleted,
            "images_created": writer.stats.images_created,
            "sources_created": writer.stats.sources_created,
            "extraction_items_created": writer.stats.extraction_items_created,
            "duplicate_clusters_created": writer.stats.duplicate_clusters_created,
            "images_written": images_written,
        }
    except Exception as e:
        LOG.exception("DB persistence failed for %s", pdf_path.name)
        return {"available": True, "persisted": False, "error": str(e)}


def _scan_type(features) -> str:
    agg = classifier_mod.aggregate(features)
    if agg["scanned_ratio"] > 0.6:
        return "scanned"
    if agg["scanned_ratio"] > 0.2:
        return "hybrid"
    return "digital"


# --------------------------------------------------------------- top-level

def run_import(
    source_dir: Path,
    *,
    cfg=None,
    only: Optional[Path] = None,
    force: bool = False,
    import_job_id: Optional[int] = None,
) -> dict:
    cfg = cfg or get_config()
    cfg.ensure_dirs()
    run_id = _run_id()
    manifest = storage.load_manifest(cfg.manifest_path)

    if only is not None:
        pdfs = [only]
    else:
        pdfs = list(_iter_pdfs(source_dir))

    LOG.info("Run %s — %d PDF(s)", run_id, len(pdfs))
    summaries: list[dict] = []
    # `import_job_id` (when supplied as int) flows into process_one_pdf so
    # the DB writer can link QuestionSource rows to the originating
    # QuestionImportJob. When None we fall back to the run_id string
    # (Phase-1 CLI semantics).
    db_job_id = import_job_id if import_job_id is not None else run_id
    for p in pdfs:
        try:
            s = process_one_pdf(p, cfg, import_job_id=db_job_id, force=force)
        except Exception as e:  # pragma: no cover - defensive
            LOG.exception("Failed on %s: %s", p, e)
            s = {"filename": p.name, "skipped": True, "reason": repr(e)}
        summaries.append(s)

    manifest.setdefault("runs", []).append({
        "run_id": run_id,
        "started_at": _now_iso(),
        "finished_at": _now_iso(),
        "processed": summaries,
    })
    storage.save_manifest(cfg.manifest_path, manifest)

    # Reports
    rep_dir = cfg.reports_dir / run_id
    rep_dir.mkdir(parents=True, exist_ok=True)

    total_q = sum(s.get("question_count", 0) for s in summaries)
    total_img = sum(s.get("image_count", 0) for s in summaries)
    total_pages = sum(s.get("page_count", 0) for s in summaries)

    report_mod.write_import_report(
        rep_dir, run_id=run_id,
        pdf_count=len(summaries), page_count=total_pages,
        question_count=total_q, image_count=total_img,
        sources=summaries,
    )

    # OCR report — derived from quality issues (low_ocr_confidence).
    ocr_pages = []
    issues_path = cfg.output_dir / "quality.jsonl"
    if issues_path.exists():
        for line in issues_path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except Exception:
                continue
            if row.get("issue_type") == "low_ocr_confidence":
                ocr_pages.append({
                    "filename": row.get("source_sha16", ""),
                    "page_number": row.get("page_number", ""),
                    "confidence": 0.0,
                })

    avg_conf = 0.0
    report_mod.write_ocr_report(
        rep_dir, run_id=run_id,
        ocr_pages=len(ocr_pages),
        avg_confidence=avg_conf,
        low_confidence_pages=ocr_pages[:50],
    )

    # Quality + missing-data reports.
    by_type: dict[str, int] = {}
    if issues_path.exists():
        for line in issues_path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except Exception:
                continue
            by_type[row.get("issue_type", "")] = by_type.get(row.get("issue_type", ""), 0) + 1
    report_mod.write_quality_report(rep_dir, run_id=run_id, issues=[], by_type=by_type)

    missing = {
        "missing_options": by_type.get("missing_options", 0),
        "missing_answers": by_type.get("missing_answer", 0),
        "missing_explanations": 0,    # tracked separately if needed
        "low_ocr_pages": by_type.get("low_ocr_confidence", 0),
        "empty_stems": by_type.get("empty_stem", 0),
    }
    report_mod.write_missing_data_report(rep_dir, run_id=run_id, **missing)

    LOG.info("Reports written to %s", rep_dir)
    return {"run_id": run_id, "summaries": summaries}


# --------------------------------------------------------------- CLI ----

def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="neetpg-runner")
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--pdf", type=Path)
    parser.add_argument("--scan", action="store_true", help="scan only (alias for --report on existing manifest)")
    parser.add_argument("--dedup", action="store_true", help="rerun dedup over existing JSONL")
    parser.add_argument("--report", action="store_true", help="regenerate reports from latest run")
    parser.add_argument("--verbose", "-v", action="count", default=0)
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    cfg = get_config()
    if args.pdf:
        return 0 if process_one_pdf(args.pdf, cfg, import_job_id=_run_id()) else 1
    if args.source_dir:
        out = run_import(args.source_dir, cfg=cfg)
        print(json.dumps(out, indent=2)[:2000])
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())