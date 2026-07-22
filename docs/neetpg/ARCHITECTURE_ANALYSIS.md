# Architecture Analysis — Existing CrackLabs Platform

> Phase 2 / Integration planning. Read alongside [INTEGRATION_PLAN.md](INTEGRATION_PLAN.md) and [DATABASE_MIGRATION_PLAN.md](DATABASE_MIGRATION_PLAN.md).

This is a snapshot of the live production codebase at `C:\Users\DIVYANSHU\Desktop\crack_cms`. Every claim is grounded in a file/line citation. Anything not found is explicitly marked `NOT FOUND` so we don't paper over gaps.

---

## 1. Django project

- **Settings:** `backend/crack_cms/settings.py`
  - `INSTALLED_APPS` includes local apps: `accounts`, `questions`, `tests_engine`, `analytics`, `ai_engine`, `textbooks`, `resources`, `video_engine`, `django_q`, `jobs`, `knowledge_base`, `axes`. (settings.py:72-98)
  - **No `importers` app is installed.** The standalone package at `backend/importers/neetpg/` (Phase 1) is a pure-Python package — it does not depend on Django models.
  - Middleware order (settings.py:100-114): security → whitenoise → corsheaders → session → common → csrf → auth → messages → clickjacking → axes → `questions.middleware.RateLimitMiddleware` → `crack_cms.cache_middleware.DisableApiCacheMiddleware` → `accounts.middleware.UpdateLastSeenMiddleware`.
  - **Auth user model:** `accounts.CustomUser` (referenced as `settings.AUTH_USER_MODEL` throughout). All FKs from `questions` already point at the swappable user model.
  - **Database:** SQLite dev fallback, Postgres via `DATABASE_URL` in prod (settings.py:164-192).
  - **Cache:** not yet confirmed; the cache middleware disables API caching. (settings.py:434+)
  - **Media:** `MEDIA_URL='/media/'`, `MEDIA_ROOT=BASE_DIR/'media'`. Static via WhiteNoise. (settings.py:360-361)
  - **STORAGES:** whitenoise for static; default storage for media. (settings.py:355)

- **Top-level URL routes** (`backend/crack_cms/urls.py`):
  - `admin/`, `api/health/`, `api/`
  - `/api/auth/`, `/api/questions/`, `/api/tests/`, `/api/analytics/`, `/api/ai/`, `/api/knowledge/`, `/api/textbooks/`, `/api/resources/`, `/api/video/`, `/api/jobs/`
  - **No `/api/imports/` route yet.** Phase 2 will add one under `/api/imports/neetpg/`.

---

## 2. Question schema (`backend/questions/models.py`)

This is the single largest model in the project and already carries nearly every field we need.

| Field | Type | Notes |
|---|---|---|
| `id` | BigAutoField | |
| `uuid` | UUIDField unique | Stable external handle. **Already exists — reuse as canonical id.** |
| `display_number` | int nullable | Per-year/per-paper display index |
| `question_text` | text | Normalised on save (mojibake fix in `text_encoding.normalize_text`) |
| `option_a/b/c/d` | text | Fixed 4-option layout (no separate `Option` table) |
| `correct_answer` | char(1) | `A/B/C/D` |
| `exam_type` | char(20) | `cms / neet_pg / usmle / fmge` (already exists) |
| `exam_track` | FK → `ExamTrack` | nullable, `related_name='questions'` |
| `year` | int (db_index) | |
| `subject` | FK → `Subject` | |
| `topic` | FK → `Topic` nullable | hierarchical (`Topic.parent` self-FK) |
| `difficulty` | char(10) | `easy / medium / hard` |
| `concept_tags` | JSONField | list[str] |
| `concept_id` | char(120) indexed | Stable concept id for related-PYQ linking (questions/models.py:116) |
| `explanation`, `concept_explanation`, `mnemonic` | text | |
| `book_name`, `chapter`, `page_number` (CharField), `reference_text` | | **No integer page number — uses string.** |
| `source` | char(200) | Source file label (questions/models.py:131) |
| `exam_source` | char(50) | default `UPSC CMS` |
| `times_asked`, `is_active`, `is_dropped`, `admin_edited`, `needs_review` | | |
| `is_scholarship_eligible`, `is_controversial`, `is_disputed` | bool | |
| `textbook_references` | JSONField | list of `{book, chapter, page, excerpt}` |
| `learning_technique`, `shortcut_tip` | text | |
| `page_screenshot` | ImageField | One screenshot per question (questions/models.py:158) |
| `concept_keywords` | JSONField | for vector similarity |
| `ai_explanation`, `ai_answer`, `ai_mnemonic`, `ai_references`, `ai_clinical_pearl` | text / json | AI slots already exist |
| `video_url`, `video_thumbnail`, `video_status`, `video_duration`, `video_generated_at`, `video_version`, `video_error` | | |
| `admin_answer_override`, `admin_explanation_override`, `admin_mnemonic_override`, `admin_references_override` | | |
| `lock_answer`, `lock_explanation` | bool | |
| `is_verified_by_admin`, `verified_by` (FK), `verified_at`, `verified_note` | | |
| `similar_questions` | M2M `self` | symmetric, concepts linking |
| Indexes | | `(year, subject)`, `(difficulty)`, `(exam_source)`, `(paper)`, `(is_active, is_verified_by_admin)`, `(subject, topic, year, difficulty)` |

**What already covers Phase 1 schema:**
- `uuid` ← Phase 1 `canonical_id`.
- `source` (CharField) ← Phase 1 `pdf_filename`.
- `page_number` (CharField) ← Phase 1 `page_number` (int).
- `concept_id` ← Phase 1 concept link.
- `ai_explanation`/`ai_mnemonic`/`ai_clinical_pearl` ← Phase 1 enrichment slots.
- `similar_questions` M2M ← Phase 1 "related questions".
- `concept_tags` JSONField ← Phase 1 tags.
- `page_screenshot` ImageField ← Phase 1 primary image, **but only one slot per question**. We need a many-to-many image relationship.
- `is_controversial`, `needs_review`, `is_active` ← Phase 1 quality flags.

**What's missing on Question:**
- **`recall_status`** (recall / coaching_compiled / official_compiled)
- **`confidence_score`** (numeric 0..1)
- **`ocr_confidence`** / **`extraction_confidence`**
- **`question_type`** (single_best / multiple_correct / assertion_reason / image_based / numerical / match)
- **`clinical_category`** (clinical / preclinical / paraclinical)
- **`session`** (jan/jul/may/nov/none) — Year is int, no session field
- **`pdf_sha256`** (link to source PDF provenance)
- **`is_image_based`** bool
- Multi-image support (current model has exactly 1 `page_screenshot` slot)

**Other models in `questions/models.py` we will reuse:**
- `Subject`, `Topic`, `ExamTrack`, `Announcement`
- `QuestionBookmark` (already wired)
- `QuestionFeedback`, `Discussion`, `DiscussionVote`, `Note`, `Flashcard`
- `QuestionAttempt` (unique on `(user, question)`)
- `QuestionImportJob` and `QuestionExtractionItem` (extracted-questions staging)
- `AdminAIPromptVersion`, `QuestionAIOperationLog`, `QuestionRevisionSnapshot`
- `similar_questions` M2M

---

## 3. Existing importers (in `questions/`)

- `QuestionImportJob` (questions/models.py:299-330) — already tracks `pdf`, `csv`, `json`, `word` jobs with `summary`, `error_report`, `created_by`, status, etc. **Reuse for PDF recall import observability.**
- `QuestionExtractionItem` (questions/models.py:333-367) — staging row that links to `Question` via `published_question`. The importer in Phase 1 can write through this table for staged approvals.
- Management commands:
  - `seed_data` — populates `Subject`/`Topic`
  - `analyze_questions`, `check_api_filters` — admin diagnostics

The `extraction_upload`, `extraction_jobs`, `extraction_items`, `extraction_item_approve`, `extraction_item_reject`, `extraction_item_publish`, `extraction_item_autotag` actions in `QuestionViewSet` (questions/views.py:287) are admin-only and already wired. **Phase 2 will route the recall pipeline output through this existing scaffolding.**

---

## 4. Existing knowledge_base app

Already has:
- `KnowledgeSource` whitelist + license catalog
- Connectors for `upsc`, `mohfw-india`, `nhm-india`, `nmc-india`, `icmr`, `ncbi`, `user_uploads`
- BM25 + vector + KG retrieval; Monica service
- Management commands: `load_ontology`, `build_kb`, `ingest_source`, `evaluate_kb`

Phase 2 will **not** touch knowledge_base. The recall pipeline writes into `questions`; `knowledge_base` may later consume `Question.concept_id` for related-PYQ lookup.

---

## 5. Existing AI engine (`backend/ai_engine/`)

- Multi-provider rotation (Groq, Cerebras, Gemini, Cohere, OpenRouter, GitHub Models, HuggingFace, Mistral, NVIDIA Mistral, DeepSeek, Ollama) — documented in `ai_engine/services.py` header.
- RAG pipeline + SQLite TF-IDF fallback (`rag_pipeline.py`, `sqlite_rag.py`).
- `ai_references` JSONField on Question already supports citation lists.
- Phase 2's `enricher.py` (already in `backend/importers/neetpg/`) is the integration point — it can call into `ai_engine.services.ai_complete()` once wired.

---

## 6. Auth + accounts

- `accounts.CustomUser` (already used as `AUTH_USER_MODEL`)
- JWT (SimpleJWT), Supabase auth bridge, `django-axes` brute-force lockout
- Token wallet + device-session tracking (in `accounts/models.py`)
- **DO NOT TOUCH.** Phase 2 integrates by attaching FKs to `settings.AUTH_USER_MODEL` only.

---

## 7. Search

- DRF `search_fields` on `QuestionViewSet` (questions/views.py:124) — `question_text`, `explanation`, `concept_tags`.
- Filterset fields include `year`, `subject`, `topic`, `difficulty`, `exam_type`, `is_verified_by_admin`, `is_scholarship_eligible`, `needs_review`, `is_controversial`.
- **No FTS5 / tsvector / pgvector today.** Phase 2 will add a SQLite FTS5 mirror (Phase 2 ships in-process; Postgres tsvector is the prod upgrade).
- **No full-text index for image OCR text today.** Phase 2 adds it via a new `QuestionImage` table whose text fields can be indexed together.

---

## 8. Bookmarks, attempts, discussions

- `QuestionBookmark` (FK→user, FK→question, unique_together) — already perfect.
- `QuestionAttempt` (FK→user, FK→question, unique_together) — already perfect.
- `Discussion` (FK→question, FK→user, self-FK parent) — already perfect.
- `Note`, `Flashcard` — already perfect.
- **No new code needed here.** Phase 2 only adds `is_recall`-aware filter convenience on the viewset.

---

## 9. Frontend (read-only summary)

- Routes under `frontend/src/app/`: `dashboard`, `questions`, `practice`, `ai-tutor`, `flashcards`, `tests`, `simulator`, `analytics`, `tokens`, plus SEO landing pages (`/cms`, `/neet-pg`, `/ini-cet`, `/fmge`, `/usmle`, …)
- `lib/api.ts`: Axios with Supabase JWT + multi-base failover
- `lib/auth.tsx`: AuthProvider (Supabase-first, Django JWT backup)
- `components/`: UI primitives (`ui/*`), `FormattedText`, `DiscussionThread`, `Sidebar`, `Header`, etc.
- `components/ui/PremiumVideoPlayer.tsx` exists for video delivery
- **Phase 2 does NOT modify frontend.** New optional components (`RecallBadge`, `QuestionImageZoom`) live under `frontend/src/components/recall/` so they're easy to opt into per page.

---

## 10. Image handling today

- `Question.page_screenshot` — single ImageField per question.
- No multi-image model, no zoom component, no image-only revision page.
- `MEDIA_ROOT=media/` is the local sink; production upload to DigitalOcean Spaces is via the existing video_engine pipeline.

**Phase 2 adds:**
- `QuestionImage` (multi-image per question) — see [DATABASE_MIGRATION_PLAN.md](DATABASE_MIGRATION_PLAN.md).
- `RecallImage` (alias on top of `QuestionImage` for recall content) — same table, filter by recall source.
- `frontend/src/components/recall/QuestionImageZoom.tsx` — opt-in.

---

## 11. Caching

- `crack_cms.cache_middleware.DisableApiCacheMiddleware` — prevents accidental API caching.
- `django_q` broker for async tasks.
- **Phase 2 will add per-question caching for the new recall search endpoint** keyed on `(exam_type, year, subject, sha16)` — opt-in, off by default.

---

## 12. Permissions

- `IsControlTowerAdmin` (in `accounts.permissions`) — already gates admin-only actions on the question viewset.
- Phase 2 reuses this for any new admin endpoints.

---

## 13. Admin

- `backend/questions/admin.py` registers `Subject`, `Topic`, `Question`, `QuestionBookmark` only.
- `QuestionExtractionItem`, `QuestionImportJob`, `Discussion`, etc. are NOT registered.
- **Phase 2 will register the new `QuestionImage`, `RecallSource`, `QuestionSource` and the recall-specific jobs so admins can review imports.** It will NOT re-register anything that already has a ModelAdmin.

---

## 14. URL pattern summary

```
admin/                                      admin
api/                                        api root
api/health/                                 health
api/auth/                                   accounts.urls
api/questions/                              questions.urls (subj/topic/feedback/announcement/exam-tracks + QuestionViewSet + flashcards/notes/discussions/chat)
api/tests/                                  tests_engine
api/analytics/                              analytics
api/ai/                                     ai_engine
api/knowledge/                              knowledge_base
api/textbooks/                              textbooks
api/resources/                              resources
api/video/                                  video_engine
api/jobs/                                   jobs
                                            + NEW: api/imports/         (Phase 2)
                                            + NEW: api/recall/          (Phase 2, optional read-only)
```

---

## 15. What already exists vs what's missing

### Already exists (reuse)

| Need | Existing asset |
|---|---|
| Question core fields | `Question` model — text/options/answer/year/subject/topic/difficulty |
| Canonical id | `Question.uuid` (unique UUIDField) |
| Concept linking | `Question.concept_id` + `similar_questions` M2M |
| Bookmarks | `QuestionBookmark` |
| Attempts | `QuestionAttempt` |
| Discussion | `Discussion`, `DiscussionVote` |
| Notes | `Note` |
| Flashcards | `Flashcard` (SM-2 scheduling) |
| Import observability | `QuestionImportJob`, `QuestionExtractionItem` |
| Verification | `is_verified_by_admin`, `verified_by`, `verified_at`, `verified_note` |
| AI explanation slots | `ai_explanation`, `ai_answer`, `ai_mnemonic`, `ai_clinical_pearl`, `ai_references` |
| Admin override / lock | `admin_answer_override`, `lock_answer`, `lock_explanation`, `QuestionRevisionSnapshot` |
| Page screenshot | `Question.page_screenshot` (single, kept) |
| Audit log | `QuestionAIOperationLog` |
| Permissions | `IsControlTowerAdmin` |
| Search endpoint | DRF `QuestionViewSet` with filterset + search |
| Analytics | `analytics/*` |
| AI engine | `ai_engine/*` with provider rotation |

### Missing — Phase 2 adds

| Need | New artefact |
|---|---|
| Multi-image per question | `questions.QuestionImage` (new model, FK to Question) |
| PDF source provenance | `questions.QuestionSource` (FK to Question, FK to RecallSource) |
| PDF manifest + checksum | `questions.RecallSource` (one per source PDF) |
| Recall content flags | `Question` gets `recall_status`, `confidence_score`, `ocr_confidence`, `extraction_confidence`, `question_type`, `clinical_category`, `session`, `is_image_based` |
| Duplicate cluster | `questions.DuplicateCluster` + `questions.DuplicateMember` |
| Image dedup / OCR | per-image pHash, OCR text, caption, modality on `QuestionImage` |
| Admin image review | `QuestionImageAdmin` + source/job admin |
| Import staging | reuse `QuestionExtractionItem` |
| Search by OCR / image caption | `QuestionImage.ocr_text` is FTS-indexed |
| Recall disclaimer banner | Frontend opt-in component `RecallBadge` |
| Phase 2 management commands | `neetpg_import_run`, `neetpg_status`, `neetpg_retry`, `neetpg_dedup`, `neetpg_repair`, `neetpg_report` (extend Phase 1) |
| DB writer for Phase 1 | new module `backend/importers/neetpg/db_writer.py` (Django ORM, gated on user opt-in) |

---

## 16. What we **never** modify

- `accounts/` — auth, JWT, Supabase bridge, devices, tokens
- Any payment / subscription code
- SEO routes and metadata (only add new ones via the standard pattern)
- Frontend `app/` pages (no UI changes in Phase 2)
- Existing migrations — only additive migrations
- `analytics/` — only consumed, not modified
- `ai_engine/` rotation logic — only consumed
- `knowledge_base/` — only consumed (concept cross-links later)
- Existing tests (`questions/tests.py`, etc.) — only extended

---

## 17. What we **extend** (additive only)

- `questions/models.py` — additive fields and new models via a single new migration
- `questions/admin.py` — new `ModelAdmin` registrations (existing classes untouched)
- `questions/views.py` — new action(s) on `QuestionViewSet` (`recall_search`, `images`)
- `questions/serializers.py` — new serializers (additive)
- `questions/urls.py` — keep `path('', include(router.urls))` last; add explicit paths before
- `crack_cms/settings.py` — add `'importers'` to INSTALLED_APPS only if/when we wire the DB writer
- `crack_cms/urls.py` — one new line for `api/imports/` (or use existing `api/jobs/`)

---

## 18. Open questions for the user

None blocking. The schema gaps above are exactly what Phase 2 will close. Existing tests are green; no destructive change is proposed.