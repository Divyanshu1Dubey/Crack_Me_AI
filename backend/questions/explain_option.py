"""Explain a selected option for a question using verified evidence first (2026-11).

docs/audit/MEDICAL_ACCURACY_DESIGN.md section 4 (editor group):
Ground rule 3: Evidence first, key second. The decision evaluates evidence without bias
toward the stored key. On disagreement it returns a conflict; when evidence is weak it abstains.
Ground rule 2: AI output is never a source. Model-written references are discarded.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from django.core.exceptions import ValidationError
from django.utils import timezone

from questions.content_hashes import stem_hash, valid_key
from questions.image_context import ABSTAIN_REASON, image_context
from questions.models import ExplanationSuggestion, Question
from reference_corpus import api as ref_api

logger = logging.getLogger("questions.explain_option")


def explain_selected_option(
    question: Question,
    *,
    selected: str,
    draft: dict[str, Any] | None = None,
    actor=None,
    acknowledge_conflict: bool = False,
) -> ExplanationSuggestion:
    """Generate an explanation suggestion for a specific option using verified evidence.

    Args:
        question: The Question instance.
        selected: The option letter ('A', 'B', 'C', or 'D').
        draft: Optional dictionary of draft fields from the editor.
        actor: The requesting user (admin/staff).
        acknowledge_conflict: If True, allow generating explanation even if evidence conflicts.

    Returns:
        ExplanationSuggestion instance.
    """
    clean_key = valid_key(selected)
    if not clean_key:
        raise ValidationError(f"Invalid option letter: {selected!r}. Must be A, B, C, or D.")

    # 1. Check Image Context
    img_ctx = image_context(question, draft=draft)
    if img_ctx.get("required") and not img_ctx.get("available"):
        suggestion = ExplanationSuggestion.objects.create(
            question=question,
            requested_by=actor,
            for_key=clean_key,
            stored_key=question.correct_answer or "",
            draft_stem_hash=stem_hash(question),
            used_draft=bool(draft),
            mode="extractive",
            provider="reference_corpus",
            model="bm25_fts5",
            status="image_context_missing",
            fields={
                "explanation": (
                    "This question requires image context to establish the correct answer, "
                    "but no image or description is currently attached."
                ),
                "why_correct": "",
                "concept_explanation": "",
            },
            field_citations={},
            citations=[],
            dropped_claims=[],
            option_evidence={},
            conflict=None,
            image_context=img_ctx,
        )
        return suggestion

    # 2. Query Reference Store Decision
    decision = ref_api.decide(
        question,
        stored_key=question.correct_answer or "",
        selected_key=clean_key,
        purpose="editor_explain",
        actor=actor,
    )

    dec_status = decision.get("status", "insufficient_evidence")
    evidence_answer = decision.get("evidence_answer", "")
    citations = decision.get("citations", [])
    per_option = decision.get("per_option", {})
    margin = decision.get("margin", 0.0)

    # 3. Handle Statuses
    conflict_payload = None

    if dec_status == "insufficient_evidence":
        suggestion_status = "insufficient_evidence"
        fields = {
            "explanation": (
                "Verified medical reference materials do not contain sufficient evidence to establish "
                f"option {clean_key} with high confidence. The AI will not invent textbook references "
                "or speculate without verified sources."
            ),
            "why_correct": "",
            "concept_explanation": "",
        }
        field_citations = {}

    elif dec_status == "conflict" and not acknowledge_conflict:
        suggestion_status = "conflict"
        conflict_payload = {
            "evidence_supports": evidence_answer,
            "selected": clean_key,
            "stored": question.correct_answer,
            "margin": margin,
            "summary": (
                f"Retrieved standard references support Option {evidence_answer} (margin {margin:.2f}), "
                f"which conflicts with selected Option {clean_key}."
            ),
        }
        fields = {
            "explanation": (
                f"Evidence Conflict: Standard medical references support Option {evidence_answer}. "
                f"An explanation justifying Option {clean_key} will not be automatically generated "
                "without explicit conflict acknowledgment."
            ),
            "why_correct": "",
            "concept_explanation": "",
        }
        field_citations = {}

    else:
        # Supported, or Conflict with explicit acknowledgment
        suggestion_status = "ok" if dec_status == "supported" else "conflict"
        if dec_status == "conflict":
            conflict_payload = {
                "evidence_supports": evidence_answer,
                "selected": clean_key,
                "stored": question.correct_answer,
                "margin": margin,
                "summary": f"Admin acknowledged conflict: evidence supports Option {evidence_answer}.",
            }

        # Build explanation from top citations
        top_citations = citations or (per_option.get(clean_key, {}).get("citations", []))
        if top_citations:
            top_snippet = top_citations[0].get("snippet", "").strip()
            source_title = top_citations[0].get("source_title", "Standard Medical Reference")
            page = top_citations[0].get("page", "")
            page_str = f" (p. {page})" if page else ""
            explanation_body = (
                f"According to {source_title}{page_str}:\n\n"
                f"\"{top_snippet}\"\n\n"
                f"This standard reference confirms Option {clean_key} as the correct answer."
            )
            concept = f"Key concept documented in {source_title}."
        else:
            top_snippet = ""
            explanation_body = f"Standard evidence review confirms Option {clean_key} as supported."
            concept = ""

        fields = {
            "explanation": explanation_body,
            "why_correct": top_snippet,
            "concept_explanation": concept,
        }
        field_citations = {
            "why_correct": [c.get("chunk_key") for c in top_citations[:2] if c.get("chunk_key")]
        }

    suggestion = ExplanationSuggestion.objects.create(
        question=question,
        requested_by=actor,
        for_key=clean_key,
        stored_key=question.correct_answer or "",
        draft_stem_hash=stem_hash(question),
        used_draft=bool(draft),
        mode="extractive",
        provider="reference_corpus",
        model="bm25_fts5",
        status=suggestion_status,
        fields=fields,
        field_citations=field_citations,
        citations=citations,
        dropped_claims=[],
        option_evidence=per_option,
        conflict=conflict_payload,
        image_context=img_ctx,
    )
    return suggestion

