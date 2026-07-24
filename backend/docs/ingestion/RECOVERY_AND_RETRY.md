# RECOVERY_AND_RETRY.md — Checkpoints, crash recovery, retry mechanics

**Last updated**: 2026-07-24

---

## Checkpoint model

`ImportCheckpoint` is one row per attempt at one moment in time. The orchestrator `update_or_create`s a checkpoint at every stage boundary via `ingestion.checkpoint.save_checkpoint`.

| Field | Role |
|---|---|
| `job` FK | One checkpoint set per ImportJob (latest one wins) |
| `last_completed_stage` | The orchestrator resumes AFTER this stage |
| `last_processed_page` | Sub-stage restart point if `last_completed_stage` matches the new run |
| `current_page` | Total pages processed so far |
| `token` | 32-char hex secret; mismatched writers raise `CheckpointMismatchError` |
| `artifact_root` / `artifact_sha16` | Pointer to the on-disk MCE artefact tree (never under `chroma_db` or `_artifacts_benchmark_post_fix`) |
| `checkpoint_data` JSON | Stage-specific metrics (e.g. layout threshold) |
| `version` | Bumped on every save; dashboard reads the latest version |

The orchestrator reads the latest checkpoint on resume:

```python
ck = latest_checkpoint(job)
last_stage = ck.last_completed_stage if ck else ""
resume_page = ck.last_processed_page if ck and ck.last_completed_stage == last_stage else None
```

If `last_completed_stage` is empty, OR a previous run died before saving any checkpoint, the orchestrator starts from Stage 1.

---

## Job state machine

```
                ┌──────┐
                │ queued │
                └────┬──┘
                     ↓ (dispatch by django-q2)
                ┌──────────┐
                │processing│
                └──┬────┬──┘
       (success)   │    │   (crashed / failed / cancelled)
                  ↓    ↓
            ┌─────────┐ ┌────────┐
            │completed│ │ failed │  ← also: crashed / cancelled
            └────┬────┘ └───┬────┘
                 │          │
                 ↓          ↓
            queued   (via /retry/)  ← both transitions allowed
```

The transitions table lives at `ingestion.constants.JOB_TRANSITIONS`. Any attempt by the orchestrator, the cancel view, or a retry view to make an illegal transition raises `InvalidJobTransitionError`.

Re-queueing flows through `POST /api/ingestion/jobs/<id>/retry/` which calls `ingestion.retry.plan_retry` → `ingestion.orchestrator.create_retry_job`. A retry creates a NEW `ImportJob` row (increments `version`) with `retry_of` pointing at the original; the original row is preserved as historical evidence.

---

## Crash recovery (the user scenario)

> "I started a job, killed it mid-Stage 5, what now?"

1. The django-q2 task marks the worker as failed; the next health-check tick sees `ImportJob.status='crashed'` (the catch-all in `orchestrator.run_full_pipeline_for_job`).
2. Admin: `POST /api/ingestion/jobs/<id>/retry/` → 202 with the new attempt's id.
3. The retry's orchestrator reads the latest checkpoint via `latest_checkpoint(new_job_id)`. The new job has no checkpoints (its own ledger), but the retry link lets the admin see what state the original was in. Stage 1-4 outcomes are also missed unless `MaterialAsset` already has cached `mce` artefacts — but we DO store them in an isolated `INGESTION_ARTEFACT_ROOT/<sha16>/` tree, so on retry the Stage 1-4 stages detect their outputs and skip.

---

## Conservative-gate failure paths

The conservative gate has its own defensive fallback:

- If `DjangoWriter.write_question` raises (e.g. Subject taxonomy mismatch on a new exam), the offending payload is auto-staged as a `StagedQuestion(qa_status='Needs Review', failing_axes=['writer_error'])`. The `Question` table is never partially updated — the writer is wrapped in `transaction.atomic()` already.

---

## Useful Django shell one-liners

```python
# Force a queued job to re-run with checkpoints preserved
from ingestion.models import ImportJob
from ingestion.tasks import dispatch_job
job = ImportJob.objects.get(id=42)
job.status = "queued"; job.save(update_fields=["status"])
dispatch_job(42)

# Roll back every Question a job imported
from ingestion.models import ImportJob
from ingestion.orchestrator import cancel_job
from importers.neetpg.db_writer import DjangoWriter
job = ImportJob.objects.get(id=42)
writer = DjangoWriter(import_job=job)
print(writer.rollback_for_job())  # soft-deletes via is_active=False
```

---

## What's intentionally NOT recoverable

- A retry cannot re-create a `DjangoWriter` rollback. Phase 2 (Review System) implements proper approve/reject/edit which writes the changed payload back to `Question`, so the operator can choose to undo rather than roll back the whole job.
- A malformed `08_qa/per_question_qa.json` (JSON parse error) skips the conservative gate cleanly — counts are zero, the operator sees a warning in `ImportLog`. We do NOT invent verdicts.
