# KNOWLEDGE_BASE_PIPELINE.md — Phase 5 design stub

**Status**: DESIGN ONLY. No code yet. Phase 1 emits `Question` rows via the conservative gate; Phase 5 derives KG rows from them.
**Last updated**: 2026-07-24

---

## Why Phase 5 exists

Phase 1's conservative gate writes Production Ready `Question` rows. The Knowledge Base app (`backend/knowledge_base/`) already maintains `KnowledgeChunk`, `KnowledgeEntity`, and `KnowledgeRelation` rows — but currently they're fed by an external `load_ontology`/`build_kb`/`ingest_source` flow.

Phase 5 closes the loop: every successfully-imported PYQ question becomes a `KnowledgeChunk`, its entities become `KnowledgeEntity` rows, and the relations join it to existing clinical knowledge.

---

## Adapter surface (`backend/ingestion/kg_adapter.py`, Phase 5 only)

```python
def derive_knowledge_rows(*, question: Question, job: ImportJob) -> DeriveResult:
    """One Question row → many KnowledgeChunk + KnowledgeEntity + KnowledgeRelation rows.
    Idempotent on (question.recall_text_hash, exam_type).
    Never writes back to Question."""
```

`DeriveResult` returns counts of chunks created / updated, entities extracted, relations emitted, plus a `kg_job_id` that maps to the existing `knowledge_base.IngestionJob` row.

The adapter is called from one place only: `ingestion.conservative_gate._import_production_ready`, immediately after the `DjangoWriter.write_question` call returns. So every PR question that survives the conservative gate also seeds the knowledge base.

---

## Three derivations, all idempotent

### 1. KnowledgeChunk

```python
KnowledgeChunk.objects.update_or_create(
    pyq_link=question,                  # already exists; nullable FK → Question
    defaults={
        "subject": question.subject,
        "topic": question.topic,
        "clinical_pearl_present": bool(question.explanation and len(question.explanation) > 200),
        "license": "internal-pyq",
        "text": f"{question.question_text}\n\n{question.explanation or ''}",
    },
)
```

### 2. KnowledgeEntity (from stem + explanation)

A small deterministic regex+matcher pulls disease / drug / anatomy terms from `question.question_text` and `question.explanation`. Each unique term becomes a `KnowledgeEntity(name, kind)`. Phase 5 doesn't ship an LLM entity extractor; it uses a curated dictionary maintained in `backend/knowledge_base/ontology/` (already exists for `load_ontology`).

```python
for term in extract_terms(question.question_text + " " + (question.explanation or "")):
    entity, _ = KnowledgeEntity.objects.get_or_create(name=term["name"], kind=term["kind"])
    KnowledgeRelation.objects.update_or_create(
        subject_entity=entity,
        chunk=chunk,
        kind="mentioned_in",
        defaults={"confidence": term["score"]},
    )
```

### 3. Cross-exam linking

The same `recall_text_hash` across exams (e.g. NEET PG 2021 Q-42 and INI-CET 2019 Q-31) collapses to one `KnowledgeChunk` via a `cross_exam_hash` row. Phase 5 walks `Question.objects.filter(recall_text_hash=X)` and consolidates incoming `KnowledgeChunk` rows under one parent. The audit trail (per-`Question` provenance) is preserved on each chunk's `pyq_link`.

---

## Adapter triggers

| Trigger | Phase | Behaviour |
|---|---|---|
| PR auto-import | Phase 1 conservative gate | Inline call to `derive_knowledge_rows`; rows written transactionally with `Question` |
| NR → PR (Phase 2 promotion) | Phase 2 review | Inline call on promote; uses the same idempotent update_or_create |
| Manual rebuild | Phase 5 management command | `python manage.py ingestion_rebuild_kg --since 2026-07-01` — backfills from existing `Question` rows; safe to re-run |

`ingestion_rebuild_kg` is the safety valve: if Phase 5 is enabled after a Phase 1 import has already run, the rebuild command walks every `Question` row newer than `--since` and derives its knowledge rows without touching UPSC tables.

---

## Audit trail

Phase 5 does NOT introduce a new audit table. It reuses the existing `knowledge_base.IngestionJob`:

```python
kg_job = knowledge_base.models.IngestionJob.objects.create(
    source="ingestion.conservative_gate",
    meta={
        "import_job_id": job.id,
        "question_id": question.id,
        "recall_text_hash": question.recall_text_hash,
    },
)
```

This row lives next to the existing `load_ontology` / `build_kb` rows, giving ops a single audit log across all KB ingests.

---

## What Phase 5 deliberately does NOT do

- **No LLM entity extraction.** The curated dictionary in `backend/knowledge_base/ontology/` is the source. Adding LLM extraction would risk hallucinated entities inside the medical KG; that's an explicit non-goal.
- **No embeddings.** Vector embeddings of chunks are deferred. The KB's hybrid BM25 + KG retrieval is the production retrieval path; embeddings are an optional add-on.
- **No entity embeddings either.** Same reasoning. The hybrid retrieval already supports cross-exam linking without vectors.

This keeps Phase 5 deterministic, idempotent, fast (microseconds per question), and trivially reversible.

---

## Rollout plan

1. Build the adapter behind a feature flag (`ENABLE_INGESTION_KG=0` default).
2. Run `ingestion_rebuild_kg --since 2026-07-01` against the existing PR `Question` rows. Assert: KG row counts match the `Question` count, audit log emits one row per Question, no `KnowledgeChunk` duplicates.
3. Enable the flag; next import batch writes KG rows inline.
4. Compare `python manage.py evaluate_kb` results before/after — retrieval precision should hold or improve.
