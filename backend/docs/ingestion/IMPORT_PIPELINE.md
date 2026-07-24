# IMPORT_PIPELINE.md — Per-stage wiring + idempotency + audit

**Last updated**: 2026-07-24

---

## Pipeline order

The orchestrator walks `ingestion.constants.PIPELINE_ORDER`:

```
1_render  →  2_layout  →  2b_reading_order  →  3_images  →  4_tables
     ↓
5_question_blocks  →  6_ocr  →  7_structured  →  7_5_llm (optional)
     ↓
8_qa  →  db_writer  →  conservative_gate
     ↓
9_graph  →  10_rag
```

Every stage call goes through MCE's frozen contract:

```python
def run(ctx: MceContext, *, pages: list[int] | None = None) -> StageResult
```

`ingestion.pipeline_stages.run_mce_stage` wraps each call so:

1. An `ImportJobStage` row is started with `status='running'`.
2. The MCE stage runs.
3. The `ImportJobStage` row is updated: `pages_processed / pages_skipped / artefacts_written / warnings / errors / metrics` are lifted from `StageResult.to_dict()`.
4. On exception, the row is marked `status='failed'`, the exception is re-raised.

---

## Idempotency

Every MCE stage writes into a per-job `INGESTION_ARTEFACT_ROOT/<sha16>/<NN_name>/` tree. Stages are themselves idempotent (Stage 5 folds phantom blocks via `_looks_like_continuation_bullet`; Stage 6 OCR replaces only low-confidence text; Stage 7 dedupes by `recall_text_hash`). Re-running a stage is safe.

The Phase 1 layer adds one more idempotency guarantee at the orchestrator level: a `latest_checkpoint` row tells the runner where to resume, so a re-dispatched job does not re-process stages whose checkpoints were already saved.

The `DjangoWriter` (used by `conservative_gate._import_production_ready`) is idempotent on `(recall_text_hash, exam_type)` — re-running a PR import updates instead of duplicating.

---

## Audit trail

`ingestion.utils.audit(actor, action, resource_type, resource_id, detail, metadata)` writes one row per sensitive action. Actions emitted today:

| Verb | resource_type | Where |
|---|---|---|
| `material.uploaded` / `material.reuploaded` | material | `views.MaterialAssetUploadView.post` |
| `job.created` | job | `views.ImportJobListView.post` |
| `job.retried` | job | `views.ImportJobRetryView.post` |
| `job.cancelled` / `job.cancel_rejected` | job | `views.ImportJobCancelView.post` |
| `batch.created` | batch | `views.BatchRunListView.post` |

Every AdminAuditLog row preserves `actor` (FK CustomUser SET_NULL) + the verb in `metadata.verb`.

---

## Concurrency model

- django-q2 worker pool: 4 workers (Q_CLUSTER unchanged).
- One `ImportJob` is processed at most once at a time. The orchestrator refreshes `job.status` at every stage boundary so an admin-triggered cancel takes effect at the next checkpoint.
- A retried job creates a NEW `ImportJob` row with `retry_of` pointing at the previous attempt. The previous attempt's `ImportJobStage` rows stay as historical evidence.

---

## Failure handling

| Stage exception | Effect | Recovery |
|---|---|---|
| MCE stage raises | `ImportJobStage.status='failed'`, exception re-raised | `POST /jobs/<id>/retry/` creates a new attempt |
| Orchestrator tries to read missing checkpoint | Empty dict / fallback to start of pipeline | Job continues, `ImportLog` records a warning |
| Conservative gate writer raises | Defensive fallback: stage that PR as NR | `Question` is NOT written; diagnostic retained on `StagedQuestion.failure_reason` |
| `django-q2` worker dies mid-stage | Next dispatch detects `import_status='crashed'` | `POST /jobs/<id>/retry/` picks up at the last checkpoint |
