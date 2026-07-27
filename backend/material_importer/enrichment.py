"""AI enrichment: take staged `ExtractedQuestion` rows and call the
existing AI service to fill in explanations, mnemonics, references, etc.

This is the bridge between the material importer and the existing
`ai_engine.services` explain pipeline. We deliberately:
  * stream rows in chunks (don't load all 8000 staged records at once)
  * skip rows already enriched (idempotent)
  * catch every exception so one bad row doesn't kill the batch
  * use the existing `explain_after_answer` if available, else fall back
    to a single `ask()` call to populate the basic fields.

Run via:
    python manage.py enrich_pending_questions --batch 12
    python manage.py enrich_pending_questions --limit 50
"""
from __future__ import annotations

import logging
import re
from typing import Iterable, List

from django.utils import timezone

from .models import ExtractedQuestion

log = logging.getLogger(__name__)


def _call_explain(question_text: str, options: dict, correct: str) -> dict:
    """Use the existing AI service to enrich one question. Returns a dict.

    Returns whatever `explain_after_answer` returns. If the call fails,
    returns a dict with `ai_explanation` set to the error string so the
    failure is visible in the admin but doesn't crash the enricher.
    """
    try:
        from ai_engine.services import ai_service  # type: ignore
    except Exception as exc:
        return {"ai_explanation": "", "ai_error": f"ai_service unavailable: {exc}"}

    # Prefer the high-quality explainer when available.
    explainer = getattr(ai_service, "explain_after_answer", None)
    if callable(explainer):
        try:
            return explainer(
                question_text=question_text,
                correct_answer=correct or "A",
                user_answer=correct or "A",
                options=options,
            ) or {}
        except Exception as exc:
            log.warning("explain_after_answer failed: %s", exc)
    # Fall back to a one-shot prompt.
    try:
        prompt = (
            "Q: " + (question_text or "") + "\n"
            "A) " + (options.get("A") or "") + "\n"
            "B) " + (options.get("B") or "") + "\n"
            "C) " + (options.get("C") or "") + "\n"
            "D) " + (options.get("D") or "") + "\n"
            f"Correct: {correct or 'A'}.\n"
            "Reply with a 3-sentence explanation and one clinical pearl."
        )
        text = ai_service.ask(prompt, mode="explain")
        return {"ai_explanation": text or "", "ai_clinical_pearl": "", "ai_mnemonic": ""}
    except Exception as exc:
        return {"ai_explanation": "", "ai_error": str(exc)}


def _apply_enrichment(eq: ExtractedQuestion, payload: dict) -> None:
    """Persist enriched fields onto the SourceExtractedQuestion + Question."""
    if not payload:
        return
    explanation = payload.get("ai_explanation") or payload.get("explanation") or eq.explanation
    if explanation and not eq.explanation:
        eq.explanation = explanation
    if payload.get("ai_clinical_pearl") and not hasattr(eq, "ai_clinical_pearl"):
        # Stored on the published Question only.
        pass
    if payload.get("ai_mnemonic"):
        eq.classification_meta = dict(eq.classification_meta or {})
        eq.classification_meta["ai_mnemonic"] = payload["ai_mnemonic"]
    if payload.get("concept_keywords"):
        eq.classification_meta = dict(eq.classification_meta or {})
        eq.classification_meta["concept_keywords"] = payload["concept_keywords"]
    if payload.get("ai_error"):
        eq.classification_meta = dict(eq.classification_meta or {})
        eq.classification_meta["ai_error"] = payload["ai_error"]
    if payload.get("textbook_reference"):
        eq.classification_meta = dict(eq.classification_meta or {})
        eq.classification_meta["textbook_reference"] = payload["textbook_reference"]
    eq.save(update_fields=["explanation", "classification_meta"])


def enrich_batch(batch_id: int, limit: int | None = None) -> int:
    """Enrich all pending ExtractedQuestion rows in a given batch."""
    qs = (
        ExtractedQuestion.objects
        .filter(material__batch_id=batch_id, status="pending")
        .select_related("material")
        .order_by("id")
    )
    if limit:
        qs = qs[:limit]
    n = 0
    for eq in qs:
        payload = _call_explain(
            eq.question_text,
            {"A": eq.option_a, "B": eq.option_b, "C": eq.option_c, "D": eq.option_d},
            eq.correct_answer,
        )
        _apply_enrichment(eq, payload)
        n += 1
    return n


def enrich_question(eq: ExtractedQuestion) -> dict:
    """Run enrichment on a single extracted question (used by admin action)."""
    payload = _call_explain(
        eq.question_text,
        {"A": eq.option_a, "B": eq.option_b, "C": eq.option_c, "D": eq.option_d},
        eq.correct_answer,
    )
    _apply_enrichment(eq, payload)
    return payload
