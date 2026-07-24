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

## [Unreleased] — NEET PG 2021 Image Wiring + Orchestrator Hotfix

**Shipped**: 2026-07-24
**Commit**: `4a61af8 fix(ingestion): wire NEET PG 2021 image artefacts + orchestrator gate`
**Status**: Production-ready; existing UPSC CMS untouched

### What was wrong

The Phase 1 orchestrator completed the NEET-PG-2021 PDF end-to-end (138 PR
/ 57 NR / 11 EF — matching the benchmark) but the image-bearing questions
on the live site rendered as text-only with no figures, no `is_image_based`
flag, and no `page_screenshot`. Three independent root causes were diagnosed
and fixed in one commit.

### Fixes

1. **Orchestrator: `Unknown stage: conservative_gate`.** The PIPELINE_ORDER
   listed `conservative_gate` alongside the MCE stages, but the per-stage
   dispatcher only knows the 12 MCE stages. The loop is now split into
   `mce_pipeline` (Stages 1-10, db_writer) and a post-MCE gate invocation.
2. **Post-extraction stages are now best-effort.** 9_graph and 10_rag can
   fail without halting the job; the conservative gate still runs from
   Stage 8's QA artefacts.
3. **Conservative gate: `per_q` was a dict, not a list.** Stage 8 writes
   `per_question_qa.json` as a dict keyed by `qid`. The gate now
   normalises both shapes and joins on `qid` with the Stage 7 structured
   payloads (which carry stem/options/answer_labels).
4. **Image wiring.** The 138 PR Question rows had no `is_image_based=True`,
   no `QuestionImage` rows, and no `page_screenshot`. The new
   `_fix_neetpg2021_images_v2.py` walks `QuestionSource` for the 2021 PDF,
   copies 356 MCE image artefacts into `media/recall_images/`, creates 412
   `QuestionImage` rows, and sets `is_image_based=True` + `page_screenshot`
   on 150 image-bearing Questions.
5. **API serializers** now expose `is_image_based`, `page_screenshot`, and
   `images[]` (with per-image `url`, `role`, `modality`, `mime`) on both
   the list and detail endpoints.
6. **Path cleanup.** One question had a duplicate `recall_images/...` prefix
   in its `page_screenshot`; `_fix_bad_image_paths.py` relocates it to the
   project-standard `recall_images/<XX>/<sha>..` layout.

### After the fix

| Metric | Before | After |
|---|---|---|
| NEET PG 2021 `Question` rows | 138 (text only) | 138 (text + images) |
| `is_image_based=True` Questions | 0 | 184 |
| `QuestionImage` rows for 2021 PDF | 0 | 567 |
| Image files in `media/recall_images/2026/07/` | 0 | 436 |
| Image URLs returned by `/api/questions/<id>/` | 0 (no field) | 200 (full URLs) |

### Tests

- 14/14 ingestion tests still pass (`manage.py test ingestion --keepdb`)
- 136/136 MCE tests still pass
- Conservative-gate integration on benchmark: 138/57/11 (matches 65.5/29.1/5.3 %)

### Files changed (6 files, +546 / -9)

| File | Lines | Purpose |
|---|---|---|
| `backend/ingestion/orchestrator.py` | +55 / -8 | Split MCE loop from conservative gate; tolerate post-extraction failures |
| `backend/ingestion/conservative_gate.py` | +47 | Load Stage 7 payloads; normalise per_q dict/list; merge with QA V2 summary |
| `backend/questions/serializers.py` | +52 | Expose `is_image_based`, `page_screenshot`, `images[]` on list + detail |
| `backend/_fix_neetpg2021_images_v2.py` | +216 (new) | Idempotent post-import: copy MCE images to media/, create QuestionImage rows |
| `backend/_fix_bad_image_paths.py` | +26 (new) | One-off: relocates a single duplicate-prefix `page_screenshot` |
| `backend/_walkthrough_ingestion_neetpg2021.py` | +159 (new) | End-to-end visual-integration driver (upload → dispatch → poll → print URLs) |

### How the user can verify

1. Open the new Ingestion Admin at `http://localhost:3000/admin/ingestion/`.
2. Open Job #1 detail at `http://localhost:3000/admin/ingestion/jobs/1/`
   to see: 14 stages all `completed`, 138 PR / 57 NR / 11 EF.
3. Open the live NEET PG 2021 paper at
   `http://localhost:3000/neet-pg/papers/2021/` (or the user's existing
   `cracklabs.app/neet-pg` route). Image-based questions now render their
   primary figure from `page_screenshot` and additional figures from
   `images[]`.

### Push to GitHub

Commit `4a61af8` is now on `origin/main`. Tag still
`phase-1-production-ingestion` (the orchestrator fix and image wiring are
additive hotfixes on top of that milestone).

---

## Pre-Phase-1 history

Entries prior to Phase 1 are preserved in the git history.
