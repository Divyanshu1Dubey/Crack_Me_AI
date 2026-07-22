# Integration Plan — Phase 2 NEET PG Recall Engine

> Companion to [ARCHITECTURE_ANALYSIS.md](ARCHITECTURE_ANALYSIS.md) and [DATABASE_MIGRATION_PLAN.md](DATABASE_MIGRATION_PLAN.md).

Goal: integrate the Phase-1 standalone PDF importer with the existing CrackLabs Django platform **without breaking anything that already works**. Every change is additive.

---

## 1. Strategy

| Layer | Decision |
|---|---|
| Models | Reuse `Question`, `Subject`, `Topic`, `ExamTrack`, `QuestionBookmark`, `QuestionAttempt`, `Discussion`, `Note`, `Flashcard`, `QuestionExtractionItem`, `QuestionImportJob` (already present). Add **4 new models** in `questions/`: `QuestionImage`, `RecallSource`, `QuestionSource`, `DuplicateCluster`, `DuplicateMember`. Add **8 new fields** on `Question` (additive migration). |
| Schema | Phase 1's full target schema (`SourceRecord`, `Provenance`, `ImageRecord`, …) is collapsed onto the existing schema — we extend, not fork. |
| Importer | Phase 1's `backend/importers/neetpg/` becomes a real Django app via a thin wrapper at `backend/importers/apps.py` and is registered in `INSTALLED_APPS`. The runner now writes into `Question` + new tables when `--write-db` is set, else stays JSONL-only. |
| Search | DRF `QuestionViewSet` keeps its existing `search_fields`. New `recall_search` action filters `is_image_based`, `recall_status`, `clinical_category`, `question_type`. SQLite FTS5 mirror is built for `question_text` + `explanation` + `mnemonic` + `concept_explanation` + `ai_explanation` + `ai_clinical_pearl` + `QuestionImage.ocr_text`. |
| Image | `QuestionImage` (new) is the multi-image slot; existing `Question.page_screenshot` is kept and continues to render as the **primary** image when present. |
| Admin | New `ModelAdmin` classes only — none of the existing admin classes is touched. |
| Frontend | One opt-in folder `frontend/src/components/recall/` — not wired into pages automatically. |
| Auth / payments / SEO | Untouched. |

---

## 2. Mapping Phase-1 dataclasses → existing + new Django models

| Phase 1 dataclass | Existing model | New model / field |
|---|---|---|
| `SourceRecord` (PDF identity) | — | **`RecallSource`** (new) |
| `ParsedQuestion` | `Question` | + 8 new fields (additive) |
| `ParsedOption` (option list) | (folded into `Question.option_a/b/c/d`) | — |
| `ImageRecord` | — | **`QuestionImage`** (new) |
| `QualityIssue` | — | new field on import staging row + JSON dump for the QUALITY report |
| Phase 1 "provenance" concept | — | **`QuestionSource`** (new) — links Question ↔ RecallSource with page + question number + OCR confidence |
| Phase 1 dedup cluster | — | **`DuplicateCluster`** + **`DuplicateMember`** (new) |
| Phase 1 "canonical id" | `Question.uuid` (already exists) | reuse, no change |

---

## 3. New models (full DDL sketch)

See [DATABASE_MIGRATION_PLAN.md](DATABASE_MIGRATION_PLAN.md) for exact field lists.

- `questions.RecallSource` — one row per source PDF: filename, sha256 (full + short), size, page count, scan type, recall status, publisher, import job FK.
- `questions.QuestionSource` — many-to-many bridge Question↔RecallSource with page_number, question_number_in_pdf, original_text, ocr_confidence, extraction_confidence, import_job_id.
- `questions.QuestionImage` — multi-image per question: source, page, file (ImageField), mime, width/height, sha256, phash, modality, ocr_text, caption, caption_source, has_diagram, has_table, is_watermarked, role (primary/option/illustration/explanation).
- `questions.DuplicateCluster` — canonical question, similarity threshold, detection method.
- `questions.DuplicateMember` — member question, similarity score, detection method.

## 4. New fields on `Question` (additive migration)

```python
recall_status            CharField  default 'official_compiled'  # recall / coaching_compiled / official_compiled
question_type            CharField  default 'single_best'         # single_best / multiple_correct / assertion_reason / match / image_based / numerical
clinical_category        CharField  default 'clinical'            # clinical / preclinical / paraclinical
session                  CharField  default ''                    # jan / jul / may / nov / none
confidence_score         DecimalField(4,3) default 1.000           # 0..1
ocr_confidence           DecimalField(5,2) null=True              # 0..100
extraction_confidence    DecimalField(4,3) default 1.000          # 0..1
is_image_based           BooleanField default False
recall_source_id         BigInteger null=True                     # FK populated on bulk import
recall_page_number       IntegerField null=True                    # primary source page
```

All fields are non-breaking — defaults ensure existing rows continue to render unchanged.

---

## 5. New endpoints (additive)

Under `/api/questions/`:
- `GET /api/questions/recall_search/?q=...&subject=...&year=...&recall_status=recall&clinical_category=clinical&is_image_based=true`
- `GET /api/questions/{id}/images/` → `QuestionImage` list (lazy-load safe)
- `GET /api/questions/{id}/sources/` → `QuestionSource` list

Under `/api/imports/` (new top-level):
- `GET /api/imports/neetpg/jobs/` — paginated `QuestionImportJob` rows where `job_type='pdf'`
- `POST /api/imports/neetpg/jobs/` — admin-only, body `{ source_dir, force }`, kicks off the runner in a `django_q` task
- `GET /api/imports/neetpg/jobs/{id}/` — status + summary + error_report
- `POST /api/imports/neetpg/jobs/{id}/retry/` — re-run a failed job
- `GET /api/imports/neetpg/reports/{run_id}/` — markdown report bundle (IMPORT, OCR, IMAGE, QUALITY, DEDUP, MISSING)

No existing endpoint is renamed or removed.

---

## 6. Admin registrations (additive only)

| Model | Admin class | Action |
|---|---|---|
| `QuestionImage` | `QuestionImageAdmin` (NEW) | list_filter by modality/source/watermark; bulk action to re-OCR |
| `RecallSource` | `RecallSourceAdmin` (NEW) | list_filter scan_type/recall_status; link to import job |
| `QuestionSource` | `QuestionSourceAdmin` (NEW) | raw list view; readonly provenance |
| `DuplicateCluster` | `DuplicateClusterAdmin` (NEW) | merge/unmerge actions |
| `DuplicateMember` | `DuplicateMemberAdmin` (NEW) | raw list view |
| `QuestionExtractionItem` | register (currently unregistered) | review queue UI |
| `QuestionImportJob` | register (currently unregistered) | import history |
| `Discussion` | register (currently unregistered) | moderation queue |

We will **not** modify `SubjectAdmin`, `TopicAdmin`, `QuestionAdmin`, `QuestionBookmarkAdmin` — they stay as-is.

---

## 7. Frontend (opt-in only)

New folder: `frontend/src/components/recall/`

Files:
- `RecallBadge.tsx` — small "Recall-based · not official" badge
- `QuestionImageZoom.tsx` — pinch-zoom + fullscreen
- `ProvenanceList.tsx` — list of source PDFs / pages for a question
- `ImageGallery.tsx` — carousel of `QuestionImage` rows for a question
- `RecallSearchBox.tsx` — chip-based filters for the recall search endpoint

None of these is wired into a page automatically. They're added so any page can opt in (e.g. `frontend/src/app/questions/page.tsx` may later wrap a `<RecallBadge>` around a question — that's a future change, not Phase 2).

---

## 8. Run-time wiring

- `backend/importers/apps.py` (NEW) — registers the package as a Django app.
- `backend/crack_cms/settings.py` — add `'importers.neetpg'` to `INSTALLED_APPS`. **Done in this Phase 2 patch.**
- `backend/crack_cms/urls.py` — add `path('api/imports/', include('importers.neetpg.urls'))` (a NEW urls module that lives next to the importer, NOT inside `questions/`).
- Management commands from Phase 1 are extended:
  - `neetpg_import` (existing) gains `--write-db` (default False until DB schema migration applied)
  - `neetpg_import_all` (existing) gains `--write-db`
  - `neetpg_import_run` (NEW) — admin endpoint entry point that wraps the runner for the API
  - `neetpg_status` (NEW) — pretty-print recent `QuestionImportJob` rows
  - `neetpg_retry` (NEW) — re-run failed jobs
  - `neetpg_reconcile` (NEW) — re-link JSONL output to the database idempotently

---

## 9. Resume, rollback, batch, dedup, validation, error recovery, incremental

| Capability | Where it lives |
|---|---|
| Resume | Phase 1 manifest is unchanged. New: a `QuestionImportJob` row tracks each run, `summary.processed` mirrors the manifest. Re-running an import checks both. |
| Rollback | `QuestionImportJob.delete()` cascades to extraction items; for production rows we provide `neetpg_rollback --job-id <id>` that soft-deletes (`is_active=False`) every Question created by that job's import_job_id. **Hard deletes are never allowed.** |
| Batch | DB writer uses `bulk_create(batch_size=500)` per page; one transaction per source PDF. |
| Dedup | Phase 1 deduplicator stays in the JSONL pipeline. When writing to DB, a new `DuplicateCluster` row is created on the first member, then `DuplicateMember` rows are added; canonical question is the highest-confidence member. Source row is preserved (`is_active=False` on the duplicate, FK kept in `QuestionSource`). |
| Logging | Python `logging` module + `QuestionImportJob.summary` + `QuestionImportJob.error_report`. Console + Sentry in prod. |
| Validation | `quality.check_questions()` from Phase 1 emits `QualityIssue` rows. New: these are also written as `QuestionExtractionItem` review queue entries (if `is_active=False`) so admins see them in admin. |
| Error recovery | Per-page try/except wraps each page in the runner. A failure increments `QuestionImportJob.error_report` and continues. |
| Incremental | Manifest + per-question `source_text_hash` dedup means a re-import of an unchanged PDF is a no-op. |

---

## 10. Image system (cross-reference)

Full design: [IMAGE_SYSTEM.md](IMAGE_SYSTEM.md). Summary: `QuestionImage` (multi-image) is the only new image-bearing model; `Question.page_screenshot` (single) is kept as the **primary** slot. `MEDIA_ROOT`/`MEDIA_URL` are reused.

---

## 11. Search (cross-reference)

Full design: [SEARCH_DESIGN.md](SEARCH_DESIGN.md). Summary: DRF filter stays. New `recall_search` action + SQLite FTS5 mirror over `question_text` + `ai_explanation` + `mnemonic` + `QuestionImage.ocr_text` + `concept_tags`.

---

## 12. Quality (cross-reference)

Full report: [QUALITY_REPORT.md](QUALITY_REPORT.md). The `QuestionImportJob.summary.quality` JSON block emits the same counters as the Phase-1 standalone QUALITY_REPORT.md.

---

## 13. Rollout order

1. Add the additive migration in `questions/migrations/0023_recall_neetpg_fields_and_models.py`.
2. Add the new admin classes (no existing class touched).
3. Wire the importer as a Django app.
4. Run `python manage.py neetpg_import_all --source-dir <path> --write-db` on the recall dataset.
5. Verify admin / API / FTS5 mirror / reports.
6. Commit.

---

## 14. What we explicitly will not do

- We will **not** modify the existing `Question` migration history or any other app's migration.
- We will **not** rename `Question` fields or tables.
- We will **not** migrate the existing `Question.page_screenshot` data — it stays as the primary image.
- We will **not** move any Phase-1 code into `questions/` — the importer stays in its own app to keep concerns separated.
- We will **not** delete questions. `Question.is_active=False` is the soft-delete handle.
- We will **not** wire the importer to write into the DB until the new migration is applied on the target environment.
- We will **not** touch auth / payments / SEO / frontend pages.