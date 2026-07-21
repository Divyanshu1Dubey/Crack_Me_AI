# Folder Structure

> A guided tour of every important folder in the repository — purpose, responsibilities, dependencies, and key files.

---

## Repository Root

| Path | Purpose |
|---|---|
| `README.md` | User-facing setup, API reference, deployment guide |
| `CLAUDE.md` | Claude Code orientation (commands + conventions + gotchas) |
| `docs/` | **Single source of truth** for all documentation (this folder) |
| `docs/INDEX.md` | Master documentation index |
| `docs/audit/` | Documentation audits |
| `.github/` | GitHub Actions workflows, Copilot rules, agent/skill definitions |
| `.cursor/`, `.vscode/`, `.idea/`, `.junie/`, `.windsurf/` | IDE-specific configs |
| `.venv/`, `backend/.venv/`, `backend/venv/` | Python virtual environments |
| `frontend/`, `backend/`, `mobile-app/` | The three deployable units |
| `scripts/` | Root-level utility scripts |
| `data_dump*.json`, `data_versions/` | Periodic DB dumps (versioning aid) |
| `seed_jobs.py`, `fix_db.py`, `check_qs.py`, `split_dump.py` | One-off DB utilities |
| `google_apps_script.js` | Sheet-driven content review scripts |
| `supabase_rescue_plan.md` | Auth migration notes |

---

## `backend/` — Django 5 Backend

```
backend/
├── manage.py
├── requirements.txt
├── build.sh                       # Render deploy contract
├── Procfile
├── .env / .env.example            # Environment templates
├── db.sqlite3                     # Committed via Git LFS
├── questions_fixture.json         # Production seed
│
├── crack_cms/                     # Django project root (settings, URLs, WSGI/ASGI)
├── accounts/                      # Users, JWT, tokens, devices
├── questions/                     # MCQ bank, flashcards, notes
├── tests_engine/                  # Adaptive + PYQ tests
├── analytics/                     # Stats, streaks, badges
├── ai_engine/                     # 11-provider AI + RAG
├── textbooks/                     # Indexed textbook library
├── resources/                     # UPSC resource catalog
├── video_engine/                  # TTS + moviepy slides
├── jobs/                          # Career / job listings
│
├── chroma_db/                     # rag_store.sqlite3 (TF-IDF vectors)
├── Medura_Train/                  # RAG source documents
│
├── scripts/                       # Backend-local utilities
├── scratch/                       # Throwaway workspace (git-ignored)
├── pyq/                           # Legacy PYQ dumps
│
└── data_dump*.json, ...           # Version snapshots
```

### `backend/crack_cms/`

**Purpose**: Django project root — global settings, root URL routing, WSGI/ASGI entrypoints.

| File | Role |
|---|---|
| `settings.py` | Loads `.env`, configures Sentry, app registry, middleware, CORS, JWT, AI env keys |
| `urls.py` | Routes `/api/{auth,questions,tests,analytics,ai,textbooks,resources,video,jobs}/` + admin + health |
| `wsgi.py`, `asgi.py` | WSGI/ASGI entrypoints (gunicorn / async) |
| `cache_middleware.py` | Custom caching middleware |
| `startup.py` | App-startup hooks |
| `management/` | Custom Django management commands |

**Depends on**: all installed apps, `python-dotenv`, `dj_database_url`, `sentry-sdk`.

---

### `backend/accounts/`

**Purpose**: Identity, auth, token economy, devices, subscriptions, payments.

| File | Role |
|---|---|
| `models.py` | `CustomUser`, `TokenBalance`, `TokenConfig`, `TokenTransaction`, `AdminAuditLog`, `PaymentAttempt`, `Subscription`, `UserDevice` |
| `views.py` | All auth endpoints (register, login, profile, password reset, devices, tokens, admin lifecycle) |
| `serializers.py` | DRF serializers for user/token/device/admin payloads |
| `supabase_auth.py`, `supabase_rest_auth.py` | Supabase token validation + identity bridge |
| `middleware.py` | Request-side user/device resolution |
| `permissions.py` | DRF custom permissions |
| `urls.py` | All `/api/auth/*` routes |
| `admin.py` | Django admin registrations |
| `tests.py` | Auth-flow unit tests |
| `management/` | Custom commands |

**Depends on**: `rest_framework`, `rest_framework_simplejwt`, `django-axes`, `razorpay`, `supabase`.

---

### `backend/questions/`

**Purpose**: The MCQ bank — questions, bookmarks, flashcards (SM-2), discussions, notes, AI extraction pipeline.

| File | Role |
|---|---|
| `models.py` | `ExamTrack`, `Subject`, `Topic`, `Question`, `QuestionImportJob`, `QuestionBookmark`, `QuestionFeedback`, `Discussion`, `DiscussionVote`, `Note`, `Flashcard`, `QuestionAttempt`, `Announcement` |
| `views.py` | Question CRUD + filters, bookmark, flashcard SM-2 review, notes, discussions, chat assistant |
| `serializers.py` | DRF serializers |
| `urls.py` | `/api/questions/*` (explicit paths before router) |
| `admin.py` | Django admin for question bank curation |
| `tasks.py` | Async enrichment tasks (django-q2) |
| `middleware.py` | Per-request hooks (e.g., token pre-check) |
| `tests.py` | Question-bank unit tests |
| `management/` | Import / export / validation commands |

**Depends on**: `ai_engine` (for enrichment), `django-filter`, `rest_framework`.

---

### `backend/tests_engine/`

**Purpose**: Adaptive tests, PYQ simulator, attempt tracking.

| File | Role |
|---|---|
| `models.py` | `Test`, `TestAttempt`, `QuestionResponse` |
| `views.py` | `TestViewSet`, `TestAttemptViewSet` |
| `urls.py` | `/api/tests/*` router |
| `serializers.py`, `admin.py` | Standard |

**Depends on**: `questions` (FK to `Question`), `accounts` (FK to `CustomUser`).

---

### `backend/analytics/`

**Purpose**: Dashboard stats, weak-topic detection, streaks, badges, leaderboards, feedback, campaigns.

| File | Role |
|---|---|
| `models.py` | `UserTopicPerformance`, `DailyActivity`, `Feedback`, `Announcement`, `StudyStreak`, `Badge`, `UserBadge` |
| `views.py` | Dashboard, weak topics, heatmap, score prediction, feedback CRUD, contact, streak, badges, leaderboard, admin campaigns |
| `urls.py` | `/api/analytics/*` |
| `serializers.py`, `admin.py` | Standard |

**Depends on**: `questions` (attempts/topic linkage), `accounts`.

---

### `backend/ai_engine/`

**Purpose**: 11-provider AI orchestration + RAG over textbook chunks.

| File | Role |
|---|---|
| `services.py` | `EnhancedAIService` — round-robin orchestration, quota notes, error filtering |
| `rag_pipeline.py` | `RAGPipeline` class — ingest, chunk, retrieve, ground |
| `sqlite_rag.py` | TF-IDF engine over SQLite (`chunks` + `idf_cache` tables) |
| `document_processor.py` | PDF/MD/TXT extractors (PyMuPDF) |
| `pyq_extractor.py` | Prior-year-question PDF extractor |
| `auto_ingest.py` | Auto-ingest new files into RAG |
| `similar_questions.py` | Find similar questions via TF-IDF |
| `upsc_cms_knowledge.py` | Bundled UPSC CMS static knowledge |
| `views.py` | All `/api/ai/*` endpoints |
| `urls.py` | `/api/ai/*` |
| `models.py` | `ChatSession`, `ChatMessage`, `AIFeedback` |
| `serializers.py`, `admin.py` | Standard |
| `management/` | Custom AI commands |

**Depends on**: `google-generativeai`, `groq`, `openai`, `cerebras-cloud-sdk`, `cohere`, `together`, `PyMuPDF`; reads `backend/Medura_Train/`; writes `backend/chroma_db/rag_store.sqlite3`.

---

### `backend/textbooks/`

**Purpose**: Indexed textbook library + PDF uploads.

| File | Role |
|---|---|
| `models.py` | Textbook + chapter + upload models |
| `views.py` | `TextbookViewSet`, `PDFUploadViewSet` |
| `urls.py` | `/api/textbooks/{books,uploads}/` |
| `serializers.py`, `admin.py` | Standard |

**Depends on**: `ai_engine` (for indexing), `Pillow`, `PyMuPDF`.

---

### `backend/resources/`

**Purpose**: UPSC resource catalog + exam guide.

| File | Role |
|---|---|
| `views.py` | `ResourceCatalogView`, `ResourceDownloadView`, `ExamGuideView` |
| `urls.py` | `/api/resources/{catalog,download/<id>,exam-guide}/` |
| `tests.py` | Resource tests |

---

### `backend/video_engine/`

**Purpose**: Video generation pipeline (edge-tts narration + moviepy slide compilation).

| File | Role |
|---|---|
| `services.py` | TTS + video orchestration |
| `slide_renderer.py` | Slide image rendering |
| `tasks.py` | Async video jobs (django-q2) |
| `views.py`, `urls.py`, `admin.py` | Scaffolding |
| `tests.py` | Pipeline tests |
| `management/` | Custom commands |

**Depends on**: `edge-tts`, `moviepy`, `Pillow`, `django-q2`.

---

### `backend/jobs/`

**Purpose**: Career / job listings (medical officer positions).

| File | Role |
|---|---|
| `models.py` | `JobCategory`, `Job`, `JobBookmark` |
| `views.py` | `JobViewSet`, `JobCategoryViewSet` |
| `urls.py` | `/api/jobs/*` |
| `serializers.py`, `admin.py` | Standard |

**Depends on**: `accounts` (FK to `CustomUser`).

---

### `backend/chroma_db/`

**Purpose**: TF-IDF RAG index store.

| File | Role |
|---|---|
| `rag_store.sqlite3` | Chunks table + IDF cache (committed via Git LFS) |

> The directory name `chroma_db` is historical — the actual implementation is **SQLite + TF-IDF** (`ai_engine/sqlite_rag.py`), not ChromaDB.

---

### `backend/Medura_Train/`

**Purpose**: Source-of-truth document corpus for RAG ingestion.

| Subfolder | Content |
|---|---|
| `textbooks/` | Standard medical textbooks (PDF/MD/TXT) |
| `PYQ/` | Prior-year UPSC CMS papers |
| `web_knowledge/` | Web-scraped CMS articles (.md, .txt) |

**Consumed by**: `_train_all.py`, `KnowledgeScanView`, `KnowledgeUploadView`, `auto_ingest.py`. PDFs >50 MB auto-skipped — use `.md` summaries.

---

### `backend/scripts/` & `backend/management/`

Custom Python utilities and Django management commands for one-shot operations:
- `_train_all.py`, `enrich_turbo.py`, `_export_fixture.py`, `_review_and_fix_answers.py`
- `validate_questions.py`, `check_db.py`, `load_chunks.py`, `split_dump.py`
- `fetch_qs.py`, `fix_qs.py`, `seed_jobs.py`, `test_all.py`, `test_api_keys.py`

---

## `frontend/` — Next.js 16 Frontend

```
frontend/
├── package.json
├── next.config.ts
├── vercel.json
├── middleware.ts
├── tsconfig.json
├── eslint.config.mjs
├── playwright.config.ts
├── sentry.client.config.ts
│
├── public/                        # Static assets (icons, images)
├── icons/                         # Icon manifest source files
├── scripts/                       # Icon download scripts
│
├── src/
│   ├── app/                       # Next.js App Router pages
│   ├── components/                # React components (UI + features)
│   ├── context/                   # React contexts (DockContext, …)
│   ├── lib/                       # api.ts, auth.tsx, supabase.ts, seo.ts, utils.ts
│   └── utils/                     # Utility helpers
│
├── tests/                         # Playwright E2E tests
│
└── .env.local, .env.supabase.local.example
```

### `frontend/src/app/` — Route Map

| Route | Purpose |
|---|---|
| `/` | Landing — hero, features, CTAs |
| `/login`, `/register`, `/forgot-password`, `/reset-password` | Auth |
| `/dashboard` | Stats, streaks, quick actions |
| `/questions` | Question bank (filters, keyboard nav A-D/N/P) |
| `/ai-tutor` | Multi-mode AI chat |
| `/flashcards` | SM-2 flashcards |
| `/tests`, `/tests/[id]`, `/simulator` | Adaptive test list / session / PYQ simulator |
| `/generate` | AI question generator |
| `/analytics`, `/trends`, `/roadmap` | Performance, trends, study plan |
| `/bookmarks`, `/textbooks`, `/resources`, `/upload` | Saved/library/upload |
| `/tokens`, `/subscription` | Wallet + Razorpay |
| `/settings`, `/leaderboard` | Profile, global ranking |
| `/jobs`, `/feedback`, `/contact` | Career, feedback, contact |
| `/admin`, `/exams` | Admin dashboard, exam tracks |
| `layout.tsx`, `loading.tsx`, `globals.css`, `robots.ts`, `sitemap.ts` | App shell + SEO |

### `frontend/src/lib/`

| File | Role |
|---|---|
| `api.ts` | Centralized Axios client (auth, failover, session tracking) |
| `auth.tsx` | `AuthProvider` React context |
| `supabase.ts` | Supabase browser client + refresh helpers |
| `seo.ts` | Brand/metadata constants |
| `utils.ts` | Generic utilities |

---

## `mobile-app/`

Companion mobile project (separate code base). Consult `mobile-app/` directly for layout details — its structure is independent of `frontend/` and `backend/`.

---

## `.github/` (CI + Copilot + Skills)

| Path | Role |
|---|---|
| `workflows/ci.yml` | GitHub Actions: backend tests + frontend build + security scan |
| `copilot-instructions.md` | Working rules for Copilot |
| `dependabot.yml` | Dependency update automation |
| `agents/` | Custom agent definitions |
| `skills/` | Custom skill definitions |

---

## `docs/` (this folder — single source of truth)

| File | Role |
|---|---|
| `INDEX.md` | Master documentation index |
| `PROJECT_OVERVIEW.md` | Vision, users, stack, integrations, repo layout |
| `ARCHITECTURE.md` | System architecture with mermaid diagrams |
| `FOLDER_STRUCTURE.md` | This document |
| `DATA_MODEL.md` | Every model + FK + index + business rule |
| `API_REFERENCE.md` | Every endpoint |
| `AUTHENTICATION.md` | JWT/session/refresh/roles/protected routes |
| `ADMIN_SYSTEM.md` | Admin dashboard, APIs, moderation |
| `SECURITY_AUDIT.md` | Security audit |
| `PERFORMANCE.md` | Performance audit |
| `SEO.md` | SEO audit |
| `SCALING_ROADMAP.md` | Scaling plan |
| `CODE_QUALITY.md` | Code smells + debt score |
| `IMPROVEMENTS.md` | Top 100 improvements |
| `AI_ASSISTANT_RULES.md` | Permanent AI-assistant rules |
| `FEATURES.md` | Per-feature reference |
| `setup/`, `guides/`, `reference/`, `reports/`, `audit/` | Operational + audit subfolders |
