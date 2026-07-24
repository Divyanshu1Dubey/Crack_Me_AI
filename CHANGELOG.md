# CHANGELOG

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased] — Phase 1: Production Content Ingestion Framework

**Shipped**: 2026-07-24
**Tag**: `phase-1-production-ingestion`
**Status**: Production-ready; isolated from UPSC CMS

### Summary

Phase 1 wraps the existing Medical Content Engine (MCE — Stages 1-10 + QA V2)
in a production orchestration layer. The conservative gate (Production Ready →
auto-write `Question`; Needs Review → staged; Extraction Failure → blocked with
diagnostics) is the user-approved safe default. UPSC CMS remains untouched.

### Added

#### New ingestion app (`backend/ingestion/`, 18 Python files, 2,521 LOC)

- **`models.py`** — 8 new tables under `ingestion_` prefix:
  - `MaterialAsset` (sha256 unique, idempotent on re-upload)
  - `BatchRun` (top-level batch coordinator)
  - `ImportJob` (one row per attempt; FK chain to `MaterialAsset` + `BatchRun` + `retry_of` self)
  - `ImportJobStage` (one row per stage execution)
  - `ImportCheckpoint` (resume ledger; UNIQUE per `job`)
  - `ImportArtifact` (pointer rows to on-disk MCE artefacts)
  - `ImportLog` (structured logs bound to a job)
  - `StagedQuestion` (NR + EF holding; `published_question` FK to `Question` is `SET_NULL`)
- **`orchestrator.py`** — `run_full_pipeline_for_job` walks `PIPELINE_ORDER`; reads `latest_checkpoint`; saves checkpoint at every stage boundary; refreshes `job.status` for cancel detection
- **`pipeline_stages.py`** — `run_mce_stage` wraps each MCE stage call with `ImportJobStage` row creation
- **`conservative_gate.py`** — THE PR / NR / EF gate. Reads `08_qa/per_question_qa.json`; PR calls `DjangoWriter.write_question`; NR + EF create `StagedQuestion` rows only (no `Question` write)
- **`checkpoint.py`** — `save_checkpoint` / `latest_checkpoint` / `assert_token` (32-char hex secret)
- **`retry.py`** — `can_retry` + `plan_retry` (creates new `ImportJob` with `retry_of` set)
- **`tasks.py`** — `run_import_job`, `cancel_import_job`, `dispatch_job` (django-q2 wrappers)
- **`views.py`** — 12 REST endpoints (see REST API section)
- **`serializers.py`** — DRF serializers for all 8 models
- **`permissions.py`** — `IsIngestionAdmin` (mirrors the existing `IsControlTowerAdmin` pattern)
- **`constants.py`** — enums for `JOB_STATUS_CHOICES`, `JOB_TRANSITIONS`, `PIPELINE_ORDER`, `STAGE_CHOICES`, etc.
- **`exceptions.py`** — `IngestionError` hierarchy
- **`utils.py`** — `audit()` helper, `INGESTION_ARTEFACT_ROOT` resolver
- **`admin.py`** — 8 ModelAdmins (read-only surface)
- **`urls.py`** — `/api/ingestion/` route group

#### Management commands (4)

- `python manage.py ingestion_run_pending` — drains the `queued` queue
- `python manage.py ingestion_retry_failed` — bulk retries anything in `RETRYABLE_STATES`
- `python manage.py ingestion_rollback --job-id=N` — soft-deletes `Question` rows written by a job
- `python manage.py ingestion_purge_old_artefacts --max-age-days=N` — Phase 7 cold-storage hook (no-op today)

#### REST API (12 endpoints under `/api/ingestion/`)

| Verb | Path | Purpose |
|---|---|---|
| `GET` | `/materials/` | List material assets |
| `POST` | `/materials/` | Upload new PDF (multipart) |
| `GET` | `/materials/<sha16>/` | Material detail |
| `GET` | `/jobs/` | List jobs (filters: status, batch, material) |
| `POST` | `/jobs/` | Create import job |
| `GET` | `/jobs/<job_id>/` | Job detail + stage timeline |
| `POST` | `/jobs/<job_id>/retry/` | Re-queue failed / crashed / cancelled |
| `POST` | `/jobs/<job_id>/cancel/` | Cancel running job |
| `GET` | `/jobs/<job_id>/checkpoints/` | List `ImportCheckpoint` rows |
| `GET` | `/jobs/<job_id>/logs/` | List `ImportLog` rows |
| `GET` | `/jobs/<job_id>/stages/` | List `ImportJobStage` rows |
| `GET` | `/staged/` | List `StagedQuestion` rows (filterable by `qa_status`, `review_status`) |
| `GET` | `/batches/` | List `BatchRun` rows |
| `POST` | `/batches/` | Create batch from N material_sha16s |
| `GET` | `/batches/<batch_id>/` | Batch detail with per-job status grid |

All endpoints RBAC-gated by `IsIngestionAdmin` (admin role OR `is_superuser`).

#### Admin pages (`/admin/ingestion/*`, 7 new pages)

- `/admin/ingestion/` — landing tiles
- `/admin/ingestion/upload/` — drop zone + recent uploads
- `/admin/ingestion/jobs/` — jobs table (filters: status, batch, material, date)
- `/admin/ingestion/jobs/<id>/` — detail with stage timeline + retry/cancel buttons
- `/admin/ingestion/batches/` — batch list
- `/admin/ingestion/batches/<id>/` — batch detail grid
- `layout.tsx` — server-side admin role gate

Sidebar: 1 new admin link (5 → 5 admin links; gated by same `isAdmin` check).

### Migration

- **`backend/ingestion/migrations/0001_initial.py`** (676 lines, 8 tables)
- Zero migrations on existing apps (`questions`, `mce`, `importers`, `accounts`, `knowledge_base`, `ai_engine`, `analytics`, `textbooks`, `tests_engine`).

### Tests (14 tests, 3 files — 14/14 PASS)

| File | Tests | Coverage |
|---|---|---|
| `test_models.py` | 6 | `TestMaterialAssetIdempotent`, `TestImportJobStateMachine` (×2), `TestCheckpointUnique`, `TestStagedQuestionSetNull`, `TestImportLogOrdering` |
| `test_orchestrator.py` | 5 | `TestOrchestratorWritesStageRows`, `TestOrchestratorRetryIncrementsVersion`, `TestOrchestratorCancel`, `TestOrchestratorArtefactRoot`, `TestOrchestratorDoesNotMutateMce` |
| `test_conservative_gate.py` | 3 | `TestGatePRWritesQuestion`, `TestGateNRStagesNoQuestion`, `TestGateEFBlocksWithDiagnostics` |

MCE regression suite: **136/136 PASS** (verified via `pytest mce/tests/`).

### Documentation (9 docs in `backend/docs/ingestion/`)

- `PRODUCTION_IMPORT_ARCHITECTURE.md` — 7-phase map, data flow diagram, why isolated app, UPSC non-modification list
- `IMPORT_PIPELINE.md` — per-stage wiring, idempotency, audit trail, concurrency model, failure handling
- `RECOVERY_AND_RETRY.md` — checkpoint semantics, job state machine, crash recovery scenario, one-liners
- `ADMIN_REVIEW_SYSTEM.md` — Phase 2 design stub (triage UI, 8 actions, RBAC, audit integration)
- `IMPORT_DASHBOARD.md` — Phase 3 design stub (8 tiles + 5 charts, refresh cadence)
- `QUALITY_ANALYTICS.md` — Phase 4 design stub (failure-reason leaderboard, OCR distribution, trends)
- `KNOWLEDGE_BASE_PIPELINE.md` — Phase 5 design stub (PR→KG adapter, idempotent, deterministic)
- `SCALABILITY_GUIDE.md` — Phase 6+7 design stub (safety hardening, ExamProfile, LRU, cold-storage)
- `IMPLEMENTATION_SUMMARY.md` — implementation summary, 3 mermaid diagrams, every endpoint + curl, regression results, migration notes, 8-step rollout plan for the 6-PDF NEET PG batch

### Touched files (additive only — 4 files, 56 lines added)

| File | Change |
|---|---|
| `backend/crack_cms/settings.py` | 1 line in `INSTALLED_APPS` + 2 comment lines |
| `backend/crack_cms/urls.py` | 1 line: `path('api/ingestion/', include('ingestion.urls'))` + 1 comment line |
| `frontend/src/components/Sidebar.tsx` | 1 `<Link>` entry (`/admin/ingestion`) |
| `frontend/src/lib/api.ts` | 1 `ingestionAPI` axios namespace (~47 lines) |

### Generated artifacts (intentionally not committed)

- `backend/_artifacts_ingestion/` — per-job MCE artefact trees
- `backend/_artifacts_benchmark_post_fix/` — MCE benchmark artefacts (not ingestion concern)
- `backend/_audit_sample.json` — local audit snapshot

### Metrics

- Tests: 14/14 ingestion PASS, 136/136 MCE PASS
- Django `manage.py check`: 0 issues
- `makemigrations --check --dry-run`: no missing migrations on existing apps
- Frontend: `Sidebar.tsx` still renders all 5 admin links; `ingestionAPI` namespace is wired

### Out of scope (Phase 2-7 design stubs only)

- Review UI at `/admin/ingestion/review/` (Phase 2)
- Dashboard at `/admin/ingestion/dashboard/` (Phase 3)
- Quality analytics at `/admin/ingestion/analytics/` (Phase 4)
- Knowledge Base adapter (Phase 5)
- Deterministic checkpoint hashes + SHA validation + consistency verification (Phase 6)
- ExamProfile first-class config + LRU cache + cold-storage eviction (Phase 7)

### How to roll out

See `backend/docs/ingestion/IMPLEMENTATION_SUMMARY.md` §6 for the 8-step
rollout plan for the 6-PDF NEET PG batch.

---

## Pre-Phase-1 history

Entries prior to Phase 1 are preserved in the git history.
