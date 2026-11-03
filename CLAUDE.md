# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⚠️ READ FIRST — Mandatory Documentation Consultation

**Before reading any repository code, always consult in this order:**

1. **`CLAUDE.md`** (this file) — orientation, commands, architecture summary, conventions.
2. **`docs/INDEX.md`** — master index of the canonical documentation. Read this next.
3. The specific `docs/*.md` file most relevant to your task:
   - `docs/PROJECT_OVERVIEW.md` — vision, users, tech stack, integrations, repo layout.
   - `docs/ARCHITECTURE.md` — system architecture with mermaid diagrams (frontend, backend, AI, auth, deployment, data flow).
   - `docs/FOLDER_STRUCTURE.md` — where every important folder/file lives.
   - `docs/FEATURES.md` — per-feature implementation reference.
   - `docs/DATA_MODEL.md` — every database model, FK, index, business rule.
   - `docs/API_REFERENCE.md` — every endpoint, auth, request/response, errors.
   - `docs/AUTHENTICATION.md` — JWT, sessions, roles, protected routes.
   - `docs/ADMIN_SYSTEM.md` — admin APIs, permissions, moderation.
   - `docs/AI_ASSISTANT_RULES.md` — permanent rules + glossary for AI assistants.
   - `docs/KNOWN_GAPS.md` — verification status (now 100% verified).
   - `docs/audit/FINAL_REPORT.md` — final consolidation summary.

4. **Persistent memory**: the index at `C:\Users\DIVYANSHU\.claude\projects\C--Users-DIVYANSHU-Desktop-crack-cms\memory\MEMORY.md` (the previously referenced `crackcms-master-knowledge.md` does not exist).
5. **Latest audit**: `docs/audit/OVERNIGHT_MISSION_FINAL_REPORT.md` (2026-11) — what was verified, fixed and still open; `docs/LOCAL_DEVELOPMENT.md` — running the whole stack locally on the restored backup.

Only after reading the relevant documentation should you open individual source files. This prevents redundant exploration and keeps edits consistent with the documented architecture. The **`docs/`** directory is the **single source of truth** for architectural facts about this repository. Do not create parallel directories like `.docs/` — they will be deleted during the next consolidation pass.

⚠️ **Verification status (2026-11-01)**: the 2026-11 audit re-read the code and found several statements in older docs wrong — e.g. RAG is **enabled** by default (only `DISABLE_RAG` / `DISABLE_RAG_IN_PRODUCTION` turn it off; there is no DEBUG gate), the AI rotation has **10 entries** (no DeepSeek or Ollama), and there is no "PDFs > 50 MB are skipped" guard. Where docs and code disagree, trust the code and `docs/audit/OVERNIGHT_MISSION_FINAL_REPORT.md`.

## Project Overview

**Crack_Me_AI** — AI-powered UPSC Combined Medical Services (CMS) exam preparation platform.

- **Frontend**: Next.js 16 + React 19 + TypeScript + Tailwind 4 + Radix UI
- **Backend**: Django 5 + DRF + SimpleJWT
- **Database**: SQLite3 (with Postgres-ready config via `dj-database-url`)
- **AI**: 10-entry provider rotation (`AIService._call_ai`) with RAG over the SQLite chunk store (whole-store BM25, `ai_engine/lexical_index.py`); `AI_OFFLINE_MODE=1` answers extractively with no external call
- **Auth**: Custom JWT + Supabase (hybrid); django-axes brute-force protection
- **Deployment**: Render (backend) + Vercel (frontend); GitHub Actions CI
- **Live**: `cracklabs.app` ↔ `api.cracklabs.app/api/`

## Common Commands

### Backend (Django, Python 3.12)

```bash
cd backend
..\.venv\Scripts\Activate.ps1     # Windows venv activation
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_question_bank   # loads fixtures/cms_fixture.json into an EMPTY CMS bank only
python manage.py runserver 8000
python manage.py createsuperuser
```

Tests / checks (the test runner blanks every external-service secret and refuses a remote
DATABASE_URL — see the "Hermetic test runs" block in settings.py; from PowerShell, never set
`$env:X=''`, which deletes the variable and lets backend/.env load it):
```bash
cd backend
DATABASE_URL= SUPABASE_DATABASE_URL= DEBUG=True python manage.py test --parallel 1   # Django test runner (bash)
python -m ai_eval.rag_benchmark --out ../docs/audit/rag   # RAG retrieval benchmark (needs a DB with the question bank)
python manage.py check --deploy                  # Production checks
python manage.py makemigrations --check --dry-run # Detect missing migrations
python test_all.py                               # Comprehensive suite (DB, fixtures, AI keys, endpoints, auth)
python test_all.py --quick                       # Skip slow AI tests
python test_all.py --endpoints-only
python test_all.py --auth-only
python test_all.py --keys-only                   # Verify all AI provider keys (test_api_keys.py no longer exists)
python manage.py train_ai                         # Index Medura_Train/ into the RAG store (_train_all.py no longer exists)
python manage.py load_exam_fixture cms --dry-run  # Check a fixture edit (backend/fixtures/README.md); without --dry-run it overwrites a live bank
```
(`validate_questions.py`, `_export_fixture.py`, `_review_and_fix_answers.py` and `questions_fixture.json` no longer exist.)

### Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev -- --webpack      # Dev server on :3000 (note: uses --webpack, not turbopack)
npm run build                 # Production build
npm run start                 # Serve production build
npm run lint                  # ESLint (eslint-config-next)
npm run test:unit             # Unit tests in tests/unit (node --test; needs Node >= 22.18 — CI job `frontend-unit` runs on Node 22)
npm run icons:download        # Fetch icon set from manifest
npx playwright test           # E2E (Playwright configured in playwright.config.ts)
```

### Pre-commit / Security

```bash
bandit -r backend/ -x '*/migrations/*,*/__pycache__/*' --skip B101 -lll -iii   # the CI gate (no baseline: hashes for keys pass usedforsecurity=False)
safety check -r backend/requirements.txt
npm audit --audit-level=high
python scripts/scan_secrets.py   # Local pre-commit hook (see .pre-commit-config.yaml)
```

## High-Level Architecture

```
frontend/ (Next.js App Router, src/ directory)
  src/app/          Route pages (dashboard, questions, ai-tutor, flashcards,
                    tests, simulator, analytics, tokens, …)
  src/components/   UI primitives (Radix wrappers), feature components, providers
  src/lib/          api.ts (Axios client w/ Supabase JWT + multi-base failover),
                    auth.tsx (AuthProvider), supabase.ts (Supabase browser client),
                    seo.ts, utils.ts
  src/context/      DockContext and other React contexts

backend/
  crack_cms/        Django project — settings.py (env loading, Sentry, app registry,
                    CORS, middleware), urls.py, wsgi/asgi, cache_middleware
  accounts/         CustomUser, Supabase auth bridge (supabase_uid linking, 2/4 device
                    limit), token wallet, subscriptions, admin token management
                    (local login/register/password-reset endpoints answer 410)
  questions/        PYQ questions, bookmarks, discussions, notes, SM-2 flashcards
  tests_engine/     Adaptive tests, PYQ simulator, attempt tracking
  analytics/        Dashboard stats, topic performance, streaks, badges, roadmap
  ai_engine/        10-entry provider rotation (services.py), RAG pipeline
                    (rag_pipeline.py + sqlite_rag.py), document processor,
                    PYQ extractor, knowledge base scan
  textbooks/        Indexed textbook library + chapter list
  resources/        UPSC exam resource catalog
  video_engine/     edge-tts + moviepy slide video generation
  jobs/             Background job model + endpoints
  chroma_db/        rag_store.sqlite3 (TF-IDF chunks, NOT chromadb in name only)
  Medura_Train/     Drop textbooks/PYQ/web_knowledge here, then run manage.py train_ai
  scripts/, *.py    Ad-hoc loader scripts, fixtures, validators
```

### Key Architectural Patterns

1. **AI provider rotation** — `AIService._call_ai` (`ai_engine/services.py`) rotates over 10 entries: OmniRoute, Groq, Cerebras, Gemini (2 models), Cohere, OpenRouter, GitHub Models, HuggingFace, Mistral, OpenRouter2 (NVIDIA Mistral is initialised but not rotated; DeepSeek and Ollama are not implemented). A global counter picks the starting provider. When every provider fails it raises `AIUnavailable` (it used to return an outage sentence that views charged for and even saved as explanations); views refund tokens/free slots and answer with an offline extract or HTTP 503 `{code: 'ai_unavailable'}`. `AI_OFFLINE_MODE=1` = no external LLM call anywhere. **Never surface or persist provider-error strings.**

2. **RAG Pipeline** — `ai_engine/rag_pipeline.py` ingests PDFs/MD/TXT from `Medura_Train/{textbooks,PYQ,web_knowledge}/` into `chroma_db/rag_store.sqlite3`. Retrieval is BM25 over the **whole** store from an in-memory index (`ai_engine/lexical_index.py`: Greek/diacritic folding, one indexing pass per source file, personal/admin documents excluded, raw question papers only on request); constructing the pipeline is read-only. Benchmark and methodology: `docs/audit/RAG_BENCHMARK.md` (`python -m ai_eval.rag_benchmark`). RAG is on by default; `DISABLE_RAG=1` / `DISABLE_RAG_IN_PRODUCTION=1` turn it off. There is no automatic size limit on PDFs.

3. **Fixture seeds, live DB is the truth** — `backend/fixtures/cms_fixture.json` (plus `neet_pg_fixture.json`, `inicet_fixture.json`) seeds a **fresh** database: `build.sh` runs `seed_question_bank`, which loads it only while the CMS bank is empty, so a deploy never overwrites a live bank (AI explanations, answer fixes, deactivations). Edits on a running deployment go through Django admin / the REST API; fixture edits follow `backend/fixtures/README.md` (`load_exam_fixture <exam> --dry-run`). `questions_fixture.json`, `_export_fixture.py` and `_review_and_fix_answers.py` no longer exist.

4. **Token Economy** — Each AI call costs 1 token. Daily (10/day, midnight reset) + Weekly (50/week, Sunday reset) + Purchased + Feedback reward (+2). Consumption priority: Free → Feedback → Purchased. Admin/staff bypass. Per-provider quota noted in `ai_engine/services.py` header.

5. **Auth Flow** — Supabase Auth only in production (local `/api/auth/login/`, `/register/`, `/password-reset/` answer 410; Django JWTs exist only for the dev-only `LOCAL_DEV_AUTH`). `frontend/src/lib/api.ts` attaches the Supabase access token and `X-Session-ID`. `accounts/supabase_rest_auth.py` matches identities by `CustomUser.supabase_uid`; an admin/staff row links automatically only for a trusted admin identity or the identity it was created from, otherwise `401 account_link_required` until `python manage.py link_supabase_identity` links it (run `--all-privileged` dry run, then `--apply`, once after `accounts.0023`). Supabase "Confirm email" and "Secure email change" must be ON (`check --deploy` warns `accounts.W001` until `SUPABASE_EMAIL_CONFIRMATION_ENABLED=true`). Device limit: 2 devices free / 4 subscribed (`UserDevice` by `X-Session-ID`; `device_limit_reached` opens `/settings?deviceLimit=1`, `device_inactive` signs out); `session_key` / `session_invalid` are no longer used. Admin pages gate on the backend profile's `role` / `is_admin`, never Supabase `user_metadata`. `django-axes` locks accounts after 5 failed attempts (30 min). Details: `docs/AUTHENTICATION.md`.

6. **Multi-Base API Failover** — `api.ts` resolves base URL from `NEXT_PUBLIC_API_URL` (or localhost for dev) with automatic failover to `NEXT_PUBLIC_API_FALLBACK_URL` on 502/503/504 (idempotent GET/HEAD/OPTIONS requests only, once). The legacy Render URL `crackcms-backend.onrender.com` is intentionally blacklisted as unhealthy; production uses the DigitalOcean URL `crackcms-vsthc.ondigitalocean.app/api` baked into `DEFAULT_PRODUCTION_API_URL`.

7. **Background Tasks** — `django-q2` broker for async work; `video_engine/tasks.py` and `questions/tasks.py` schedule enrichment + video generation. Jobs, the daily renewal-reminder schedule and the `ingestion_recover_stale_jobs` sweeper (every 10 min; both schedules are created by `migrate`) run only while `python manage.py qcluster` is up — on DigitalOcean a separate Worker component (`backend/Procfile` `worker:` is not started automatically).

## Conventions & Rules (from .github/copilot-instructions.md)

- Prefer **minimal, targeted changes**; do not revert user changes.
- Keep auth behavior consistent with the **Supabase-first** flow.
- Preserve **Next.js static generation** stability.
- Use **existing patterns** before introducing new abstractions.
- Reference docs: `README.md`, `ARCHITECTURE.md`, `DOCUMENTATION.md`, `plan-crackCmsPlatformFixAndEnhancement.prompt.md`, `.github/skills/*`, `.github/agents/*`.
- Be **concise and factual**; mention exact files changed; verify with build/test commands.

## Important Files / Locations

| Concern | Path |
|---|---|
| Backend settings, env loading, middleware | `backend/crack_cms/settings.py` |
| API URL routing | `backend/crack_cms/urls.py` |
| AI orchestration (10-entry rotation, RAG) | `backend/ai_engine/services.py`, `rag_pipeline.py`, `sqlite_rag.py` |
| Question models + views (largest app) | `backend/questions/models.py`, `views.py` |
| Token wallet + admin grants | `backend/accounts/views.py` |
| Frontend Axios client (auth, failover, session) | `frontend/src/lib/api.ts` |
| Auth provider (React context) | `frontend/src/lib/auth.tsx` |
| Page routes | `frontend/src/app/*` |
| Build / deploy contract | `backend/build.sh`, `backend/Procfile` (release / web / worker) |
| Vercel config + security headers | `frontend/vercel.json` |
| CI workflow (Python 3.12 / Node 20) | `.github/workflows/ci.yml` |
| AI API keys reference | `docs/setup/API_KEYS.md`, `backend/.env.example` |
| RAG training sources | `backend/Medura_Train/{textbooks,PYQ,web_knowledge}/` |
| RAG SQLite store | `backend/chroma_db/rag_store.sqlite3` |
| Question-bank seed (empty bank only) | `backend/fixtures/cms_fixture.json` (+ `neet_pg_fixture.json`, `inicet_fixture.json`) |
| Mobile app | `mobile-app/` |

## Setup Gotchas

- **Frontend dev server uses `--webpack`** (not turbopack) — see `package.json` `dev` script.
- **`build.sh` is the deploy contract** — installs deps, runs `collectstatic`, migrates, prints the `link_supabase_identity --all-privileged` dry run, seeds an empty CMS bank (`seed_question_bank`), then the idempotent blog / KB / image-relink steps. It no longer runs `import_neet_pg` and never runs destructive data commands; one-time owner steps (`import_neet_pg --replace --dry-run` → `--replace`, `cleanup_seed_samples`, `link_supabase_identity --apply`, setting `NUM_PROXIES` / `TRUSTED_CLIENT_IP_HEADER` after checking `GET /api/health/client-ip/` as an admin) are listed in `docs/ARCHITECTURE.md` §7. Add new idempotent deploy steps there.
- **Media in production**: Django serves `/media/` only with `DEBUG=True`; MEDIA-linked files (e.g. textbook page screenshots from `/api/ai/screenshot/<id>/`) need the platform to serve `MEDIA_ROOT` or a bucket.
- **Venv path**: project uses both `.venv\` (root) and `backend/.venv\` — README activates root, then `cd backend`. Backend pip installs go in root venv.
- **AI provider env vars** in `backend/.env`: `GROQ_API_KEY`, `CEREBRAS_API_KEY`, `GEMINI_API_KEY`, `GITHUB_TOKEN`, `OPENROUTER_API_KEY`, `OPENROUTER_API_KEY2`, `COHERE_API_KEY`, `HUGGINGFACE_API_KEY`, `MISTRAL_API_KEY`, `NVIDIA_MISTRAL_API_KEY`, `DEEPSEEK_API_KEY`, `TOGETHER_API_KEY`, `AIML_API_KEY`. Missing keys = silent skip in round-robin.
- **Required backend env** in production: `DJANGO_SECRET_KEY`, all AI keys above, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, `FRONTEND_URL` (default CORS/CSRF origin and links in backend emails; password reset goes through Supabase), `SUPABASE_URL` + `SUPABASE_ANON_KEY`, `SUPABASE_EMAIL_CONFIRMATION_ENABLED=true` (once Supabase "Confirm email" and "Secure email change" are on), `CORE_DATA_BACKUP_PATH` (persistent volume), `NUM_PROXIES` / `TRUSTED_CLIENT_IP_HEADER`. `python manage.py check --deploy` reports missing auth/backup settings as `accounts.W001`–`W003`.
- **Required frontend env**: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_API_FALLBACK_URL`, `NEXT_PUBLIC_USE_API_PROXY` (optional), Supabase keys.
- **PDF handling**: `**/textbooks/*.pdf` and `*.sqlite3` are tracked via **Git LFS** (see `.gitattributes`).
- **`.gitignore` exceptions**: `db.sqlite3`, `chroma_db/rag_store.sqlite3`, and `chroma_db/chroma.sqlite3` ARE committed (deployment needs them); other `*.sqlite3` are ignored.
