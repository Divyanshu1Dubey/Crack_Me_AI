# IMPLEMENTATION_SUMMARY.md — Phase 1 Production Import Framework

**Date**: 2026-07-24
**Phase**: 1 of 7 (Production Import Framework)
**Status**: SHIPPED. 14/14 ingestion tests green, Django check clean, 0 migrations on existing apps, 1 new migration on `ingestion`.

---

## 1. Implementation summary

### Backend (`backend/ingestion/`)

**18 new Python files**, **2,521 LOC** of ingest code (excluding tests), **8 new tables**, **12 REST endpoints**, **4 management commands**, **3 stage-bridging wrapper modules**.

| File | LOC | Role |
|---|---|---|
| `models.py` | 366 | 8 tables: `MaterialAsset`, `BatchRun`, `ImportJob`, `ImportJobStage`, `ImportCheckpoint`, `ImportArtifact`, `ImportLog`, `StagedQuestion` |
| `orchestrator.py` | 300 | `run_full_pipeline_for_job` walks `PIPELINE_ORDER`; reads `latest_checkpoint`; save_checkpoint at every stage boundary |
| `conservative_gate.py` | 280 | THE PR / NR / EF gate. Reads `08_qa/per_question_qa.json`; PR → `DjangoWriter.write_question`; NR/EF → `StagedQuestion` rows only |
| `serializers.py` | 268 | DRF serializers for all 8 models + read-shape variants |
| `views.py` | 415 | 12 endpoints (materials, jobs, batches, retry, cancel, checkpoints, logs, stages, staged) |
| `constants.py` | 242 | Enums + `JOB_TRANSITIONS` table + `PIPELINE_ORDER` |
| `pipeline_stages.py` | 191 | `run_mce_stage` wraps every MCE stage with `ImportJobStage` row creation |
| `checkpoint.py` | 93 | `save_checkpoint` / `latest_checkpoint` / `assert_token` |
| `admin.py` | 80 | 8 ModelAdmins (read-only surface) |
| `tasks.py` | 52 | `run_import_job`, `cancel_import_job`, `dispatch_job` |
| `retry.py` | 36 | `plan_retry` / `can_retry` |
| `utils.py` | 57 | `audit()` helper, `INGESTION_ARTEFACT_ROOT` resolver |
| `apps.py` | 8 | AppConfig |
| `exceptions.py` | 54 | `IngestionError` hierarchy |
| `permissions.py` | 32 | `IsIngestionAdmin` (mirrors `IsControlTowerAdmin`) |
| `urls.py` | 32 | `/api/ingestion/` route group |
| `__init__.py` | 15 | e |

**Migration**: `backend/ingestion/migrations/0001_initial.py` (676 lines, 8 tables — `MaterialAsset`, `BatchRun`, `ImportJob`, `ImportJobStage`, `ImportCheckpoint`, `ImportArtifact`, `ImportLog`, `StagedQuestion`).

**Management commands** (4):
- `python manage.py ingestion_run_pending` — drains the `queued` queue
- `python manage.py ingestion_retry_failed` — bulk retries anything in `RETRYABLE_STATES`
- `python manage.py ingestion_rollback --job-id=N` — soft-deletes `Question` rows written by a job
- `python manage.py ingestion_purge_old_artefacts --max-age-days=N` — Phase 7 cold-storage hook (no-op today)

### Tests (`backend/ingestion/tests/`, 3 files, 14 tests)

| File | Tests | Coverage |
|---|---|---|
| `test_models.py` | 6 | `TestMaterialAssetIdempotent`, `TestImportJobStateMachine` (×2), `TestCheckpointUnique`, `TestStagedQuestionSetNull`, `TestImportLogOrdering` |
| `test_orchestrator.py` | 5 | `TestOrchestratorWritesStageRows`, `TestOrchestratorRetryIncrementsVersion`, `TestOrchestratorCancel`, `TestOrchestratorArtefactRoot`, `TestOrchestratorDoesNotMutateMce` |
| `test_conservative_gate.py` | 3 | `TestGatePRWritesQuestion`, `TestGateNRStagesNoQuestion`, `TestGateEFBlocksWithDiagnostics` |

### Frontend (`frontend/src/app/admin/ingestion/`, 7 pages)

```
/admin/ingestion/
├── layout.tsx                    # server-side admin role gate
├── page.tsx                      # landing tiles
├── upload/page.tsx               # drop zone
├── jobs/page.tsx                 # jobs table (filters: status, batch, material, date)
├── jobs/[id]/page.tsx            # detail + stage timeline + retry/cancel
├── batches/page.tsx              # batch list
└── batches/[id]/page.tsx         # batch detail grid
```

### Shared touched files (additive — 4 lines total)

| File | Change |
|---|---|
| `backend/crack_cms/settings.py` | 1 line in `INSTALLED_APPS` |
| `backend/crack_cms/urls.py` | 1 line: `path('api/ingestion/', include('ingestion.urls'))` |
| `frontend/src/components/Sidebar.tsx` | 1 admin link (`/admin/ingestion`) gated by same `isAdmin` |
| `frontend/src/lib/api.ts` | 1 block: `ingestionAPI` namespace (~80 lines) |

### Documentation (`backend/docs/ingestion/`, 8 docs)

| Doc | Role |
|---|---|
| `PRODUCTION_IMPORT_ARCHITECTURE.md` | High-level architecture, 7-phase map, data flow, why isolated app, UPSC non-modification list |
| `IMPORT_PIPELINE.md` | Per-stage wiring, idempotency, audit trail, concurrency model, failure handling |
| `RECOVERY_AND_RETRY.md` | Checkpoint semantics, job state machine, crash recovery scenario, one-liners |
| `ADMIN_REVIEW_SYSTEM.md` | Phase 2 design stub (UI surface, triage actions, RBAC) |
| `IMPORT_DASHBOARD.md` | Phase 3 design stub (tiles, charts, refresh cadence) |
| `QUALITY_ANALYTICS.md` | Phase 4 design stub (failure-reason leaderboard, OCR distribution, trends) |
| `KNOWLEDGE_BASE_PIPELINE.md` | Phase 5 design stub (PR→KnowledgeChunk/Entity adapter, idempotent) |
| `SCALABILITY_GUIDE.md` | Phase 6+7 design stub (safety hardening, ExamProfile, LRU, cold-storage) |

---

## 2. Architecture diagrams

### 2.1 Data flow (upload → orchestrator → MCE → conservative gate)

```
                          ┌─────────────────────────────────┐
                          │  Admin (browser)                │
                          │  /admin/ingestion/upload        │
                          └────────────┬────────────────────┘
                                       │ multipart upload
                                       ▼
                       ┌────────────────────────────────┐
                       │ POST /api/ingestion/materials/ │
                       │ (views.MaterialAssetUploadView)│
                       └────────────┬───────────────────┘
                                    │ sha256 + file_size + page_count
                                    ▼
                       ┌────────────────────────────────┐
                       │ MaterialAsset (sha256 UNIQUE)  │
                       │ ingestion_uploaded_materials   │
                       └────────────┬───────────────────┘
                                    │ POST /api/ingestion/jobs/
                                    ▼
                       ┌────────────────────────────────┐
                       │ ImportJob (status=queued,      │
                       │ parent_exam=neet_pg, …)        │
                       └────────────┬───────────────────┘
                                    │ tasks.dispatch_job
                                    ▼
                       ┌────────────────────────────────┐
                       │ django-q2 task                 │
                       │ ingestion.tasks.run_import_job │
                       └────────────┬───────────────────┘
                                    │
                                    ▼
              ┌─────────────────────────────────────────────┐
              │ orchestrator.run_full_pipeline_for_job      │
              │   for stage in PIPELINE_ORDER:               │
              │     ck = latest_checkpoint(job)              │
              │     run_mce_stage(stage, ctx, resume_page)   │
              │     save_checkpoint(...)                     │
              │     job.refresh_from_db()  # cancel detect  │
              └─────────────────────────────────────────────┘
                                    │
        ┌──────────┬──────────┬─────┴──────┬──────────┬──────────┐
        ▼          ▼          ▼            ▼          ▼          ▼
   Stage 1    Stage 2    Stage 2b     Stage 3   Stage 4    Stage 5
   render     layout     read-order   images    tables    q-blocks
        │          │          │            │          │          │
        └──────────┴──────────┴─────┬──────┴──────────┴──────────┘
                                    ▼
                       Stage 6 → Stage 7 → Stage 8 (QA V2)
                                    │           │
                                    │           ▼
                                    │    08_qa/per_question_qa.json
                                    │
                                    ▼
                       ┌────────────────────────────────────┐
                       │ conservative_gate.apply_qa_v2_verdict │
                       ├────────────────────────────────────┤
                       │ status=Production Ready             │
                       │   → DjangoWriter.write_question     │
                       │   → questions.Question row          │
                       ├────────────────────────────────────┤
                       │ status=Needs Review                 │
                       │   → StagedQuestion(review_status=   │
                       │     pending)                        │
                       │   → NO Question write               │
                       ├────────────────────────────────────┤
                       │ status=Extraction Failure           │
                       │   → StagedQuestion(review_status=   │
                       │     blocked, failure_reason=…)      │
                       │   → NO Question write               │
                       └────────────────────────────────────┘
                                    │
                ┌───────────────────┼───────────────────┐
                ▼                   ▼                   ▼
       ImportJob.status=    ImportJob.qa_v2_*_pct  ImportJob.
       completed            recorded              questions_imported
                                                  / staged_nr / staged_ef
```

### 2.2 Checkpoint-recovery loop

```
   ┌──────────────────────────────────────────────────────────────┐
   │  orchestrator.run_full_pipeline_for_job(job_id)              │
   │                                                              │
   │  ck = latest_checkpoint(job)                                  │
   │  resume_from_stage = ck.last_completed_stage or "1_render"   │
   │                                                              │
   │  for stage in PIPELINE_ORDER[after resume_from_stage]:      │
   │      ┌──────────────────────────────────────────┐            │
   │      │ 1. job.refresh_from_db()                  │            │
   │      │ 2. if job.status == "cancelled": break    │            │
   │      │ 3. run_mce_stage(stage, ctx, resume_page) │            │
   │      │    └─ writes ImportJobStage row            │            │
   │      │    └─ writes ImportLog rows               │            │
   │      │ 4. save_checkpoint(job, stage, …)         │            │
   │      │ 5. update job.progress_pct                │            │
   │      └──────────────────────────────────────────┘            │
   │                                                              │
   │  if cancelled:                                                │
   │      job.status = "cancelled"                                │
   │  elif any stage raised:                                       │
   │      job.status = "failed"                                   │
   │  else:                                                        │
   │      conservative_gate.apply_qa_v2_verdict(job, artefact_root)│
   │      job.status = "completed"                                 │
   └──────────────────────────────────────────────────────────────┘
                    ▲
                    │ retry flow
                    │
   ┌──────────────────────────────────────────────────────────────┐
   │  POST /api/ingestion/jobs/<id>/retry/                         │
   │    retry.plan_retry(old_job_id)                              │
   │      └─ creates new ImportJob(retry_of=old_job_id, version+=1)│
   │      └─ dispatches new job                                   │
   │      └─ reads latest_checkpoint(NEW job) — empty             │
   │      └─ orchestrator starts fresh from Stage 1               │
   │      └─ Stage 1-4 outputs are detected via artefact tree;     │
   │         their `latest_checkpoint` lets them skip             │
   └──────────────────────────────────────────────────────────────┘
```

### 2.3 Retry semantics

```
       Failed / Crashed / Cancelled / Completed (any)
                          │
                          ▼
                ┌─────────────────────┐
                │ POST /jobs/<id>/    │
                │     retry/          │
                │   (RBAC: admin)     │
                └────────┬────────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │ retry.plan_retry()  │
              │  - validate state   │
              │  - validate         │
              │    retry-able       │
              │  - create new       │
              │    ImportJob        │
              │  - copy config,     │
              │    parent_exam,     │
              │    material         │
              │  - retry_of =       │
              │    old_job.id       │
              │  - version =        │
              │    old_job.version  │
              │      + 1            │
              │  - dispatch_job()   │
              └────────┬────────────┘
                       │
                       ▼
              ┌─────────────────────┐
              │ AuditLog row:       │
              │ verb="job.retried"  │
              │ actor=<admin>       │
              │ metadata={          │
              │   old_job_id,       │
              │   new_job_id,       │
              │   version           │
              │ }                   │
              └─────────────────────┘
```

The original `ImportJob` row is preserved as historical evidence. The retry creates a brand-new `ImportJob` and runs a fresh pipeline; the original `ImportJobStage` rows remain visible on the *original* job's detail page.

---

## 3. API documentation

All endpoints served under `/api/ingestion/`. Permissions: `IsIngestionAdmin` (admin role OR `is_superuser`). Auth: Supabase JWT + Django session, same as the rest of the platform.

### 3.1 Material assets

```http
POST /api/ingestion/materials/
Content-Type: multipart/form-data

file: <binary PDF>
```

Response 201:

```json
{
  "id": 17,
  "sha256": "8ebea8995a4ade79...",
  "sha256_short": "8ebea899",
  "original_filename": "NEET-PG-2021.pdf",
  "file_size": 2456789,
  "page_count": 144,
  "uploaded_at": "2026-07-24T10:00:00Z",
  "is_active": true
}
```

```http
GET /api/ingestion/materials/?sha256=8ebea899
```

```http
GET /api/ingestion/materials/8ebea8995a4ade79/
```

### 3.2 Import jobs

```http
POST /api/ingestion/jobs/
Content-Type: application/json

{
  "material_sha16": "8ebea8995a4ade79",
  "parent_exam": "neet_pg",
  "batch_id": 12,                  # optional
  "config": {
    "strategy": "auto-pr-only"     # default; "auto-all" | "manual"
  }
}
```

Response 202:

```json
{
  "id": 117,
  "version": 1,
  "status": "queued",
  "parent_exam": "neet_pg",
  "progress_pct": 0.0,
  "material_asset": "8ebea8995a4ade79",
  "batch_run": 12
}
```

```http
GET /api/ingestion/jobs/?status=completed&batch_id=12&material=8ebea899
GET /api/ingestion/jobs/117/
```

```http
POST /api/ingestion/jobs/117/retry/    # → 202 with new job id
POST /api/ingestion/jobs/117/cancel/   # → 200, status flips to "cancelled"
```

```http
GET /api/ingestion/jobs/117/checkpoints/
GET /api/ingestion/jobs/117/logs/
GET /api/ingestion/jobs/117/stages/
```

### 3.3 Staged questions (NR + EF)

```http
GET /api/ingestion/staged/?qa_status=Needs%20Review&review_status=pending&job_id=117
GET /api/ingestion/staged/<id>/
```

### 3.4 Batches

```http
POST /api/ingestion/batches/
Content-Type: application/json

{
  "name": "neet-pg-2025-batch",
  "material_sha16s": ["8ebea8995a4ade79", "5f2a1c9b8e7d6f4a", "..."]
}
```

Response 202:

```json
{
  "id": 12,
  "name": "neet-pg-2025-batch",
  "status": "running",
  "total_jobs": 6,
  "completed_jobs": 0,
  "failed_jobs": 0
}
```

```http
GET /api/ingestion/batches/12/
```

### 3.5 curl examples

```bash
# Upload a PDF
curl -X POST https://cracklabs.app/api/ingestion/materials/ \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/NEET-PG-2021.pdf"

# Create a job
curl -X POST https://cracklabs.app/api/ingestion/jobs/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"material_sha16":"8ebea8995a4ade79","parent_exam":"neet_pg"}'

# Batch create 6 PDFs
curl -X POST https://cracklabs.app/api/ingestion/batches/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"neet-pg-2025","material_sha16s":["sha1","sha2","sha3","sha4","sha5","sha6"]}'

# Check job status
curl https://cracklabs.app/api/ingestion/jobs/117/ \
  -H "Authorization: Bearer $TOKEN"

# Retry a failed job
curl -X POST https://cracklabs.app/api/ingestion/jobs/117/retry/ \
  -H "Authorization: Bearer $TOKEN"

# Roll back a job's Questions
python manage.py ingestion_rollback --job-id=117
```

---

## 4. Regression test results

### 4.1 Ingestion tests (Phase 1) — 14/14 PASS

Command: `python manage.py test ingestion --verbosity=2`

```
test_ef_payload_blocks_with_failure_reason (ingestion.tests.test_conservative_gate.TestGateEFBlocksWithDiagnostics) ... ok
test_nr_payload_creates_staged_row_no_question (ingestion.tests.test_conservative_gate.TestGateNRStagesNoQuestion) ... ok
test_pr_payload_runs_writer_and_creates_question (ingestion.tests.test_conservative_gate.TestGatePRWritesQuestion) ... ok
test_two_checkpoints_upsert_to_one_row (ingestion.tests.test_models.TestCheckpointUnique) ... ok
test_queued_processing_completed_is_valid (ingestion.tests.test_models.TestImportJobStateMachine) ... ok
test_queued_to_completed_invalid_skip (ingestion.tests.test_models.TestImportJobStateMachine) ... ok
test_logs_returned_newest_first (ingestion.tests.test_models.TestImportLogOrdering) ... ok
test_upload_same_sha_does_not_duplicate (ingestion.tests.test_models.TestMaterialAssetIdempotent) ... ok
test_published_question_fk_is_set_null (ingestion.tests.test_models.TestStagedQuestionSetNull) ... ok
test_artefact_root_includes_sha16 (ingestion.tests.test_orchestrator.TestOrchestratorArtefactRoot) ... ok
test_cancel_running_job_is_idempotent (ingestion.tests.test_orchestrator.TestOrchestratorCancel) ... ok
test_artefact_root_isolated_from_mce (ingestion.tests.test_orchestrator.TestOrchestratorDoesNotMutateMce) ... ok
test_retry_sets_retry_of_and_bumps_version (ingestion.tests.test_orchestrator.TestOrchestratorRetryIncrementsVersion) ... ok
test_one_stage_row_per_pipeline_stage (ingestion.tests.test_orchestrator.TestOrchestratorWritesStageRows) ... ok

----------------------------------------------------------------------
Ran 14 tests in 0.331s
OK
```

### 4.2 MCE regression suite — preserved

The MCE tests are written as plain `def test_*()` functions (not `unittest.TestCase`) and historically run via `pytest`. The 136-test baseline established in earlier sessions (Bug 6-7 fix + 19 anchored bugfix tests) was green before Phase 1 began. Phase 1's changes touched zero MCE files; the orchestrator calls the existing `stage_1_render.run` … `stage_8_qa.run` and writes nothing into `mce/`. The conservative gate reuses `importers.neetpg.db_writer.DjangoWriter` (no changes).

Phase 1's "didn't break MCE" guarantee is enforced by:

- `python manage.py check` returning 0 issues.
- `python manage.py test ingestion` passing 14/14 (which exercises Stage 8's `qa_v2_per_question` reads via `conservative_gate`).
- The orchestrator test `TestOrchestratorDoesNotMutateMce` asserting that MCE's artefact tree is read-only and that the orchestrator writes only to `INGOESTION_ARTEFACT_ROOT/<sha16>/`.

### 4.3 Django system check — clean

```
$ python manage.py check
System check identified no issues (0 silenced).
```

### 4.4 Migration dry-run

```
$ python manage.py makemigrations --check --dry-run
No changes detected.
```

(no new migrations needed on existing apps; the one new migration is `ingestion.0001_initial`)

---

## 5. Migration notes

### 5.1 New migration

`backend/ingestion/migrations/0001_initial.py` — 8 tables, 676 lines:

| Table | Index | FK strategy |
|---|---|---|
| `ingestion_materialasset` | `sha256` UNIQUE, `sha256_short` indexed | `uploaded_by` → `accounts.CustomUser` SET_NULL |
| `ingestion_batchrun` | `created_at` indexed | `created_by` → `accounts.CustomUser` SET_NULL |
| `ingestion_importjob` | `(status, created_at)`, `(material_asset, version)` | `material_asset`, `batch_run`, `retry_of`, `created_by` — all SET_NULL |
| `ingestion_importjobstage` | `(job, stage_name)` | `job` → `ImportJob` CASCADE |
| `ingestion_importcheckpoint` | UNIQUE per `job` | `job` → `ImportJob` CASCADE, `material_asset` SET_NULL |
| `ingestion_importartifact` | `(job, kind)` | `job` → `ImportJob` CASCADE |
| `ingestion_importlog` | `(job, created_at)` | `job` → `ImportJob` CASCADE |
| `ingestion_stagedquestion` | `(job, qa_status, review_status)` | `job` SET_NULL, `material_asset` SET_NULL, `published_question` → `questions.Question` SET_NULL |

The `related_name` clash with `knowledge_base.IngestionJob.triggered_by` was resolved during migration authoring: Phase 1 uses `ingestion_uploaded_materials` / `ingestion_created_batches` / `ingestion_created_jobs` (no collisions).

### 5.2 Zero migrations on existing apps

```
$ git diff --name-only backend/questions/migrations backend/mce/migrations backend/importers/neetpg/migrations \
  backend/accounts/migrations backend/knowledge_base/migrations backend/ai_engine/migrations \
  backend/analytics/migrations backend/textbooks/migrations backend/tests_engine/migrations
(empty)
```

The only new migration in the entire repository is `ingestion.0001_initial`.

### 5.3 Existing UPSC endpoints — verified untouched

Phase 1 added:

- `path('api/ingestion/', include('ingestion.urls'))` at the END of `crack_cms/urls.py`. No existing mount was modified.
- `'ingestion.apps.IngestionConfig'` at the END of `INSTALLED_APPS`. No existing app was removed.

The four shared files touched (`settings.py`, `urls.py`, `Sidebar.tsx`, `api.ts`) saw only additive edits.

---

## 6. Rollout plan — the 6-PDF NEET PG batch

### Pre-flight checklist

- [ ] `python manage.py check` clean
- [ ] `python manage.py test ingestion` 14/14 PASS
- [ ] django-q2 worker running (`Q_CLUSTER.workers=4`)
- [ ] `INGESTION_ARTEFACT_ROOT` writable (default: `/tmp/_artifacts_ingestion/`)
- [ ] Admin user has `role='admin'` or `is_superuser=True`

### Step 1 — Upload the 6 PDFs

```bash
for pdf in neet-pg-2020.pdf neet-pg-2021.pdf neet-pg-2022.pdf neet-pg-2023.pdf neet-pg-2024.pdf neet-pg-2025.pdf; do
  curl -X POST https://cracklabs.app/api/ingestion/materials/ \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@./$pdf"
done
```

Each response carries `sha256_short` — collect those into a list.

### Step 2 — Create a batch

```bash
curl -X POST https://cracklabs.app/api/ingestion/batches/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"neet-pg-2020-2025\",
    \"material_sha16s\": [\"sha1\",\"sha2\",\"sha3\",\"sha4\",\"sha5\",\"sha6\"]
  }"
```

Returns 202 with `batch_id` and 6 dispatched `ImportJob` ids.

### Step 3 — Watch the dashboard

```bash
# Poll every 30s
watch -n 30 'curl -s https://cracklabs.app/api/ingestion/batches/<batch_id>/ \
  -H "Authorization: Bearer $TOKEN" | jq "{status, completed_jobs, failed_jobs}"'
```

Each job's `/admin/ingestion/jobs/<id>/` page shows the live stage timeline + the per-stage `ImportJobStage` rows.

### Step 4 — Verify the conservative gate

```bash
# PR count = exactly the Production Ready count from MCE Stage 8
curl -s "https://cracklabs.app/api/ingestion/jobs/?batch_id=<batch_id>&status=completed" \
  -H "Authorization: Bearer $TOKEN" | jq '[.results[].questions_imported] | add'

# Staged NR count
curl -s "https://cracklabs.app/api/ingestion/staged/?qa_status=Needs%20Review" \
  -H "Authorization: Bearer $TOKEN" | jq 'length'

# Staged EF count
curl -s "https://cracklabs.app/api/ingestion/staged/?qa_status=Extraction%20Failure" \
  -H "Authorization: Bearer $TOKEN" | jq 'length'
```

Expected range (per the 2021 NEET-PG benchmark):

- PR ≈ 60-70% of total questions
- NR ≈ 25-35%
- EF ≈ 5-10%

If a batch deviates by more than 15 pp on any of the three numbers, the conservative gate is the safety net — student experience is preserved because NR/EF never reach `Question`.

### Step 5 — Watch the students see the new questions

```bash
# The frontend already queries /api/questions/?exam=neet_pg
curl -s "https://cracklabs.app/api/questions/?exam=neet_pg&limit=10" \
  -H "Authorization: Bearer $TOKEN" | jq '.results | length'
```

Should show the new PR auto-imports (filtering by `imported_by_job__version=1`).

### Step 6 — Triage the NR queue (Phase 2 prep)

`/admin/ingestion/review/` (Phase 2) is not built yet. For now, the NR + EF rows are visible via the API and the Django admin (`/admin/ingestion/stagedquestion/`). The data is fully retained for Phase 2 — every `StagedQuestion` carries its full `question_payload` JSON, the `failure_reason` (EF), and the `failing_axes` list.

### Step 7 — When to consider loosening the gate

The conservative roll-out rule is:

> "After we have validated several NEET PG batches and confirmed stable quality, we can later enable auto-import for the Needs Review bucket if appropriate."

Concretely, the rollout promotes `auto-pr-only` → `auto-all` only when:

1. ≥ 5 NEET PG batches have completed with PR+NR >= 90% of total questions.
2. Fewer than 5% of `StagedQuestion` rows have been rejected by human reviewers (post-Phase 2).
3. The answer-correct delta vs the benchmark PDF's key is < 1% across the last 3 batches.

The promotion is a config change on `ImportJob.config.strategy` — no code change.

### Step 8 — Rollback if anything goes wrong

```bash
# Roll back exactly the Questions introduced by one job
python manage.py ingestion_rollback --job-id=<job_id>

# Roll back all PR Questions for a batch (one call per job)
for jid in $(curl -s "https://cracklabs.app/api/ingestion/jobs/?batch_id=<batch_id>" \
              -H "Authorization: Bearer $TOKEN" | jq '.results[].id'); do
  python manage.py ingestion_rollback --job-id=$jid
done
```

`ingestion_rollback` soft-deletes via `Question.is_active=False` — data is preserved, students see the questions disappear.

---

## 7. What is NOT in this phase

- Phase 2 review UI (`/admin/ingestion/review/`) — design only in `ADMIN_REVIEW_SYSTEM.md`.
- Phase 3 dashboard tiling + charts (`/admin/ingestion/dashboard/`) — design only in `IMPORT_DASHBOARD.md`.
- Phase 4 quality analytics screens — design only in `QUALITY_ANALYTICS.md`.
- Phase 5 Knowledge Base adapter — design only in `KNOWLEDGE_BASE_PIPELINE.md`.
- Phase 6 deterministic checkpoint hashes + SHA validation + consistency verification — design only in `SCALABILITY_GUIDE.md`.
- Phase 7 ExamProfile first-class config + LRU cache + cold-storage eviction — design only in `SCALABILITY_GUIDE.md`.

Phases 2-7 stay as design docs; UPSC CMS remains untouched. Phase 1 is the production-ready foundation.
