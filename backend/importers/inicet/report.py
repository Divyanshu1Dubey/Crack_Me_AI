"""Markdown report generators.

Each report is a single Markdown file summarising one stage of the
run. Reports are intentionally small — for deep dives, look at the
JSONL outputs.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .models import ParsedQuestion, QualityIssue, ImageRecord


def _md_table(headers: list[str], rows: Iterable[list[str]]) -> str:
    head = "| " + " | ".join(headers) + " |"
    sep = "|" + "|".join("---" for _ in headers) + "|"
    body = "\n".join("| " + " | ".join(r) + " |" for r in rows)
    return "\n".join([head, sep, body])


def write_import_report(
    out_dir: Path,
    *,
    run_id: str,
    pdf_count: int,
    page_count: int,
    question_count: int,
    image_count: int,
    sources: list[dict],
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [
        [s.get("filename", ""),
         str(s.get("page_count", "")),
         str(s.get("question_count", "")),
         str(s.get("image_count", "")),
         s.get("scan_type", "")]
        for s in sources
    ]
    body = f"""# Import Report

- **Run ID:** `{run_id}`
- **PDFs processed:** {pdf_count}
- **Pages processed:** {page_count}
- **Questions parsed:** {question_count}
- **Images extracted:** {image_count}

## Per-source

{_md_table(["Filename", "Pages", "Questions", "Images", "Scan type"], rows)}
"""
    path = out_dir / "IMPORT_REPORT.md"
    path.write_text(body, encoding="utf-8")
    return path


def write_ocr_report(
    out_dir: Path,
    *,
    run_id: str,
    ocr_pages: int,
    avg_confidence: float,
    low_confidence_pages: list[dict],
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [
        [r.get("filename", ""), str(r.get("page_number", "")),
         f"{r.get('confidence', 0):.1f}"]
        for r in low_confidence_pages
    ]
    body = f"""# OCR Report

- **Run ID:** `{run_id}`
- **Pages OCR'd:** {ocr_pages}
- **Average confidence:** {avg_confidence:.1f}

## Low-confidence pages (warn)

{_md_table(["Filename", "Page", "Confidence"], rows) if rows else "_None._"}
"""
    path = out_dir / "OCR_REPORT.md"
    path.write_text(body, encoding="utf-8")
    return path


def write_image_report(
    out_dir: Path,
    *,
    run_id: str,
    images: list[ImageRecord],
    modality_counts: dict[str, int],
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [[m, str(c)] for m, c in sorted(modality_counts.items(), key=lambda x: -x[1])]
    body = f"""# Image Extraction Report

- **Run ID:** `{run_id}`
- **Total images:** {len(images)}

## Modality breakdown

{_md_table(["Modality", "Count"], rows) if rows else "_None._"}
"""
    path = out_dir / "IMAGE_EXTRACTION_REPORT.md"
    path.write_text(body, encoding="utf-8")
    return path


def write_quality_report(
    out_dir: Path,
    *,
    run_id: str,
    issues: list[QualityIssue],
    by_type: dict[str, int],
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [[t, str(c)] for t, c in sorted(by_type.items(), key=lambda x: -x[1])]
    body = f"""# Quality Report

- **Run ID:** `{run_id}`
- **Total flagged:** {len(issues)}

## Issue breakdown

{_md_table(["Type", "Count"], rows) if rows else "_None._"}

> Flagged rows are still stored with full provenance. They are surfaced
> in the admin UI for human review and never silently dropped.
"""
    path = out_dir / "QUALITY_REPORT.md"
    path.write_text(body, encoding="utf-8")
    return path


def write_dedup_report(
    out_dir: Path,
    *,
    run_id: str,
    new_canonical: int,
    exact_sha: int,
    fuzzy: int,
    embedding: int,
    image: int,
    cluster_count: int,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    body = f"""# Deduplication Report

- **Run ID:** `{run_id}`
- **New canonical questions:** {new_canonical}
- **Exact sha duplicates:** {exact_sha}
- **Fuzzy duplicates:** {fuzzy}
- **Embedding duplicates:** {embedding}
- **Image-hash duplicates:** {image}
- **Clusters formed:** {cluster_count}

> Duplicates are linked to their canonical question. Source rows are
> preserved in `Provenance` — nothing is deleted.
"""
    path = out_dir / "DEDUPLICATION_REPORT.md"
    path.write_text(body, encoding="utf-8")
    return path


def write_missing_data_report(
    out_dir: Path,
    *,
    run_id: str,
    missing_options: int,
    missing_answers: int,
    missing_explanations: int,
    low_ocr_pages: int,
    empty_stems: int,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [
        ["Missing options", str(missing_options)],
        ["Missing answers", str(missing_answers)],
        ["Missing explanations", str(missing_explanations)],
        ["Low-OCR pages", str(low_ocr_pages)],
        ["Empty stems", str(empty_stems)],
    ]
    body = f"""# Missing Data Report

- **Run ID:** `{run_id}`

{_md_table(["Issue", "Count"], rows)}

> These counts are tracked so we can prioritise follow-up repair jobs.
"""
    path = out_dir / "MISSING_DATA_REPORT.md"
    path.write_text(body, encoding="utf-8")
    return path


__all__ = [
    "write_import_report",
    "write_ocr_report",
    "write_image_report",
    "write_quality_report",
    "write_dedup_report",
    "write_missing_data_report",
]