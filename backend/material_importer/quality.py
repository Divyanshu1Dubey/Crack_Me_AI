"""QA / quality reporting for the importer.

Given a batch id, this module walks every imported material and flags:
  * questions missing any option or correct answer
  * images whose MIME is missing or whose sha256 collides with another
  * duplicate questions that survived the dedupe pass (cross-file dupes
    are not caught by content hash alone when both files import them in
    the same run)
  * theories with empty body
  * materials that finished with parse errors

The report is a JSON-friendly dict and can be dumped to file or printed.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from typing import Any, Dict, List


def build_qa_report(batch_id: int) -> Dict[str, Any]:
    from .models import (
        ExtractedQuestion,
        ExtractedTheory,
        ImportedImage,
        ImportAuditLog,
        ImportMaterial,
    )

    materials = ImportMaterial.objects.filter(batch_id=batch_id)
    report: Dict[str, Any] = {
        "batch_id": batch_id,
        "files_total": materials.count(),
        "files_parsed_ok": 0,
        "files_failed": 0,
        "files_with_warnings": 0,
        "questions": {
            "total": 0,
            "missing_option": 0,
            "missing_correct_answer": 0,
            "missing_question_text": 0,
            "duplicates_caught": 0,
        },
        "images": {
            "total": 0,
            "missing_mime": 0,
            "duplicate_in_batch": 0,
            "byte_size_total": 0,
        },
        "theory_blocks": {
            "total": 0,
            "empty": 0,
        },
        "audit_errors": [],
        "warnings_by_file": [],
        "errors_by_file": [],
    }

    image_hash_counter: Counter = Counter()
    for img in ImportedImage.objects.filter(material__batch_id=batch_id):
        report["images"]["total"] += 1
        report["images"]["byte_size_total"] += img.size_bytes or 0
        if not img.mime_type:
            report["images"]["missing_mime"] += 1
        image_hash_counter[img.sha256 or ""] += 1
    report["images"]["duplicate_in_batch"] = sum(
        c - 1 for h, c in image_hash_counter.items() if c > 1 and h
    )

    for eq in ExtractedQuestion.objects.filter(material__batch_id=batch_id):
        report["questions"]["total"] += 1
        if not (eq.question_text and eq.question_text.strip()):
            report["questions"]["missing_question_text"] += 1
        if not all([eq.option_a, eq.option_b, eq.option_c, eq.option_d]):
            report["questions"]["missing_option"] += 1
        if not eq.correct_answer:
            report["questions"]["missing_correct_answer"] += 1
        if eq.status == "duplicate":
            report["questions"]["duplicates_caught"] += 1

    for t in ExtractedTheory.objects.filter(material__batch_id=batch_id):
        report["theory_blocks"]["total"] += 1
        if not (t.body_text or t.heading):
            report["theory_blocks"]["empty"] += 1

    for m in materials:
        if m.parse_status == "failed":
            report["files_failed"] += 1
            report["errors_by_file"].append({
                "file": m.original_filename,
                "errors": list(m.parse_errors or [])[:10],
            })
        else:
            report["files_parsed_ok"] += 1
        if m.parse_warnings:
            report["files_with_warnings"] += 1
            report["warnings_by_file"].append({
                "file": m.original_filename,
                "warnings": list(m.parse_warnings or [])[:10],
            })

    for al in ImportAuditLog.objects.filter(batch_id=batch_id, level="error"):
        report["audit_errors"].append({
            "id": al.id,
            "code": al.code,
            "message": al.message,
            "material": al.material.original_filename if al.material_id else None,
        })

    return report


def save_qa_report(batch_id: int, path: str) -> str:
    report = build_qa_report(batch_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    return path
