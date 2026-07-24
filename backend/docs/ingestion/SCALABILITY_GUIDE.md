# SCALABILITY_GUIDE.md — Phase 6 + 7 design stub

**Status**: DESIGN ONLY. No code yet. Phase 1 already lays the foundation; Phase 6 hardens safety; Phase 7 scales to 1000+ PDFs.
**Last updated**: 2026-07-24

---

## Why this doc exists

Phase 1 already covers the spine of a production ingestion platform: resumable checkpoints, an audit trail, three management commands, and a conservative gate. What it does NOT yet do (and what Phase 6 + 7 add) is:

- **Phase 6 (safety)**: deterministic checkpoint hashes, SHA validation on every artefact reference, dedup-by-image-sha256, consistency verification, rollback command polish.
- **Phase 7 (scalability)**: per-`parent_exam` ExamProfile configs, parallel ingestion workers, LRU cache for MCE artefact roots, cold-storage eviction.

Both phases are additive — they reuse the Phase 1 tables and never break the conservative gate contract.

---

## Phase 6 — Safety

### Deterministic checkpoint hashes

The current `ImportCheckpoint` has a `version` int. Phase 6 adds a `deterministic_hash` (32-char sha256 over `job_id + last_completed_stage + last_processed_page + current_page + token`) and rejects any save that re-uses the same hash. This catches the "two concurrent writes" race that the Phase 1 token-only check misses.

### SHA validation on every artefact reference

`ImportArtifact.path_rel` is currently a free-form string. Phase 6 enforces: every artefact read goes through `importers.mce.storage.read_artefact(path_rel)` which checks the `sha256` recorded on `ImportArtifact` against the on-disk hash. Mismatch → `ArtefactCorruptionError`; the orchestrator marks the stage `failed` and the admin sees a clear rollback path.

### Image dedup

`DjangoWriter.write_image` already dedupes by image sha256 (the existing UPSC pipeline). Phase 6 adds a regression test that asserts: importing the same NEET PG PDF twice does not create new `recall_images` rows. Adds the test to `ingestion/tests/test_conservative_gate.py`.

### Consistency verification job

A new management command `python manage.py ingestion_verify` walks every `ImportJob` with `status='completed'` and re-derives the per-question counts from `per_question_qa.json` on disk. Mismatch with `ImportJob.qa_v2_*_pct` → emits a structured log + an `AdminAuditLog` row with `metadata.verb="consistency_mismatch"`. The command is dry-run by default; `--fix` re-syncs `ImportJob` fields from the JSON.

### Rollback command polish

`python manage.py ingestion_rollback --job-id=N` already exists (Phase 1). Phase 6 adds:

- `--dry-run` — print affected `Question` rows without touching them.
- `--include-staged` — also mark `StagedQuestion` rows as `rejected`.
- Confirmation prompt with batch_id echo before any write.
- A pre-rollback snapshot of `Question` rows into `importers.neetpg.management.commands._snapshot_for_rollback` so an accidental rollback is recoverable.

### Failure-mode coverage table

| Mode | Today (Phase 1) | After Phase 6 |
|---|---|---|
| Worker crash mid-stage | Resume from `ImportCheckpoint` | Same + deterministic-hash check |
| Disk corruption | Silent (orchestrator reads poisoned JSON) | SHA validation prevents consumption |
| Two concurrent `conservative_gate` writers | `update_or_create` is sufficient | Same + retry-on-conflict lock |
| Rollback mistake | One-shot, no audit | Snapshotted + auditable |
| Long-running drift | Daily `consistency_check` job | Same + email alert on mismatch |

---

## Phase 7 — Scalability

### ExamProfile configs

The MCE already maintains 5 profiles (`neet_pg`, `ini_cet`, `fmge`, `usmle`, `plab`). Phase 7 promotes them to first-class `importers.profiles.ExamProfile` rows (already partial in MCE; Phase 7 finishes the wiring). The orchestrator reads `ImportJob.parent_exam` → resolves to the profile → runs the pipeline with the profile's layout thresholds + answer-pattern set.

```python
@dataclass(frozen=True)
class ExamProfile:
    key: str                  # "neet_pg"
    layout_min_text_ratio: float
    answer_patterns: list[str]
    preferred_font: str
    image_density_threshold: float
```

### Parallel ingestion workers

Phase 1 keeps `Q_CLUSTER.workers=4` (unchanged), so it processes up to 4 PDFs concurrently. Phase 7 raises this to `workers=8`, adds a per-job lock so two `ConservativeGate` writers never collide, and exposes a `concurrency=2` knob on `POST /api/ingestion/batches/` for batches that should respect a slower cadence.

### LRU cache for MCE artefact roots

The MCE writes `<artefact_root>/<sha16>/<stage>/...` trees per job. Phase 1's `ImporterOrchestrator.run_full_pipeline` re-reads these on retry. Phase 7 adds an LRU cache in `ingestion.orchestrator._artefact_root_for(sha16)` keyed by `sha16_short`, cache size 128, with a `stats.hit_rate` accessor for the dashboard.

### Cold-storage eviction

The `purge_old_artefacts` management command (Phase 1) is a no-op. Phase 7 makes it real:

- Walks `ImportArtifact.path_rel` for jobs older than `--max-age-days` (default 90).
- For each, computes `du -b <full_path>`; if total size > `--max-on-disk-mb`, moves the tree to `<cold_storage_root>/<sha16>/...` (configurable env var).
- `ImportArtifact.path_rel` is updated to the new path; the `ImportJob` row is untouched (the dashboard still works).
- Pushing back: a "warm" command (`ingestion_warm_artefacts --sha16=...`) re-materializes the tree on demand.

### Phase 7 scaling test plan

1. Run 100 PDFs through `POST /api/ingestion/batches/` (8 workers, concurrency=2). Measure wall-clock end-to-end.
2. After completion, run `python manage.py ingestion_verify` across all 100 jobs. Assert zero consistency mismatches.
3. Run `ingestion_purge_old_artefacts --max-age-days=0 --dry-run`; assert the on-disk count matches the `ImportArtifact` count.
4. Run `ingestion_purge_old_artefacts --max-age-days=0`; assert the LRU cache hit rate stays above 0.4 for the most recent 10 jobs (the hot working set).
5. Boot a second django-q2 worker pod; re-run a single batch; assert no double-writes via `Question.objects.filter(imported_by_job__version__gt=1).count() == 0`.

### Scaling ceilings (intentional)

Phase 7 caps at:

- **1000 PDFs across 5 exam profiles** — covers the long-term roadmap (NEET PG PDFs through 2030, INI-CET PDFs through 2030, FMGE/USMLE/PLAB annuals).
- **8 concurrent workers** — Phase 7 doesn't propose a worker-per-job model; the singleness-of-writer-per-job model is the safety guarantee.
- **5 GB on-disk artefact tree** — beyond this, cold-storage eviction kicks in.

Going beyond these limits requires a re-architecture (multi-tenant storage, queue partitioning). Phase 7 explicitly does not commit to those.

---

## Out of scope

- Multi-region deployment. Phase 7 stays single-region.
- Vector embeddings for the KG. Phase 5 defers them; Phase 7 doesn't introduce them.
- Customer-facing auto-import tools. The admin UI is the only ingest path; B2B / API consumer access is a separate product.
