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
- Stored content first (admin / curated / previously generated fields),
  then the cache, then -- only when the caller allows it -- one LLM call.
- ``fallback=False`` (what the API uses) returns ``None`` when there is no
  genuine content, so the reveal panel hides the section instead of
  showing template boilerplate as if it were an expert explanation. The
  default ``fallback=True`` keeps the old offline template strings for
  direct callers.
- ``allow_ai`` may be a bool or a zero-argument callable (see
  ``generation_gate``) evaluated right before a real LLM call, so a
  per-user generation budget is only spent on actual generations.
- Persists genuine AI output to the empty ``Question.ai_*`` fields (never
  overwrites curated content, never persists failure text).
- Cached in `django.core.cache` keyed on question + feature so the same
  question's "concept" only consumes 1 token across all users.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count
from django.utils import timezone

LOG = logging.getLogger(__name__)

CACHE_TTL = 60 * 60 * 24  # 24h — feature-level memo

# Default per-user budget of NEW per-question LLM generations per hour
# (stored / cached content is free). Override with
# settings.AI_PER_QUESTION_HOURLY_LIMIT.
DEFAULT_GENERATION_HOURLY_LIMIT = 60


# ---------- failure detection (shared) -------------------------------------

# Text the provider rotation / older code paths returned *instead of* an
# answer. Never shown or persisted as content.
_FAILURE_MARKERS = (
    "all ai services are temporarily unavailable",
    "ai explanation unavailable",
    "ai service temporarily unavailable",
    "ai service is temporarily unavailable",
    "regenerated ai explanation placeholder",
)


def usable_ai_text(raw) -> str:
    """``raw`` stripped, or ``""`` when it is empty or a provider-failure /
    outage payload (``AIService._call_ai`` used to *return* the sentence
    "All AI services are temporarily unavailable..." instead of raising)."""
    if raw is None:
        return ""
    text = (raw if isinstance(raw, str) else str(raw)).strip()
    if not text:
        return ""
    lowered = text.lower()
    if any(marker in lowered for marker in _FAILURE_MARKERS):
        return ""
    try:  # same phrase list AIService._looks_like_provider_error_response uses
        from ai_engine.services import _PROVIDER_ERROR_PHRASES
        if any(phrase in lowered for phrase in _PROVIDER_ERROR_PHRASES):
            return ""
    except Exception:  # pragma: no cover - defensive
        pass
    try:  # newer ai_engine builds ship a shared outage detector
        from ai_engine.offline import is_unusable_text
        if is_unusable_text(text) is True:
            return ""
    except Exception:
        pass
    return text


def usable_explain_result(result) -> bool:
    """True when an ``AIService.explain_after_answer`` result is real
    structured content that may be persisted.

    Rejects the unparsed final fallback (it carries ``raw_response``, and
    its ``why_correct`` is the truncated raw reply -- often the outage
    sentence), ``_failed`` results and results without usable text.
    """
    if not isinstance(result, dict) or result.get("_failed") or "raw_response" in result:
        return False
    return bool(
        usable_ai_text(result.get("why_correct"))
        or usable_ai_text(result.get("core_concept"))
        or usable_ai_text(result.get("analysis"))
    )


# ---------- generation gate ------------------------------------------------

def generation_gate(user, *, unlimited: bool = False):
    """``allow_ai`` for an authenticated caller.

    Returns ``True`` for unlimited callers (admins / staff), otherwise a
    callable that spends one unit of the user's hourly generation budget
    and says whether this generation may proceed.
    """
    if unlimited:
        return True
    user_id = getattr(user, "pk", None)
    if user_id is None:
        return False

    def _gate() -> bool:
        limit = int(getattr(settings, "AI_PER_QUESTION_HOURLY_LIMIT", DEFAULT_GENERATION_HOURLY_LIMIT))
        if limit <= 0:
            return False
        key = f"ai_per_q_budget:{user_id}:{timezone.now():%Y%m%d%H}"
        try:
            cache.add(key, 0, 60 * 60)
            used = cache.incr(key)
        except Exception:  # pragma: no cover - cache backend hiccup
            return False
        if used > limit:
            LOG.info("per-question AI generation budget exhausted for user=%s", user_id)
            return False
        return True

    return _gate


def _may_generate(allow_ai) -> bool:
    if callable(allow_ai):
        try:
            return bool(allow_ai())
        except Exception:  # pragma: no cover - defensive
            return False
    return bool(allow_ai)


def _q_id(q):
    return getattr(q, "id", None) or (q.get("id") if isinstance(q, dict) else None)


def _ai_call(prompt: str, max_tokens: int = 220) -> str:
    """Call the shared `AIService` provider rotation.

    Returns ``""`` when every provider failed (or returned a provider-error
    payload) so callers fall back *without* persisting anything.
    """
    try:
        from ai_engine.services import AIService
        out = (AIService()._call_ai(prompt, temperature=0.4, max_tokens=max_tokens) or "").strip()
    except Exception as e:  # pragma: no cover - defensive (AIUnavailable etc.)
        LOG.warning("AI call failed, no content generated: %s", e)
        return ""
    return usable_ai_text(out)


def _stored(q, field: str) -> str:
    """Return a non-empty, usable stored AI/admin field for ``q`` (or ``""``).

    Older regenerate / backfill runs persisted the provider-outage sentence
    into ``ai_*`` fields; such values are treated as empty.
    """
    if isinstance(q, dict):
        return usable_ai_text(q.get(field))
    return usable_ai_text(getattr(q, field, ""))


def _stored_explain_json(q) -> dict:
    """The structured ``explain_after_answer`` result stored in
    ``ai_explanation`` (by the AI cache task / backfill), if any."""
    raw = q.get("ai_explanation") if isinstance(q, dict) else getattr(q, "ai_explanation", "")
    raw = (raw or "").strip()
    if not raw.startswith("{"):
        return {}
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    if not isinstance(data, dict) or data.get("_failed") or "raw_response" in data:
        return {}
    return data


# ---------- template fallbacks (offline-safe, direct callers only) ---------

_FALLBACK = {
    "concept":                "Core concept: review the textbook chapter covering the stem's keywords.",
    "why_correct":            "The correct option matches the canonical guideline / definition referenced by the question stem.",
    "clinical_significance":  "Clinically relevant: appears in viva voce and INI-CET short cases.",
    "memory_trick":          "Mnemonic: look for the first-letter pattern across the four options.",
    "exam_importance":        "Medium-high yield; appears in ≥2 PYQs over the last 5 years.",
}


def _fallback(feature: str, fallback: bool):
    return _FALLBACK[feature] if fallback else None


def _correct_letter(q):
    if isinstance(q, dict):
        return q.get("correct_answer") or "A"
    return getattr(q, "correct_answer", None) or "A"


def _stem_text(q):
    if isinstance(q, dict):
        return q.get("question_text") or q.get("stem") or ""
    return getattr(q, "question_text", "") or ""


# ---------- per-feature impls --------------------------------------------

def concept(q, allow_ai=False, *, fallback: bool = True):
    cid = _q_id(q)
    if cid is None:
        return _fallback("concept", fallback)
    stored = usable_ai_text(_stored_explain_json(q).get("core_concept"))
    if stored:
        return stored
    cached = cache.get(_k(cid, "concept"))
    if cached:
        return cached
    if not _may_generate(allow_ai):
        return _fallback("concept", fallback)
    prompt = (f"In one short clause, name the underlying concept for this "
              f"NEET-PG question:\n\nQ: {_stem_text(q)}\n\nConcept:")
    out = _ai_call(prompt, max_tokens=64)
    if not out:
        return _fallback("concept", fallback)
    cache.set(_k(cid, "concept"), out, CACHE_TTL)
    return out


def why_correct(q, options: list[str] | None = None, allow_ai=False, *, fallback: bool = True):
    cid = _q_id(q)
    if cid is None:
        return _fallback("why_correct", fallback)
    stored = (
        _stored(q, "ai_answer")
        or _stored(q, "why_correct")
        or usable_ai_text(_stored_explain_json(q).get("why_correct"))
    )
    if stored:
        return stored
    cached = cache.get(_k(cid, "why_correct"))
    if cached:
        return cached
    if not _may_generate(allow_ai):
        return _fallback("why_correct", fallback)
    correct = _correct_letter(q)
    opts = options or _options(q)
    correct_text = ""
    if opts:
        idx = "ABCD".index(correct.upper()) if correct.upper() in "ABCD" else 0
        correct_text = opts[idx] if 0 <= idx < len(opts) else ""
    prompt = (f"Why is option {correct} correct for this NEET-PG question?\n\n"
              f"Q: {_stem_text(q)}\nOption {correct}: {correct_text}\n"
              f"Reason (2-3 lines):")
    out = _ai_call(prompt, max_tokens=220)
    if not out:
        return _fallback("why_correct", fallback)
    cache.set(_k(cid, "why_correct"), out, CACHE_TTL)
    _persist_ai_field(q, "ai_answer", out)
    return out


def _stored_why_incorrect(q) -> str:
    """Genuine per-distractor reasons: the curated ``why_wrong_*`` fields
    (admin AI generation), else the ``why_wrong`` map of a stored
    ``explain_after_answer`` result."""
    correct = (_correct_letter(q) or "").upper()[:1]
    opts = _options(q)
    lines = []
    for i, letter in enumerate("ABCD"):
        if letter == correct:
            continue
        reason = _stored(q, f"why_wrong_{letter.lower()}")
        if reason:
            label = (opts[i] or "")[:80] if i < len(opts) else ""
            lines.append(f"{letter}: {label} — {reason}" if label else f"{letter}: {reason}")
    if lines:
        return "\n".join(lines)
    why_wrong = _stored_explain_json(q).get("why_wrong")
    if isinstance(why_wrong, dict):
        for letter in "ABCD":
            if letter == correct:
                continue
            reason = usable_ai_text(why_wrong.get(letter) or why_wrong.get(letter.lower()))
            if reason:
                lines.append(f"{letter}: {reason}")
    return "\n".join(lines)


def why_incorrect(q, options: list[str] | None = None, *, fallback: bool = True):
    """Why each distractor fails. Only genuine stored content is returned
    with ``fallback=False``; the default keeps the old template text."""
    cid = _q_id(q)
    if cid is None:
        return ("Each wrong distractor fails because it does not satisfy the canonical "
                "definition referenced by the stem.") if fallback else None
    stored = _stored_why_incorrect(q)
    if stored:
        return stored
    if not fallback:
        return None
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


def clinical_significance(q, allow_ai=False, *, fallback: bool = True):
    cid = _q_id(q)
    if cid is None:
        return _fallback("clinical_significance", fallback)
    stored = _stored(q, "ai_clinical_pearl") or usable_ai_text(_stored_explain_json(q).get("clinical_pearl"))
    if stored:
        return stored
    cached = cache.get(_k(cid, "clinical_significance"))
    if cached:
        return cached
    if not _may_generate(allow_ai):
        return _fallback("clinical_significance", fallback)
    prompt = (f"Explain the clinical significance of this NEET-PG concept in 2 sentences:\n\n"
              f"Q: {_stem_text(q)}\nSignificance:")
    out = _ai_call(prompt, max_tokens=140)
    if not out:
        return _fallback("clinical_significance", fallback)
    cache.set(_k(cid, "clinical_significance"), out, CACHE_TTL)
    _persist_ai_field(q, "ai_clinical_pearl", out)
    return out


def memory_trick(q, allow_ai=False, *, fallback: bool = True):
    cid = _q_id(q)
    if cid is None:
        return _fallback("memory_trick", fallback)
    stored = (
        _stored(q, "admin_mnemonic_override")
        or _stored(q, "ai_mnemonic")
        or _stored(q, "mnemonic")
    )
    if stored:
        return stored
    cached = cache.get(_k(cid, "memory_trick"))
    if cached:
        return cached
    if not _may_generate(allow_ai):
        return _fallback("memory_trick", fallback)
    prompt = (f"Give a 1-line mnemonic or memory trick to recall the answer "
              f"to:\n\nQ: {_stem_text(q)}\nMnemonic:")
    out = _ai_call(prompt, max_tokens=80)
    if not out:
        return _fallback("memory_trick", fallback)
    cache.set(_k(cid, "memory_trick"), out, CACHE_TTL)
    _persist_ai_field(q, "ai_mnemonic", out)
    return out


def related_pyqs(q, limit: int = 8):
    """Return a small list of related PYQs as dicts (id, year, subject, stem).

    Only active questions. The concept bucket is skipped when the question
    has no concept id (``concept_id=''`` used to match every question with
    an empty concept id, i.e. the newest unrelated questions).
    """
    cid = _q_id(q)
    if cid is None:
        return []
    limit = max(1, int(limit or 8))
    from questions.models import Question
    fields = ("id", "year", "session", "question_text", "subject_id", "topic_id")
    cached = cache.get(_k(cid, f"related_pyqs:{limit}"))
    if cached is not None:
        # Drop rows archived / removed since they were cached.
        active_ids = set(
            Question.objects.filter(id__in=[row["id"] for row in cached], is_active=True)
            .values_list("id", flat=True)
        )
        return [row for row in cached if row["id"] in active_ids]
    base = Question.objects.filter(is_active=True).exclude(id=cid)
    out = []
    concept_key = (getattr(q, "concept_id", None) or "").strip() if not isinstance(q, dict) else (q.get("concept_id") or "").strip()
    if concept_key:
        cand = base.filter(concept_id=concept_key).order_by("-year")[:limit]
        out = list(cand.values(*fields))
    if len(out) < limit:
        # Fallback to text token overlap
        stem = (_stem_text(q) or "").lower()
        tokens = [t for t in stem.split() if len(t) >= 4][:5]
        if tokens:
            extra = base
            for tok in tokens:
                extra = extra.filter(question_text__icontains=tok)
            extra = extra.exclude(id__in=[o["id"] for o in out]).order_by("-year")[: limit - len(out)]
            out.extend(list(extra.values(*fields)))
    cache.set(_k(cid, f"related_pyqs:{limit}"), out, CACHE_TTL)
    return out


def related_topics(q, limit: int = 8):
    cid = _q_id(q)
    if cid is None:
        return []
    limit = max(1, int(limit or 8))
    cached = cache.get(_k(cid, f"related_topics:{limit}"))
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
    cache.set(_k(cid, f"related_topics:{limit}"), out, CACHE_TTL)
    return out


def exam_importance(q, *, fallback: bool = True):
    """Crude yield score from how many active questions share the concept.

    Without a concept id there is no signal: ``fallback=False`` returns
    ``None`` (the old fixed 30/100 looked like a real measurement).
    """
    cid = _q_id(q)
    if cid is None:
        return 50 if fallback else None
    concept_key = (getattr(q, "concept_id", None) or "").strip() if not isinstance(q, dict) else (q.get("concept_id") or "").strip()
    if not concept_key and not fallback:
        return None
    cached = cache.get(_k(cid, "exam_importance"))
    if cached is not None:
        return cached
    from questions.models import Question
    score = 30
    if concept_key:
        cluster = Question.objects.filter(concept_id=concept_key, is_active=True).count()
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
    """Store genuine AI output on the Question row -- only while the field
    is still empty, so admin-curated or previously generated content is
    never overwritten by a student-triggered request."""
    value = usable_ai_text(value)
    if not value:
        return
    try:
        from questions.models import Question
        qid = _q_id(q)
        if qid is None:
            return
        updated = Question.objects.filter(pk=qid, **{field: ""}).update(
            **{field: value, "ai_generated_at": timezone.now()}
        )
        if updated and not isinstance(q, dict):
            setattr(q, field, value)
    except Exception as e:  # pragma: no cover - defensive
        LOG.debug("Persist AI field failed (%s): %s", field, e)
