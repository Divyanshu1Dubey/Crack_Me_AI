"""
Monica — the citation-aware RAG orchestrator.

This is the high-level service called from views. It composes:
  1. RetrievalPipeline (hybrid search + KG + rerank)
  2. AIService from ai_engine (provider rotation) — called directly with
     Monica's own citation system prompt (not via ask_tutor, which adds the
     legacy textbook context, its own reference format and a references
     footer that contradict the numbered KB citations)
  3. Citation engine (attaches source attribution to every claim)

When the knowledge base has enough approved chunks
(``settings.KB_FALLBACK_THRESHOLD``) we use the citation-aware path.
Otherwise the context comes from the legacy textbook store
(``RAGPipeline.search``) for the SAME question — the student's question is
always what the model answers.

Failure contract: when no provider answers, ``answer()`` raises
``ai_engine.services.AIUnavailable`` with the retrieved passages attached,
so the view can refund and serve an extractive offline answer.
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional

from django.conf import settings

from knowledge_base.models import KnowledgeChunk
from knowledge_base.retrieval.pipeline import RetrievalPipeline, RetrievedChunk
from knowledge_base.ontology.loader import expand_query

logger = logging.getLogger(__name__)

KB_FALLBACK_THRESHOLD = int(getattr(settings, "KB_FALLBACK_THRESHOLD", 10))

_CITATION_MARK_RE = re.compile(r"\[(\d{1,3})\]")


def _kb_cache():
    """The dedicated ``kb_retrieval`` cache (settings), else the default."""
    from django.core.cache import caches
    try:
        return caches["kb_retrieval"]
    except Exception:
        return caches["default"]


@dataclass
class MonicaResponse:
    answer: str
    citations: list[dict]
    confidence: str
    used_kb: bool
    query_expansion: dict
    retrieval_count: int
    invalid_citations_removed: int = 0


class Monica:
    """Citation-aware RAG orchestrator."""

    SYSTEM_PROMPT = (
        "You are Monica, an AI tutor for UPSC CMS / NEET PG medical aspirants. "
        "Your answers are grounded in retrieved reference material. "
        "For every clinical claim, you MUST cite the source(s) using the "
        "inline format [1], [2], etc. matching the numbered citations below. "
        "Never invent citations. If the retrieved context does not support "
        "the answer, say so plainly. Keep answers exam-focused: define, "
        "classify, list high-yield facts, and offer a memory aid when useful."
    )

    def __init__(self, retrieval: Optional[RetrievalPipeline] = None):
        self.retrieval = retrieval or RetrievalPipeline(cache=_kb_cache())

    # ─── Retrieval ─────────────────────────────────────────

    @staticmethod
    def kb_ready() -> bool:
        """True when the KB has at least KB_FALLBACK_THRESHOLD approved
        chunks (cached for 5 minutes)."""
        threshold = int(getattr(settings, "KB_FALLBACK_THRESHOLD", KB_FALLBACK_THRESHOLD))
        if threshold <= 0:
            return True
        cache = _kb_cache()
        key = "kb:approved_chunk_count:v1"
        try:
            count = cache.get(key)
        except Exception:
            count = None
        if count is None:
            count = KnowledgeChunk.objects.filter(
                is_active=True,
                approval_state__in=[KnowledgeChunk.APPROVAL_AUTO, KnowledgeChunk.APPROVAL_ADMIN],
            ).count()
            try:
                cache.set(key, count, timeout=300)
            except Exception:
                pass
        return count >= threshold

    def retrieve(self, question: str, subject: Optional[str] = None,
                 top_k: Optional[int] = None) -> tuple[list[RetrievedChunk], list[dict]]:
        """(KB chunks, legacy textbook passages) for the question — only one
        of the two is non-empty."""
        top_k = top_k or int(getattr(settings, "KB_DEFAULT_TOP_K", 8))
        chunks: list[RetrievedChunk] = []
        if self.kb_ready():
            try:
                chunks = self.retrieval.search(question, top_k=top_k, subject=subject)
            except Exception as e:
                logger.warning(f"KB retrieval failed, falling back: {e}")
                chunks = []
        if chunks:
            return chunks, []
        return [], self._legacy_passages(question, top_k)

    @staticmethod
    def _legacy_passages(question: str, top_k: int) -> list[dict]:
        try:
            from ai_engine.offline import retrieve_passages
            return retrieve_passages(question, k=top_k)
        except Exception as e:
            logger.warning(f"Legacy textbook retrieval failed: {e}")
            return []

    @staticmethod
    def offline_passages(chunks: list[RetrievedChunk], legacy: list[dict]) -> list[dict]:
        """Passages in the shape ai_engine.offline.compose_offline_answer takes."""
        if chunks:
            return [{
                "text": c.text,
                "book": c.source_name,
                "page": c.locator,
                "cite": f"{c.source_name} — {c.locator}" if c.locator else c.source_name,
            } for c in chunks]
        return list(legacy)

    # ─── Answer ────────────────────────────────────────────

    def answer(self, question: str, mode: str = "tutor",
               subject: Optional[str] = None,
               top_k: Optional[int] = None,
               max_context_chars: int = 4000) -> MonicaResponse:
        # Lazy import so ai_engine/services.py stays authoritative
        from ai_engine.services import AIService, AIUnavailable

        expansion = expand_query(question)
        chunks, legacy = self.retrieve(question, subject=subject, top_k=top_k)
        used_kb = bool(chunks)

        if used_kb:
            context_str, citations = self._build_context(chunks, max_context_chars)
            confidence = "high" if chunks[0].final_score > 0.5 else "medium"
        else:
            context_str, citations = self._build_legacy_context(legacy, max_context_chars)
            confidence = "medium" if citations else "low"

        if citations:
            user_prompt = (
                f"QUESTION: {question}\n\n"
                f"REFERENCE CONTEXT (use these for citations):\n{context_str}\n\n"
                f"Answer the question using ONLY the references above. "
                f"Cite every claim inline as [1], [2], etc."
            )
        else:
            user_prompt = (
                f"QUESTION: {question}\n\n"
                "No reference passages were found for this question. Answer from "
                "general medical knowledge, say plainly that no reference was "
                "found, and do not use citation markers."
            )

        try:
            answer = AIService()._call_ai(user_prompt, system=self.SYSTEM_PROMPT,
                                          temperature=0.2, max_tokens=2048)
        except AIUnavailable as exc:
            exc.passages = self.offline_passages(chunks, legacy)
            raise

        answer, removed = self._check_citations(answer, len(citations))
        return MonicaResponse(
            answer=answer,
            citations=citations,
            confidence=confidence,
            used_kb=used_kb,
            query_expansion=expansion,
            retrieval_count=len(chunks) if used_kb else len(legacy),
            invalid_citations_removed=removed,
        )

    @staticmethod
    def _check_citations(answer: str, n_citations: int) -> tuple[str, int]:
        """Remove inline [k] markers that do not map to a returned citation
        (the model invented them). Returns (answer, markers removed)."""
        removed = 0

        def repl(m):
            nonlocal removed
            k = int(m.group(1))
            if 1 <= k <= n_citations:
                return m.group(0)
            removed += 1
            return ""

        cleaned = _CITATION_MARK_RE.sub(repl, answer or "")
        if removed:
            logger.info("Monica: removed %d citation marker(s) with no matching source", removed)
        return cleaned, removed

    def _build_context(self, chunks: list[RetrievedChunk],
                        max_chars: int) -> tuple[str, list[dict]]:
        parts = []
        citations = []
        used = 0
        for c in chunks:
            excerpt = c.text.strip()
            if used + len(excerpt) > max_chars:
                excerpt = excerpt[: max(0, max_chars - used)]
            if not excerpt:
                continue
            i = len(citations) + 1
            parts.append(
                f"[{i}] {c.attribution} — {c.locator or c.source_slug}\n{excerpt}\n"
            )
            used += len(excerpt)
            citations.append({
                "index": i,
                "source_slug": c.source_slug,
                "source_name": c.source_name,
                "attribution": c.attribution,
                "license": c.license,
                "locator": c.locator,
                "url": c.source_url,
                "excerpt": excerpt[:300],
                "subject": c.subject,
                "topic": c.topic,
                "score": round(c.final_score, 4),
                "citation_text": (
                    f"{c.attribution}. {c.locator}. {c.source_url}"
                    if c.locator or c.source_url
                    else c.attribution
                ),
            })
            if used >= max_chars:
                break
        return "\n".join(parts), citations

    @staticmethod
    def _build_legacy_context(passages: list[dict], max_chars: int) -> tuple[str, list[dict]]:
        """Numbered context + citations from the legacy textbook store."""
        parts = []
        citations = []
        used = 0
        for p in passages:
            text = (p.get("text") or "").strip()
            if used + len(text) > max_chars:
                text = text[: max(0, max_chars - used)]
            if not text:
                continue
            i = len(citations) + 1
            book = str(p.get("book") or "Textbook")
            page = p.get("page") or ""
            locator = f"p.{page}" if page not in ("", None, 0) else ""
            parts.append(f"[{i}] {book} {locator}\n{text}\n")
            used += len(text)
            citations.append({
                "index": i,
                "source_slug": "textbook-library",
                "source_name": book,
                "attribution": book,
                "license": "",
                "locator": locator,
                "url": "",
                "excerpt": text[:300],
                "subject": "",
                "topic": "",
                "score": round(float(p.get("norm_score", p.get("score", 0)) or 0), 4),
                "citation_text": f"{book}, {locator}" if locator else book,
            })
            if used >= max_chars:
                break
        return "\n".join(parts), citations
