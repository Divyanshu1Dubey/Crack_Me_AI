"""Explain a selected option for a question using verified evidence first (2026-11).

docs/audit/MEDICAL_ACCURACY_DESIGN.md section 4 (editor group):

* Ground rule 3, evidence first, key second: ``reference_corpus.api.decide`` scores every option
  from the reference passages without looking at the key, then compares. When the evidence supports
  another option the suggestion is a ``conflict`` and carries no text: an explanation is never
  written for an option the evidence contradicts (``acknowledge_conflict`` only adds the passages
  retrieved for the selected option, for the admin to read). Weak evidence gives
  ``insufficient_evidence`` and no text; so does a server without a reference store
  (``retrieval_mode='none'``).
* Ground rule 2, AI output is never a source: the suggestion is extractive. Its text quotes stored
  passages (at most ``QUOTE_MAX_CHARS`` each) with the passage's own title and page; no model writes
  a book, chapter, page or quote.
* ``fields`` only ever holds explanation text an admin may accept into the editor (the explanation
  fields ``questions.editorial.save_explanation`` writes). Status messages are not stored in it.

The outcome is an ``ExplanationSuggestion`` (status ok | conflict | insufficient_evidence |
image_context_missing | failed); ``model`` records the retrieval mode the decision used.
"""
from __future__ import annotations

import logging
from typing import Any

from django.core.exceptions import ValidationError

from questions.content_hashes import stem_hash, valid_key
from questions.image_context import image_context
from questions.models import ExplanationSuggestion, Question
from reference_corpus import api as ref_api

logger = logging.getLogger("questions.explain_option")

# Unsaved editor values a request may lay over the stored question (image_context reads the same).
DRAFT_FIELDS = ("question_text", "option_a", "option_b", "option_c", "option_d",
                "explanation", "concept_explanation", "mnemonic", "is_image_based", "question_type")
QUOTE_MAX_CHARS = 240
MAX_QUOTES = 2
_PROVIDER = "reference_corpus"


class _Draft:
    """The question with the editor's unsaved values laid over it (read-only)."""

    __slots__ = ("_question", "_draft")

    def __init__(self, question, draft):
        self._question = question
        self._draft = draft

    def __getattr__(self, name):
        draft = object.__getattribute__(self, "_draft")
        if name in draft:
            return draft[name]
        return getattr(object.__getattribute__(self, "_question"), name)


def clean_draft(draft: dict[str, Any] | None) -> dict[str, Any]:
    """Only the known draft fields; text fields must be strings, ``is_image_based`` a boolean."""
    out: dict[str, Any] = {}
    for name, value in (draft or {}).items():
        if name not in DRAFT_FIELDS:
            continue
        if name == "is_image_based":
            if isinstance(value, bool):
                out[name] = value
        elif isinstance(value, str):
            out[name] = value
    return out


def clip_quote(text: str, max_chars: int = QUOTE_MAX_CHARS) -> str:
    """``text`` on one line, cut at a word boundary to at most ``max_chars`` (ellipsis included)."""
    text = " ".join((text or "").split())
    if len(text) <= max_chars:
        return text
    cut = text[: max_chars - 1]
    if " " in cut[int(max_chars * 0.6):]:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(" ,;:") + "…"


def _page_label(citation: dict) -> str:
    page = citation.get("page")
    if isinstance(page, int) and page > 0:
        return f"PDF p. {page}"
    if isinstance(page, str) and page.strip():
        return f"PDF p. {page.strip()[:16]}"
    return ""


def clean_citations(rows) -> list[dict]:
    """The decision's passages as stored by the suggestion: retrieved store passages only
    (chunk key, title, page, tier, a quote of at most ``QUOTE_MAX_CHARS``)."""
    out = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        snippet = clip_quote(str(row.get("snippet") or row.get("text") or ""))
        chunk_key = str(row.get("chunk_key") or "")[:160]
        if not snippet or not chunk_key:
            continue
        tier = row.get("tier")
        out.append({
            "chunk_key": chunk_key,
            "source_title": " ".join(str(row.get("source_title") or "").split())[:300] or "Reference",
            "page": row.get("page") if isinstance(row.get("page"), (int, str)) else None,
            "page_label": _page_label(row),
            "tier": tier if isinstance(tier, int) else None,
            "snippet": snippet,
        })
    return out


def _option_evidence(per_option) -> dict:
    out = {}
    for letter in ("A", "B", "C", "D"):
        row = (per_option or {}).get(letter) or {}
        try:
            support = round(float(row.get("support") or 0.0), 3)
            contradiction = round(float(row.get("contradiction") or 0.0), 3)
        except (TypeError, ValueError):
            support, contradiction = 0.0, 0.0
        out[letter] = {"support": support, "contradiction": contradiction,
                       "citations": clean_citations(row.get("citations"))}
    return out


def _extractive_explanation(letter: str, option_text: str, citations: list[dict]) -> str:
    """Quotes of the passages that support ``letter``, each with its title and page."""
    head = f"Option {letter}"
    option_text = " ".join((option_text or "").split())
    if option_text:
        head += f" ({clip_quote(option_text, 120)})"
    lines = [f"{head}: reference passages"]
    for citation in citations[:MAX_QUOTES]:
        where = ", ".join(p for p in (citation["source_title"], citation["page_label"]) if p)
        lines.append(f"“{citation['snippet']}” ({where})")
    return "\n\n".join(lines)


def _suggestion(question, *, actor, letter, draft, view, status, img_ctx, retrieval_mode, fields=None,
                field_citations=None, citations=None, option_evidence=None, conflict=None):
    return ExplanationSuggestion.objects.create(
        question=question,
        requested_by=actor if getattr(actor, "is_authenticated", False) else None,
        for_key=letter,
        stored_key=valid_key(question.correct_answer),
        draft_stem_hash=stem_hash(view),
        used_draft=bool(draft),
        mode="extractive",
        provider=_PROVIDER,
        model=(retrieval_mode or "none")[:120],
        status=status,
        fields=fields or {},
        field_citations=field_citations or {},
        citations=citations or [],
        dropped_claims=[],
        option_evidence=option_evidence or {},
        conflict=conflict,
        image_context=img_ctx,
    )


def explain_selected_option(
    question: Question,
    *,
    selected: str,
    draft: dict[str, Any] | None = None,
    actor=None,
    acknowledge_conflict: bool = False,
) -> ExplanationSuggestion:
    """An evidence-first explanation suggestion for option ``selected``.

    Args:
        question: The Question instance.
        selected: The option letter ('A', 'B', 'C', or 'D').
        draft: Unsaved editor values (``DRAFT_FIELDS``) to check instead of the stored ones.
        actor: The requesting user (admin/staff).
        acknowledge_conflict: On a conflict, also return the passages retrieved for ``selected``.
            Never produces text for an option the evidence contradicts.

    Returns:
        ExplanationSuggestion instance (nothing is written to the question).
    """
    clean_key = valid_key(selected)
    if not clean_key or (selected or "").strip().upper() != clean_key:
        raise ValidationError(f"Invalid option letter: {selected!r}. Must be A, B, C, or D.")
    draft = clean_draft(draft)
    view = _Draft(question, draft) if draft else question
    common = {"actor": actor, "letter": clean_key, "draft": draft, "view": view}

    # 1. A question that depends on a figure nobody can see is not explained.
    img_ctx = image_context(question, draft=draft or None)
    if img_ctx.get("required") and not img_ctx.get("available"):
        return _suggestion(question, status="image_context_missing", img_ctx=img_ctx, retrieval_mode="none", **common)

    # 2. Evidence first: the decision scores every option from the reference passages.
    stored = valid_key(getattr(view, "correct_answer", ""))
    try:
        decision = ref_api.decide(view, stored_key=stored, selected_key=clean_key, purpose="editor_explain",
                                  actor=actor)
    except Exception as exc:  # noqa: BLE001 - a broken store must not become a 500 or a made-up answer
        logger.warning("explain-option: evidence decision failed for question %s (%s)", question.pk,
                       type(exc).__name__)
        return _suggestion(question, status="failed", img_ctx=img_ctx, retrieval_mode="error", **common)
    if not isinstance(decision, dict):
        return _suggestion(question, status="failed", img_ctx=img_ctx, retrieval_mode="error", **common)

    retrieval_mode = str(decision.get("retrieval_mode") or "none")
    dec_status = decision.get("status") or "insufficient_evidence"
    evidence_answer = valid_key(decision.get("evidence_answer"))
    option_evidence = _option_evidence(decision.get("per_option"))
    try:
        margin = round(float(decision.get("margin") or 0.0), 3)
    except (TypeError, ValueError):
        margin = 0.0
    common.update(img_ctx=img_ctx, retrieval_mode=retrieval_mode, option_evidence=option_evidence)
    if dec_status == "image_context_missing":
        return _suggestion(question, status="image_context_missing", **common)

    # 3. The evidence names another option: a conflict, never a justification of the selected one.
    if dec_status == "conflict" and evidence_answer and evidence_answer != clean_key:
        conflict = {
            "evidence_supports": evidence_answer,
            "selected": clean_key,
            "stored": stored,
            "margin": margin,
            "summary": (f"The reference passages support option {evidence_answer}, not option {clean_key} "
                        f"(support margin {margin:.2f}). No explanation is suggested for option {clean_key}."),
            "acknowledged": bool(acknowledge_conflict),
        }
        # The passages behind the evidence answer, so the admin can read why; with the
        # acknowledgement also the (weaker) passages retrieved for the selected option.
        citations = clean_citations(decision.get("citations")) or option_evidence[evidence_answer]["citations"]
        if acknowledge_conflict:
            seen = {c["chunk_key"] for c in citations}
            citations = citations + [c for c in option_evidence[clean_key]["citations"] if c["chunk_key"] not in seen]
        return _suggestion(question, status="conflict", citations=citations, conflict=conflict, **common)

    # 4. Weak evidence (or no reference store on this server): abstain.
    if dec_status != "supported" or evidence_answer != clean_key:
        return _suggestion(question, status="insufficient_evidence", **common)

    # 5. Supported: quote the passages (extractive; the admin edits before saving).
    citations = clean_citations(decision.get("citations")) or option_evidence[clean_key]["citations"]
    if not citations:
        return _suggestion(question, status="insufficient_evidence", **common)
    option_text = getattr(view, f"option_{clean_key.lower()}", "") or ""
    quoted = citations[:MAX_QUOTES]
    return _suggestion(
        question, status="ok",
        fields={"explanation": _extractive_explanation(clean_key, option_text, quoted)},
        field_citations={"explanation": [c["chunk_key"] for c in quoted]},
        citations=citations, **common,
    )
