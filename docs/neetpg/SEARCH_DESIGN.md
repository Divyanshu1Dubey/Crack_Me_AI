# Search Design — Phase 2

> Existing DRF `QuestionViewSet` keeps its `search_fields` + `filterset_fields`. Phase 2 adds a recall-aware search action and a SQLite FTS5 mirror (Postgres tsvector is the prod upgrade path).

---

## 1. Existing search surface (unchanged)

- `QuestionViewSet.search_fields = ['question_text', 'explanation', 'concept_tags']` — DRF `SearchFilter` (icontains).
- `QuestionViewSet.filterset_fields` include `year`, `subject`, `topic`, `difficulty`, `exam_type`, `is_verified_by_admin`, `is_scholarship_eligible`, `needs_review`, `is_controversial`.
- Custom `?flagged=true|false` filter and `?accuracy_min=…&accuracy_max=…` annotations.

We **do not** touch any of this.

---

## 2. New recall-aware search action

`QuestionViewSet.recall_search` — `GET /api/questions/recall_search/`.

Query parameters:

| Param | Type | Default | Notes |
|---|---|---|---|
| `q` | str | `''` | full-text query |
| `exam_type` | str enum | `neet_pg` | `cms / neet_pg / ini_cet / aiims_pg / usmle / fmge` |
| `subject` | int | — | FK to `Subject` |
| `topic` | int | — | FK to `Topic` |
| `subtopic` | int | — | Phase 2 subtopic hierarchy |
| `year` | int | — | |
| `session` | str enum | — | `jan / jul / may / nov / none` |
| `recall_status` | str enum | — | `recall / coaching_compiled / official_compiled` |
| `clinical_category` | str enum | — | `clinical / preclinical / paraclinical` |
| `question_type` | str enum | — | `single_best / multiple_correct / assertion_reason / match / image_based / numerical` |
| `difficulty` | str enum | — | `easy / medium / hard / expert` |
| `is_image_based` | bool | — | `true / false` |
| `concept_id` | str | — | exact match on `Question.concept_id` |
| `modality` | str enum | — | filters via `QuestionImage` (joined) |
| `image_ocr` | str | — | matches inside `QuestionImage.ocr_text` |
| `min_confidence` | float 0..1 | 0.0 | `Question.confidence_score >= min` |

Response:

```json
{
  "count": 1234,
  "facets": {
    "exam_type": {"neet_pg": 1234},
    "year": {"2018": 200, "2019": 200, ...},
    "subject": {"Medicine": 200, "Surgery": 150, ...},
    "recall_status": {"recall": 1100, "coaching_compiled": 134},
    "clinical_category": {"clinical": 1000, "preclinical": 200, "paraclinical": 34},
    "modality": {"radiology": 80, "histopathology": 40, ...}
  },
  "results": [/* QuestionListSerializer */]
}
```

Performance budget: < 200 ms p95 for 1M-question corpus on Postgres + pgvector + tsvector; < 500 ms on SQLite with FTS5 mirror.

---

## 3. SQLite FTS5 mirror

Local dev / SQLite uses a virtual table `questions_question_fts`:

```sql
CREATE VIRTUAL TABLE questions_question_fts USING fts5(
  question_id UNINDEXED,
  question_text,
  explanation,
  mnemonic,
  ai_explanation,
  ai_clinical_pearl,
  concept_tags,
  tokenize='porter unicode61'
);

CREATE VIRTUAL TABLE questions_questionimage_fts USING fts5(
  image_id UNINDEXED,
  ocr_text,
  caption,
  tokenize='porter unicode61'
);
```

Triggers maintain sync on `INSERT/UPDATE/DELETE` of `Question` and `QuestionImage`.

`questions.recall_search.build_fts_query()` returns a `WHERE questions_question_fts MATCH ?` SQL fragment + a parameterised tsquery.

Postgres prod migration: replace with `tsvector` + `pg_trgm` GIN index on `Question.question_text`, `Question.explanation`, `Question.mnemonic`, `Question.ai_explanation`, `QuestionImage.ocr_text`. Migration path: when `DATABASES['default']['ENGINE']` ends with `postgresql`, the search action issues a `to_tsquery('english', ?)` query.

---

## 4. Cross-corpus search (Phase 3 hook)

`Question.concept_id` already exists. The recall search action returns `related_question_ids` derived from `Question.similar_questions` M2M plus the `DuplicateCluster.canonical_question`. A future upgrade can compute semantic similarity via embeddings stored in `QuestionImage.embedding` (a future optional migration).

---

## 5. Frontend integration

`frontend/src/components/recall/RecallSearchBox.tsx` exposes chip filters wired to the recall_search endpoint. **It is opt-in; existing pages stay unchanged.**

---

## 6. Privacy

Search results are filtered by `Question.is_active=True` for non-admin users — same as the existing `QuestionViewSet`.

---

## 7. Caching

Per-query cache key: `recall_search:{sha256(normalised_params)}`. Cached for 5 minutes via `django.core.cache.cache.get_or_set`. Cache invalidates on:

- `Question.save()` (signal-based).
- `QuestionImage.save()` (signal-based).
- `neetpg_rollback` (manual cache clear).

---

## 8. Indexes that exist after the migration

From existing `Question` Meta:
- `(year, subject)`, `(difficulty)`, `(exam_source)`, `(paper)`, `(is_active, is_verified_by_admin)`, `(subject, topic, year, difficulty)`

Added in Phase 2:
- `(recall_status)`, `(question_type)`, `(clinical_category)`, `(recall_text_hash)`

For `QuestionImage`:
- `(question)`, `(sha256_short)`, `(phash)`, `(modality)`

For `QuestionSource`:
- `(recall_source, page_number)`, `(question)`

---

## 9. What's deliberately out of scope

- Embedding-based semantic search (Phase 3).
- Federated search across `knowledge_base` (separate app).
- Cross-app concept graph (future).