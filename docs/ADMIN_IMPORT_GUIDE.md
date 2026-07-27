# Admin Import Center — User Guide

The Admin Import Center is the browser-based content ingestion system for
CrackLabs. It lets a non-technical content team member upload thousands of
medical questions in DOCX/PDF/PPTX/CSV/ZIP format without ever touching the
terminal — replacing the previous `python manage.py import_mocktests` CLI
workflow with a full UI.

> **Audience**: Content managers, content QA, medical editors.
> **Access**: `/admin/import-center` — staff/admin users only.
> **Replaces**: `python manage.py import_mocktests` and the ad-hoc CLI
> scripts under `backend/material_importer/management/commands/`.

---

## 1. Quick start

1. Sign in as an admin.
2. Navigate to **/admin/import-center**.
3. Click **📤 Upload Files** in *Quick Actions*.
4. Drag & drop one or more `.docx` files (or a `.zip` containing many) into
   the upload zone.
5. Optionally tweak the *Source label*, *Use AI classifier*, or
   *Force re-import* options.
6. Click **Upload &amp; Parse**.
7. You are auto-redirected to the batch detail page where live progress is
   shown.
8. When parsing finishes, click **Publish &amp; Build Tests** to promote
   extracted questions to the live question bank and auto-create mock tests.
9. Review the **Review Queue** for any items flagged `needs_review`.

---

## 2. Layout map

| Tab | URL | Purpose |
|---|---|---|
| **Dashboard** | `/admin/import-center` | Tiles for batches/questions/published/duplicate rate + recent uploads |
| **Upload** | `/admin/import-center/upload` | Drag/drop upload form with options |
| **Batches** | `/admin/import-center/batches` | Table of every batch with status & counters |
| **Batch detail** | `/admin/import-center/batches/[id]` | Per-file metrics, audit log, actions |
| **Review Queue** | `/admin/import-center/review` | Approve / reject staging questions |
| **Search** | `/admin/import-center/search` | Full-text search of staging area |

A persistent tab bar shows where you are inside the Import Center.

---

## 3. Uploading material

### Supported formats

- **DOCX** — Microsoft Word documents (`.docx`)
- **PDF** — Portable Document Format (`.pdf`)
- **PPTX** — PowerPoint slides (`.pptx`)
- **TXT / MD** — Plain text or Markdown
- **ZIP** — Bundle containing any of the above

### Limits (defense in depth)

- 200 MB per file
- 200 files per upload
- Only the extensions above are accepted; everything else is rejected.

### Drag & drop

Drag files from your OS file manager onto the upload zone. The drop zone
turns primary-colored when you hover with files.

### Multi-file & folder upload

Click **Choose Files** for multi-file selection, or **Choose Folder** to
select an entire directory at once (Chromium / Edge / Opera only).

### Options

| Option | Effect |
|---|---|
| **Source label** | Free-form label attached to the batch (e.g. "NEET PG 2024 Recall — Docx Set 3"). |
| **Use AI classifier** | Slower (calls the AI round-robin) but produces better subject/topic/difficulty guesses. |
| **Force re-import** | Bypasses the cross-batch duplicate detector — only use for fidelity upgrades or fixture re-runs. |

### What happens after you click *Upload &amp; Parse*

1. Files are streamed to the backend over `multipart/form-data`.
2. Each file is validated for size + extension.
3. A new `ImportBatch` row is created in `queued` state and the upload is
   accepted (HTTP 201).
4. A background thread on the backend parses every file:
   - Walks the directory, picks a parser per file (`docx_fidelity`,
     `docx_parser`, `pdf_parser`, `pptx_parser`, `text_parser`).
   - Persists `ImportMaterial`, `ExtractedQuestion`, `ExtractedTheory`,
     `ImportedImage`, and `ImportAuditLog` rows.
   - Uploads images to Supabase Storage (bucket
     `crack-cms-question-images`) or to `MEDIA_ROOT/imports/` if Supabase is
     not configured.
5. The batch detail page polls `/api/admin/import/batches/{id}/` every 4
   seconds and updates live counters.
6. When parsing finishes the status flips to `completed` or `partial`.

### Cancel / retry / resume

- **Cancel** — only effective while `queued` or `processing`. Stops the
  background work; the batch is marked `cancelled` and its staging rows are
  preserved so a partial result is still inspectable.
- **Retry** — for failed uploads, just upload the file again. Each upload
  creates a *new* batch; failed batches can also be left in place for
  audit purposes.
- **Resume interrupted upload** — there is no in-progress *resume*: each
  upload is independent. Re-upload any missed files into a new batch.

---

## 4. The pipeline panel

The batch detail page shows the per-file *Materials* table and an *Audit Log*
of every event the parser emitted. Useful columns:

| Column | Meaning |
|---|---|
| **Found** | Total questions the parser saw in the file (before dedup / rejection). |
| **Saved** | Questions actually persisted into `ExtractedQuestion`. |
| **Dupes** | Cross-batch duplicates the dedup detector skipped. |
| **Images** | Images extracted from the file. |
| **Ms** | Parse duration in milliseconds. |
| **Status** | `parsed` / `failed` / `skipped` (duplicate batch). |

The audit log records every step with timestamps, levels (`info` / `warning`
/ `error`), and a stable `code` you can grep on.

---

## 5. Pre-import preview

The pipeline does **not** write anything to the live `Question` table
during upload. It only writes to the staging `ExtractedQuestion` rows
(in-memory preview is one click away in the Review Queue).

To preview the questions of a given batch:

1. Open the batch detail page.
2. Click **Review Queue** in the navigation.
3. Filter by the batch id using the *Batch #* input.
4. Click any question to open the **Preview Drawer** — it shows the full
   question text, options, correct answer, explanation, classification, and
   inline image tokens.

Nothing is published until you click **Publish &amp; Build Tests** on the
batch detail page.

---

## 6. Validation

Every batch run is automatically validated. The system flags:

- **Missing options** — `option_a/b/c/d` empty rows (rejected).
- **Missing answer** — `correct_answer` not in {A,B,C,D} (flagged
  `needs_review`).
- **Duplicate questions** — content_hash collision with an existing
  `Question` (skipped; counted under *Dupes*).
- **Broken images** — any image that fails upload or fails to render.
- **Unsupported layouts** — parser emits a warning but still saves
  whatever it could.
- **Formatting loss** — `parse_warnings` per file is preserved.
- **Table issues** — flagged as parser warnings.
- **Reference issues** — when a question references an image filename that
  doesn't exist in the source file.

---

## 7. Import Report

The **Report** endpoint (`GET /api/admin/import/batches/{id}/report/`)
returns a JSON snapshot of every counter, error, warning, and per-file
metric. Use it for QA or to build a downloadable CSV.

---

## 8. Auto Mock Test generation

After publish, the *Generate Mock Test* modal lets you create a single
mock test from this batch using one of these strategies:

| Strategy | Filter applied |
|---|---|
| **Entire File** | All approved/published questions in the batch. |
| **By Subject** | Questions whose `subject` matches the chosen subject id. |
| **By Chapter** | Same as subject (alias). |
| **By Topic** | Questions whose `topic` matches the chosen topic id. |
| **By Difficulty** | Filter by `inferred_difficulty` ∈ {easy, medium, hard}. |
| **Random Mix** | Random sample, capped by question_count. |
| **Image Based** | Questions with at least one extracted image. |
| **Grand Test** | Full-length simulated exam. |
| **Revision Test** | Same source, smaller cap. |
| **Weekly Test** | A rolling weekly set. |

The generated test is an idempotent `Test` row whose title is unique
(`Auto • <strategy> • batch <id>`) so re-running just replaces the
question set.

In addition to the manual modal, the **Publish &amp; Build Tests** button
on the batch detail page auto-creates per-subject, per-topic, mixed, and
PYQ-year tests via `mock_test_builder.build_for_batch()`. The build is
also idempotent — re-running replaces the existing auto-tests rather than
duplicating them.

---

## 9. AI features

### Auto-classification

Every imported question is auto-classified by the heuristic classifier in
`material_importer.ai_classifier`. When the *Use AI classifier* option is
enabled on upload, the round-robin AI service is also consulted for
high-confidence guesses of:

- Subject
- Topic
- Subtopic
- Difficulty (easy / medium / hard)
- Clinical importance
- Image-based flag
- Repeated PYQ flag
- High-yield flag

Per-row AI re-classification is also exposed as
`POST /api/admin/import/questions/{id}/classify-ai/` — the *🧠 Re-classify*
button in the preview drawer calls it.

### Flashcards, revision notes, mnemonics, related questions, video prompts

These are **out of scope** for this version of the Import Center and are
delegated to the existing question-detail UI / AI Tutor endpoints. The
import pipeline always preserves `question_text`, `explanation`, and
`inferred_topic` so downstream AI features keep working without changes.

---

## 10. Admin dashboard

The dashboard tile is a snapshot of:

- Total batches
- Total questions imported
- Total questions published
- Total needs-review count
- Duplicate rate (across all batches)
- Image questions count
- Subjects / topics counts
- Pending reviews count
- Recent uploads (last 10 batches)

Use the dashboard to spot batches with unusually high rejection or
duplication rates.

---

## 11. Review Queue

The review queue lists every `ExtractedQuestion` row that has not yet been
published. By default the filter is `status=needs_review` so the screen
focuses on the items that need human attention.

### Per-row actions

- **Approve** — sets `status=approved`. The question becomes eligible for
  the next publish pass.
- **Reject** — sets `status=rejected`. Excluded from future publish passes.
- **Reset** — sets `status=pending`. Useful when re-running AI
  classification and you want a fresh look.

### Bulk actions

Select multiple rows with the checkbox column, then click **Approve /
Reject / Reset** in the toolbar. Each bulk action writes a single
`ImportAuditLog` row per touched batch.

### Preview Drawer

Click any question row to open the *Preview Drawer* with:

- Full question text
- All four options with the correct one highlighted
- Explanation
- Inline image tokens (when supported)
- Image counts
- Classification metadata (subject, topic, difficulty, confidence, bloom)
- Per-row Approve / Reject / Reset / 🧠 Re-classify buttons

---

## 12. Search

The search bar is a debounced full-text lookup across:

- `question_text`
- `option_a` … `option_d`
- `explanation`
- `inferred_topic`
- `material.original_filename`

Results are limited to 200 hits and ordered by recency. Each result links
back to the parent batch.

---

## 13. Batch management

| Action | Endpoint | Effect |
|---|---|---|
| **View** | `GET /api/admin/import/batches/{id}/` | Detail view. |
| **Cancel** | `POST /api/admin/import/batches/{id}/cancel/` | Stops parsing; preserves staging rows. |
| **Publish** | `POST /api/admin/import/batches/{id}/publish/` | Promotes approved rows to live `Question`, then auto-builds mock tests. |
| **Republish** | `POST /api/admin/import/batches/{id}/republish/` | Rebuilds mock tests without touching live Question rows. |
| **Rollback** | `POST /api/admin/import/batches/{id}/rollback/` | Cascade-deletes the batch's `ImportMaterial`, `ExtractedQuestion`, `ExtractedTheory`, `ImportedImage`, and the auto-generated `Test` rows. Pass `delete_published=true` to also delete the published `Question` rows. |
| **Generate Mock** | `POST /api/admin/import/batches/{id}/generate-mock/` | Build one extra mock test using a chosen strategy. |
| **Download Report** | `GET /api/admin/import/batches/{id}/report/` | JSON snapshot — pipe it into a CSV / PDF converter of your choice. |
| **View Audit** | `GET /api/admin/import/batches/{id}/audit/` | Paginated audit log. |
| **View Materials** | `GET /api/admin/import/batches/{id}/materials/` | Per-file metrics. |

---

## 14. Security

- All endpoints are gated by `IsAdminUser`. Non-staff users get a 403 even
  with a valid token.
- File extensions and MIME types are validated server-side.
- Upload size and per-batch file counts are hard-capped.
- Every state-changing action (cancel, publish, rollback, approve, reject,
  classify) emits an `ImportAuditLog` row including the acting username.

---

## 15. Performance

- Parsing runs in a background thread per batch. The HTTP request returns
  immediately with the new `batch_id`.
- Batch detail page polls every 4 seconds; polling stops automatically when
  status is no longer `processing` / `queued`.
- `bulk_create(batch_size=200)` keeps DB round-trips low.
- The dedup index is cached on disk (see
  `ingest_service._seed_existing_dedup`) so 10k-question imports complete
  in seconds rather than minutes.

---

## 16. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Upload accepted but `status=processing` never changes | Background thread crashed. | Open the audit log; look for `code=ingest_crash`. |
| High *Rejected* count | Missing answer markers in source file. | Check `needs_review` filter and use the Preview Drawer to fix manually. |
| Images missing from preview | Source file used a non-image MIME we don't store. | Inspect `parse_warnings` for `image_format_unsupported`. |
| Test build returns 0 | No `approved` rows yet. | Approve some questions first. |
| Rollback deletes published questions unexpectedly | Caller passed `delete_published=true`. | Re-upload the source files into a new batch. |