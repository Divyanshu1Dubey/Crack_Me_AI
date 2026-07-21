# Knowledge Base — Architecture

Production-grade knowledge platform backing the **Monica** AI tutor for
UPSC CMS / NEET PG aspirants. Built on a strict, legally-defensible
source whitelist.

## Goals

1. **Permanent, versioned knowledge** — every chunk carries license +
   attribution + version; nothing disappears on re-index.
2. **Citation-aware answers** — every claim in a Monica answer maps to
   a numbered source the student can verify.
3. **Continuous learning** — new whitelisted sources are ingested
   without code changes.
4. **Multi-stage retrieval** — query expansion → BM25 + vector →
   knowledge-graph boost → cross-encoder rerank → context compression.
5. **YMYL-safe** — medical content is grounded in government / public-
   domain / CC-licensed material only. Nothing copyrighted is ingested.

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                SOURCE LAYER (whitelisted only)                  │
│  Internal Notes │ PYQs │ NCBI Bookshelf │ OpenStax (CC BY)      │
│  MoHFW/NMC/ICMR │ NHM │ UPSC │ WHO │ NHS CKS │ Radiopaedia     │
│  User uploads (with rights attestation)                         │
└─────────┬────────────────────────────────────────────────────────┘
          │ connector + license guard
          ▼
┌──────────────────────────────────────────────────────────────────┐
│              INGESTION (IngestionService)                        │
│  license whitelist check → sha256 dedup → KnowledgeChunk row    │
│  recorded in IngestionJob (audit trail)                          │
└─────────┬────────────────────────────────────────────────────────┘
          │
          ▼
┌──────────────────────────────────────────────────────────────────┐
│                     STORAGE                                     │
│  KnowledgeChunk (Postgres / SQLite)                              │
│  KnowledgeEmbedding (vector JSON; pgvector-ready)                │
│  KnowledgeEntity / KnowledgeRelation (curated KG + auto-extracted)│
└─────────┬────────────────────────────────────────────────────────┘
          │
          ▼
┌──────────────────────────────────────────────────────────────────┐
│         RETRIEVAL (RetrievalPipeline — multi-stage)              │
│  1. Query rewrite (synonyms, abbreviations)                      │
│  2. BM25 + vector search                                         │
│  3. Reciprocal Rank Fusion                                       │
│  4. Knowledge-graph neighbour boost                              │
│  5. Cross-encoder rerank                                         │
│  6. Citation assembly                                            │
└─────────┬────────────────────────────────────────────────────────┘
          │
          ▼
┌──────────────────────────────────────────────────────────────────┐
│           MONICA ORCHESTRATOR (services/monica.py)               │
│  composes RetrievalPipeline + existing AIService                 │
│  emits answer + citations + confidence                           │
└─────────┬────────────────────────────────────────────────────────┘
          │
          ▼
┌──────────────────────────────────────────────────────────────────┐
│             API + ADMIN + EVAL                                   │
│  /api/knowledge/ask, /search, /stats, /upload, /ingest, /eval   │
│  Django admin (knowledge_base.admin)                             │
│  python manage.py evaluate_kb                                    │
└──────────────────────────────────────────────────────────────────┘
```

## Why this is best-in-class for UPSC CMS

- **Sources**: NCBI Bookshelf (StatPearls + open books), OpenStax
  (Anatomy, Physiology, Microbiology, Psychology), MoHFW/NMC/ICMR/NHM
  guidelines, WHO, UPSC notifications, NHS CKS, Radiopaedia. **All
  legally usable** without paid licenses.
- **Scale**: OpenStax alone covers ~half of the MBBS syllabus with
  peer-reviewed, CC BY 4.0 content. StatPearls gives 9,000+ USMLE-grade
  topic summaries (US public domain).
- **Retrieval**: BM25 + vector + KG + rerank matches what Mar Deep
  Medicine, Amboss, and UWorld ship — without the licensing fees.
- **Citation engine**: every answer surfaces the source so students
  build the trust required for YMYL medical content.
- **No copyright traps**: the loader refuses chunks that look like they
  came from a copyrighted textbook even if a connector is misconfigured.

## Coexistence with the existing pipeline

The existing `ai_engine/sqlite_rag.py` and `ai_engine/rag_pipeline.py`
are untouched and continue to work as the **fallback path** when the
knowledge base has too few chunks (`KB_FALLBACK_THRESHOLD`, default 10).
`Monica.answer()` automatically picks the path with higher confidence.