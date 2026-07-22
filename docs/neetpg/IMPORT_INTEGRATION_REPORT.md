# Import Integration Report — Phase 2

> Wires the Phase-1 standalone `backend/importers/neetpg/` package into the
> Django platform. All flows are additive; no existing endpoint changes.

---

## 1. What was wired

| Capability | Where it lives |
|---|---|
| Importer as a Django app | `backend/importers/apps.py` (new) — registered in `INSTALLED_APPS` via `crack_cms/settings.py` |
| URL namespace | `backend/importers/neetpg/urls.py` (new) — mounted at `api/imports/neetpg/` |
| JSONL → DB writer | `backend/importers/neetpg/db_writer.py` (new) — `Writer` protocol, `DjangoWriter` impl |
| Resume / rollback / batch / dedup / logging / validation / error recovery / incremental | All consolidated in the new `runner.py` rewrite; details below |
| Import observability | Reuses `QuestionImportJob` (already exists) |
| Staging review queue | Reuses `QuestionExtractionItem` (already exists) |
| Reports | `backend/importers/neetpg/reports/` directory + `api/imports/neetpg/reports/<run_id>/` endpoint |

---

## 2. New management commands

| Command | Purpose |
|---|---|
| `python manage.py neetpg_import_run --source-dir <path> [--write-db]` | Production entrypoint. Writes to DB if `--write-db` is set and the migration is applied. Otherwise stays JSONL-only. |
| `python manage.py neetpg_status` | Lists the latest `QuestionImportJob` rows where `job_type='pdf'`. |
| `python manage.py neetpg_retry --job-id <id>` | Re-runs a failed job. |
| `python manage.py neetpg_reconcile` | Re-links Phase-1 JSONL output to DB rows idempotently (used after the first DB import to retro-fill DB rows from existing JSONL). |
| `python manage.py neetpg_rollback --job-id <id>` | Soft-deletes (`is_active=False`) every Question whose provenance references the given import job. **Never hard-deletes.** |

(Phase 1 commands `neetpg_scan`, `neetpg_import`, `neetpg_import_all`, `neetpg_dedup`, `neetpg_repair`, `neetpg_report` are extended, not removed.)

---

## 3. New API endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/imports/neetpg/jobs/` | Paginated list of recall PDF jobs |
| `POST` | `/api/imports/neetpg/jobs/` | Admin: kick off an import run via `django_q` |
| `GET` | `/api/imports/neetpg/jobs/{id}/` | Job detail (status, summary, error_report) |
| `POST` | `/api/imports/neetpg/jobs/{id}/retry/` | Admin: retry a failed job |
| `GET` | `/api/imports/neetpg/reports/{run_id}/` | Markdown report bundle |

---

## 4. Resume semantics

```
manifest.json (Phase 1)        QuestionImportJob (Phase 2)
─────────────────────          ─────────────────────────────
runs[].processed[].sha16   →   QuestionImportJob.summary.processed[*]
runs[].started_at          →   QuestionImportJob.created_at
runs[].finished_at         →   QuestionImportJob.updated_at
```

The runner checks both: if a `(sha16, page_range)` is in any finished manifest entry OR has a successful `QuestionImportJob` row, it's skipped. If a manifest entry exists but the DB job failed, it's retried.

---

## 5. Rollback semantics

`neetpg_rollback --job-id <id>` walks every `QuestionSource` row with `import_job_id=<id>` and sets the corresponding `Question.is_active=False`. Source rows stay (they're provenance). The `QuestionImportJob` row is left in place but its `summary.rolled_back=True`.

A separate `neetpg_rollback --hard` is intentionally **not implemented** — provenance is sacred.

---

## 6. Batch semantics

The DB writer:

1. Opens a `transaction.atomic()` block per source PDF.
2. For each parsed question, calls `Question.objects.update_or_create(recall_text_hash=...)`.
3. On `update_or_create`, a `QuestionRevisionSnapshot` is captured before any field is changed (cheap insurance — only captured when there is an actual diff).
4. `bulk_create` is used for `QuestionSource`, `QuestionImage`, `DuplicateMember` rows.
5. `QuestionImportJob.summary.batch_size` records the actual batch size used.

---

## 7. Duplicate detection

Phase 1's `deduplicator.dedup_batch()` is reused. When a duplicate is found:

- If neither question is in the DB → both are written; the second one is flagged `is_active=False` with a `QuestionSource` row pointing at it. A `DuplicateCluster` + two `DuplicateMember` rows are created.
- If one is in the DB and the other is new → the new one is added with `is_active=False` and joined to the existing cluster.
- If both are in the DB → the new `QuestionSource` row is appended; cluster membership is updated.

Canonical question = the one with the highest `confidence_score` (ties → earliest `created_at`).

---

## 8. Logging

- Python `logging` logger `importers.neetpg`.
- Per-job `QuestionImportJob.summary.steps` records every stage with `started_at`, `finished_at`, `count`.
- Errors land in `QuestionImportJob.error_report` as a list of `{stage, message, sha16, page}` dicts.
- Console output includes one-line-per-stage summaries.
- Sentry capture in production via existing `SENTRY_DSN`.

---

## 9. Validation

`backend/importers/neetpg/quality.py::check_questions()` (Phase 1) emits `QualityIssue` rows. In Phase 2:

- `error_report` issues are persisted as `QuestionExtractionItem` rows with `status='pending'` so admins see them in the review queue (admin: Questions → Extraction items → Filter by job).
- `warn` issues are recorded in `QuestionImportJob.summary.quality.by_type`.

---

## 10. Error recovery

- Each page is wrapped in `try/except`. A failure increments `QuestionImportJob.summary.failed_pages` and the loop continues.
- Mid-run crash → manifest + DB job are both marked partial. Re-running picks up where it left off (per-page idempotency via `QuestionSource` unique constraint).
- Per-image extraction failure → `QuestionImage.extraction_confidence=0.0`, file still saved with `is_watermarked=False` (default). The image stays in the DB but is flagged in admin.
- Per-question parsing failure → `QuestionExtractionItem` row with `status='failed'` + the raw chunk.

---

## 11. Incremental imports

The Phase-1 manifest + per-source fingerprint makes re-imports cheap:

- Same PDF, same page range → skipped (manifest hit).
- Same PDF, different page range → processed (new manifest entry).
- Same PDF, same content but new bundle metadata → re-processed only if `--force`.

For DB-side: `QuestionSource` has `UniqueConstraint(recall_source, page_number, question_number_in_pdf)` so re-imports are idempotent at the question level.

---

## 12. Tests

New unit tests in `backend/importers/neetpg/tests/test_db_writer.py` cover:

- `Question.update_or_create` via `recall_text_hash`.
- `QuestionSource` uniqueness enforcement.
- `DuplicateCluster` creation.
- `QuestionImportJob.summary` population.
- Soft-delete via `neetpg_rollback`.

---

## 13. Rollout checklist

- [ ] Apply migration 0023 on staging.
- [ ] Verify `Question.objects.count()` is unchanged.
- [ ] Run `python manage.py neetpg_import_run --source-dir <path> --write-db --dry-run`.
- [ ] Inspect `QuestionImportJob` row.
- [ ] Run without `--dry-run`.
- [ ] Verify FTS5 mirror build (`python manage.py shell -c "from questions.recall_search import rebuild_fts; rebuild_fts()"`).
- [ ] Verify admin pages render (`/admin/questions/recallsource/`, `/admin/questions/questionimage/`).
- [ ] Smoke-test `/api/imports/neetpg/jobs/`.
- [ ] Commit.

---

## 14. Failure modes we explicitly do not auto-fix

- Broken option counts (we store anyway, flag for review).
- Missing answer (we store anyway, flag for review).
- Low OCR confidence (we store anyway, mark `needs_review=True`).
- Encoding issues (we apply existing `normalize_text` mojibake fix at write-time, same as the rest of the platform).
- Two questions with the same `recall_text_hash` across different `QuestionSource` rows (dedup cluster forms, both rows preserved).

---

## 15. What we never do

- Hard-delete questions or sources.
- Overwrite `original_text` in `QuestionSource`.
- Drop `QuestionImportJob` history.
- Touch `accounts`, `payments`, `SEO`, frontend pages.