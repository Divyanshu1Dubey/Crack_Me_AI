# Phase 4 — Search Audit

**Date:** 2026-07-22

## Endpoint catalog

| URL | Permission | Notes |
|---|---|---|
| `GET /api/questions/recall_search/` | AllowAny | Phase 2; extended Phase 3 + Phase 4 cache |
| `GET /api/questions/images/facets/` | AllowAny | Phase 3 image modality etc. |
| `GET /api/questions/practice_modes/` | AllowAny | Mode catalogue |
| `GET /api/questions/practice_queue/?mode=...` | IsAuthenticated | Practice queues |

## Filter dimensions (Phase 3 additions)

* `q` — keyword search (tokenized AND across 5 fields).
* `exam_type`, `year`, `session`, `recall_status`,
  `clinical_category`, `question_type`, `difficulty`,
  `is_image_based`, `concept_id`, `subject_id`, `topic_id` —
  all indexed columns on `Question`.
* `diagnosis`, `drug`, `disease`, `investigation`,
  `clinical_system`, `subtopic` — tokenized OR across 6 text fields.
* `modality`, `body_region`, `has_diagram`, `has_table` — image-level
  filters via `QuestionImage` join.
* `image_ocr` — substring search on `QuestionImage.ocr_text`.
* `has_image` — boolean.
* `min_confidence` — float floor on `confidence_score`.

## Facets (returned in every search response)

`exam_type, year, session, recall_status, clinical_category,
question_type, difficulty, modality` — all `dict[value, count]`.

## Cache

* `recall_search` — 60-second cache keyed on `QUERY_STRING`.
* `dashboard_v3` — 60-second per-user cache (Phase 4 addition).
* AI per-question — 24-hour per-question cache.

## Ranking

Currently alphabetical-by-year, ID-tiebreak.  Recommend adding
BM25-style ranking in Phase 5 once FTS5 mirror is materialised.

## Phase 4 actions taken

* Removed unused `Sum` import in `dashboard_v3.py`.
* Confirmed `select_related("subject", "topic")` is applied at the top
  of every Phase-3 queryset.
* Confirmed facet queries use `values().annotate(Count)` (not raw
  aggregates).

## Recommended Phase-5 follow-ups

* Materialise FTS5 mirror on `Question(question_text, explanation,
  ai_explanation, mnemonic, ai_clinical_pearl)`.
* Add `typo-tolerant` search (Postgres `pg_trgm` or DuckDB-WASM in
  the front end).
* Add `SearchLog` model + instrumentation for
  `/api/analytics/search_analytics/`.
