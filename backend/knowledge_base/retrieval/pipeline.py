"""
Hybrid retrieval pipeline for the knowledge base.

Pipeline stages:
  1. Query expansion (medical synonyms + abbreviations)
  2. BM25 search (in-Python inverted index, built once per process and
     rebuilt when the approved chunk set changes)
  3. Vector search (cosine over stored embeddings; skipped when no real
     embedding provider is available; bounded scan)
  4. Reciprocal Rank Fusion (RRF) to combine rankings
  5. Knowledge-graph neighbour boost (for entities mentioned in query)
  6. Cross-encoder rerank (when available and ``KB_USE_RERANK``; otherwise a
     lexical rerank)
  7. Context compression — return top-K chunks with citations

All stages degrade gracefully if their dependency is unavailable. Models
are loaded once per process (views build a new pipeline per request).
"""

import hashlib
import logging
import math
import re
import threading
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Optional

from django.conf import settings
from django.db.models import Count, Max

from knowledge_base.models import (
    KnowledgeChunk, KnowledgeEntity, KnowledgeRelation, KnowledgeSource,
)
from knowledge_base.ontology.loader import expand_query, get_kg_neighbors
from knowledge_base.services.embedding import EmbeddingService

logger = logging.getLogger(__name__)

CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
_LOAD_RETRY_SECONDS = 600

_APPROVED = (KnowledgeChunk.APPROVAL_AUTO, KnowledgeChunk.APPROVAL_ADMIN)

# ─── Per-process caches ───────────────────────────────────────────────

_CE_LOCK = threading.Lock()
_CE_STATE = {"model": None, "failed_at": None}

_CORPUS_LOCK = threading.Lock()
_CORPUS = {"sig": None, "index": None}

_KG_LOCK = threading.Lock()
_KG_CACHE = {"sig": None, "entities": []}


def _offline() -> bool:
    try:
        from ai_engine.offline import ai_offline_mode
        return ai_offline_mode()
    except Exception:
        return False


def get_cross_encoder():
    """The process-wide CrossEncoder, or None (not installed, not cached
    locally in offline mode, or a recent load failed)."""
    model = _CE_STATE["model"]
    if model is not None:
        return model
    failed_at = _CE_STATE["failed_at"]
    if failed_at is not None and time.monotonic() - failed_at < _LOAD_RETRY_SECONDS:
        return None
    with _CE_LOCK:
        if _CE_STATE["model"] is not None:
            return _CE_STATE["model"]
        try:
            from sentence_transformers import CrossEncoder  # type: ignore
            kwargs = {"local_files_only": True} if _offline() else {}
            _CE_STATE["model"] = CrossEncoder(CROSS_ENCODER_MODEL, **kwargs)
            _CE_STATE["failed_at"] = None
        except Exception as e:
            logger.info(f"Cross-encoder unavailable ({e}); using lexical rerank")
            _CE_STATE["failed_at"] = time.monotonic()
            return None
        return _CE_STATE["model"]


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


@dataclass
class _BM25Corpus:
    docs: list
    postings: dict          # term -> list[(doc_idx, tf)]
    lengths: list
    avgdl: float


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

    @staticmethod
    def cache_key(query: str, top_k: int, subject: Optional[str],
                  source_slugs: Optional[list[str]], use_rerank: bool, use_kg: bool) -> str:
        """Stable across processes (``hash()`` of a str is randomised per
        process, so workers could never share entries)."""
        raw = "\x1f".join([
            query or "", str(top_k), subject or "", ",".join(sorted(source_slugs or [])),
            str(bool(use_rerank)), str(bool(use_kg)),
        ])
        return "kb:ret:v2:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def search(self, query: str, top_k: Optional[int] = None,
               subject: Optional[str] = None,
               source_slugs: Optional[list[str]] = None,
               use_rerank: Optional[bool] = None,
               use_kg: Optional[bool] = None) -> list[RetrievedChunk]:
        if top_k is None:
            top_k = int(getattr(settings, "KB_DEFAULT_TOP_K", 8))
        if use_rerank is None:
            use_rerank = bool(getattr(settings, "KB_USE_RERANK", True))
        if use_kg is None:
            use_kg = bool(getattr(settings, "KB_USE_KG_BOOST", True))

        cache_key = self.cache_key(query, top_k, subject, source_slugs, use_rerank, use_kg)
        if self.cache is not None:
            try:
                cached = self.cache.get(cache_key)
            except Exception:
                cached = None
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

    def _corpus(self) -> Optional[_BM25Corpus]:
        """Tokenized approved corpus + inverted index, built once per process
        and rebuilt when the approved chunk set changes (one aggregate query
        per search instead of loading and tokenizing every chunk)."""
        qs = KnowledgeChunk.objects.filter(is_active=True, approval_state__in=_APPROVED)
        agg = qs.aggregate(n=Count("id"), last=Max("updated_at"), top=Max("id"))
        sig = (agg["n"], agg["last"], agg["top"])
        if _CORPUS["sig"] == sig and _CORPUS["index"] is not None:
            return _CORPUS["index"]
        with _CORPUS_LOCK:
            if _CORPUS["sig"] == sig and _CORPUS["index"] is not None:
                return _CORPUS["index"]
            limit = int(getattr(settings, "KB_BM25_MAX_DOCS", 5000))
            docs = list(qs.select_related("source").order_by("id").values(
                "id", "text", "subject", "topic", "locator", "source__slug",
                "source__name", "source__attribution", "license",
                "source__source_url",
            )[:limit])
            postings: dict = defaultdict(list)
            lengths = []
            for i, d in enumerate(docs):
                toks = self._tokenize(d["text"])
                lengths.append(len(toks))
                for term, tf in Counter(toks).items():
                    postings[term].append((i, tf))
            index = _BM25Corpus(
                docs=docs, postings=dict(postings), lengths=lengths,
                avgdl=(sum(lengths) / len(lengths)) if lengths else 1.0,
            )
            _CORPUS["sig"], _CORPUS["index"] = sig, index
            return index

    def _bm25(self, query: str, top_k: int, subject: Optional[str],
              source_slugs: Optional[list[str]]) -> list[RetrievedChunk]:
        """BM25 over the active, approved chunk corpus (IDF over the whole
        cached corpus; subject/source filters applied per document)."""
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []
        corpus = self._corpus()
        if corpus is None or not corpus.docs:
            return []
        slugs = set(source_slugs or [])
        n_docs = len(corpus.docs)
        k1, b = 1.5, 0.75
        acc: dict[int, float] = defaultdict(float)
        for q in set(query_tokens):
            entries = corpus.postings.get(q)
            if not entries:
                continue
            df = len(entries)
            idf = math.log((n_docs - df + 0.5) / (df + 0.5) + 1)
            for i, tf in entries:
                d = corpus.docs[i]
                if subject and d.get("subject") != subject:
                    continue
                if slugs and d.get("source__slug") not in slugs:
                    continue
                dl = corpus.lengths[i]
                denom = tf + k1 * (1 - b + b * dl / max(corpus.avgdl, 1))
                acc[i] += idf * ((tf * (k1 + 1)) / max(denom, 1e-9))

        out = []
        for i, s in sorted(acc.items(), key=lambda x: x[1], reverse=True)[:top_k]:
            d = corpus.docs[i]
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
            qvec = self.embedding.embed_query(query)
        except Exception as e:
            logger.warning(f"Embedding failed: {e}")
            return []
        if not qvec:
            # No real embedding provider: BM25-only (never compare
            # meaningless hash vectors).
            return []

        qs = KnowledgeChunk.objects.filter(
            is_active=True,
            approval_state__in=_APPROVED,
            embedding__isnull=False,
        )
        if subject:
            qs = qs.filter(subject=subject)
        if source_slugs:
            qs = qs.filter(source__slug__in=source_slugs)
        limit = int(getattr(settings, "KB_VECTOR_SCAN_LIMIT", 5000))

        scored = []
        for chunk in qs.select_related("embedding", "source").order_by("-id")[:limit].iterator(chunk_size=500):
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

    @staticmethod
    def _kg_entities() -> list[tuple[str, set]]:
        """(name, lower-cased names+synonyms) for every entity, cached per
        process until the entity table changes."""
        agg = KnowledgeEntity.objects.aggregate(n=Count("id"), top=Max("id"))
        sig = (agg["n"], agg["top"])
        if _KG_CACHE["sig"] == sig:
            return _KG_CACHE["entities"]
        with _KG_LOCK:
            entities = []
            for name, synonyms in KnowledgeEntity.objects.values_list("name", "synonyms"):
                names = {str(name).lower(), *(str(s).lower() for s in (synonyms or []))}
                entities.append((name, names))
            _KG_CACHE["sig"], _KG_CACHE["entities"] = sig, entities
            return entities

    def _kg_boost(self, chunks: list[RetrievedChunk], expansion: dict) -> None:
        tokens = set(expansion.get("tokens", []))
        # Find entities mentioned in the query
        entities = [name for name, names in self._kg_entities() if tokens & names]

        if not entities:
            return

        # Build a chunk_id -> boost map by walking KG neighbors
        boosts: dict[int, float] = defaultdict(float)
        for name in entities:
            for edge in get_kg_neighbors(name, hops=1):
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
        """Cross-encoder rerank when the (process-wide) model is available,
        otherwise a lightweight lexical rerank that favours chunks with more
        query token overlap."""
        if not chunks:
            return
        model = get_cross_encoder()
        if model is not None:
            try:
                pairs = [(expanded_query, c.text[:512]) for c in chunks]
                scores = model.predict(pairs)
                for c, s in zip(chunks, scores):
                    c.rerank_score = float(s)
                    c.final_score = 0.7 * float(s) + 0.3 * c.final_score
                return
            except Exception as e:
                logger.info(f"Cross-encoder rerank failed ({e}); using lexical rerank")

        query_tokens = set(self._tokenize(expanded_query))
        for c in chunks:
            text_tokens = set(self._tokenize(c.text))
            overlap = len(query_tokens & text_tokens)
            c.rerank_score = float(overlap)
            c.final_score = c.final_score + 0.05 * overlap

    # ─── Citations ────────────────────────────────────────

    def _attach_citations(self, chunks: list[RetrievedChunk]) -> None:
        # One query for every chunk's source template (was one per chunk).
        objs = KnowledgeChunk.objects.select_related("source").in_bulk([c.chunk_id for c in chunks])
        for c in chunks:
            chunk_obj = objs.get(c.chunk_id)
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
