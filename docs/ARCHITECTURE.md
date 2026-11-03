# Architecture

> Complete system architecture for CrackCMS — frontend, backend, AI, auth, deployment, database, and data flow.

---

## 1. System Overview

CrackCMS is a **two-tier server-rendered SPA** with an externalized AI tier. The browser hits the Next.js frontend (Vercel), which proxies authenticated calls to the Django REST backend (Render / DigitalOcean). The backend fans out to a **round-robin AI provider pool**, a **SQLite TF-IDF RAG store**, and managed services (Supabase, Sentry, Datadog, Razorpay, Gmail SMTP).

```mermaid
flowchart LR
    Browser([End User — Browser / Mobile])
    Vercel[Next.js 16 Frontend\nVercel CDN]
    Render[Django 5 + DRF\nRender / DigitalOcean]
    SQLite[(SQLite — App DB)]
    RAG[(chroma_db/rag_store.sqlite3\nTF-IDF chunks)]
    SUpabase[(Supabase Auth + DB)]
    Sentry[[Sentry]]
    DD[[Datadog RUM]]
    Razorpay[[Razorpay]]
    SMTP[[Gmail SMTP]]
    AI{Round-Robin\n10 rotation entries}

    Browser <--> Vercel
    Vercel -->|REST + JWT| Render
    Render --> SQLite
    Render --> RAG
    Render <--> SUpabase
    Render --> AI
    Vercel --> DD
    Render --> Sentry
    Render --> Razorpay
    Render --> SMTP
```

---

## 2. Frontend Architecture

The frontend is a Next.js **App Router** project (`src/app/`) with React Server + Client Components.

```mermaid
flowchart TD
    Layout[src/app/layout.tsx\nRootLayout — Fonts, Providers]
    Providers[Providers:\nAuthProvider, ThemeProvider,\nDockProvider, ExamTrackProvider,\nTooltipProvider, PWAProvider]
    Pages[Route Pages:\n/dashboard, /questions, /ai-tutor,\n/flashcards, /tests, /simulator,\n/analytics, /roadmap, /tokens, /admin, ...]
    Comp[Components:\nUI primitives + feature components]
    Lib[Lib:\napi.ts Axios client,\nauth.tsx, supabase.ts, seo.ts]
    SEO[SEO:\nrobots.ts, sitemap.ts, layout metadata]

    Layout --> Providers --> Pages
    Pages --> Comp
    Pages --> Lib
    Lib -->|Axios + Supabase JWT| Backend[(Django REST API)]
    SEO -.-> Pages
```

### Key Frontend Modules

| Module | Path | Responsibility |
|---|---|---|
| API Client | `frontend/src/lib/api.ts` | Axios instance, base-URL failover, Supabase JWT + `X-Session-ID` injection, sign-out on session-ending codes (`account_blocked`, `device_inactive`, `account_link_required`, ...), `/settings?deviceLimit=1` on `device_limit_reached` |
| Auth Context | `frontend/src/lib/auth.tsx` | `AuthProvider`, `useAuth`; the user (and admin role) comes from the backend profile |
| Supabase Client | `frontend/src/lib/supabase.ts` | Browser-side Supabase session helpers, refresh-token error detection |
| SEO | `frontend/src/lib/seo.ts` | Brand constants, OG image defaults, metadata helpers |
| UI Primitives | `frontend/src/components/ui/*` | Radix-wrapped buttons, dialogs, dropdowns, tabs, tooltips |
| Layout | `frontend/src/app/layout.tsx` | Root providers, fonts, Datadog init, watermark, GA |

### Frontend Configuration

- `frontend/next.config.ts` — sets `outputFileTracingRoot` to repo root.
- `frontend/vercel.json` — security headers: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`.
- `frontend/middleware.ts` — middleware for route protection / rewrites.
- `frontend/sentry.client.config.ts` — Sentry browser init.

---

## 3. Backend Architecture

The backend is Django 5 with a clear **app-per-bounded-context** split.

```mermaid
flowchart TB
    subgraph Django[Django 5 — backend/]
        Root[crack_cms/\nsettings, urls, wsgi]
        Accounts[accounts/\nUsers, JWT, Tokens]
        Questions[questions/\nMCQs, Flashcards, Notes]
        Tests[tests_engine/\nAdaptive + PYQ Tests]
        Analytics[analytics/\nStats, Streaks, Roadmap]
        AI[ai_engine/\n11-Provider AI + RAG]
        Textbooks[textbooks/\nIndexed Library]
        Resources[resources/\nUPSC Resources]
        Video[video_engine/\nedge-tts + moviepy]
        Jobs[jobs/\nCareer Listings]
        Q[django-q2\nAsync Tasks]
    end

    Root --> Accounts & Questions & Tests & Analytics & AI & Textbooks & Resources & Video & Jobs
    Accounts -.-> Q
    Questions -.-> Q
    Video -.-> Q
    AI -.-> Q
```

### App Responsibilities

| App | Models | Endpoints | Purpose |
|---|---|---|---|
| `accounts` | `CustomUser`, `TokenBalance`, `TokenConfig`, `TokenTransaction`, `AdminAuditLog`, `PaymentAttempt`, `Subscription`, `UserDevice` | `/api/auth/*` | Users, JWT, token wallet, devices, subscriptions, payments |
| `questions` | `ExamTrack`, `Subject`, `Topic`, `Question`, `QuestionImportJob`, `QuestionBookmark`, `QuestionFeedback`, `Discussion`, `Note`, `Flashcard`, `QuestionAttempt`, `Announcement` | `/api/questions/*` | MCQ bank, flashcards (SM-2), notes, discussions, bookmarks, chat assistant |
| `tests_engine` | `Test`, `TestAttempt`, `QuestionResponse` | `/api/tests/*` | Adaptive tests, PYQ simulator, attempt submission/review |
| `analytics` | `UserTopicPerformance`, `DailyActivity`, `Feedback`, `Announcement`, `StudyStreak`, `Badge`, `UserBadge` | `/api/analytics/*` | Dashboard, weak-topic detection, streaks, badges, leaderboard, campaigns |
| `ai_engine` | `ChatSession`, `ChatMessage`, `AIFeedback` | `/api/ai/*` | AI tutor, RAG, knowledge ingestion, study plan, high-yield topics |
| `textbooks` | textbook + upload models | `/api/textbooks/books/`, `/uploads/` | Textbook library + PDF uploads |
| `resources` | — | `/api/resources/catalog/`, `/download/<id>/`, `/exam-guide/` | UPSC resource catalog + exam guide |
| `video_engine` | — | (app skeleton) | Video generation pipeline |
| `jobs` | `JobCategory`, `Job`, `JobBookmark` | `/api/jobs/*` | Career / job listings |

### Middleware Stack (verified from `crack_cms/settings.py` lines 100–113)

Order (top → bottom):

1. `SecurityMiddleware`
2. `WhiteNoiseMiddleware` (serves static files)
3. `corsheaders.middleware.CorsMiddleware`
4. `SessionMiddleware`
5. `CommonMiddleware`
6. `CsrfViewMiddleware`
7. `AuthenticationMiddleware`
8. `MessageMiddleware`
9. `XFrameOptionsMiddleware` (deny)
10. `axes.middleware.AxesMiddleware` (brute-force)
11. **`questions.middleware.RateLimitMiddleware`** (questions-app rate limiting)
12. **`crack_cms.cache_middleware.DisableApiCacheMiddleware`** (disables client-side caching on API responses)
13. **`accounts.middleware.UpdateLastSeenMiddleware`** (updates `CustomUser.last_seen`)

---

## 4. AI Architecture

### 4.1 Round-Robin Orchestrator

```mermaid
flowchart LR
    Request[AI Request\nfrom views.py] --> Counter[Round-Robin Counter\n_call_counter % 10]
    Counter --> P0[1 OmniRoute]
    Counter --> P1[2 Groq\nllama-3.3-70b-versatile]
    Counter --> P2[3 Cerebras\ngemma-4-31b]
    Counter --> P3[4 Gemini x2 models]
    Counter --> P4[5 Cohere\ncommand-a-03-2025]
    Counter --> P5[6 OpenRouter\n4 free models]
    Counter --> P6[7 GitHub Models\ngpt-4o-mini]
    Counter --> P7[8 HuggingFace\nvia Novita router]
    Counter --> P8[9 Mistral\nmistral-small-latest]
    Counter --> P9[10 OpenRouter2\n2 free models]
    P0 -.fail/timeout.-> P1
    P1 -.fail.-> P2
    P2 -.fail.-> P3
    P3 -.fail.-> P4
    P4 -.fail.-> P5
    P5 -.fail.-> P6
    P6 -.fail.-> P7
    P7 -.fail.-> P8
    P8 -.fail.-> P9
    P9 -.fail/timeout.-> Fallback[AIUnavailable:\nrefund + offline answer\nor 503 ai_unavailable]
```

**Verified from `backend/ai_engine/services.py`**:
- `_call_ai()` rotation list has **10 entries** (OmniRoute first); a global counter picks the starting provider
- **Per-call deadline**: `AI_CALL_DEADLINE_SECONDS` (default 90 s) and `AI_CALL_MAX_ATTEMPTS`; each attempt's SDK timeout is cut to what is left of the deadline
- **`NVIDIA Mistral` is initialised but NOT in the rotation**; DeepSeek and Ollama are not implemented
- When every provider fails, `_call_ai()` raises `AIUnavailable`; views refund tokens / free slots and answer with an offline extract or `503 {code: 'ai_unavailable'}`. `AI_OFFLINE_MODE=1` makes no external call at all.
- `_PROVIDER_ERROR_PHRASES` filter prevents provider-internal error strings from reaching users
- Per-provider self-disable: if a provider returns 401/403, `self.<provider> = None` to skip it for the rest of the session
- **RAG is on by default**; only `DISABLE_RAG=1` or `DISABLE_RAG_IN_PRODUCTION=1` turn it off (there is no `DEBUG` gate)

### 4.2 RAG Pipeline

```mermaid
flowchart LR
    Sources[Medura_Train/\ntextbooks, PYQ, web_knowledge] --> Ingest[Train Pipeline\nmanage.py train_ai]
    Ingest --> Chunk[Chunk\n~200-500 tok]
    Chunk --> TFIDF[(SQLite\nchunks + idf_cache)]
    Query[User Query] --> Tokenize[TF-IDF Tokenize]
    Tokenize --> TopK[Top-K\ncosine similarity]
    TFIDF --> TopK
    TopK --> Context[Context Injection]
    Context --> Prompt[System Prompt +\nCMS-specific grounding]
    Prompt --> AIProviders[AI Provider]
    AIProviders --> Answer[RAG Answer\nwith citations]
```

**Implementation**: `backend/ai_engine/rag_pipeline.py` + `backend/ai_engine/sqlite_rag.py`; retrieval is BM25 over the whole store from an in-memory index (`ai_engine/lexical_index.py`, see [`audit/RAG_BENCHMARK.md`](./audit/RAG_BENCHMARK.md)). Set `DISABLE_RAG=1` to skip on memory-constrained hosts. There is no automatic PDF size limit.

### 4.3 AI Endpoints (`/api/ai/`)

| Method | Path | Purpose |
|---|---|---|
| POST | `/tutor/` | RAG-enhanced chat tutoring |
| POST | `/explain/` | Concept explainer at adjustable depth |
| POST | `/mnemonic/` | Generate mnemonic for a topic |
| POST | `/analyze/` | Analyze a question's structure |
| POST | `/explain-answer/` | Explain after user answers (rich JSON) |
| POST | `/rag-search/` | RAG top-K chunks (no LLM) |
| POST | `/rag-answer/` | RAG-grounded answer with citations |
| POST | `/textbook-reference/` | Get textbook reference for a question |
| GET | `/screenshot/<question_id>/` | Cited textbook page as JSON `{screenshot_url}` (`202` while rendering, `402` when the caller may not see the answer, `404` when no page exists); the render is a MEDIA file (`Question.page_screenshot`), see §7 |
| POST | `/study-plan/` | Personalized study roadmap |
| GET | `/high-yield/` | High-yield topics list |
| POST | `/generate-questions/` | AI-generated MCQs |
| POST | `/knowledge/upload/` | Upload a single file |
| POST | `/knowledge/scan/` | Scan & reindex training folders |
| GET | `/knowledge/stats/` | Knowledge-base stats |
| GET | `/status/` | Per-provider health |
| GET | `/test/` | Smoke test |
| CRUD | `/chat/sessions/`, `/chat/sessions/<id>/messages/` | Chat history |
| POST | `/feedback/` | Submit AI feedback (+2 tokens reward on verify) |

---

## 5. Authentication Flow

CrackCMS signs users in with **Supabase Auth**. The frontend attaches the Supabase access token and the `X-Session-ID` device id; the backend links the identity to a `CustomUser` by `supabase_uid` and enforces the 2 / 4 device limit. Django JWTs are used only by the dev-only local auth (`LOCAL_DEV_AUTH`, `DEBUG=True`).

```mermaid
sequenceDiagram
    participant U as User Browser
    participant FE as Next.js Frontend
    participant SB as Supabase Auth
    participant API as Django REST API
    participant DB as SQLite

    U->>FE: Click Login
    FE->>SB: signInWithPassword(email, pwd)
    SB-->>FE: access_token + refresh_token (HTTP-only cookie)
    U->>FE: Make authenticated request
    FE->>FE: api.ts interceptor reads Supabase session
    FE->>API: Authorization: Bearer <supabase_token>
    API->>API: SupabaseJWTAuthentication validates token (Supabase /auth/v1/user)
    API->>DB: Resolve CustomUser by supabase_uid, check device limit
    DB-->>API: user row
    API-->>FE: 200 OK + payload
    Note over FE,API: account_blocked / device_inactive / account_link_required → clear local session + /login?authError=… · device_limit_reached → /settings?deviceLimit=1
```

See [`AUTHENTICATION.md`](./AUTHENTICATION.md) for the full auth spec (JWT, refresh, roles, protected routes).

---

## 6. Authorization Flow

Three role tiers:

| Role | Privileges |
|---|---|
| **Anonymous** | Public landing, register/login pages |
| **Student (default)** | Question bank, AI tutor, flashcards, tests, analytics — all token-metered |
| **Staff / Superuser** | Django admin, admin token grant/transfer, system reset, weak-area control, campaigns, backups |

**Enforcement points**:
- DRF permissions (`accounts/permissions.py` `IsControlTowerAdmin`, per-view `IsAdminUser` / `IsAuthenticated`).
- Django Admin (`/admin/`) requires `is_staff`.
- REST admin endpoints (`/api/auth/admin/*`, `/api/auth/tokens/admin/*`, `/api/analytics/admin/*`, `/api/imports/*`, `/api/ingestion/*`) require `IsControlTowerAdmin`: `role='admin'` or `is_superuser`.
- The frontend's `/admin` pages decide access from the backend profile (`role` / `is_admin`), never from Supabase `user_metadata`.
- Token-metered AI features check balance in middleware/service layer before provider call.

See [`ADMIN_SYSTEM.md`](./ADMIN_SYSTEM.md) for the admin permission matrix.

---

## 7. Deployment Architecture

```mermaid
flowchart LR
    Dev[Developer] -->|git push| GH[GitHub main]
    GH -->|trigger| GHA[GitHub Actions\nCI: lint, test, build, bandit, safety]
    GHA -->|on success| DO[DigitalOcean App Service\nbackend]
    GHA -->|on success| Vercel[Vercel\nfrontend]
    DO -->|gunicorn + whitenoise| LiveAPI[crackcms-vsthc.ondigitalocean.app/api]
    Vercel -->|Next.js| LiveFE[cracklabs.app]
    User([End User]) --> LiveFE
    LiveFE --> LiveAPI
    LiveAPI --> Supa[(Supabase)]
    LiveAPI --> Sentry
    LiveAPI --> Razorpay
```

### Backend Deploy (DigitalOcean App Platform; Render is legacy)

- **Build** (`backend/build.sh`, the deploy contract): `pip install` → `collectstatic` → `migrate` (also (re)creates the django-q schedules: the daily renewal-reminder schedule and the `ingestion_recover_stale_jobs` sweeper, every 10 min) → `link_supabase_identity --all-privileged` (**dry-run report only**) → `seed_question_bank` (loads `fixtures/cms_fixture.json` only while the CMS bank is empty; a live bank is never overwritten) → `seed_blogs` → create `MEDIA_ROOT/recall_images` → `load_ontology` → `ingest_source internal-notes` → embedding backfill → optional KB network ingest (`KB_INGEST_NETWORK=1`) → optional AI backfill (`BACKFILL_AI_ON_DEPLOY=1`) → `relink_fixture_images --apply`. It no longer runs `import_neet_pg` (that used to delete every NEET PG question and its user history on each build) and never runs destructive data commands.
- **Process types** (`backend/Procfile`): `release: python manage.py migrate --no-input`, `web: gunicorn crack_cms.wsgi:application --bind 0.0.0.0:$PORT --workers 3 --threads 4 --timeout 120`, `worker: python manage.py qcluster`.
- **Worker**: background jobs (ingestion / recall imports, video generation), the renewal-reminder schedule and the stale-job sweeper run only while a django-q worker is up. DigitalOcean App Platform does not start a Procfile worker (or run `release`) on its own: add a **Worker component** with run command `python manage.py qcluster` and the web component's environment, or queued jobs stay queued and no reminder is sent.
- **Media**: Django serves `/media/` only with `DEBUG=True` (`crack_cms/urls.py`). Question images go through `GET /api/questions/images/<id>/serve/`, but files linked by MEDIA URL, such as the textbook page screenshots (`Question.page_screenshot`, returned by `/api/ai/screenshot/<id>/`), are reachable in production only if the platform serves `MEDIA_ROOT` at `/media/` (or the storage is moved to a bucket). Container disk is wiped on redeploy.
- **Required env**: `DJANGO_SECRET_KEY`, AI keys, `CORS_ALLOWED_ORIGINS=https://cracklabs.app`, `CSRF_TRUSTED_ORIGINS=…`, `FRONTEND_URL`, `SUPABASE_URL` + `SUPABASE_ANON_KEY` (and `SUPABASE_SERVICE_ROLE_KEY` for admin tooling), `SUPABASE_EMAIL_CONFIRMATION_ENABLED=true` once Supabase "Confirm email" and "Secure email change" are on, `CORE_DATA_BACKUP_PATH` (persistent volume), `NUM_PROXIES` / `TRUSTED_CLIENT_IP_HEADER`. `manage.py check --deploy` reports the missing auth/backup settings as `accounts.W001`–`W003` (see [`AUTHENTICATION.md`](./AUTHENTICATION.md) §4.2).

**One-time operator steps** (never run by `build.sh`):
1. After deploying `accounts.0023`: `python manage.py link_supabase_identity --all-privileged` (dry run), review, then `--all-privileged --apply` ([`AUTHENTICATION.md`](./AUTHENTICATION.md) §4.1).
2. Once per database that ever ran the old `import_neet_pg` deploy step: `python manage.py import_neet_pg --replace --dry-run`, review the counts, then `python manage.py import_neet_pg --replace` (repairs the 2025 rows, hides the 2020 paper that has no answer key; admin-edited rows are skipped).
3. Once per database from releases before the `seed_data` fix: `python manage.py cleanup_seed_samples` (dry run), then `--apply` (moves the 15 demo questions stored as 2019–2023 UPSC CMS PYQs to year 0).
4. Client IP: as an admin, `GET /api/health/client-ip/` on the deployed site shows which address headers reach Django, the `peer` and whether the edge header was read. On Railway behind Cloudflare set `TRUSTED_CLIENT_IP_HEADER=CF-Connecting-IP`; once that endpoint shows a Cloudflare address as the right-most `X-Forwarded-For` entry, also set `NUM_PROXIES=1` and `TRUSTED_CLIENT_IP_HEADER_FROM=cloudflare` (opt-in): the header is then only read when the hop Railway appended is a Cloudflare address, so the `*.up.railway.app` hostname cannot be used to forge it (`crack_cms/client_ip.py`; [`DEPLOY_RAILWAY.md`](./DEPLOY_RAILWAY.md) §2). Check that a forged header sent to the platform hostname does not change `client_ip`.
5. Optional: `python manage.py ingestion_run_pending` after a worker outage (it runs the stale-job recovery pass first, then dispatches queued jobs that have no task); the scheduled sweeper already covers stalled jobs while the worker runs.

### Frontend Deploy (Vercel)

- **Framework**: Next.js (auto-detected)
- **Config**: `frontend/vercel.json` (security headers + rewrites)
- **Required env**: `NEXT_PUBLIC_API_URL=https://crackcms-vsthc.ondigitalocean.app/api` (DigitalOcean is the default production API; Render is flagged unhealthy in `api.ts`), Supabase keys

### CI Pipeline (`.github/workflows/ci.yml`)

Runs on push to `main`/`develop` and PRs to `main`:

1. **Backend** (Python 3.12): `pip install` → `manage.py check --deploy` → `makemigrations --check` → `manage.py test --verbosity=2`
2. **Frontend** (Node 20): `npm ci` → `npm run lint` → `npm audit --audit-level=high` → `npm run build`
3. **Frontend unit** (Node 22, `check-latest`): `npm ci` → `npm run test:unit` (`node --test` runs the TypeScript tests directly; needs Node ≥ 22.18)
4. **Secret scan** (blocking): `python scripts/scan_secrets.py --all-tracked` (credentials and personal-data dumps in any tracked file)
5. **Security**: Bandit report (`bandit -r backend/ -x '*/migrations/*,*/__pycache__/*' --skip B101 -f json`, never fails) + Bandit gate (`... --skip B101 -lll -iii`: fails on any high-severity, high-confidence finding; there is no baseline, non-security hashes pass usedforsecurity=False) + `safety check -r backend/requirements.txt` (non-blocking)

### Pre-commit Hook (`.pre-commit-config.yaml`)

- Local `secret-scan` hook → `python scripts/scan_secrets.py`

---

## 8. Database Architecture

### Primary DB — `backend/db.sqlite3` (committed via Git LFS)

Django app tables (see [`DATA_MODEL.md`](./DATA_MODEL.md) for every model + FK + index):

| App | Core Tables |
|---|---|
| `accounts` | `accounts_customuser`, `accounts_tokenbalance`, `accounts_tokenconfig`, `accounts_tokentransaction`, `accounts_adminauditlog`, `accounts_paymentattempt`, `accounts_subscription`, `accounts_userdevice` |
| `questions` | `questions_examtrack`, `questions_subject`, `questions_topic`, `questions_question`, `questions_questionimportjob`, `questions_questionbookmark`, `questions_questionfeedback`, `questions_discussion`, `questions_discussionvote`, `questions_note`, `questions_flashcard`, `questions_questionattempt`, `questions_announcement` |
| `tests_engine` | `tests_test`, `tests_testattempt`, `tests_questionresponse` |
| `analytics` | `analytics_usertopicperformance`, `analytics_dailyactivity`, `analytics_feedback`, `analytics_announcement`, `analytics_studystreak`, `analytics_badge`, `analytics_userbadge` |
| `ai_engine` | `ai_engine_chatsession`, `ai_engine_chatmessage`, `ai_engine_aifeedback` |
| `textbooks` | textbook + upload tables |
| `jobs` | `jobs_jobcategory`, `jobs_job`, `jobs_jobbookmark` |
| `django_q` | Task queue tables (managed by `django-q2`) |
| `axes` | Login-attempt tracking |

### RAG DB — `backend/chroma_db/rag_store.sqlite3` (committed via Git LFS)

```sql
CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    document TEXT NOT NULL,
    book TEXT NOT NULL,
    page INTEGER DEFAULT 0,
    chunk_index INTEGER DEFAULT 0,
    source_file TEXT DEFAULT '',
    tokens TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS idf_cache (
    term TEXT PRIMARY KEY,
    idf REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_book ON chunks(book);
```

### Production DB Strategy

- **SQLite is the default** for development and small production.
- `dj_database_url` is included — set `DATABASE_URL=postgres://…` in Render env to switch to Postgres.
- The committed `db.sqlite3` keeps a working seed that Render can use at boot.
- See [`setup/SUPABASE_SETUP.md`](./setup/SUPABASE_SETUP.md) for migration steps.

### Backup Strategy

- `backend/fixtures/cms_fixture.json` (plus `neet_pg_fixture.json`, `inicet_fixture.json`) is the seed for a **fresh** database: `seed_question_bank` loads it only while the CMS bank is empty, so a live bank (with its AI explanations, answer fixes and deactivations) is never overwritten; re-sync on purpose with `manage.py load_exam_fixture <exam>`.
- Admin endpoints `/api/auth/admin/system/backup-data/` and `/restore-data/` write / read the core configuration fixture at `CORE_DATA_BACKUP_PATH` (a persistent volume; `503 backup_not_configured` without it in production).
- Ad-hoc table dumps (`backend/scripts/_export_tables.py` etc.) hold user data and must be written outside the repository (`--output-dir`); see [`backup/MIGRATION_STATUS.md`](../backup/MIGRATION_STATUS.md).

---

## 9. Request Lifecycle

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant FE as Next.js FE
    participant AX as Axios Interceptor
    participant API as Django View
    participant MW as Middleware
    participant SVC as Service Layer
    participant AI as AI Provider Pool
    participant DB as SQLite

    U->>FE: Click "Explain Answer"
    FE->>AX: api.post('/ai/explain-answer/', payload)
    AX->>AX: Attach Supabase JWT + X-Session-ID
    AX->>API: HTTPS request
    API->>MW: SecurityMiddleware, AxesMiddleware, Custom MW
    MW->>MW: Validate JWT → resolve user
    MW->>SVC: Dispatch to service method
    SVC->>SVC: Check token balance
    SVC->>DB: Record token consumption
    SVC->>AI: Round-robin call (Gemini #3)
    AI-->>SVC: AI JSON response
    SVC->>SVC: Validate JSON shape, filter provider errors
    SVC-->>API: Cleaned response
    API-->>AX: 200 OK + JSON
    AX-->>FE: Render explanation UI
    FE-->>U: Display answer
```

---

## 10. Data Flow

### Question Bank Flow

```mermaid
flowchart LR
    PDF[PDF / MD / TXT] --> Extract[PYQ Extractor\n+ Document Processor]
    Extract --> Raw[Raw Question Records]
    Raw --> Enrich[AI Enrichment]
    Enrich --> Vetted[Multi-Model Vote]
    Vetted --> DB[(questions DB)]
    DB --> Validate[validate_questions.py]
    Validate --> Export[_export_fixture.py]
    Export --> Fixture[questions_fixture.json]
    Fixture --> Deploy[build.sh on Render]
    Deploy --> LiveDB[(Production SQLite)]
    LiveDB --> API[/api/questions/*/]
    API --> FE[Next.js UI]
```

Current state: `validate_questions.py`, `_export_fixture.py` and `backend/questions_fixture.json` no longer exist. The seed is `backend/fixtures/cms_fixture.json`, and `build.sh` (`seed_question_bank`) loads it only into an empty bank; on a running deployment the live database is the source of truth.

### RAG Ingestion Flow

```mermaid
flowchart LR
    A[Medura_Train/textbooks/] --> C{manage.py train_ai}
    B[Medura_Train/PYQ/] --> C
    C2[Medura_Train/web_knowledge/] --> C
    C --> Chunk[Chunk ~200 words]
    Chunk --> TFIDF[(rag_store.sqlite3)]
    UI[/api/ai/knowledge/upload/] --> C
    Scan[/api/ai/knowledge/scan/] --> C
```

### Token Consumption Flow

```mermaid
flowchart LR
    Req[AI Request] --> Check{Token balance > 0?}
    Check -- No --> Block[Block + 402 Payment Required]
    Check -- Yes --> Pick[Pick source:\nDaily Free > Weekly Free > Feedback > Purchased]
    Pick --> Decrement[Decrement 1 token]
    Decrement --> Call[Call AI provider]
    Call --> Log[Write TokenTransaction row]
```

---

## 11. Error Handling Flow

### Frontend

- `api.ts` response interceptor:
  - On a session-ending `code` (`account_blocked`, `email_not_confirmed`, `email_required`, `account_link_required`, `device_inactive`) → clear the local session + redirect to `/login?authError=…`.
  - On `device_limit_reached` → open `/settings?deviceLimit=1` (not from `/settings` or `/subscription`).
  - On `upgrade_required` (402) → open the upgrade modal.
  - On 502/503/504 → automatic base-URL failover for idempotent requests (production fallback URL).
  - Other errors → `Promise.reject` to caller.

### Backend

- `django-axes` lockout after 5 failed attempts.
- DRF exception handler returns structured `{ "error": "...", "code": "..." }`.
- Sentry captures unhandled exceptions (gated by `SENTRY_DSN` env var).
- `_PROVIDER_ERROR_PHRASES` filter prevents AI provider error strings from reaching users.
- `AI_CALL_DEADLINE_SECONDS` (default 90 s) per AI call; when no provider answers, `AIUnavailable` → refund + offline answer or `503 ai_unavailable`.
- All admin token grants/transfers write `AdminAuditLog` rows.

### Logging

- Structured logs via `python-json-logger`.
- `ddtrace` for distributed tracing.
- `frontend/sentry.client.config.ts` for browser errors.
- Datadog RUM + browser logs via `DatadogInit` component.

---

## 12. Environment Configuration

### Backend `.env` (see `backend/.env.example`)

| Variable | Required | Notes |
|---|---|---|
| `DJANGO_SECRET_KEY` | Yes (prod) | Falls back to insecure default in DEBUG |
| `DEBUG` | No | `True`/`False` |
| `ALLOWED_HOSTS` | Yes (prod) | Comma-separated |
| `DATABASE_URL` | No | Postgres override of SQLite |
| `GROQ_API_KEY` … `OPENROUTER_API_KEY2` | No (graceful skip) | AI provider keys (10 rotation entries) |
| `AI_OFFLINE_MODE` | No | `1` = no external LLM call anywhere (extractive offline answers) |
| `CORS_ALLOWED_ORIGINS` | Yes (prod) | `https://cracklabs.app` |
| `CSRF_TRUSTED_ORIGINS` | Yes (prod) | `https://cracklabs.app` |
| `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | Yes (prod) | Gmail App Password |
| `FRONTEND_URL` | Yes (prod) | Links in backend emails |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY` | Yes (prod) | Token verification (`accounts.W002` without the public key) |
| `SUPABASE_SERVICE_ROLE_KEY` | Admin tooling | Supabase admin API (`link_supabase_identity`, admin cleanups) |
| `SUPABASE_EMAIL_CONFIRMATION_ENABLED` | Yes (prod) | `true` once Supabase "Confirm email" and "Secure email change" are on (`accounts.W001`) |
| `CONTROL_TOWER_ADMIN_EMAILS` / `BOOTSTRAP_ADMIN_EMAIL` | No | Confirmed addresses that sign in as admin |
| `CORE_DATA_BACKUP_PATH` | Yes (prod) | Persistent file for admin backup / restore (`accounts.W003`) |
| `NUM_PROXIES` / `TRUSTED_CLIENT_IP_HEADER` | Yes (prod) | Client IP behind the edge (throttles, question-bank limiter); check `GET /api/health/client-ip/` |
| `SENTRY_DSN` | No | Enables Sentry init |
| `DISABLE_RAG` / `DISABLE_RAG_IN_PRODUCTION` | No | Set to `1` to skip RAG init |

### Frontend `.env.local`

| Variable | Required | Notes |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | Yes | Production: DigitalOcean URL |
| `NEXT_PUBLIC_API_FALLBACK_URL` | No | Failover URL |
| `NEXT_PUBLIC_USE_API_PROXY` | No | Local dev only |
| `NEXT_PUBLIC_SUPABASE_URL` | Conditional | When Supabase auth enabled |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Conditional | |
| `NEXT_PUBLIC_GA_MEASUREMENT_ID` | No | Default: `G-MM88RT1QQK` |
| `NEXT_PUBLIC_ANALYTICS_IN_DEV` | No | Enable GA in dev |

---

## 13. Architectural Decisions & Rationale

| Decision | Rationale |
|---|---|
| **SQLite default** | Zero infra cost at low traffic; `dj_database_url` allows painless Postgres upgrade |
| **10-entry AI provider rotation** | No single-vendor dependency; combined free tier ~35K req/day |
| **Typed AI failure (`AIUnavailable`)** | No provider-error text is shown or stored; charges are refunded; `AI_OFFLINE_MODE` answers extractively without any provider |
| **TF-IDF over vector embeddings** | No extra runtime cost, no model downloads |
| **Fixture-first question workflow** | Reproducible deploys; PRs reviewed as JSON diffs |
| **Token economy** | Aligns free-tier users with growth loop; pays for AI cost |
| **Supabase Auth + Django permissions** | Modern Supabase auth UX + battle-tested Django permissions; identities linked by `supabase_uid` |
| **Device limit (2 free / 4 subscribed)** | Anti-account-sharing for paid content |
| **Git LFS for PDFs + sqlite** | Avoids bloating git history with binary content |
| **App-per-bounded-context** | Easy to spin out into microservices later if scale demands |
