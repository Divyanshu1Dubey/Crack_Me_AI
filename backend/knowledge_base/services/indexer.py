"""
Embedding indexer — fill in KnowledgeEmbedding rows for chunks that
don't have one yet (or are stale). Designed to run as a background
job after ingestion.
"""

import logging
from typing import Optional

from django.db import transaction
from django.utils import timezone

from knowledge_base.models import KnowledgeChunk, KnowledgeEmbedding
from .embedding import EmbeddingService

logger = logging.getLogger(__name__)


class EmbeddingIndexer:
    def __init__(self, embedding: Optional[EmbeddingService] = None,
                 batch_size: int = 64):
        self.embedding = embedding or EmbeddingService()
        self.batch_size = batch_size

    def index_pending(self, max_chunks: Optional[int] = None,
                      model: Optional[str] = None) -> int:
        model_name = model or self.embedding.model
        # Chunks without an embedding for this model
        qs = (KnowledgeChunk.objects
              .filter(is_active=True, approval_state__in=[
                  KnowledgeChunk.APPROVAL_AUTO, KnowledgeChunk.APPROVAL_ADMIN,
              ])
              .exclude(embedding__model=model_name)
              .order_by("id"))
        if max_chunks:
            qs = qs[:max_chunks]

        indexed = 0
        batch = []
        for chunk in qs.iterator(chunk_size=self.batch_size):
            batch.append(chunk)
            if len(batch) >= self.batch_size:
                indexed += self._index_batch(batch, model_name)
                batch = []
        if batch:
            indexed += self._index_batch(batch, model_name)
        logger.info(f"EmbeddingIndexer: indexed {indexed} chunks with {model_name}")
        return indexed

    @transaction.atomic
    def _index_batch(self, chunks: list[KnowledgeChunk], model_name: str) -> int:
        texts = [c.text for c in chunks]
        try:
            vecs = self.embedding.embed(texts)
        except Exception as e:
            logger.warning(f"Embedding batch failed: {e}")
            return 0
        n = 0
        for chunk, vec in zip(chunks, vecs):
            try:
                KnowledgeEmbedding.objects.update_or_create(
                    chunk=chunk,
                    model=model_name,
                    defaults={
                        "dim": len(vec),
                        "vector": vec,
                    },
                )
                n += 1
            except Exception as e:
                logger.debug(f"Failed to save embedding for chunk {chunk.id}: {e}")
        return n