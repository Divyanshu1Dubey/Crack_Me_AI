"""Quality checks — flag broken / low-confidence rows.

Never auto-fixes; flags for human review. The runner queues flagged
rows into a `quality.jsonl` and includes them in the QUALITY_REPORT.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .models import ParsedQuestion, QualityIssue


@dataclass
class QualityStats:
    total: int = 0
    flagged: int = 0
    by_type: dict[str, int] = None  # type: ignore

    def __post_init__(self) -> None:
        if self.by_type is None:
            self.by_type = {}


def check_questions(
    questions: Iterable[ParsedQuestion],
    *,
    min_ocr_confidence: float = 60.0,
    min_parse_confidence: float = 0.30,
) -> tuple[list[ParsedQuestion], list[QualityIssue], QualityStats]:
    """Return (kept_questions, issues, stats)."""
    issues: list[QualityIssue] = []
    kept: list[ParsedQuestion] = []
    stats = QualityStats()
    for q in questions:
        stats.total += 1
        flagged = False

        if not (q.stem or "").strip():
            issues.append(QualityIssue(
                source_sha16=q.source_sha16, page_number=q.page_number,
                issue_type="empty_stem", severity="error",
                message="Question stem is empty after parsing.",
                question_number_in_pdf=q.question_number_in_pdf,
            ))
            flagged = True

        if not q.options:
            issues.append(QualityIssue(
                source_sha16=q.source_sha16, page_number=q.page_number,
                issue_type="missing_options", severity="error",
                message="No options detected for this question.",
                question_number_in_pdf=q.question_number_in_pdf,
            ))
            flagged = True

        if q.options and len(q.options) not in (4, 5):
            issues.append(QualityIssue(
                source_sha16=q.source_sha16, page_number=q.page_number,
                issue_type="option_count_unusual", severity="warn",
                message=f"Detected {len(q.options)} options; expected 4–5.",
                question_number_in_pdf=q.question_number_in_pdf,
            ))
            flagged = True

        if not q.answer_labels:
            issues.append(QualityIssue(
                source_sha16=q.source_sha16, page_number=q.page_number,
                issue_type="missing_answer", severity="warn",
                message="No answer label detected (A/B/C/D).",
                question_number_in_pdf=q.question_number_in_pdf,
            ))
            flagged = True

        if q.ocr_confidence and q.ocr_confidence < min_ocr_confidence:
            issues.append(QualityIssue(
                source_sha16=q.source_sha16, page_number=q.page_number,
                issue_type="low_ocr_confidence", severity="warn",
                message=f"OCR confidence {q.ocr_confidence:.1f} < {min_ocr_confidence}.",
                question_number_in_pdf=q.question_number_in_pdf,
            ))
            flagged = True

        if q.extraction_confidence < min_parse_confidence:
            issues.append(QualityIssue(
                source_sha16=q.source_sha16, page_number=q.page_number,
                issue_type="low_parse_confidence", severity="warn",
                message=f"Parse confidence {q.extraction_confidence:.2f} < {min_parse_confidence}.",
                question_number_in_pdf=q.question_number_in_pdf,
            ))
            flagged = True

        if flagged:
            stats.flagged += 1
            for issue in [i for i in issues if i.question_number_in_pdf == q.question_number_in_pdf
                          and i.page_number == q.page_number and i.source_sha16 == q.source_sha16]:
                stats.by_type[issue.issue_type] = stats.by_type.get(issue.issue_type, 0) + 1

        # We keep everything (even flagged) — provenance is sacred.
        kept.append(q)

    return kept, issues, stats


__all__ = ["QualityStats", "check_questions"]