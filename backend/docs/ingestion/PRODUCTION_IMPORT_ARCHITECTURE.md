# PRODUCTION_IMPORT_ARCHITECTURE.md

**Status**: Phase 1 SHIPPED. Phases 2-7 designed (no code yet).
**Last updated**: 2026-07-24
**Source SHA** (MCE benchmark): `8ebea8995a4ade79` (NEET-PG-2021, 65.5% PR / 29.1% NR / 5.3% EF)

---

## Why this exists

The Medical Content Engine (MCE — Stages 1-10 + `stage_db_writer` + QA V2) is stable on the 2021 NEET-PG benchmark:

- 206 candidate blocks → 135 Production Ready + 60 Needs Review + 11 Extraction Failure.
- 19 anchored regression tests (`mce/tests/test_bugfixes_2021.py`) preserve every Bug 1-7 fix.
- 136/136 MCE tests pass.

We now need to **wrap** that engine in production-grade orchestration so a single PDF upload reliably becomes either a published Question row, a staged review queue entry, or a logged/blocked diagnostic — without ever requiring the operator to re-investigate from scratch.

**Hard architectural constraint (user-approved)**: The existing live UPSC CMS platform MUST NOT be broken. NEET PG / INI-CET / FMGE / USMLE / PLAB become isolated products inside one backend. Every shared concern that crosses the boundary lives in its own dedicated Django app; nothing in UPSC is touched by Phase 1 except via additive reuse through public APIs.

---

## 7-Phase map

| Phase | Title | Status | Output |
|---|---|---|---|
| **1** | Production Import Framework | **SHIPPED** | `backend/ingestion/` (16 files, 8 tables, 12 endpoints, 14 tests) + `/admin/ingestion/*` |
| 2 | Review System | Designed | Reads/writes `ingestion.StagedQuestion`; UI at `/admin/ingestion/review/` |
| 3 | Premium Dashboard | Designed | Recharts tiles; querys Phase 1's `ImportJob` + `ImportJobStage` |
| 4 | Quality Analytics | Designed | Reads `08_qa/summary.json` + `per_question_qa.json` written by Stage 8 |
| 5 | Knowledge Base integration | Designed | Adapter writes `KnowledgeChunk` / `KnowledgeEntity` from `Question.payload` |
| 6 | Safety | Designed | Checkpoints (already wired) + dedup + rollback (already shipped) |
| 7 | Scalability | Designed | LRU + cold-storage eviction; no new tables |

Phases 2-7 are documented in their respective files:

- [ADMIN_REVIEW_SYSTEM.md](ADMIN_REVIEW_SYSTEM.md) — Phase 2 stub
- [IMPORT_DASHBOARD.md](IMPORT_DASHBOARD.md) — Phase 3 stub
- [QUALITY_ANALYTICS.md](QUALITY_ANALYTICS.md) — Phase 4 stub
- [KNOWLEDGE_BASE_PIPELINE.md](KNOWLEDGE_BASE_PIPELINE.md) — Phase 5 stub
- [SCALABILITY_GUIDE.md](SCALABILITY_GUIDE.md) — Phase 6+7 stub
- [RECOVERY_AND_RETRY.md](RECOVERY_AND_RETRY.md) — checkpoint / retry mechanics

---

## Data flow

```
PDF upload
   ↓
POST /api/ingestion/materials/upload/               [views.MaterialAssetUploadView]
   ↓
MaterialAsset(sha256, sha256_short, ...)            [models.MaterialAsset]
   ↓
POST /api/ingestion/jobs/                           [views.ImportJobListView]
   ↓
ImportJob(status=queued, parent_exam, ...)           [models.ImportJob]
   +
django_q2 task → ingestion.tasks.run_import_job     [tasks.py]
   ↓
run_full_pipeline_for_job                           [orchestrator.run_full_pipeline_for_job]
   ↓
PIPELINE_ORDER (Stages 1 → 8 → db_writer → gate → 9 → 10)
   ↓
ImportJobStage rows per stage                       [models.ImportJobStage]
ImportLog rows per stage                            [models.ImportLog]
ImportCheckpoint rows at every stage boundary       [models.ImportCheckpoint]
   ↓
Stage 8 → 08_qa/per_question_qa.json (read by gate) [mce.stage_8_qa]
   ↓
conservative_gate.apply_qa_v2_verdict               [conservative_gate.py]
   ├─ Production Ready → DjangoWriter.write_question → questions.Question row
   ├─ Needs Review     → StagedQuestion(review_status=pending)
   └─ Extraction Failure → StagedQuestion(review_status=blocked)
   ↓
ImportJob.status = completed
ImportJob.qa_v2_*_pct recorded
```

---

## Why an isolated `ingestion/` Django app

The user-confirmed hard rule:

> "Do not modify existing UPSC CMS files. The ingestion app should be plug-and-play. The existing UPSC CMS admin should continue working exactly as it does today."

Practically, that means:

| UPSC file | Touched by Phase 1? | How |
|---|---|---|
| `backend/questions/*` | NO NEW MIGRATIONS | `admin.py` registers new admin pages; `StagedQuestion.published_question FK` is nullable + SET_NULL |
| `backend/importers/neetpg/db_writer.py` | NO | We reuse the class via lazy import; never re-implement QA V2 or the writer |
| `backend/accounts/models.py` | NO | `AdminAuditLog` is reused via `ingestion.utils.audit()` (best-effort emission) |
| `backend/mce/*` | NO | Every stage call goes through `run(ctx, *, pages=None)` — the frozen contract |
| `backend/crack_cms/settings.py` | ADDITIVE | One line added to INSTALLED_APPS |
| `backend/crack_cms/urls.py` | ADDITIVE | One line: `path('api/ingestion/', include('ingestion.urls'))` |
| `frontend/src/components/Sidebar.tsx` | ADDITIVE | One new admin link |
| `frontend/src/lib/api.ts` | ADDITIVE | One new namespace (`ingestionAPI`) |
| `frontend/src/app/admin/layout.tsx` | NO | New role gate lives at `frontend/src/app/admin/ingestion/layout.tsx` |

Anyone reading `git diff` after Phase 1 will see exactly: ONE new app, two additive lines in `settings.py`, two additive lines in `urls.py`, one additive line in `Sidebar.tsx`, one additive block in `api.ts`. UPSC CMS code paths are unmodified.

---

## Conservative import gate (Phase 1 policy)

The user-confirmed conservative rollout:

| QA V2 verdict | Action | Why |
|---|---|---|
| **Production Ready** | WRITE to `questions.Question` via existing `DjangoWriter` | High-confidence auto-import; visible to students immediately |
| **Needs Review** | STAGE to `StagedQuestion(review_status=pending)`; **NO `Question` write** | Student experience preserved; admin can triage via Phase 2 UI |
| **Extraction Failure** | STAGE to `StagedQuestion(review_status=blocked, failure_reason=…)`; **NO `Question` write** | Diagnostic data retained; admin sees failure mode + overlay paths |

The gate reads `08_qa/per_question_qa.json` written by MCE Stage 8. We do NOT re-score; QA V2 is the single source of truth.

`ImportJob.config.strategy` selects between three pre-built strategies:

- `auto-pr-only` (default, conservative) — only PR auto-imports.
- `auto-all` — both PR and NR auto-import (deferred until 2021 base rate is validated).
- `manual` — every question goes to staging; admin approves each.

---

## What "world-class" means here

Three measurable claims:

1. **Every import is resumable.**  `ImportCheckpoint` saves state at every stage boundary; orchestrator `run_full_pipeline_for_job` reads `last_completed_stage` and resumes from `last_processed_page`. No import ever requires starting over.
2. **Every admin action is auditable.**  `ingestion.utils.audit()` writes to `accounts.AdminAuditLog` for every material upload, job create, retry, cancel, batch create. `AdminAuditLog.action='system_rerun_evaluation'` is reused (the precise verb lives in `metadata.verb`); no new enum coupling.
3. **Every question is traceable.**  Every `Question` row written by the conservative gate has its provenance on `ImportJob` + `MaterialAsset` (via `Question.recall_text_hash` ↔ `MaterialAsset.sha256_short`). Every `StagedQuestion` carries its full `question_payload` JSON for Phase 2 replay.
