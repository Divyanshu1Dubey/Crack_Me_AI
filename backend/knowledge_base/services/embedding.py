"""
Embedding service.

Strategy:
- Default model: BGE-small-en-v1.5 (384-dim) — small, fast, open,
  Apache 2.0, well-suited for medical prose.
- Optional upgrade to BGE-large / MedCPT / OpenAI text-embedding-3-small
  via env var EMBEDDING_MODEL.
- Provider order (lazy init):
    1. sentence-transformers local (HuggingFace) — best for cost
    2. OpenAI text-embedding-3-* — fallback
    3. Cohere embed-english-v3.0 — fallback

When no provider is available ``embed()`` returns ``[]``: retrieval then
runs BM25-only and the indexer stores nothing. The deterministic hash
"embedding" (``_hash_embed``) carries no meaning — cosine between two hash
vectors is noise — so it is only produced when a caller explicitly asks
for it (``allow_hash_fallback=True``), never for search or indexing.

SentenceTransformer models are loaded once per process and shared by every
EmbeddingService instance (views build a new one per request); a failed
load is remembered for a while instead of being retried on every query.
With ``AI_OFFLINE_MODE`` on, models are only loaded from the local cache
and the hosted embedding APIs are not called.
"""

import hashlib
import logging
import math
import os
import threading
import time
from typing import Optional, Sequence, Union

from django.conf import settings

logger = logging.getLogger(__name__)

# Per-process model cache: repo id -> SentenceTransformer, and repo id ->
# monotonic time of the last failed load (retried after _LOAD_RETRY_SECONDS).
_ST_MODELS: dict = {}
_ST_FAILED: dict = {}
_ST_LOCK = threading.Lock()
_LOAD_RETRY_SECONDS = 600


def _offline() -> bool:
    try:
        from ai_engine.offline import ai_offline_mode
        return ai_offline_mode()
    except Exception:
        return False


def get_sentence_transformer(repo: str):
    """The process-wide SentenceTransformer for ``repo``, or None."""
    model = _ST_MODELS.get(repo)
    if model is not None:
        return model
    failed_at = _ST_FAILED.get(repo)
    if failed_at is not None and time.monotonic() - failed_at < _LOAD_RETRY_SECONDS:
        return None
    with _ST_LOCK:
        model = _ST_MODELS.get(repo)
        if model is not None:
            return model
        try:
            from sentence_transformers import SentenceTransformer
            kwargs = {'local_files_only': True} if _offline() else {}
            model = SentenceTransformer(repo, **kwargs)
        except Exception as e:
            logger.info(f"sentence-transformers model {repo} unavailable ({e})")
            _ST_FAILED[repo] = time.monotonic()
            return None
        _ST_MODELS[repo] = model
        _ST_FAILED.pop(repo, None)
        return model


DEFAULT_MODEL = os.getenv("EMBEDDING_MODEL", "bge-small-en-v1.5")

# Map: model name -> dim
_MODEL_DIMS = {
    "bge-small-en-v1.5": 384,
    "bge-base-en-v1.5": 768,
    "bge-large-en-v1.5": 1024,
    "all-MiniLM-L6-v2": 384,
    "pubmedbert-base-embed": 768,
    "text-embedding-3-small": 1536,
    "cohere-embed-english-v3.0": 1024,
}


class EmbeddingService:
    """Lazy embedding provider with graceful fallback."""

    _REPO_MAP = {
        "bge-small-en-v1.5": "BAAI/bge-small-en-v1.5",
        "bge-base-en-v1.5": "BAAI/bge-base-en-v1.5",
        "bge-large-en-v1.5": "BAAI/bge-large-en-v1.5",
        "all-MiniLM-L6-v2": "sentence-transformers/all-MiniLM-L6-v2",
        "pubmedbert-base-embed": "NeuML/pubmedbert-base-embeddings",
    }

    def __init__(self, model: Optional[str] = None):
        self.model = model or DEFAULT_MODEL
        self.dim = _MODEL_DIMS.get(self.model, 384)
        self._openai_client = None
        self._cohere_client = None

    # ─── Public API ────────────────────────────────────────

    def embed(self, text: Union[str, Sequence[str]],
              allow_hash_fallback: bool = False) -> list[list[float]]:
        """Embed a single string or list of strings.

        Returns ``[]`` when no real embedding provider is available (unless
        ``allow_hash_fallback``), so callers never compare meaningless
        vectors.
        """
        inputs = [text] if isinstance(text, str) else list(text)
        if not inputs:
            return []

        # Provider chain
        vecs = (
            self._try_st(inputs)
            or self._try_openai(inputs)
            or self._try_cohere(inputs)
        )
        if not vecs:
            if not allow_hash_fallback:
                return []
            vecs = [self._hash_embed(t) for t in inputs]

        # Pad / trim to declared dim (defensive)
        return [self._fit_dim(v) for v in vecs]

    def embed_query(self, query: str) -> Optional[list[float]]:
        """One query vector from a real provider, or None."""
        vecs = self.embed(query)
        return vecs[0] if vecs else None

    # ─── Providers ─────────────────────────────────────────

    def _try_st(self, inputs: list[str]) -> Optional[list[list[float]]]:
        repo = self._REPO_MAP.get(self.model)
        if not repo:
            return None
        model = get_sentence_transformer(repo)
        if model is None:
            return None
        try:
            vecs = model.encode(inputs, normalize_embeddings=True, show_progress_bar=False)
            return [list(map(float, v)) for v in vecs]
        except Exception as e:
            logger.info(f"sentence-transformers encode failed ({e}); trying next provider")
            return None

    def _try_openai(self, inputs: list[str]) -> Optional[list[list[float]]]:
        if not self.model.startswith("text-embedding") or _offline():
            return None
        api_key = getattr(settings, "OPENAI_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            return None
        try:
            from openai import OpenAI
            if self._openai_client is None:
                self._openai_client = OpenAI(api_key=api_key)
            resp = self._openai_client.embeddings.create(
                model=self.model,
                input=inputs,
            )
            return [d.embedding for d in resp.data]
        except Exception as e:
            logger.warning(f"OpenAI embeddings failed: {e}")
            return None

    def _try_cohere(self, inputs: list[str]) -> Optional[list[list[float]]]:
        if "cohere" not in self.model or _offline():
            return None
        api_key = getattr(settings, "COHERE_API_KEY", "") or os.getenv("COHERE_API_KEY", "")
        if not api_key:
            return None
        try:
            import cohere
            if self._cohere_client is None:
                self._cohere_client = cohere.Client(api_key)
            resp = self._cohere_client.embed(texts=inputs, model=self.model,
                                              input_type="search_document")
            return resp.embeddings
        except Exception as e:
            logger.warning(f"Cohere embeddings failed: {e}")
            return None

    def _hash_embed(self, text: str) -> list[float]:
        """Deterministic pseudo-embedding. NOT semantic: identical text gives
        identical vectors, anything else gives noise. Only produced when a
        caller passes ``allow_hash_fallback=True``."""
        # 384-dim vector seeded by SHA-256 repeated
        vec = [0.0] * self.dim
        seed = hashlib.sha256(text.encode("utf-8")).digest()
        for i in range(self.dim):
            b = seed[i % len(seed)]
            vec[i] = (b / 255.0) - 0.5
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def _fit_dim(self, vec: list[float]) -> list[float]:
        if len(vec) == self.dim:
            return vec
        if len(vec) > self.dim:
            return vec[: self.dim]
        return vec + [0.0] * (self.dim - len(vec))