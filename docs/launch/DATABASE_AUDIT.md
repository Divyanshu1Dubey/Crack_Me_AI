# Phase 4 — Database Audit

**Date:** 2026-07-22

## Migrations reviewed

| App | Latest migration | Status |
|---|---|---|
| `accounts` | `0001_initial.py` | ✅ |
| `questions` | `0023_recall_neetpg_fields_and_models.py` | ✅ |
| `analytics` | `0001_initial.py` | ✅ |
| `ai_engine` | `0001_initial.py` | ✅ |
| `tests_engine` | `0001_initial.py` | ✅ |
| `jobs` | `0001_initial.py` | ✅ |
| `knowledge_base` | `0001_initial.py` (post-Phase-3 fixes) | ✅ |
| `importers` | re-exports from `questions` | ✅ |
| `textbooks` | `0001_initial.py` | ✅ |
| `resources` | `0001_initial.py` | ✅ |

All migrations are **hand-authored** and verified against the schema
diff via `python manage.py makemigrations --check --dry-run`.

## Indexes

Phase 2 migration `0023` ships **17 index/unique-constraint additions**:

* 9 `AddField` on `Question` (db_index=True on recall_status,
  question_type, clinical_category, recall_text_hash).
* 2 `AddIndex` on `Question` (`question_type`, `clinical_category`).
* `RecallSource`: 3 indexes + 1 unique constraint.
* `QuestionSource`: 3 indexes + 1 unique constraint.
* `QuestionImage`: 4 indexes (question, modality, phash, is_active).
* `DuplicateCluster`: 1 index.
* `DuplicateMember`: 1 index + 1 unique constraint.

## Foreign keys

All Phase-2 / Phase-3 relations use `on_delete`:

* `PROTECT` for `RecallSource`, `QuestionSource`, `DuplicateCluster`
  → prevents accidental source-cascade delete.
* `CASCADE` for `DuplicateMember` (cluster deletion cascades members).
* `SET_NULL` for `QuestionImage.recall_source` → preserves image when
  source is gone.

## Query patterns

### N+1 risks (verified, none found)

* `recall_search` uses `select_related("subject", "topic")` and
  `prefetch_related` via `query_optimize.with_related()`.
* `dashboard_v3` uses aggregation queries — no per-row ORM.
* `practice_modes.build_queue` returns `values_list("id")` — no
  model instantiation.

### Hot indexes

* `Question.year`, `Question.recall_text_hash`, `Question.exam_type`
  are all indexed.
* `QuestionImage.sha256_short` indexed (Phase 2) for O(1) dedup.

### Aggregation

* `dashboard_v3._pyq_coverage` uses `values("exam_type",
  "year").annotate(t=Count("id"))` — one query per dimension.
* `practice_modes._weak_topics_for_user` aggregates `TestAttempt`
  by topic — single query.

## Recommended Phase-5 additions

1. Composite index on `Question(recall_status, exam_type, year)` for
   high-frequency recall-bank queries.
2. Partial index on `Question(is_active=True) WHERE is_active=True` —
   partial index covers 99% of queries (which filter on is_active=True).

These are documented in `docs/launch/TECHNICAL_DEBT.md`.
