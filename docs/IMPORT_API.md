# Admin Import Center — REST API Reference

The Import Center exposes a staff-only REST API under `/api/admin/import/`.
All endpoints require an authenticated admin (server-side `IsAdminUser`)
and return JSON.

> **Base URL**: `${NEXT_PUBLIC_API_URL}/admin/import/`
> **Auth**: Supabase JWT or Django JWT — whichever the rest of the API uses.
> **Content-Type**: `application/json` (except upload, which is `multipart/form-data`).

---

## Conventions

- All ids are integers.
- All timestamps are ISO 8601 strings.
- All counts are non-negative integers.
- List endpoints (`batches/`, `questions/`) use the project pagination:
  `?page=N&page_size=M`, 20 per page by default, `page_size` up to 100,
  response `{count, next, previous, results}`. The batch `audit/` endpoint
  has its own `page` / `page_size` (default 50, max 200).

Standard response codes:

| Code | Meaning |
|---|---|
| 200 | OK |
| 201 | Created |
| 400 | Validation error |
| 401 | Unauthenticated |
| 403 | Authenticated but not an admin |
| 404 | Batch or question not found |
| 409 | Invalid state transition (e.g. cancelling a completed batch), or a publish / test rebuild already running for the batch |

---

## Dashboard

### `GET /api/admin/import/dashboard/`

Returns aggregate stats for the dashboard tiles.

```json
{
  "total_batches": 12,
  "total_questions_imported": 8421,
  "total_questions_published": 7103,
  "total_needs_review": 211,
  "duplicate_rate": 0.0643,
  "image_questions": 1842,
  "subjects_count": 9,
  "topics_count": 84,
  "pending_reviews": 218,
  "recent_uploads": [
    {
      "batch_id": 12,
      "source_label": "NEET PG 2024 Recall — Docx Set 3",
      "status": "completed",
      "questions_extracted": 1023,
      "created_at": "2026-07-27T14:30:00Z",
      "created_by": "admin"
    }
  ]
}
```

---

## Health / lookups

### `GET /api/admin/import/health/`

Liveness probe for the parser pipeline and Supabase storage.

```json
{
  "status": "ok",
  "checks": {
    "supabase": true,
    "parsers": ["docx", "pdf", "pptx", "txt", "md", "zip"],
    "django_q2": true
  },
  "last_batch": { "id": 12, "status": "completed", "created_at": "2026-07-27T14:30:00Z" }
}
```

### `GET /api/admin/import/lookups/`

Tiny lookup so dropdowns can populate.

```json
{
  "subjects": [{ "id": 1, "name": "General Medicine", "code": "MED" }],
  "topics":   [{ "id": 1, "name": "Cardiology",     "subject_id": 1 }]
}
```

---

## Search

### `GET /api/admin/import/search/?q=<text>`

Full-text search across the staging area.

- `q` *(required)* — search term (case-insensitive substring).
- Returns up to 200 most-recent matches.

```json
{
  "term": "heart",
  "count": 14,
  "items": [
    {
      "id": 12345,
      "material": 12,
      "material_filename": "Cardiology Mock Test 4.docx",
      "question_text": "Which of the following...",
      "correct_answer": "B",
      "inferred_subject": "General Medicine",
      "inferred_topic": "Cardiology",
      "status": "pending"
    }
  ]
}
```

---

## Batches

### `GET /api/admin/import/batches/`

List batches. Query params:

- `status` — filter by status.
- `needs_review=1` — only batches with at least one `needs_review` question.

### `POST /api/admin/import/upload/`

Multipart upload. Form fields:

- `files` *(one or more required)* — `.docx`, `.pdf`, `.pptx`, `.txt`, `.md`, or
  `.zip`. ZIPs are auto-extracted.
  Each file is checked by its **content**, not only its extension: PDF /
  DOCX / PPTX by their magic bytes (`accounts.upload_validation`), a ZIP must
  carry the ZIP signature, and TXT / MD must not contain binary (NUL) bytes.
  A renamed file is rejected (listed in `files_rejected`). ZIP members get the
  same check (a member with the wrong content, an unsupported extension or an
  unsafe path is skipped), and an archive may hold at most 500 files and
  expand to at most 1 GiB. Max 200 MB per upload.
- `source_label` *(optional)* — up to 255 chars.
- `use_ai` *(optional, default 0)* — call the AI round-robin classifier per question.
- `force` *(optional, default 0)* — bypass the cross-batch dedup detector.

Response 201:

```json
{
  "batch_id": 12,
  "status": "queued",
  "files_accepted": 14,
  "files_rejected": ["hack.exe: unsupported extension"],
  "files_too_big": [],
  "work_dir": "/var/www/.../imports/up_20260727_143022_123456",
  "poll_url": "/api/admin/import/batches/12/"
}
```

### `GET /api/admin/import/batches/{id}/`

Detail view with totals, summary, error_report, and the most recent 25
`ImportAuditLog` rows.

### `GET /api/admin/import/batches/{id}/materials/`

Per-file status rows.

### `GET /api/admin/import/batches/{id}/audit/?page=N&page_size=M`

Paginated audit log for this batch.

### `GET /api/admin/import/batches/{id}/report/`

JSON snapshot of the import — totals, error report, materials — for
downloadable CSV / PDF conversion.

### `POST /api/admin/import/batches/{id}/cancel/`

Stop parsing (only while `queued` / `processing`, else `409`). Parsing stops
after the current file. Questions already staged stay in the review queue and
can still be published.

### `POST /api/admin/import/batches/{id}/publish/`

Body:

```json
{
  "max_per_test": 100,
  "build_tests": true,
  "only_publish": false
}
```

Publishes `approved` rows to the live `Question` table, then auto-builds per-
subject, per-topic, mixed, and PYQ-year `Test` rows. It runs in a background
thread and answers at once:

```json
{ "batch_id": 12, "publish": { "state": "running", "started_at": "...", "heartbeat_at": "...", "by": "admin" } }
```

with status `202`. Progress is `summary["publish"]` on the batch detail
(`running` → `done` with `published` / `tests_built`, or `failed` with
`error`); a run that stops heartbeating for 30 minutes is reported as stale
and can be started again (publishing is idempotent).

Allowed for a `completed` / `partial` batch, and for a **cancelled** batch that
staged questions before the cancel (not for a rolled-back batch: `409`). `409`
while a publish or a test rebuild (`republish`) runs for the batch.

### `POST /api/admin/import/batches/{id}/republish/`

Rebuild only the auto-tests (no writes to `Question`), synchronously →
`{ "batch_id": 12, "tests_built": 7 }`. The rebuild holds
`summary["rebuild"]` while it runs, which blocks a publish; `409` while a
publish or another rebuild runs. If the request dies (gunicorn's 120 s
timeout, a worker restart) the slot goes stale after 5 minutes instead of
blocking publish.

### `POST /api/admin/import/batches/{id}/rollback/`

Body:

```json
{ "delete_published": false, "confirm": true }
```

`confirm: true` is required (`400`). `409` while the batch is still parsing
(cancel it first) or while a publish or test rebuild runs. The rollback
deletes the staging rows (materials, extracted questions / theory / images)
and retires the batch's auto-tests: tests nobody attempted are deleted, tests
with student attempts are unpublished and kept. Default
`delete_published=false` leaves the live `Question` rows intact;
`delete_published=true` removes them from the bank the way "Remove from bank"
does (inactive + dropped + a `RemovedQuestion` tombstone; never a hard
delete). Response: `{ "batch_id": 12, "rolled_back": { "materials", "questions", "tests", "tests_unpublished", "published_question_ids", "published_questions_removed" } }`;
the batch becomes `cancelled` with `summary["rollback"]` set.

### `POST /api/admin/import/batches/{id}/generate-mock/`

Body:

```json
{
  "strategy": "by_subject",
  "question_count": 50,
  "difficulty": "mixed",
  "subject_id": null,
  "topic_id": null
}
```

Valid `strategy` values: `entire_file`, `by_subject`, `by_chapter`,
`by_topic`, `by_difficulty`, `random`, `image_based`, `grand`, `revision`,
`weekly`.

Response:

```json
{
  "batch_id": 12,
  "test_id": 130,
  "test_title": "Auto • By Subject • batch 12",
  "question_count": 50
}
```

---

## Questions (review queue)

### `GET /api/admin/import/questions/`

List staging questions. Query params:

- `batch` — filter by batch id.
- `material` — filter by material id.
- `subject` — filter by subject id (or name).
- `topic` — filter by topic id (or name).
- `status` — filter by status.
- `needs_review=1` — short for `status=needs_review`.
- `difficulty` — easy / medium / hard.
- `q` — text search.

### `GET /api/admin/import/questions/{id}/`

Full preview with explanation, classification metadata, raw_text, image
references, provenance checksum, and review note.

### `POST /api/admin/import/questions/{id}/decision/`

Body:

```json
{ "decision": "approve", "note": "looks correct" }
```

`decision` ∈ `approve` / `reject` / `reset`.

### `POST /api/admin/import/questions/{id}/classify-ai/`

Re-run the AI classifier on a single question.

Body:

```json
{ "use_ai": true }
```

Response:

```json
{
  "id": 12345,
  "subject": "General Medicine",
  "topic": "Cardiology",
  "difficulty": "medium",
  "bloom_level": "apply",
  "confidence": 0.78
}
```

### `POST /api/admin/import/questions/bulk-decision/`

Approve / reject / reset many rows at once.

Body:

```json
{
  "ids": [1, 2, 3],
  "decision": "approve",
  "note": "batch OK"
}
```

`ids` must be a non-empty list. One `ImportAuditLog` row is written per
touched batch.

---

## Related APIs and commands

These are separate from the Import Center (`IsControlTowerAdmin`: `role='admin'`
or superuser). Full tables: [`API_REFERENCE.md`](./API_REFERENCE.md#import-endpoints-admin-only).

- **Recall importers** — `GET /api/imports/neetpg/jobs/` and
  `GET /api/imports/inicet/jobs/` are paginated (`count` / `next` /
  `results`, 20 per page, `?page_size=` up to 100). Each job records its
  importer in `summary["importer"]`; each mount lists, shows and retries only
  its own jobs (jobs without one are NEET PG's). `manage.py neetpg_status
  --importer inicet` lists INI-CET jobs; `neetpg_retry --job-id N` re-runs a
  job with the importer that created it.
- **Ingestion platform** — `GET /api/ingestion/jobs/counts/` →
  `{counts: {queued, processing, completed, failed, cancelled, crashed}, total}`
  over every job. Job rows carry `exam`, `exam_label` and `material_filename`;
  batch status and job counts are computed from the batch's jobs. Stale jobs:
  see [`BATCH_SYSTEM.md`](./BATCH_SYSTEM.md#ingestion-platform-jobs).
- **`manage.py import_docx_fidelity <path> --rollback`** first rolls back
  every earlier batch that imported the same file (matched by sha256). Their
  published questions **stay live**; add `--remove-published` to also take
  them out of the bank (soft delete + `RemovedQuestion` tombstone). They are
  not replaced until the re-import is approved and published.
- **`manage.py ingestion_sweep_stale [--dry-run] [--older-than-minutes N]`**
  marks `processing` ingestion jobs whose worker died as `crashed` (no
  re-queue).
- **`manage.py cleanup_seed_samples [--apply] [--deactivate]`** finds the 15
  `seed_data` demo questions that older releases stored as UPSC CMS PYQs of
  2019–2023 and sets `year=0` ("Expert Curated"). Dry run without `--apply`;
  admin-edited / verified / answer-locked rows are left alone unless
  `--include-admin-edited`.

---

## Error responses

All endpoints may return:

```json
{ "error": "Human-readable message" }
```

Validation errors from serializers (400) include the standard DRF payload
shape with field-level keys.

---

## Example: end-to-end import

```bash
# 1. An admin's Supabase access token (POST /api/auth/login/ is disabled, 410).
#    Copy it from a signed-in admin browser session, or use the dev-only
#    /api/auth/local/login/ when running locally with LOCAL_DEV_AUTH=1.
TOKEN="<supabase access token of a staff user>"

# 2. Upload three files in one request
BATCH_ID=$(curl -s -X POST "$API/admin/import/upload/" \
  -H "Authorization: Bearer $TOKEN" \
  -F 'files=@./cardiology.docx' \
  -F 'files=@./surgery.docx' \
  -F 'files=@./bundle.zip' \
  -F 'source_label=Q3 docs' | jq -r .batch_id)

# 3. Poll the batch
while true; do
  S=$(curl -s -H "Authorization: Bearer $TOKEN" "$API/admin/import/batches/$BATCH_ID/" | jq -r .status)
  echo "status=$S"
  [ "$S" = "completed" ] || [ "$S" = "partial" ] || [ "$S" = "failed" ] && break
  sleep 5
done

# 4. Bulk approve all pending
curl -s -X POST "$API/admin/import/questions/bulk-decision/" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"ids": [1,2,3], "decision": "approve"}'

# 5. Publish + build tests
curl -s -X POST "$API/admin/import/batches/$BATCH_ID/publish/" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"max_per_test":100, "build_tests": true}'
```

