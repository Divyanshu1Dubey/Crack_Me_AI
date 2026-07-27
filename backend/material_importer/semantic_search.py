"""Bridge between the importer and the existing sqlite_rag / RAGPipeline.

The pipeline already indexes PDF / textbook material into a TF-IDF
SQLite store at `backend/chroma_db/rag_store.sqlite3`. After ingest we
push every approved `ExtractedQuestion` + `ExtractedTheory` block into
the same store so they participate in semantic retrieval for the AI
tutor, search, and adaptive tests.
"""
from __future__ import annotations

import logging
from typing import Iterable, List

log = logging.getLogger(__name__)


def add_to_rag_index(
    questions: Iterable["ExtractedQuestion"],  # type: ignore[name-defined]
    theory: Iterable["ExtractedTheory"],        # type: ignore[name-defined]
) -> int:
    """Push docs into the RAG index. Returns number of docs added.

    Skips silently if the RAG pipeline is disabled in this environment
    (it hardcodes a DEBUG gate) — that's intentional; see ai_engine.
    """
    try:
        from ai_engine.rag_pipeline import RAGPipeline  # type: ignore
    except Exception as exc:
        log.warning("RAG pipeline import failed: %s", exc)
        return 0

    pipeline = RAGPipeline()
    docs: List[str] = []
    for eq in questions:
        stem = eq.question_text or ""
        body = " ".join(filter(None, [eq.option_a, eq.option_b, eq.option_c, eq.option_d, eq.explanation]))
        docs.append(f"QUESTION: {stem}\n{body}")
    for t in theory:
        docs.append(f"THEORY: {t.heading}\n{t.subheading}\n{t.body_text}")

    if not docs:
        return 0
    n = 0
    for d in docs:
        try:
            pipeline.add_document(d, source="material_importer")
            n += 1
        except Exception:
            continue
    return n
