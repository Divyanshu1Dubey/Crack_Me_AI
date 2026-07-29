"""
FederatedRetrieval: queries legacy TF-IDF RAG + modern embeddings RAG.

Phase 3 (2026-07-29). The AI Tutor and the RAG endpoints now go
through this single class instead of calling the legacy
RAGPipeline directly. Two backends are queried:

  1. Legacy   : ai_engine.rag_pipeline.RAGPipeline
                - chroka_db/rag_store.sqlite3, TF-IDF, 7,823 chunks
                - license-fenced 'internal' (copyrighted textbooks)
  2. Modern   : knowledge_base.retrieval.pipeline.RetrievalPipeline
                - Postgres+JSON, BM25+vector+KG+rerank
                - license-clean (public domain, govt, attested)

Both backends can be missing or empty without breaking the call.
We use a `ThreadPoolExecutor` so the two backends are queried in
parallel within a hard time budget. Results are merged via
Reciprocal Rank Fusion (RRF, k=60) — same algorithm as
knowledge_base/retrieval/pipeline.py:265-281.

Citation shape (matches the front-end `Message['citations']`):

  {
    "book":        str,
    "page":        int,
    "license":     str,
    "source_slug": str,
    "attribution": str,
    "locator":     str,
    "excerpt":     str,    # up to 300 chars
    "score":       float,  # final fused score
    "backend":     "legacy" | "modern",
  }
"""
from __future__ import annotations

import concurrent.futures
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)


# ─── Result dataclass ──────────────────────────────────────────────────

@dataclass
class FederatedResult:
    """One search hit from any backend."""
    text: str
    book: str = ""
    page: int = 0
    license: str = "internal"
    source_slug: str = ""
    attribution: str = ""
    locator: str = ""
    source_file: str = ""
    chapter: str = ""
    excerpt: str = ""
    score: float = 0.0
    bm25_score: float = 0.0
    vector_score: float = 0.0
    rerank_score: float = 0.0
    backend: str = "legacy"
    chunk_id: Optional[int] = None
    citation: dict = field(default_factory=dict)

    def to_citation(self) -> dict:
        """Shape consumed by the AI Tutor frontend (Message['citations']).

        Phase 7 (2026-07-29): every citation now carries a stable
        `attribution` line, a `locator` suitable for a frontend link,
        and the raw `source_file` for deep-linking to a textbook PDF
        page when the frontend wants to render a thumbnail.
        """
        # Defensive attribution — never empty.
        attr = self.attribution.strip()
        if not attr:
            page_part = f", p.{self.page}" if self.page else ""
            attr = f"{self.book}{page_part}".strip() or "Unknown source"

        return {
            "book": self.book,
            "page": self.page,
            "license": self.license,
            "source_slug": self.source_slug,
            "attribution": attr,
            "locator": self.locator or (f"p.{self.page}" if self.page else ""),
            "source_file": self.source_file,
            "chapter": self.chapter,
            "excerpt": self.excerpt or self.text[:300],
            "relevance": round(self.score, 4),
            "score": round(self.score, 4),
            "backend": self.backend,
            "chunk_id": self.chunk_id,
        }


# ─── Main class ────────────────────────────────────────────────────────

class FederatedRetrieval:
    """
    Federated retrieval across legacy TF-IDF + modern embeddings.

    Thread-safe. One instance per process is enough; the legacy
    SQLite connection is opened lazily (Phase 8 will tighten this
    with threading.local).
    """

    RRF_K = 60  # standard RRF k constant

    def __init__(self):
        self._legacy = None
        self._modern = None
        self._legacy_status: str = "uninitialized"
        self._modern_status: str = "uninitialized"
        self._last_legacy_latency_ms: float = 0.0
        self._last_modern_latency_ms: float = 0.0

        # Lazy: don't open either backend here. Let `search()` /
        # `_ensure_backends()` open them on first call so the
        # import / startup path stays cheap.

    # ─── Public API ─────────────────────────────────────────

    def search(
        self,
        query: str,
        n_results: int = 5,
        book_filter: Optional[str] = None,
        subject: Optional[str] = None,
        source_slugs: Optional[list[str]] = None,
    ) -> list[dict]:
        """Search both backends, merge via RRF, return top-K citations."""
        backend_results = self._query_backends(
            query=query,
            n_results=n_results,
            book_filter=book_filter,
            subject=subject,
            source_slugs=source_slugs,
        )

        flat: list[FederatedResult] = []
        for backend_name, results in backend_results.items():
            for r in results or []:
                if isinstance(r, FederatedResult):
                    flat.append(r)
                elif isinstance(r, dict):
                    flat.append(self._normalize_modern_dict(r, backend_name))
                else:
                    # knowledge_base.retrieval.pipeline.RetrievedChunk is a
                    # dataclass, not a dict — handle it here.
                    flat.append(self._normalize_modern_dict(r, backend_name))

        fused = self._rrf_merge(flat, top_k=n_results)
        return [r.to_citation() for r in fused]

    def rag_answer(self, question: str, n_context: int = 5) -> dict:
        """
        RAG-style answer with citations. Backwards-compatible with
        ai_engine.rag_pipeline.RAGPipeline.rag_answer().
        """
        citations = self.search(question, n_results=n_context)
        if not citations:
            return {
                "answer": getattr(
                    settings,
                    'RAG_FALLBACK_USER_MESSAGE',
                    'AI Tutor is temporarily unavailable.',
                ),
                "citations": [],
                "confidence": "low",
            }

        context_str = ""
        for i, c in enumerate(citations):
            loc = f" p.{c['page']}" if c.get('page') else ""
            context_str += (
                f"\n[Source {i+1}: {c.get('book','')}{loc}]\n"
                f"{c.get('excerpt','')}\n"
            )

        # The actual LLM call lives in AIService. We return the
        # context+cited docs; the caller (services.rag_answer) does
        # the LLM step. This keeps FederatedRetrieval LLM-agnostic.
        return {
            "answer": None,  # caller fills via _generate_answer
            "citations": citations,
            "context": context_str,
            "confidence": "high" if citations[0].get("relevance", 0) > 0.3 else "medium",
        }

    def find_textbook_reference(self, question_text: str, n_results: int = 3) -> list[dict]:
        """Thin wrapper — used by views.TextbookReferenceView."""
        return self.search(question_text, n_results=n_results)

    def health_check(self) -> dict:
        """Combined health report from both backends. Read-only."""
        legacy = self._legacy_health()
        modern = self._modern_health()

        # Status synthesis
        if legacy["status"] == "healthy" or modern["status"] == "healthy":
            status = "healthy"
        elif legacy["status"] == "missing" and modern["status"] == "missing":
            status = "missing"
        elif legacy["status"] in ("corrupt", "error") and modern["status"] in ("corrupt", "error"):
            status = "corrupt"
        else:
            status = "degraded"

        return {
            "backend": "federated",
            "status": status,
            "legacy": legacy,
            "modern": modern,
            "last_legacy_latency_ms": self._last_legacy_latency_ms,
            "last_modern_latency_ms": self._last_modern_latency_ms,
        }

    # ─── Backend query ─────────────────────────────────────

    def _query_backends(
        self,
        query: str,
        n_results: int,
        book_filter: Optional[str],
        subject: Optional[str],
        source_slugs: Optional[list[str]],
    ) -> dict[str, list]:
        """Run legacy + modern in parallel; degrade if either fails."""
        timeout = getattr(settings, 'RAG_QUERY_TIMEOUT', 10)
        out: dict[str, list] = {"legacy": [], "modern": []}

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            futures = {}
            try:
                futures[ex.submit(
                    self._query_legacy, query, n_results, book_filter
                )] = "legacy"
            except Exception as e:
                logger.warning(f"Legacy backend dispatch failed: {e}")
            try:
                futures[ex.submit(
                    self._query_modern, query, n_results, subject, source_slugs
                )] = "modern"
            except Exception as e:
                logger.warning(f"Modern backend dispatch failed: {e}")

            for fut, name in futures.items():
                try:
                    out[name] = fut.result(timeout=timeout) or []
                except concurrent.futures.TimeoutError:
                    logger.warning(f"{name} backend timed out after {timeout}s")
                except Exception as e:
                    logger.warning(f"{name} backend failed: {e}")

        return out

    def _query_legacy(self, query: str, n_results: int, book_filter: Optional[str]) -> list[dict]:
        """Query the legacy TF-IDF pipeline."""
        start = time.time()
        try:
            pipeline = self._ensure_legacy()
            if pipeline is None:
                return []
            results = pipeline.search(
                query,
                n_results=n_results,
                book_filter=book_filter or None,
            )
            self._last_legacy_latency_ms = (time.time() - start) * 1000
            return [self._legacy_to_federated(r) for r in results]
        except Exception as e:
            logger.warning(f"Legacy query failed: {e}", exc_info=True)
            return []

    def _query_modern(
        self,
        query: str,
        n_results: int,
        subject: Optional[str],
        source_slugs: Optional[list[str]],
    ) -> list:
        """Query the modern knowledge_base pipeline. May be empty."""
        start = time.time()
        try:
            pipeline = self._ensure_modern()
            if pipeline is None:
                return []
            chunks = pipeline.search(
                query,
                top_k=n_results,
                subject=subject,
                source_slugs=source_slugs,
                use_rerank=True,
                use_kg=True,
            )
            self._last_modern_latency_ms = (time.time() - start) * 1000
            return chunks  # already a list of RetrievedChunk
        except Exception as e:
            logger.warning(f"Modern query failed: {e}", exc_info=True)
            return []

    # ─── Backend lifecycle ─────────────────────────────────

    def _ensure_legacy(self):
        """Lazy-init the legacy RAGPipeline (None on failure)."""
        if self._legacy is not None:
            return self._legacy
        try:
            from ai_engine.rag_pipeline import RAGPipeline
            self._legacy = RAGPipeline()
            self._legacy_status = "initialized"
            logger.info("FederatedRetrieval: legacy backend initialized")
        except Exception as e:
            self._legacy_status = f"unavailable: {e}"
            logger.warning(f"Legacy RAG init failed: {e}")
        return self._legacy

    def _ensure_modern(self):
        """Lazy-init the modern knowledge_base pipeline (None on failure)."""
        if self._modern is not None:
            return self._modern
        try:
            from knowledge_base.retrieval.pipeline import RetrievalPipeline
            self._modern = RetrievalPipeline()
            self._modern_status = "initialized"
            logger.info("FederatedRetrieval: modern backend initialized")
        except Exception as e:
            self._modern_status = f"unavailable: {e}"
            logger.debug(f"Modern KB unavailable (expected on empty KB): {e}")
        return self._modern

    # ─── Shape normalizers ─────────────────────────────────

    @staticmethod
    def _legacy_to_federated(r: dict) -> FederatedResult:
        """Convert a legacy RAGPipeline.search() result dict to FederatedResult.

        Phase 7 (2026-07-29): propagate `source_file` so the frontend
        can deep-link to a textbook PDF page, and build a stable
        `source_slug` (slugified book name + page) that the frontend
        can use as a React key.
        """
        # Legacy book name cleanup (matches _clean_book_name behavior)
        raw_book = r.get("book", "") or ""
        book = raw_book.split(" (")[0] if " (" in raw_book else raw_book
        book = book.strip()
        page = int(r.get("page") or 0)
        text = r.get("text", "") or ""
        score = float(r.get("score") or 0.0)
        source_file = r.get("source_file", "") or ""

        # Stable slug: kebab-case book + page, used as React key.
        slug_base = re.sub(r"[^a-zA-Z0-9]+", "-", book).strip("-").lower()
        source_slug = f"legacy:{slug_base}" + (f"-p{page}" if page else "")

        return FederatedResult(
            text=text,
            book=book,
            page=page,
            license="internal",  # legacy = license-fenced copyrighted sources
            source_slug=source_slug,
            attribution=f"{book}" + (f", p.{page}" if page else ""),
            locator=f"p.{page}" if page else "",
            source_file=source_file,
            excerpt=text[:300],
            score=score,
            backend="legacy",
        )

    @staticmethod
    def _normalize_modern_dict(r: dict, backend_name: str) -> FederatedResult:
        """Convert a knowledge_base RetrievedChunk to FederatedResult.

        RetrievalPipeline.search returns RetrievedChunk dataclasses
        which already have .citation filled. We accept either a
        RetrievedChunk or a dict.
        """
        # RetrievedChunk is a dataclass
        citation = getattr(r, 'citation', None) or {}
        return FederatedResult(
            text=getattr(r, 'text', '') or citation.get('text', ''),
            book=getattr(r, 'source_name', '') or citation.get('source_name', ''),
            page=_try_int(getattr(r, 'locator', '')),
            license=getattr(r, 'license', '') or citation.get('license', 'unknown'),
            source_slug=getattr(r, 'source_slug', '') or citation.get('source_slug', ''),
            attribution=getattr(r, 'attribution', '') or citation.get('attribution', ''),
            locator=getattr(r, 'locator', '') or citation.get('locator', ''),
            excerpt=(getattr(r, 'text', '') or '')[:300],
            score=float(getattr(r, 'final_score', 0.0) or citation.get('score', 0.0)),
            bm25_score=float(getattr(r, 'bm25_score', 0.0)),
            vector_score=float(getattr(r, 'vector_score', 0.0)),
            rerank_score=float(getattr(r, 'rerank_score', 0.0)),
            backend=backend_name,
            chunk_id=getattr(r, 'chunk_id', None),
        )

    # ─── RRF ───────────────────────────────────────────────

    def _rrf_merge(self, results: list[FederatedResult], top_k: int) -> list[FederatedResult]:
        """Reciprocal Rank Fusion across backend results.

        Algorithm: identical to knowledge_base/retrieval/pipeline.py:265-281.
        Score per result = sum(1 / (k + rank + 1)) across all backends.
        """
        if not results:
            return []

        # Group by backend (each backend contributes its own ranking).
        per_backend: dict[str, list[FederatedResult]] = {}
        for r in results:
            per_backend.setdefault(r.backend, []).append(r)

        # Score each backend's ranking; merge into a single dict by (book, page, text-hash).
        fused: dict[str, FederatedResult] = {}
        for backend, items in per_backend.items():
            for rank, r in enumerate(items):
                rrf_score = 1.0 / (self.RRF_K + rank + 1)
                key = self._merge_key(r)
                if key in fused:
                    fused[key].score += rrf_score
                else:
                    # First time we see this chunk — copy and set score.
                    r.score = rrf_score
                    fused[key] = r

        ranked = sorted(fused.values(), key=lambda r: r.score, reverse=True)
        return ranked[:top_k]

    @staticmethod
    def _merge_key(r: FederatedResult) -> str:
        """Stable dedup key. Modern has chunk_id; legacy falls back to (book,page,text[:120])."""
        if r.chunk_id is not None:
            return f"modern:{r.chunk_id}"
        # Legacy: text-prefix hash (cheap)
        return f"legacy:{r.book}:{r.page}:{hash(r.text[:120])}"

    # ─── Health probes ─────────────────────────────────────

    def _legacy_health(self) -> dict:
        """Probe legacy via static method (no full pipeline init)."""
        try:
            from ai_engine.rag_pipeline import RAGPipeline
            h = RAGPipeline.health_check_static()
            h["enabled"] = self._legacy_status != "uninitialized" or True
            h["last_status"] = self._legacy_status
            return h
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _modern_health(self) -> dict:
        """Probe modern KB. If empty, that's still 'healthy' (just no data)."""
        try:
            from knowledge_base.models import KnowledgeChunk
            total = KnowledgeChunk.objects.filter(is_active=True).count()
            return {
                "backend": "modern_pg_json",
                "status": "healthy" if total > 0 else "empty",
                "active_chunks": total,
                "last_status": self._modern_status,
            }
        except Exception as e:
            return {
                "backend": "modern_pg_json",
                "status": "unavailable",
                "error": str(e),
                "last_status": self._modern_status,
            }


def _try_int(s: str) -> int:
    """Best-effort page number extraction from a locator string."""
    if not s:
        return 0
    m = re.search(r"\b(\d{1,5})\b", str(s))
    return int(m.group(1)) if m else 0
