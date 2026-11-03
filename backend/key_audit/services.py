"""Answer-key audit services: signal detection, classification, and review queue integration.

Ground rules (docs/audit/MEDICAL_ACCURACY_DESIGN.md):
1. An answer key is NEVER changed automatically. Audit produces QuestionAudit records
   with status, priority, risk signals, and suggested_key for human review.
2. AI output is never a primary evidence source; only verified publisher/textbook passages count.
3. Classifications: verified, likely_correct, needs_review, contradictory_sources,
   insufficient_evidence, image_context_missing.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Iterable, Sequence

from django.db import transaction
from django.utils import timezone

from key_audit.explanation_check import STATES_OTHER, check_explanation
from key_audit.models import QuestionAudit
from questions.content_hashes import valid_key
from questions.models import Question, QuestionImage

logger = logging.getLogger("key_audit.services")

# Path to precomputed source keys recovered from PDFs
SOURCE_KEYS_PATH = Path(r"C:\Users\DIVYANSHU\crack_local\key_audit\source_keys.jsonl")
_SOURCE_KEYS_CACHE: dict[int, dict[str, Any]] | None = None


def _get_source_keys_cache() -> dict[int, dict[str, Any]]:
    global _SOURCE_KEYS_CACHE
    if _SOURCE_KEYS_CACHE is None:
        cache = {}
        if SOURCE_KEYS_PATH.exists():
            try:
                with open(SOURCE_KEYS_PATH, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        row = json.loads(line)
                        qid = row.get("question_id")
                        if qid:
                            cache[qid] = row
            except Exception as e:
                logger.warning("Could not load source_keys.jsonl: %s", e)
        _SOURCE_KEYS_CACHE = cache
    return _SOURCE_KEYS_CACHE


def queue_question_audit(question_id: int, reason: str = "") -> None:
    """Mark the QuestionAudit for this question as stale so it gets re-audited."""
    try:
        QuestionAudit.objects.filter(question_id=question_id).update(
            is_stale=True,
            status_reason=f"Stale: {reason}" if reason else "Question changed",
        )
    except Exception:
        logger.exception("Failed to mark QuestionAudit stale for Q%s", question_id)


def on_question_changed(question, *, old_key: str = "", old_stem_hash: str = "", reason: str = "", actor=None) -> None:
    """Dispatcher callback from questions.content_hooks."""
    qid = getattr(question, "pk", question)
    queue_question_audit(qid, reason=reason)


def audit_question(question: Question, *, reviews: Sequence[dict[str, Any]] | None = None, run_evidence: bool = False) -> QuestionAudit:
    """Audit a single question against deterministic signals, source keys, and explanation consistency."""
    current_key = valid_key(question.correct_answer)
    signals: list[dict[str, Any]] = []
    suggested_key = ""
    status = "likely_correct"
    status_reason = ""
    priority = 0.0

    # Signal 1: Invalid or missing key
    if not current_key:
        signals.append({
            "code": "invalid_or_missing_key",
            "severity": "high",
            "detail": f"Stored key is {question.correct_answer!r}, not one of A, B, C, D.",
        })
        status = "needs_review"
        status_reason = "invalid_or_missing_key"
        priority = max(priority, 70.0)

    # Signal 2: Recovered source keys from publisher PDFs
    source_cache = _get_source_keys_cache()
    source_info = source_cache.get(question.id)
    evidence_summary: dict[str, Any] = {}
    if source_info:
        evidence_summary = {
            "source_file": source_info.get("source_file"),
            "chapter": source_info.get("chapter"),
            "source_page": source_info.get("source_page"),
            "evidence_page": source_info.get("evidence_page"),
            "qno": source_info.get("qno"),
            "method": source_info.get("method"),
        }
        if source_info.get("status") == "mismatch":
            pub_key = valid_key(source_info.get("bank_letter") or source_info.get("source_letter"))
            if pub_key and pub_key != current_key:
                signals.append({
                    "code": "source_key_mismatch",
                    "severity": "critical",
                    "detail": f"Publisher PDF key in {source_info.get('source_file')} (p.{source_info.get('source_page')}) is {pub_key}, but database stores {current_key}.",
                    "published_key": pub_key,
                })
                suggested_key = pub_key
                status = "needs_review"
                status_reason = "source_key_mismatch"
                priority = max(priority, 95.0)

    # Signal 3: Explanation contradicts stored answer key
    expl_result = check_explanation(question)
    if expl_result.get("status") == STATES_OTHER:
        stated = valid_key(expl_result.get("stated_key"))
        signals.append({
            "code": "explanation_states_other",
            "severity": "critical",
            "detail": f"Explanation explicitly states option {stated} is correct ({expl_result.get('method')}: {expl_result.get('excerpt')[:120]}), contradicting stored key {current_key}.",
            "stated_key": stated,
        })
        if not suggested_key and stated:
            suggested_key = stated
        status = "needs_review"
        status_reason = "explanation_states_other"
        priority = max(priority, 100.0)

    # Signal 4: Systematic default key (NEET PG / INI-CET 2025 parser anomaly)
    exam_tag = getattr(question, "exam_type", "") or ""
    year_tag = getattr(question, "year", None)
    if current_key == "A" and ((exam_tag == "neet_pg" and year_tag == 2025) or (exam_tag == "ini_cet" and year_tag == 2025)):
        signals.append({
            "code": "systematic_default_key",
            "severity": "high",
            "detail": f"Question is from {exam_tag} {year_tag} where >90% of questions were keyed 'A' by the importer vote parser.",
        })
        if status != "needs_review":
            status = "needs_review"
            status_reason = "systematic_default_key"
        priority = max(priority, 80.0)

    # Signal 5: Student dispute or review flags
    if getattr(question, "is_disputed", False):
        signals.append({
            "code": "is_disputed",
            "severity": "medium",
            "detail": "Question is flagged as disputed by student reports.",
        })
        if status != "needs_review":
            status = "needs_review"
            status_reason = "is_disputed"
        priority = max(priority, 60.0)

    if getattr(question, "needs_review", False):
        signals.append({
            "code": "needs_review_flag",
            "severity": "low",
            "detail": "Question has needs_review flag set.",
        })
        if status == "likely_correct":
            status = "needs_review"
            status_reason = "needs_review_flag"
        priority = max(priority, 30.0)

    # Signal 6: Image required but missing
    text_to_check = f"{question.question_text} {question.explanation}".lower()
    references_image = any(k in text_to_check for k in ("given image", "refer to image", "shown in image", "identify the image", "in the photograph", "following histology"))
    has_image = QuestionImage.objects.filter(question=question).exists()
    if references_image and not has_image:
        signals.append({
            "code": "image_context_missing",
            "severity": "high",
            "detail": "Question text references an image or photograph, but no QuestionImage is attached.",
        })
        status = "image_context_missing"
        status_reason = "image_context_missing"
        priority = max(priority, 65.0)

    # Verified status if verified by staff
    if getattr(question, "answer_key_status", "") == "verified" or getattr(question, "verified_at", None):
        status = "verified"
        status_reason = "staff_verified"
        priority = 0.0

    # Save or update QuestionAudit record
    audit, _created = QuestionAudit.objects.update_or_create(
        question=question,
        defaults={
            "status": status,
            "status_reason": status_reason,
            "stored_key": current_key,
            "original_key": getattr(question, "original_key", current_key) or current_key,
            "key_provenance": "import",
            "suggested_key": suggested_key,
            "confidence": 0.95 if (suggested_key and source_info) else (0.8 if status == "likely_correct" else 0.4),
            "priority": priority,
            "signals": signals,
            "reviews": list(reviews or []),
            "evidence_summary": evidence_summary,
            "method_version": "v1.0-deterministic",
            "is_stale": False,
            "audited_at": timezone.now(),
        },
    )
    return audit


def key_status_for(question_ids: Iterable[int]) -> dict[int, str]:
    """Fast lookup of audit key statuses for a list of question IDs."""
    qs = QuestionAudit.objects.filter(question_id__in=list(question_ids)).values("question_id", "status")
    return {row["question_id"]: row["status"] for row in qs}

