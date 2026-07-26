# Manual Question Fix — Admin Editor with Inline Image Upload

**Date:** 2026-07-26
**Status:** Draft (awaiting user review)
**Author:** Claude (brainstorming skill)

## Problem

The live `/questions/neet-pg/practice` page (and the other exam-scoped practice pages) shows ~637 NEET PG recall rows whose `question_text` is polluted with embedded options, leaked answers, and `MEDICAL JUNCTION TEAM` trailers. The root cause is the recall importer stuffing the whole PDF block into `question_text` instead of splitting fields. There is currently no admin UI to manually repair these rows one by one, and there is no way for an admin to insert images inline into a question. After a manual edit, the public page must reflect the change immediately because both the admin tool and the public site read from the same `Question` row.

## Goals

1. Add an **exam-type filter** (CMS / NEET PG / INI-CET / USMLE / FMGE) to the admin `/admin/questions-editor` page.
2. Let an admin **open any question in a modal editor** and fix `question_text`, `option_a`–`option_d`, `correct_answer`, `explanation`, `mnemonic`, `concept_explanation`, `difficulty`, `topic`, `needs_review`, `is_dropped`, and `is_controversial`.
3. Let the admin **upload images inline** anywhere in `question_text` (token-based: `[[img:N]]`). Stored in Supabase Storage, surfaced via the existing `QuestionImage` model.
4. Save → live DB → live website picks up the change on the next request (no rebuild, no cache flush needed because the public page reads from the same DB and the renderer caches per-question resolved HTML in memory).

## Non-goals

- AI re-generation triggered by an edit (the existing `forceRegenerate` button on `/admin/questions-editor` is unchanged).
- Bulk CSV/JSON import of fixes.
- Multi-user lock UI beyond a 409 version-conflict message.
- Image upload into options, answer field, or explanation (only `question_text` per the user-chosen scope).
- Replacing the existing `page_screenshot` ImageField on `Question`.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  /admin/questions-editor (existing, extended)                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ Filters: [exam_type ▾] [subject ▾] [topic ▾] [year ▾]       │   │
│  │          [needs_review ☐] [is_dropped ☐] [search ...]        │   │
│  │          [is_image_based ☐] [is_controversial ☐]             │   │
│  └──────────────────────────────────────────────────────────────┘   │
│  Table: ID | Exam | Year | Subject | Preview | Flags | [Edit]      │
│                                                                     │
│  Click [Edit] → opens modal:                                        │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ Question #4821 (NEET PG 2025)                                │   │
│  │ [Question Text textarea + [+ Insert image]]                  │   │
│  │   images appear inline as [[img:12]] with a hover preview   │   │
│  │ [Option A] [Option B] [Option C] [Option D]                  │   │
│  │ Correct: A / B / C / D radio                                 │   │
│  │ [Explanation textarea + [+ Insert image]]                    │   │
│  │ [Difficulty] [Topic] [Needs Review] [Dropped] [Badges]       │   │
│  │ Images attached: [img #12] [img #13] [Reorder] [×]           │   │
│  │                                              [Cancel] [Save] │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

## Components

### Backend (Django)

1. **New ViewSet: `QuestionImageViewSet`** mounted at `/questions/images/`
   - `POST /questions/images/upload/` — multipart → upload to Supabase → create `QuestionImage` row → return `{ id, url, sha256_short, modality, caption }`. Requires `IsAdminUser`.
   - `PATCH /questions/images/{id}/` — update `caption`, `modality`, `modality_subtype`, `body_region`, `role`. Requires admin.
   - `DELETE /questions/images/{id}/` — delete the file from Supabase bucket + delete the row. Requires admin.
   - `POST /questions/images/{id}/reorder/` — body `{ question_id, new_index_in_page }` → updates `image_index_in_page` for the affected rows. Requires admin.
2. **Supabase Storage config** — new private bucket `crack-cms-question-images`; public read via signed/public URL stored on the row. Service-role key in `backend/.env` as `SUPABASE_SERVICE_ROLE_KEY` (already available for `accounts/` use).
3. **Helper module `backend/questions/image_upload.py`** — wraps the Supabase storage client, returns the public URL, computes `sha256`, `width`, `height`, `bytes`. Reuses the same Supabase client used by `accounts/supabase_auth.py`.
4. **Migration `0009_questionimage_uploaded_by_admin.py`** — adds `uploaded_by_admin = BooleanField(default=False)` to `QuestionImage`. Lets us audit/filter admin uploads vs recall-imported images. Reuses existing model.
5. **Soft optimistic locking** — `QuestionViewSet.perform_update()` checks `updated_at` against the value the client sent in the `If-Match` header. Mismatch → `409 ConflictError` with current row. This protects against another admin overwriting in the same minute.

### Frontend (Next.js)

1. **`frontend/src/app/admin/questions-editor/page.tsx`** (modified)
   - Add `<select>` for `exam_type` in the existing filter bar.
   - Add `<input>` for `year`.
   - Add `[Edit]` button per row that opens the modal.
   - Existing `needsReview`, `isDropped`, `search` filters retained.
2. **`frontend/src/app/admin/questions-editor/QuestionEditModal.tsx`** (new)
   - Controlled form bound to `question`, `option_a-d`, `correct_answer`, `explanation`, `mnemonic`, `concept_explanation`, `difficulty`, `topic`, `needs_review`, `is_dropped`, `is_controversial`.
   - Image insertion: click `[+ Insert image]` → `<input type="file">` → upload → on success insert `[[img:<id>]]` at cursor position.
   - Image strip at the bottom: drag to reorder, click × to delete.
   - Save button: `PATCH /questions/{id}/` with `If-Match: <updated_at>` header. On 409, show "Question was edited by X — current values:" diff and offer `[Reload]` or `[Overwrite]`.
   - Cancel button: confirm if dirty.
3. **`frontend/src/lib/imageUpload.ts`** (new)
   - `uploadImage(file: File, questionId: number): Promise<QuestionImage>` — POSTs multipart to `/questions/images/upload/` with auth header.
   - `deleteImage(id: number)`, `reorderImage(id, newIndex)`.
4. **`frontend/src/lib/imageTokens.ts`** (new)
   - `resolveImageTokens(html: string, images: QuestionImage[]): string` — replaces `[[img:N]]` with `<img src="…" alt="…" loading="lazy" />`. Logs a warning if the id is missing.
   - Cached per `(questionId, imagesHash)` inside a `Map` to avoid re-resolution on every render.
5. **`frontend/src/lib/api.ts`** (modified)
   - Add `questionsAPI.uploadImage()`, `questionsAPI.updateImage()`, `questionsAPI.deleteImage()`, `questionsAPI.reorderImage()`.
   - Extend `questionsAPI.update()` to accept an `If-Match` header.
6. **Public-page renderer updates** (modified)
   - `frontend/src/app/questions/[exam]/practice/page.tsx`
   - `frontend/src/components/inicet-pg/IniCetLanding.tsx`
   - `frontend/src/components/...` `NeetPgPlayer` if it exists
   - All call `resolveImageTokens(question.question_text, question.images ?? [])` before rendering.

## Data flow

### Filter

1. User picks `exam_type=neet_pg` in the existing filter bar.
2. Frontend URL: `GET /questions/?exam_type=neet_pg&page=1&page_size=20`.
3. `QuestionViewSet` already supports `exam_type` in `filterset_fields` (line 144 of `views.py`).
4. Table renders with the existing columns.

### Edit + Save

1. User clicks `[Edit]` → modal opens with `GET /questions/{id}/` (already returns `images` via the existing serializer).
2. User edits fields; click `[+ Insert image]` triggers upload.
3. User clicks `Save` → `PATCH /questions/{id}/` with all changed fields + `If-Match: <updated_at>` header.
4. Backend:
   - Validates admin auth.
   - Compares `updated_at` → if changed → `409 ConflictError` with the current row.
   - Otherwise saves + returns updated row.
5. Frontend updates local state; modal closes.
6. Public `/questions/neet-pg/practice` page reads the same row on next request → shows the fix.

### Image upload

1. User picks a file in the modal.
2. Client → `POST /questions/images/upload/` (multipart, `question_id`, `file`).
3. Backend → uploads to Supabase bucket → creates `QuestionImage` row with `uploaded_by_admin=True` → returns `{ id, url, sha256_short, width, height, bytes, modality }`.
4. Client inserts `[[img:<id>]]` at the cursor in `question_text`.
5. On save, the token is persisted as part of `question_text`.

### Public rendering

1. Public page renders question → calls `resolveImageTokens(question.question_text, question.images ?? [])`.
2. Each `[[img:N]]` becomes `<img src=… loading="lazy">`.
3. Cache key = `q${id}:v${imagesHash}` so changes invalidate.

## Error handling

| Failure | Behavior |
|---|---|
| Image upload fails (network / Supabase 5xx / 401) | Toast `Failed to upload image`, modal stays open, no token inserted. Retry button on the failed slot. |
| Image upload returns 401 (admin session expired) | Redirect to `/admin/login`. |
| Save returns 409 (concurrent edit) | Modal stays open with banner: `Question was edited by <user> at <time>`. Two buttons: `[Reload]` (discard local edits) and `[Overwrite]` (forces save by re-fetching + re-applying). |
| Save returns 400 (validation) | Highlight field with error message. |
| Save returns 401 | Redirect to `/admin/login`. |
| `[[img:N]]` references a deleted image | Renderer shows `![missing image #N]` placeholder + `console.warn`. Admin can re-upload. |
| `image_index_in_page` conflict on reorder | Backend returns 409 with current ordering; modal reloads. |
| Supabase Storage bucket missing | Backend logs `ERROR` at startup if `upload_to_question_images_bucket` fails; falls back to local `MEDIA_ROOT` for dev only with a warning banner in the modal. |

## Migration plan

1. Add Supabase bucket `crack-cms-question-images` (public read). One-time setup via `python manage.py shell` script `scripts/setup_supabase_bucket.py`.
2. Backend migration `0009_questionimage_uploaded_by_admin.py` (adds the boolean field with default `False`).
3. No new env vars beyond what's already configured for `accounts/supabase_auth.py` (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`).
4. Frontend: no new env vars.
5. `backend/build.sh` on Render: no changes (no new packages; `supabase` Python client is already in `requirements.txt`).

## Testing

### Backend unit tests

- `backend/questions/tests/test_image_upload.py`
  - `test_upload_requires_admin` — anonymous → 401, non-admin → 403.
  - `test_upload_creates_question_image` — happy path → row created, URL returned, `uploaded_by_admin=True`.
  - `test_upload_dedupes_by_sha256` — same image uploaded twice → reuses existing row, returns same id.
  - `test_update_returns_409_on_stale_match` — simulate `If-Match` mismatch → 409.
  - `test_delete_removes_file_and_row` — happy path → row deleted, Supabase `storage.from().remove()` called.
  - `test_reorder_updates_image_index` — happy path → `image_index_in_page` updated atomically.

### Frontend tests

- `frontend/tests/e2e/admin-question-fix.spec.ts`
  - Login as admin → navigate to `/admin/questions-editor` → pick `exam_type=NEET PG` → click `[Edit]` on the first row in the screenshot (`2025 • Anaesthesia`).
  - Assert the polluted `question_text` is visible in the modal.
  - Replace `question_text` with a clean version + add an image upload → save.
  - Visit `/questions/neet-pg/practice` → assert the row now shows the fixed text and the image is rendered.
  - Screenshot for visual confirmation.

### Manual QA

1. Deploy to Render.
2. Hit the live `cracklabs.app/admin/questions-editor` → filter NEET PG → open the corrupted `2025 • Anaesthesia` rows.
3. Replace the polluted text, re-enter the correct answer (A), upload an image, save.
4. Open `cracklabs.app/questions/neet-pg/practice` in another tab → confirm the fix is visible without refresh.

## Files changed

### New

- `backend/questions/image_upload.py`
- `backend/questions/migrations/0009_questionimage_uploaded_by_admin.py`
- `backend/questions/serializers.py` (extend `QuestionImageSerializer` with `uploaded_by_admin` flag)
- `backend/scripts/setup_supabase_bucket.py`
- `backend/questions/tests/test_image_upload.py`
- `frontend/src/app/admin/questions-editor/QuestionEditModal.tsx`
- `frontend/src/lib/imageUpload.ts`
- `frontend/src/lib/imageTokens.ts`
- `frontend/tests/e2e/admin-question-fix.spec.ts`

### Modified

- `backend/questions/views.py` (add `QuestionImageViewSet`, add `perform_update` optimistic lock)
- `backend/questions/urls.py` (register `QuestionImageViewSet` router)
- `backend/crack_cms/urls.py` (no change — registered via app router)
- `frontend/src/app/admin/questions-editor/page.tsx` (add `exam_type` filter, `[Edit]` button)
- `frontend/src/lib/api.ts` (add 4 image methods, `If-Match` support)
- `frontend/src/app/questions/[exam]/practice/page.tsx` (use `resolveImageTokens`)
- `frontend/src/components/inicet-pg/IniCetLanding.tsx` (use `resolveImageTokens`)
- `frontend/src/components/...` any other player that renders `question_text`

## Open questions

None at design time. All four clarifying questions answered.
