"""
Monica — the citation-aware RAG orchestrator.

This is the high-level service called from views. It composes:
  1. RetrievalPipeline (hybrid search + KG + rerank)
  2. AIService from ai_engine (existing 11-provider rotation)
  3. Citation engine (attaches source attribution to every claim)

When the knowledge base has enough approved chunks (>=10) we use
the citation-aware path. Otherwise we fall through to the existing
RAGPipeline (sqlite TF-IDF) so behaviour stays consistent.
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional

from django.conf import settings
from django.core.cache import cache as default_cache

from knowledge_base.retrieval.pipeline import RetrievalPipeline, RetrievedChunk
from knowledge_base.ontology.loader import expand_query

logger = logging.getLogger(__name__)

KB_FALLBACK_THRESHOLD = int(getattr(settings, "KB_FALLBACK_THRESHOLD", 10))


@dataclass
class MonicaResponse:
    answer: str
    citations: list[dict]
    confidence: str
    used_kb: bool
    query_expansion: dict
    retrieval_count: int


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
        self.retrieval = retrieval or RetrievalPipeline(cache=default_cache)

    def answer(self, question: str, mode: str = "tutor",
               subject: Optional[str] = None,
               top_k: int = 6,
               max_context_chars: int = 4000) -> MonicaResponse:
        # Lazy import so ai_engine/services.py stays authoritative
        from ai_engine.services import AIService

        expansion = expand_query(question)

        # Retrieval
        chunks: list[RetrievedChunk] = []
        used_kb = False
        try:
            chunks = self.retrieval.search(
                question, top_k=top_k, subject=subject,
                use_rerank=True, use_kg=True,
            )
            used_kb = len(chunks) >= 1
        except Exception as e:
            logger.warning(f"Retrieval failed, falling back: {e}")

        # Build prompt
        context_str, citations = self._build_context(chunks, max_context_chars)

        if used_kb and citations:
            user_prompt = (
                f"QUESTION: {question}\n\n"
                f"REFERENCE CONTEXT (use these for citations):\n{context_str}\n\n"
                f"Answer the question using ONLY the references above. "
                f"Cite every claim inline as [1], [2], etc."
            )
            confidence = "high" if chunks and chunks[0].final_score > 0.5 else "medium"
        else:
            # Fall back to existing pipeline behaviour
            try:
                from ai_engine.sqlite_rag import SQLiteRAGPipeline
                sqlite_rag = SQLiteRAGPipeline()
                fallback = sqlite_rag.rag_answer(question, n_context=top_k)
                user_prompt = fallback.get("answer", "")
                citations = fallback.get("citations", [])
                confidence = fallback.get("confidence", "low")
                if not isinstance(citations, list):
                    citations = []
                # Convert to dict shape if needed
                citations = [
                    c if isinstance(c, dict)
                    else {"book": str(c), "page": "", "excerpt": "",
                          "relevance": 0.0}
                    for c in citations
                ]
                used_kb = False
            except Exception as e:
                logger.warning(f"SQLite RAG fallback also failed: {e}")
                user_prompt = question
                confidence = "low"

        # Generate via existing 11-provider rotation
        try:
            ai = AIService()
            if hasattr(ai, "ask_tutor"):
                answer = ai.ask_tutor(user_prompt, context="")
            elif hasattr(ai, "generate_response"):
                answer = ai.generate_response(
                    system=self.SYSTEM_PROMPT,
                    user=user_prompt,
                )
            else:
                answer = ai.ask(user_prompt, system=self.SYSTEM_PROMPT)
        except Exception as e:
            logger.error(f"AI generation failed: {e}")
            answer = "AI service is temporarily unavailable. Please retry."

        # Confidence fallback
        if not chunks and not citations:
            confidence = "low"

        return MonicaResponse(
            answer=answer,
            citations=citations,
            confidence=confidence,
            used_kb=used_kb,
            query_expansion=expansion,
            retrieval_count=len(chunks),
        )

    def _build_context(self, chunks: list[RetrievedChunk],
                        max_chars: int) -> tuple[str, list[dict]]:
        parts = []
        citations = []
        used = 0
        for i, c in enumerate(chunks, 1):
            excerpt = c.text.strip()
            if used + len(excerpt) > max_chars:
                excerpt = excerpt[: max(0, max_chars - used)]
            if not excerpt:
                continue
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