"""
AI Engine retrieval layer.

Phase 3 (2026-07-29): FederatedRetrieval that queries both the
legacy TF-IDF store (`ai_engine.rag_pipeline.RAGPipeline`) and the
modern embeddings-aware knowledge base
(`knowledge_base.retrieval.pipeline.RetrievalPipeline`).

A single user-facing API (`search`, `rag_answer`,
`find_textbook_reference`) merges results from both backends via
Reciprocal Rank Fusion. Either backend can be missing or empty
without breaking the federated call.
"""
from .federated import FederatedRetrieval, FederatedResult  # noqa: F401