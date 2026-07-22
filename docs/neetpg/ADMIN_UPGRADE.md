# Admin Upgrade — Phase 2

> New `ModelAdmin` registrations only. Existing admin classes stay untouched.

---

## 1. Existing admin (DO NOT TOUCH)

- `SubjectAdmin` (`backend/questions/admin.py:11`)
- `TopicAdmin` (`backend/questions/admin.py:23`)
- `QuestionAdmin` (`backend/questions/admin.py:51`) — has fieldsets, filters, search_fields, admin actions (`generate_ai_cache`, `generate_video`)
- `QuestionBookmarkAdmin` (`backend/questions/admin.py:110`)

These continue to render exactly as today.

---

## 2. New registrations (additive)

### 2.1 `QuestionImageAdmin`

- `list_display`: `id`, `question_id`, `modality`, `phash`, `sha256_short`, `is_active`, `created_at`
- `list_filter`: `modality`, `modality_subtype`, `role`, `is_watermarked`, `is_active`
- `search_fields`: `caption`, `ocr_text`, `question__question_text`
- `readonly_fields`: `sha256`, `phash`, `dhash`, `bytes`, `created_at`
- Bulk actions:
  - `re_ocr_selected` — re-run OCR on selected images (admin async task).
  - `mark_watermarked` — bulk set `is_watermarked=True`.

### 2.2 `RecallSourceAdmin`

- `list_display`: `id`, `pdf_filename`, `pdf_sha256_short`, `page_count`, `scan_type`, `recall_status`, `question_count`, `created_at`
- `list_filter`: `scan_type`, `recall_status`, `is_active`
- `search_fields`: `pdf_filename`, `publisher`
- `readonly_fields`: `pdf_sha256`, `pdf_size_bytes`, `metadata`, `created_at`
- Bulk actions:
  - `rerun_import` — re-run the importer for the selected source.

### 2.3 `QuestionSourceAdmin`

- `list_display`: `id`, `question_id`, `recall_source_id`, `page_number`, `ocr_confidence`, `extraction_confidence`, `imported_at`
- `list_filter`: `recall_source`, `import_job_id`
- `search_fields`: `question__question_text`, `recall_source__pdf_filename`
- `readonly_fields`: all (provenance is immutable)

### 2.4 `DuplicateClusterAdmin`

- `list_display`: `id`, `canonical_question_id`, `similarity_threshold`, `detection_method`, `member_count`, `created_at`
- `readonly_fields`: `created_at`
- Inline `DuplicateMemberInline`
- Admin actions:
  - `unmerge_cluster` — re-activates all member questions (sets `is_active=True`) and clears the cluster.

### 2.5 `DuplicateMemberAdmin`

- `list_display`: `id`, `cluster_id`, `question_id`, `similarity_score`, `created_at`
- `readonly_fields`: all

### 2.6 `QuestionExtractionItemAdmin` (currently unregistered)

- `list_display`: `id`, `job_id`, `status`, `year`, `subject`, `topic`, `created_at`
- `list_filter`: `status`, `year`, `subject`, `paper`
- `search_fields`: `raw_text`, `question_text`
- Bulk actions:
  - `approve_and_publish_selected`
  - `reject_selected`

### 2.7 `QuestionImportJobAdmin` (currently unregistered)

- `list_display`: `id`, `job_type`, `status`, `source_filename`, `summary`, `created_by`, `created_at`
- `list_filter`: `job_type`, `status`, `created_at`
- `search_fields`: `source_filename`, `summary`
- `readonly_fields`: `summary`, `error_report`, `created_at`, `updated_at`

### 2.8 `DiscussionAdmin` (currently unregistered)

- `list_display`: `id`, `question_id`, `user_id`, `is_pinned`, `upvotes`, `created_at`
- `list_filter`: `is_pinned`, `created_at`
- `search_fields`: `text`

---

## 3. Custom admin site header

A small patch to `crack_cms/urls.py` admin site (`admin.site.site_header = "CrackLabs Control Tower"`, etc.) — **NO**, that's UI/branding. We leave the admin site header untouched.

---

## 4. Permission gating

All new admin classes set `has_module_permission` and `has_change_permission` to defer to `IsControlTowerAdmin` (existing permission class). Admins are still the same `is_staff` users; control-tower admins are gated via `accounts.permissions.IsControlTowerAdmin` (already in use across `questions/views.py`).

---

## 5. Admin URL additions

`backend/questions/admin.py` registers `QuestionImage`, `RecallSource`, `QuestionSource`, `DuplicateCluster`, `DuplicateMember`, `QuestionExtractionItem`, `QuestionImportJob`, `Discussion`. None of the existing `@admin.register(...)` decorators is changed.

---

## 6. Tests

`backend/questions/tests_recall_admin.py` (new) — uses Django's `AdminSite` test client to verify each new admin class:

- Renders the changelist with at least one row.
- Filters by `modality` / `scan_type` / `status`.
- Bulk actions dispatch correctly (mocked).

---

## 7. Out of scope (deliberately)

- We do NOT add a custom admin theme.
- We do NOT add a dashboard app.
- We do NOT change existing ModelAdmin classes.