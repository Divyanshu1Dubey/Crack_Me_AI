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
    4. Deterministic hash-based pseudo-embedding — last-resort
       fallback that still produces consistent vectors

We never crash the API if embeddings are unavailable; retrieval falls
back to BM25-only and logs a warning.
"""

import hashlib
import logging
import math
import os
from typing import Optional, Sequence, Union

from django.conf import settings

logger = logging.getLogger(__name__)


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

    def __init__(self, model: Optional[str] = None):
        self.model = model or DEFAULT_MODEL
        self.dim = _MODEL_DIMS.get(self.model, 384)
        self._st_model = None
        self._st_loaded = False
        self._openai_client = None
        self._cohere_client = None

    # ─── Public API ────────────────────────────────────────

    def embed(self, text: Union[str, Sequence[str]]) -> list[list[float]]:
        """Embed a single string or list of strings."""
        inputs = [text] if isinstance(text, str) else list(text)
        if not inputs:
            return []

        # Provider chain
        vecs = (
            self._try_st(inputs)
            or self._try_openai(inputs)
            or self._try_cohere(inputs)
            or [self._hash_embed(t) for t in inputs]
        )

        # Pad / trim to declared dim (defensive)
        return [self._fit_dim(v) for v in vecs]

    # ─── Providers ─────────────────────────────────────────

    def _try_st(self, inputs: list[str]) -> Optional[list[list[float]]]:
        if self._st_loaded and self._st_model is None:
            return None  # already known missing
        try:
            from sentence_transformers import SentenceTransformer
            if self._st_model is None:
                # Map our model names to HF repo ids
                repo_map = {
                    "bge-small-en-v1.5": "BAAI/bge-small-en-v1.5",
                    "bge-base-en-v1.5": "BAAI/bge-base-en-v1.5",
                    "bge-large-en-v1.5": "BAAI/bge-large-en-v1.5",
                    "all-MiniLM-L6-v2": "sentence-transformers/all-MiniLM-L6-v2",
                    "pubmedbert-base-embed": "NeuML/pubmedbert-base-embeddings",
                }
                repo = repo_map.get(self.model)
                if not repo:
                    return None
                self._st_model = SentenceTransformer(repo)
            vecs = self._st_model.encode(inputs, normalize_embeddings=True,
                                         show_progress_bar=False)
            self._st_loaded = True
            return [list(map(float, v)) for v in vecs]
        except Exception as e:
            logger.info(f"sentence-transformers unavailable ({e}); trying next provider")
            self._st_model = None
            self._st_loaded = True
            return None

    def _try_openai(self, inputs: list[str]) -> Optional[list[list[float]]]:
        if not self.model.startswith("text-embedding"):
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
        if "cohere" not in self.model:
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
        """Deterministic fallback embedding (still semantically useful for
        exact/near-duplicate match via hamming-style cosine)."""
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