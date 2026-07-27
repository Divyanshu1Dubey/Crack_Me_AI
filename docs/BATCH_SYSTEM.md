# Batch System

Every upload — whether from the Import Center UI or the
`ingest_cms_material` CLI — is wrapped in an `ImportBatch` row. The batch
is the unit of:

- **State tracking** (queued → processing → completed/partial/failed/cancelled)
- **Reporting** (totals, error_report, audit log)
- **Rollback** (cascade-delete everything inside the batch)
- **Publishing** (promote all approved rows to live `Question` rows)
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
   POST /batches/{id}/publish/              (status = completed | partial)
            │  (publishes approved rows → live Question)
            │  (builds auto-tests)
            ▼
   (ready for Review Queue)
```

A batch stays queryable in `partial` or `failed` state — admin can decide
whether to roll back, republish, or just inspect.

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

Only effective while `queued` or `processing`. Sets `status=cancelled`.
Staging rows are preserved so a partial result is still inspectable.

### Publish

`POST /api/admin/import/batches/{id}/publish/` with body:

```json
{ "max_per_test": 100, "build_tests": true, "only_publish": false }
```

Effects:

- For each `ExtractedQuestion.status='approved'`, the publish pipeline
  creates a `Question` row (via
  `material_importer.publishing.publish_extracted_question`).
- Then `mock_test_builder.build_for_batch()` rebuilds auto-tests:
  - One per `(subject)` → kind=`subject`.
  - One per `(subject, topic)` → kind=`topic`.
  - One `mixed` omnibus test.
  - One per `PYQ <year>` filename match → kind=`pyq_year`.
- Idempotent: re-running replaces the same auto-tests rather than creating
  duplicates (the builder pre-deletes any prior tests whose title contains
  `batch <id>`).

### Republish

`POST /api/admin/import/batches/{id}/republish/`

Same effect as `Publish` with `only_publish=true`, but useful when the
auto-tests are stale.

### Rollback

`POST /api/admin/import/batches/{id}/rollback/` with body:

```json
{ "delete_published": false, "confirm": true }
```

Default behaviour:

- Cascade-delete every `ImportMaterial` in the batch.
- Cascade-delete every `ExtractedQuestion`, `ExtractedTheory`,
  `ImportedImage` via FK.
- Delete every `tests_engine.Test` whose title contains `batch <id>`.

With `delete_published=true`, the live `Question` rows created by
`publish_batch()` are also deleted (the publish-side link is nullified
first so re-uploads don't trip the unique constraint).

**Always** requires `confirm: true` server-side.

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
    --dir cms_exclusive_material/ \
    --source-label "Q3 docs"

# 2) Bulk approve all needs_review rows
python manage.py enrich_pending_questions --status needs_review --action approve

# 3) Publish + build tests
python manage.py publish_batch --all-pending --max-per-test 100
```

## Example: full lifecycle via the UI

1. `/admin/import-center/upload` — drag files in.
2. Auto-redirect to `/admin/import-center/batches/{id}` — watch live
   progress.
3. Click **Publish &amp; Build Tests**.
4. `/admin/import-center/review` — bulk approve the `needs_review` rows
   that were auto-flagged.
5. Click **Publish &amp; Build Tests** again.