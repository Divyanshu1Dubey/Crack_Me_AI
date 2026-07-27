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
- Pagination uses `?page=N&page_size=M` on every list endpoint (default 50,
  max 200).

Standard response codes:

| Code | Meaning |
|---|---|
| 200 | OK |
| 201 | Created |
| 400 | Validation error |
| 401 | Unauthenticated |
| 403 | Authenticated but not an admin |
| 404 | Batch or question not found |
| 409 | Invalid state transition (e.g. cancelling a completed batch) |

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

Stop parsing if possible (only while `queued` / `processing`).

### `POST /api/admin/import/batches/{id}/publish/`

Body:

```json
{
  "max_per_test": 100,
  "build_tests": true,
  "only_publish": false
}
```

Publishes approved rows to the live `Question` table, then auto-builds per-
subject, per-topic, mixed, and PYQ-year `Test` rows.

Response:

```json
{ "batch_id": 12, "published": 1023, "tests_built": 7 }
```

### `POST /api/admin/import/batches/{id}/republish/`

Rebuild only the auto-tests (no DB writes to `Question`).

### `POST /api/admin/import/batches/{id}/rollback/`

Body:

```json
{ "delete_published": false, "confirm": true }
```

Default `delete_published=false` cascades on the staging tables and the
auto-tests but leaves the live `Question` rows intact.

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
# 1. Get a JWT
TOKEN=$(curl -s -X POST "$API/auth/login/" \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"..."}' | jq -r .access)

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

