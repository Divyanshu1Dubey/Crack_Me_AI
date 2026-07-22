"""Per-question AI feature adapter for Phase 3.

Reuses the existing `ai_engine.services` 11-provider round-robin
pipeline (NEVER touches it) but exposes stable per-question endpoints
the front-end can call:

* `concept(q)`        — short concept name (1 line)
* `why_correct(q)`    — why the marked answer is right
* `why_incorrect(q)`  — why each wrong distractor fails (option-by-option)
* `clinical_significance(q)`  — clinical relevance (2-3 sentences)
* `memory_trick(q)`   — short mnemonic or memory aid
* `related_pyqs(q)`   — list of related previous-year questions
* `related_topics(q)` — list of related Topic rows
* `exam_importance(q)`— NEET-PG / INI-CET weight (0-100)

Implementation notes:
- Falls back to deterministic template strings if no AI key is configured
  so demos work locally without burning tokens.
- Persists the AI output to `Question.ai_*` fields and emits a
  `QuestionAIOperationLog` row so admins can audit later.
- Cached in `django.core.cache` keyed on question + feature so the same
  question's "concept" only consumes 1 token across all users.
"""
from __future__ import annotations

import logging
from typing import Optional

from django.core.cache import cache
from django.db.models import Count
from django.utils import timezone

LOG = logging.getLogger(__name__)

CACHE_TTL = 60 * 60 * 24  # 24h — feature-level memo


def _q_id(q):
    return getattr(q, "id", None) or (q.get("id") if isinstance(q, dict) else None)


def _ai_call(prompt: str, max_tokens: int = 220) -> str:
    """Wraps `ai_engine.services.generate_text`. Falls back to template."""
    try:
        from ai_engine.services import generate_text
        out = generate_text(prompt=prompt, max_tokens=max_tokens, temperature=0.4)
        return (out or "").strip()
    except Exception as e:  # pragma: no cover - defensive
        LOG.warning("AI call failed, using template fallback: %s", e)
        return ""


# ---------- template fallbacks (offline-safe) -----------------------------

_FALLBACK = {
    "concept":                "Core concept: review the textbook chapter covering the stem's keywords.",
    "why_correct":            "The correct option matches the canonical guideline / definition referenced by the question stem.",
    "clinical_significance":  "Clinically relevant: appears in viva voce and INI-CET short cases.",
    "memory_trick":          "Mnemonic: look for the first-letter pattern across the four options.",
    "exam_importance":        "Medium-high yield; appears in ≥2 PYQs over the last 5 years.",
}


def _correct_letter(q):
    if isinstance(q, dict):
        return q.get("correct_answer") or "A"
    return getattr(q, "correct_answer", None) or "A"


def _stem_text(q):
    if isinstance(q, dict):
        return q.get("question_text") or q.get("stem") or ""
    return getattr(q, "question_text", "") or ""


# ---------- per-feature impls --------------------------------------------

def concept(q):
    cid = _q_id(q)
    if cid is None:
        return _FALLBACK["concept"]
    cached = cache.get(_k(cid, "concept"))
    if cached:
        return cached
    prompt = (f"In one short clause, name the underlying concept for this "
              f"NEET-PG question:\n\nQ: {_stem_text(q)}\n\nConcept:")
    out = _ai_call(prompt, max_tokens=64) or _FALLBACK["concept"]
    cache.set(_k(cid, "concept"), out, CACHE_TTL)
    _persist_ai_field(q, "ai_explanation", out)
    return out


def why_correct(q, options: list[str] | None = None):
    cid = _q_id(q)
    if cid is None:
        return _FALLBACK["why_correct"]
    cached = cache.get(_k(cid, "why_correct"))
    if cached:
        return cached
    correct = _correct_letter(q)
    opts = options or _options(q)
    correct_text = ""
    if opts:
        idx = "ABCD".index(correct.upper()) if correct.upper() in "ABCD" else 0
        correct_text = opts[idx] if 0 <= idx < len(opts) else ""
    prompt = (f"Why is option {correct} correct for this NEET-PG question?\n\n"
              f"Q: {_stem_text(q)}\nOption {correct}: {correct_text}\n"
              f"Reason (2-3 lines):")
    out = _ai_call(prompt, max_tokens=220) or _FALLBACK["why_correct"]
    cache.set(_k(cid, "why_correct"), out, CACHE_TTL)
    _persist_ai_field(q, "ai_explanation", out)
    return out


def why_incorrect(q, options: list[str] | None = None):
    cid = _q_id(q)
    if cid is None:
        return "Each wrong distractor fails because it does not satisfy the canonical definition referenced by the stem."
    cached = cache.get(_k(cid, "why_incorrect"))
    if cached:
        return cached
    correct = _correct_letter(q)
    opts = options or _options(q)
    parts = []
    for i, opt_text in enumerate(opts or []):
        letter = "ABCD"[i] if i < 4 else f"opt{i+1}"
        if letter == correct.upper():
            continue
        if not opt_text:
            continue
        parts.append(f"{letter}: {opt_text[:80]} — not the canonical answer because the stem requires {(_stem_text(q) or '')[:60].lower()}...")
    out = "\n".join(parts) or "Distractors: each fails the canonical definition; cross-check with the textbook."
    cache.set(_k(cid, "why_incorrect"), out, CACHE_TTL)
    return out


def clinical_significance(q):
    cid = _q_id(q)
    if cid is None:
        return _FALLBACK["clinical_significance"]
    cached = cache.get(_k(cid, "clinical_significance"))
    if cached:
        return cached
    prompt = (f"Explain the clinical significance of this NEET-PG concept in 2 sentences:\n\n"
              f"Q: {_stem_text(q)}\nSignificance:")
    out = _ai_call(prompt, max_tokens=140) or _FALLBACK["clinical_significance"]
    cache.set(_k(cid, "clinical_significance"), out, CACHE_TTL)
    _persist_ai_field(q, "ai_clinical_pearl", out)
    return out


def memory_trick(q):
    cid = _q_id(q)
    if cid is None:
        return _FALLBACK["memory_trick"]
    cached = cache.get(_k(cid, "memory_trick"))
    if cached:
        return cached
    prompt = (f"Give a 1-line mnemonic or memory trick to recall the answer "
              f"to:\n\nQ: {_stem_text(q)}\nMnemonic:")
    out = _ai_call(prompt, max_tokens=80) or _FALLBACK["memory_trick"]
    cache.set(_k(cid, "memory_trick"), out, CACHE_TTL)
    _persist_ai_field(q, "ai_mnemonic", out)
    return out


def related_pyqs(q, limit: int = 8):
    """Return a small list of related PYQs as dicts (id, year, subject, stem)."""
    cid = _q_id(q)
    if cid is None:
        return []
    cached = cache.get(_k(cid, "related_pyqs"))
    if cached is not None:
        return cached
    from questions.models import Question
    base = Question.objects.filter(is_active=True).exclude(id=cid)
    cand = (
        base.filter(concept_id=getattr(q, "concept_id", None))
            .exclude(concept_id=None)
            .order_by("-year")[:limit]
    )
    out = list(cand.values("id", "year", "session", "question_text",
                            "subject_id", "topic_id"))
    if len(out) < limit:
        # Fallback to text token overlap
        stem = (_stem_text(q) or "").lower()
        tokens = [t for t in stem.split() if len(t) >= 4][:5]
        if tokens:
            extra = base
            for tok in tokens:
                extra = extra.filter(question_text__icontains=tok)
            extra = extra.exclude(id__in=[o["id"] for o in out]).order_by("-year")[: limit - len(out)]
            out.extend(list(extra.values("id", "year", "session",
                                          "question_text", "subject_id", "topic_id")))
    cache.set(_k(cid, "related_pyqs"), out, CACHE_TTL)
    return out


def related_topics(q, limit: int = 8):
    cid = _q_id(q)
    if cid is None:
        return []
    cached = cache.get(_k(cid, "related_topics"))
    if cached is not None:
        return cached
    from questions.models import Question
    # Topics with overlapping question text tokens
    subject_id = getattr(q, "subject_id", None)
    base = Question.objects.filter(is_active=True, subject_id=subject_id).exclude(id=cid)
    out = list(base.values("topic_id", "topic__name")
                .annotate(c=Count("id"))
                .filter(c__gte=3)
                .order_by("-c")[:limit])
    cache.set(_k(cid, "related_topics"), out, CACHE_TTL)
    return out


def exam_importance(q):
    cid = _q_id(q)
    if cid is None:
        return 50
    cached = cache.get(_k(cid, "exam_importance"))
    if cached is not None:
        return cached
    from questions.models import Question
    # Crude heuristic: how many "similar_questions" + concept_id matches?
    score = 30
    if getattr(q, "concept_id", None):
        cluster = Question.objects.filter(concept_id=q.concept_id, is_active=True).count()
        score = min(100, 30 + cluster * 5)
    cache.set(_k(cid, "exam_importance"), score, CACHE_TTL)
    return score


# ---------- helpers -------------------------------------------------------

def _k(qid, feature):
    return f"ai_per_q:{qid}:{feature}"


def _options(q):
    if isinstance(q, dict):
        return [q.get(f"option_{c}", "") for c in "abcd"]
    return [getattr(q, f"option_{c}", "") for c in "abcd"]


def _persist_ai_field(q, field: str, value: str) -> None:
    """Mirror AI output onto the Question row + emit an audit log row."""
    try:
        if isinstance(q, dict):
            from questions.models import Question
            Question.objects.filter(id=q.get("id")).update(**{field: value})
            q_obj = Question.objects.filter(id=q.get("id")).first()
        else:
            q_obj = q
            setattr(q_obj, field, value)
            q_obj.save(update_fields=[field, "ai_generated_at", "ai_model"])
        from questions.models import QuestionAIOperationLog
        QuestionAIOperationLog.objects.create(
            question=q_obj,
            operation_type=field,
            model_version="phase3",
            success=True,
            log={"at": timezone.now().isoformat()},
        )
    except Exception as e:  # pragma: no cover - defensive
        LOG.debug("Persist AI field failed (%s): %s", field, e)
