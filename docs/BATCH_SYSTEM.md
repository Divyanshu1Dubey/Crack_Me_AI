# Batch System

Every upload — whether from the Import Center UI or the
`ingest_cms_material` CLI — is wrapped in an `ImportBatch` row. The batch
is the unit of:

- **State tracking** (queued → processing → completed/partial/failed/cancelled)
- **Reporting** (totals, error_report, audit log)
- **Rollback** (delete the staging rows, retire the auto-tests; published questions stay live unless `delete_published`)
- **Publishing** (promote all approved rows to live `Question` rows, in the background)
- **Mock test generation** (auto-build per-subject / per-topic / mixed / PYQ-year tests)

This document explains the lifecycle, the data model, and the operations
you can run on a batch.

---

## Lifecycle

```
   POST /admin/import/upload/                 (status = queued)
            │
            ▼
   background thread starts                   (status = processing)
            │
   ┌────────┴──────────────────────────────┐
   │  parse each file (ParserFactory)      │
   │  persist ImportMaterial, …            │
   │  bulk_create every 200 rows           │
   │  write ImportAuditLog per step        │
   └────────┬──────────────────────────────┘
            ▼
   POST /batches/{id}/publish/              (status = completed | partial,
            │                                 or cancelled with staged rows)
            │  202: background thread, progress in summary["publish"]
            │  (publishes approved rows → live Question)
            │  (builds auto-tests)
            ▼
   (ready for Review Queue)
```

A batch stays queryable in `partial`, `failed` or `cancelled` state — admin
can decide whether to roll back, publish what was staged, republish, or just
inspect.

## Data model

`material_importer.models.ImportBatch`:

| Field | Type | Meaning |
|---|---|---|
| `status` | enum | `queued` / `processing` / `completed` / `partial` / `failed` / `cancelled` |
| `source_label` | str(255) | Human-readable label (`"NEET PG 2024 Recall — Docx Set 3"`). |
| `root_path` | str(500) | Working directory used during ingest. |
| `total_files` | int | Count of files scheduled. |
| `files_processed` | int | Count of files the parser has finished. |
| `files_failed` | int | Count of files that raised. |
| `questions_extracted` | int | Total `ExtractedQuestion`s persisted. |
| `questions_found` | int | Total raw questions the parser saw (pre-dedup). |
| `questions_rejected` | int | Dropped for missing options / no answer marker. |
| `theory_blocks_extracted` | int | `ExtractedTheory` rows saved. |
| `images_extracted` | int | `ImportedImage` rows saved. |
| `duplicates_skipped` | int | Cross-batch duplicates dedup detector skipped. |
| `ai_enrichment_queued` | int | Reserved for future AI backfill jobs. |
| `summary` | JSON | Final parse summary. |
| `error_report` | JSON | Per-file errors (capped at 200). |
| `started_at` / `finished_at` | dt | Timing. |
| `created_by` | FK → User | Admin who initiated the batch. |
| `created_at` / `updated_at` | dt | Auditing. |

`ImportMaterial` is the per-file child row. It captures parser choice,
parse status, counts, and per-file warnings/errors.

`ExtractedQuestion`, `ExtractedTheory`, `ImportedImage` and
`ImportAuditLog` all have a foreign-key chain to the batch via
`material → batch_id`.

## Operations

### Create

Either the UI upload endpoint (`POST /api/admin/import/upload/`) or the CLI
command:

```bash
python manage.py ingest_cms_material --dir cms_exclusive_material/ \
    --source-label "Q3 docs" --use-ai
```

Both create an `ImportBatch` row and kick off the parse. The CLI runs
*synchronously* in the same process; the UI spawns a background thread.

### Inspect

```bash
python manage.py qa_report --batch 12
```

Or open `/admin/import-center/batches/12` in the UI.

The report contains:

- `totals.questions_extracted`, `duplicates_skipped`, `images_extracted`, …
- `materials[]` — per-file counts and parser diagnostics.
- `error_report[]` — capped at 200 file-level errors.

### Cancel

Only effective while `queued` or `processing` (`409` otherwise). Sets
`status=cancelled`; parsing stops after the current file. Staging rows are
preserved, and a cancelled (not rolled-back) batch can still **publish** the
questions it staged before the cancel.

### Publish

`POST /api/admin/import/batches/{id}/publish/` with body:

```json
{ "max_per_test": 100, "build_tests": true, "only_publish": false }
```

Runs in a background thread and answers `202` at once; the state is
`summary["publish"]` (`running` with a heartbeat → `done` / `failed`). A run
that stops heartbeating for 30 minutes is reported as stale and can be
started again. `409` while another publish or a test rebuild runs, for a
batch still parsing, and for a rolled-back batch.

Effects:

- For each `ExtractedQuestion.status='approved'`, the publish pipeline
  creates a `Question` row (via
  `material_importer.publishing.publish_extracted_question`).
- Two kinds of row are not published. They go back to `needs_review` with a
  review note (added once):
  - no valid A–D answer: `Not published: no valid correct answer (A-D) was
    extracted.`
  - an answer / explanation label or a correctness flag in the stem or the
    options (`questions.answer_leak.label_hold_reasons`; the stem and the
    options are public text): `Not published: answer / explanation label in
    the stem or options (<codes>).`, where the codes are
    `answer_label_in_public_text`, `explanation_label_in_public_text`,
    `answer_flag_in_option` and / or `answer_flag_in_stem`. The text is not
    repaired automatically: clean it first ([`REVIEW_QUEUE.md`](./REVIEW_QUEUE.md#rows-held-at-publish)).
- Then `mock_test_builder.build_for_batch()` rebuilds auto-tests:
  - One per `(subject)` → kind=`subject`.
  - One per `(subject, topic)` → kind=`topic`.
  - One `mixed` omnibus test.
  - One per `PYQ <year>` filename match → kind=`pyq_year`.
- Idempotent: re-running replaces the question sets of the same auto-tests
  rather than creating duplicates. A batch's tests are found by the ids
  recorded in `summary` (`auto_test_ids` / `mock_test_ids`) plus the exact
  title shape `Auto • … • batch <id>` (never batch 10 for batch 1). A test
  that students have attempted is never deleted by the importer: it is
  unpublished instead, so attempt history survives.

### Republish

`POST /api/admin/import/batches/{id}/republish/`

Rebuilds only the batch's auto-tests (no writes to `Question`),
synchronously, and returns `{batch_id, tests_built}`. Publish and rebuild
exclude each other (both build the batch's tests): the rebuild holds
`summary["rebuild"]` while it runs, and a publish or another rebuild gets
`409`. If the request dies (gunicorn's 120 s timeout, a worker restart) the
`rebuild` slot goes stale after 5 minutes. `summary["publish"]` (the last
publish result) is never touched.

### Rollback

`POST /api/admin/import/batches/{id}/rollback/` with body:

```json
{ "delete_published": false, "confirm": true }
```

Refused with `409` while the batch is still parsing (cancel it first) or
while a publish or test rebuild runs.

Default behaviour:

- Cascade-delete every `ImportMaterial` in the batch.
- Cascade-delete every `ExtractedQuestion`, `ExtractedTheory`,
  `ImportedImage` via FK.
- Retire the batch's auto-tests (exact ownership, as above): tests nobody
  attempted are deleted, tests with attempts are unpublished and kept.
- Leave the live `Question` rows published.

With `delete_published=true`, the batch's published `Question` rows are also
removed from the bank the way the admin "Remove from bank" action does
(`is_active=False`, `is_dropped=True`, `admin_edited=True` and a
`RemovedQuestion` tombstone); a hard delete would destroy user history.
Either way the published question ids are returned and kept in
`summary["rollback"]`, and the batch is set to `cancelled`.

**Always** requires `confirm: true` server-side.

The CLI `manage.py import_docx_fidelity <path> --rollback` rolls back every
earlier batch that imported the same file (by sha256) before re-importing;
their published questions stay live unless `--remove-published` is passed.

### Generate Mock (one-off)

`POST /api/admin/import/batches/{id}/generate-mock/`

Filters the batch's `published` rows by `strategy` and creates a single
new `Test` record whose question set is just that filter. Strategies:

- `entire_file`, `by_subject`, `by_chapter`, `by_topic`, `by_difficulty`,
  `random`, `image_based`, `grand`, `revision`, `weekly`.

The new `Test` is **idempotent on title** — same strategy + same batch =
same `Test.id` (the `_ensure_test` helper upserts).

### Delete

`DELETE /api/admin/import/batches/{id}/` is exposed via the viewset but the
viewset is currently `ReadOnlyModelViewSet`. Use the **Rollback** action
explicitly so the operation is auditable.

---

## Ingestion platform jobs

The Production Content Ingestion Platform (`backend/ingestion/`,
`/api/ingestion/`) has its own `BatchRun` → `ImportJob` model, separate from
the Import Center's `ImportBatch`. Its jobs run on the django-q worker
(`python manage.py qcluster`; on DigitalOcean a separate Worker component).

- **Batch status and counts are computed from the jobs.** `status`,
  `total_jobs`, `completed_jobs` and `failed_jobs` in the batch API are
  derived from the batch's jobs (a cancelled batch stays cancelled; all jobs
  finished → `done`, or `cancelled` if every job was cancelled; otherwise
  `running`). The stored counters were never kept up to date.
- **Job rows** carry `exam` (the job's exam, or its material's exam hint),
  `exam_label` and `material_filename`. `GET /api/ingestion/jobs/` returns
  the newest 200; `GET /api/ingestion/jobs/counts/` counts every job per
  status (`queued`, `processing`, `completed`, `failed`, `cancelled`,
  `crashed`) plus `total`.
- **Stale-job recovery.** A worker that dies mid-job (django-q timeout, OOM,
  deploy restart) leaves its job `processing`. The django-q Schedule
  `ingestion_recover_stale_jobs` (created after every `migrate`; every
  `INGESTION_RECOVERY_SCHEDULE_MINUTES`, default 10, 0 removes it) runs on
  the `qcluster` worker. It marks processing jobs idle for longer than the
  django-q task timeout + 10 minutes as `crashed`, and re-queues the ones that
  stalled recently (within 24 h) to resume from their checkpoint, at most
  `INGESTION_MAX_AUTO_RESUMES` (default 2) times per job; the rest stay
  `crashed` for a person to retry.
- **Commands.** `ingestion_run_pending` runs the same recovery pass
  (`--no-sweep` skips it), then dispatches queued jobs that have no django-q
  task (`--redispatch` also re-dispatches those that have one).
  `ingestion_sweep_stale [--dry-run] [--older-than-minutes N]` only marks
  stale jobs `crashed`. `ingestion_retry_failed` bulk-retries failed /
  crashed / cancelled jobs (like the per-job Retry endpoint).

---

## Concurrent imports

Each batch runs on its own background thread / CLI invocation. They share
the dedup cache (read-only after init), so concurrent uploads are safe.
The DB still serializes within a single transaction, but `bulk_create()`
and the lack of long-held locks keep contention low.

If two admins upload the same file at the same time, the second batch
will see the first's content as duplicates and skip those rows.

## Audit log

Every operation appends to `ImportAuditLog`:

```
[info] uploaded by admin: 14 files
[info] parsed with docx_fidelity: 1023 questions, 14 images
[warning] parser_warnings: image_format_unsupported (x2)
[info] ingest_done: 1023 questions, 14 images
[info] published: 1023 questions, 7 tests built
[warning] rollback: {"materials": 4, "questions": 1023, "tests": 7}
```

The batch detail page shows the most recent 25 entries; the dedicated
`/audit/` endpoint paginates through the full history.

## Limits

- Max upload size: 200 MB per file, 200 files per batch.
- Max files per batch is enforced in the upload endpoint
  (`MAX_FILES_PER_UPLOAD`).
- Parser warnings / errors are capped at 50 rows per material row to keep
  the JSON small.
- `error_report` is capped at 200 file-level errors.

## Example: full lifecycle via the CLI

```bash
# 1) Ingest a folder
python manage.py ingest_cms_material \
    --path cms_exclusive_material/ \
    --label "Q3 docs"

# 2) Approve the reviewed rows. There is no CLI for this: use the review
#    queue (bulk Approve) or Django admin -> ExtractedQuestion -> "Mark
#    selected as approved". (enrich_pending_questions --batch N runs AI
#    enrichment on staged rows; it does not approve them.)

# 3) Publish + build tests
python manage.py publish_batch --all-pending --max-per-test 100
```

Approved rows still go through the publish holds above: a row whose stem or
options carry an answer / explanation label or a correctness flag is put back
to `needs_review` on the next publish until its text is cleaned.

## Example: full lifecycle via the UI

1. `/admin/import-center/upload` — drag files in.
2. Auto-redirect to `/admin/import-center/batches/{id}` — watch live
   progress.
3. Click **Publish &amp; Build Tests**.
4. `/admin/import-center/review` — bulk approve the `needs_review` rows
   that were auto-flagged. Rows held for an answer / explanation label or a
   correctness flag in their text are held again on the next publish until
   that text is cleaned (Django admin → `ExtractedQuestion`).
5. Click **Publish &amp; Build Tests** again.