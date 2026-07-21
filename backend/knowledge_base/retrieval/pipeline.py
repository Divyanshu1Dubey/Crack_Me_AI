"""
Hybrid retrieval pipeline for the knowledge base.

Pipeline stages:
  1. Query expansion (medical synonyms + abbreviations)
  2. BM25 search (Postgres tsvector when available; in-Python fallback)
  3. Vector search (cosine over stored embeddings; pure Python numpy)
  4. Reciprocal Rank Fusion (RRF) to combine rankings
  5. Knowledge-graph neighbour boost (for entities mentioned in query)
  6. Cross-encoder rerank (when available; otherwise skip)
  7. Context compression — return top-K chunks with citations

All stages degrade gracefully if their dependency is unavailable.
"""

import logging
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Optional

from django.conf import settings
from django.db import connection

from knowledge_base.models import (
    KnowledgeChunk, KnowledgeEntity, KnowledgeRelation, KnowledgeSource,
)
from knowledge_base.ontology.loader import expand_query, get_kg_neighbors
from knowledge_base.services.embedding import EmbeddingService

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    chunk_id: int
    text: str
    source_slug: str
    source_name: str
    attribution: str
    license: str
    source_url: str = ""
    locator: str = ""
    subject: str = ""
    topic: str = ""
    bm25_score: float = 0.0
    vector_score: float = 0.0
    kg_score: float = 0.0
    rerank_score: float = 0.0
    final_score: float = 0.0
    citation: dict = field(default_factory=dict)


class RetrievalPipeline:
    """
    Default hybrid retriever. Wraps BM25, vector, KG, and rerank
    stages. Cache-aware: respects Redis cache when REDIS_URL is set.
    """

    def __init__(self, embedding: Optional[EmbeddingService] = None,
                 cache=None):
        self.embedding = embedding or EmbeddingService()
        self.cache = cache  # optional django.core.cache

    # ─── Public ────────────────────────────────────────────

    def search(self, query: str, top_k: int = 8,
               subject: Optional[str] = None,
               source_slugs: Optional[list[str]] = None,
               use_rerank: bool = True,
               use_kg: bool = True) -> list[RetrievedChunk]:
        # Cache key
        cache_key = f"kb:ret:{hash(query)}:{top_k}:{subject}:{','.join(source_slugs or [])}"
        if self.cache is not None:
            cached = self.cache.get(cache_key)
            if cached:
                return [RetrievedChunk(**c) for c in cached]

        expansion = expand_query(query)
        expanded = expansion["expanded"]

        # Get candidate set from BM25
        bm25_results = self._bm25(expanded, top_k=top_k * 3,
                                  subject=subject,
                                  source_slugs=source_slugs)
        # Vector search
        vector_results = self._vector(expanded, top_k=top_k * 3,
                                      subject=subject,
                                      source_slugs=source_slugs)
        # RRF combine
        combined = self._rrf(bm25_results, vector_results, top_k=top_k * 2)
        # KG boost
        if use_kg:
            self._kg_boost(combined, expansion)
        # Optional rerank
        if use_rerank:
            self._rerank(combined, expanded)

        # Sort, take top_k, build citations
        combined.sort(key=lambda c: c.final_score, reverse=True)
        top = combined[:top_k]
        self._attach_citations(top)

        # Cache
        if self.cache is not None:
            try:
                self.cache.set(cache_key,
                               [self._to_cache_dict(c) for c in top],
                               timeout=600)
            except Exception as e:
                logger.debug(f"Cache set failed: {e}")

        return top

    # ─── BM25 ─────────────────────────────────────────────

    _STOP = {"the","a","an","is","are","was","were","of","in","to","for",
             "with","on","at","by","as","or","and","but","if","so","it",
             "its","this","that","these","those","be","been","being","have",
             "has","had","do","does","did","will","would","should","can",
             "could","may","might","must","shall"}

    def _tokenize(self, text: str) -> list[str]:
        return [t.lower() for t in re.findall(r"[a-zA-Z][a-zA-Z0-9\-]+", text)
                if t.lower() not in self._STOP and len(t) > 1]

    def _bm25(self, query: str, top_k: int, subject: Optional[str],
              source_slugs: Optional[list[str]]) -> list[RetrievedChunk]:
        """BM25 over the active chunk corpus.

        Implementation note: we tried using Postgres tsvector via
        django.contrib.postgres.search, but kept this engine-agnostic
        in-Python implementation so it works on SQLite dev and Postgres
        prod. Cost is bounded: we materialize docs from chunks tagged
        as auto-approved + admin-approved.
        """
        qs = KnowledgeChunk.objects.filter(is_active=True, approval_state__in=[
            KnowledgeChunk.APPROVAL_AUTO, KnowledgeChunk.APPROVAL_ADMIN,
        ])
        if subject:
            qs = qs.filter(subject=subject)
        if source_slugs:
            qs = qs.filter(source__slug__in=source_slugs)
        # Cap candidate set for performance
        docs = list(qs.select_related("source").values(
            "id", "text", "subject", "topic", "locator", "source__slug",
            "source__name", "source__attribution", "license",
            "source__source_url",
        )[:5000])
        if not docs:
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        # Build BM25 structures
        tokenized = [self._tokenize(d["text"]) for d in docs]
        N = len(docs)
        df = Counter()
        for toks in tokenized:
            for t in set(toks):
                df[t] += 1
        avgdl = sum(len(t) for t in tokenized) / max(N, 1)

        k1, b = 1.5, 0.75
        scores = []
        for i, toks in enumerate(tokenized):
            s = 0.0
            tf = Counter(toks)
            dl = len(toks)
            for q in query_tokens:
                if q not in tf:
                    continue
                idf = math.log((N - df[q] + 0.5) / (df[q] + 0.5) + 1)
                denom = tf[q] + k1 * (1 - b + b * dl / max(avgdl, 1))
                s += idf * ((tf[q] * (k1 + 1)) / max(denom, 1e-9))
            if s > 0:
                scores.append((s, i))

        scores.sort(reverse=True, key=lambda x: x[0])
        out = []
        for s, i in scores[:top_k]:
            d = docs[i]
            out.append(RetrievedChunk(
                chunk_id=d["id"],
                text=d["text"],
                source_slug=d["source__slug"],
                source_name=d["source__name"],
                attribution=d["source__attribution"],
                license=d["license"],
                source_url=d.get("source__source_url") or "",
                locator=d.get("locator") or "",
                subject=d.get("subject") or "",
                topic=d.get("topic") or "",
                bm25_score=float(s),
            ))
        return out

    # ─── Vector ───────────────────────────────────────────

    def _vector(self, query: str, top_k: int, subject: Optional[str],
                source_slugs: Optional[list[str]]) -> list[RetrievedChunk]:
        try:
            qvec = self.embedding.embed(query)[0]
        except Exception as e:
            logger.warning(f"Embedding failed: {e}")
            return []

        qs = KnowledgeChunk.objects.filter(
            is_active=True,
            approval_state__in=[
                KnowledgeChunk.APPROVAL_AUTO,
                KnowledgeChunk.APPROVAL_ADMIN,
            ],
            embedding__isnull=False,
        )
        if subject:
            qs = qs.filter(subject=subject)
        if source_slugs:
            qs = qs.filter(source__slug__in=source_slugs)

        scored = []
        for chunk in qs.select_related("embedding", "source").iterator(chunk_size=500):
            try:
                vec = chunk.embedding.vector
                score = self._cosine(qvec, vec)
                if score > 0:
                    scored.append((score, chunk))
            except Exception:
                continue

        scored.sort(key=lambda x: x[0], reverse=True)
        out = []
        for score, chunk in scored[:top_k]:
            out.append(RetrievedChunk(
                chunk_id=chunk.id,
                text=chunk.text,
                source_slug=chunk.source.slug,
                source_name=chunk.source.name,
                attribution=chunk.source.attribution,
                license=chunk.license,
                source_url=chunk.source_url or chunk.source.source_url,
                locator=chunk.locator or "",
                subject=chunk.subject or "",
                topic=chunk.topic or "",
                vector_score=float(score),
            ))
        return out

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        if not na or not nb:
            return 0.0
        return dot / (na * nb)

    # ─── RRF ──────────────────────────────────────────────

    @staticmethod
    def _rrf(bm25: list[RetrievedChunk], vec: list[RetrievedChunk],
             k: int = 60, top_k: int = 16) -> list[RetrievedChunk]:
        idx: dict[int, RetrievedChunk] = {}
        for rank, c in enumerate(bm25):
            c.final_score = 1.0 / (k + rank + 1)
            idx[c.chunk_id] = c
        for rank, c in enumerate(vec):
            v = 1.0 / (k + rank + 1)
            if c.chunk_id in idx:
                idx[c.chunk_id].final_score += v
                idx[c.chunk_id].vector_score = c.vector_score
            else:
                c.final_score = v
                idx[c.chunk_id] = c
        ranked = sorted(idx.values(), key=lambda c: c.final_score, reverse=True)
        return ranked[:top_k]

    # ─── KG boost ─────────────────────────────────────────

    def _kg_boost(self, chunks: list[RetrievedChunk], expansion: dict) -> None:
        tokens = set(expansion.get("tokens", []))
        # Find entities mentioned in the query
        entities = []
        for e in KnowledgeEntity.objects.all():
            names = {e.name.lower(), *(s.lower() for s in e.synonyms)}
            if tokens & names:
                entities.append(e)

        if not entities:
            return

        # Build a chunk_id -> boost map by walking KG neighbors
        boosts: dict[int, float] = defaultdict(float)
        for e in entities:
            for edge in get_kg_neighbors(e.name, hops=1):
                # Match by name appearing in chunk text
                for c in chunks:
                    if edge["from"].lower() in c.text.lower() or edge["to"].lower() in c.text.lower():
                        boosts[c.chunk_id] += edge["weight"] * 0.1
                        c.kg_score += edge["weight"] * 0.1

        for c in chunks:
            if c.chunk_id in boosts:
                c.final_score += boosts[c.chunk_id]

    # ─── Rerank ───────────────────────────────────────────

    def _rerank(self, chunks: list[RetrievedChunk], expanded_query: str) -> None:
        """Lightweight lexical rerank — favours chunks with more query
        token overlap. A real cross-encoder would be better; we keep
        this engine-agnostic so it runs in any environment.

        If `sentence-transformers` `CrossEncoder` is available we'll
        upgrade to that automatically.
        """
        try:
            from sentence_transformers import CrossEncoder  # type: ignore
            model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
            pairs = [(expanded_query, c.text[:512]) for c in chunks]
            scores = model.predict(pairs)
            for c, s in zip(chunks, scores):
                c.rerank_score = float(s)
                c.final_score = 0.7 * float(s) + 0.3 * c.final_score
            return
        except Exception:
            pass

        query_tokens = set(self._tokenize(expanded_query))
        for c in chunks:
            text_tokens = set(self._tokenize(c.text))
            overlap = len(query_tokens & text_tokens)
            c.rerank_score = float(overlap)
            c.final_score = c.final_score + 0.05 * overlap

    # ─── Citations ────────────────────────────────────────

    def _attach_citations(self, chunks: list[RetrievedChunk]) -> None:
        for c in chunks:
            chunk_obj = KnowledgeChunk.objects.filter(pk=c.chunk_id).select_related("source").first()
            tpl = chunk_obj.source.citation_template if chunk_obj and chunk_obj.source.citation_template else "{title} — {attribution} ({locator}). {url}"
            try:
                citation = tpl.format(
                    title=(c.topic or "Untitled").title(),
                    attribution=c.attribution,
                    locator=c.locator or "",
                    url=c.source_url or "",
                    year="",
                )
            except Exception:
                citation = f"{c.attribution} — {c.locator}"
            c.citation = {
                "chunk_id": c.chunk_id,
                "source_slug": c.source_slug,
                "source_name": c.source_name,
                "attribution": c.attribution,
                "license": c.license,
                "locator": c.locator,
                "url": c.source_url,
                "citation_text": citation,
                "score": round(c.final_score, 4),
            }

    # ─── Helpers ──────────────────────────────────────────

    @staticmethod
    def _to_cache_dict(c: RetrievedChunk) -> dict:
        return {
            "chunk_id": c.chunk_id,
            "text": c.text,
            "source_slug": c.source_slug,
            "source_name": c.source_name,
            "attribution": c.attribution,
            "license": c.license,
            "source_url": c.source_url,
            "locator": c.locator,
            "subject": c.subject,
            "topic": c.topic,
            "bm25_score": c.bm25_score,
            "vector_score": c.vector_score,
            "kg_score": c.kg_score,
            "rerank_score": c.rerank_score,
            "final_score": c.final_score,
            "citation": c.citation,
        }