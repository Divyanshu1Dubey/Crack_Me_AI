"""AI enrichment stub.

Designed to plug into the existing CrackCMS AI stack (Monica, Groq,
Cerebras, Gemini, …) without forcing the import path to depend on any
of them. The current implementation returns an empty dict; real
enrichment runs as a separate async job once AI keys are configured.
"""
from __future__ import annotations

import logging
from typing import Any

from .models import ParsedQuestion

LOG = logging.getLogger(__name__)


def enrich_question(question: ParsedQuestion) -> dict[str, Any]:
    """Return enrichment slots for a parsed question.

    Phase 1 (this file): empty dict, structured keys documented below.
    Phase 2: wire to ai_engine.services.ai_complete() with prompts for
    concept extraction, mnemonic generation, clinical pearl, related
    PYQs.
    """
    LOG.debug("enrich_question called for qno=%s (stub)", question.question_number_in_pdf)
    return {
        "concept": None,           # str — primary medical concept
        "mnemonic": None,          # str — memory trick
        "clinical_pearl": None,    # str — clinical relevance
        "why_correct": None,       # str — explanation of correct option
        "why_incorrect": None,     # list[str] — explanation of each wrong option
        "related_pyqs": [],        # list[int] — IDs of related canonical questions
        "exam_importance": None,   # str — "high" / "medium" / "low"
    }


__all__ = ["enrich_question"]