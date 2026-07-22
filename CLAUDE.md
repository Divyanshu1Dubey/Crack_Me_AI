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

4. **Persistent memory**: `C:\Users\DIVYANSHU\.claude\projects\C--Users-DIVYANSHU-Desktop-crack-cms\memory\crackcms-master-knowledge.md` — full verified codebase knowledge, including every model field, AI provider config, middleware order, DRF throttling rates, and convention patterns. **Read this for fast context loading** at the start of any session.

Only after reading the relevant documentation should you open individual source files. This prevents redundant exploration and keeps edits consistent with the documented architecture. The **`docs/`** directory is the **single source of truth** for architectural facts about this repository. Do not create parallel directories like `.docs/` — they will be deleted during the next consolidation pass.

✅ **Verification status**: All documentation has been **verified by reading actual source code** (see `docs/audit/FINAL_REPORT.md`). The 12 most critical corrections (Cerebras model = `gemma-4-31b`, RAG hardcoded disabled in production, AI rotation has 9 providers not 11, DRF throttling is configured, RateLimitMiddleware exists, mobile is Capacitor wrapper, etc.) have been applied. Treat the docs as authoritative.

## Project Overview

**Crack_Me_AI** — AI-powered UPSC Combined Medical Services (CMS) exam preparation platform.

- **Frontend**: Next.js 16 + React 19 + TypeScript + Tailwind 4 + Radix UI
- **Backend**: Django 5 + DRF + SimpleJWT
- **Database**: SQLite3 (with Postgres-ready config via `dj-database-url`)
- **AI**: 11-provider round-robin with RAG over TF-IDF SQLite store
- **Auth**: Custom JWT + Supabase (hybrid); django-axes brute-force protection
- **Deployment**: Render (backend) + Vercel (frontend); GitHub Actions CI
- **Live**: `cracklabs.app` ↔ `crackcms-vsthc.ondigitalocean.app/api/`

## Common Commands

### Backend (Django, Python 3.12)

```bash
cd backend
..\.venv\Scripts\Activate.ps1     # Windows venv activation
pip install -r requirements.txt
python manage.py migrate
python manage.py loaddata questions_fixture.json
python manage.py runserver 8000
python manage.py createsuperuser
```

Tests / checks:
```bash
cd backend
python manage.py test --verbosity=2              # Django test runner
python manage.py check --deploy                  # Production checks
python manage.py makemigrations --check --dry-run # Detect missing migrations
python test_all.py                               # Comprehensive suite (DB, fixtures, AI keys, endpoints, auth)
python test_all.py --quick                       # Skip slow AI tests
python test_all.py --endpoints-only
python test_all.py --auth-only
python test_api_keys.py                          # Verify all AI provider keys
python validate_questions.py                     # Question-bank QA
python _train_all.py                             # Rebuild RAG index from Medura_Train/
python _export_fixture.py                        # DB → questions_fixture.json
python _review_and_fix_answers.py export --year 2018
```

### Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev -- --webpack      # Dev server on :3000 (note: uses --webpack, not turbopack)
npm run build                 # Production build
npm run start                 # Serve production build
npm run lint                  # ESLint (eslint-config-next)
npm run icons:download        # Fetch icon set from manifest
npx playwright test           # E2E (Playwright configured in playwright.config.ts)
```

### Pre-commit / Security

```bash
bandit -r backend/ -x backend/__pycache__,backend/migrations --skip B101
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
  accounts/         CustomUser, JWT views, token wallet, device-session tracking,
                    Supabase auth bridge, password reset, admin token management
  questions/        PYQ questions, bookmarks, discussions, notes, SM-2 flashcards
  tests_engine/     Adaptive tests, PYQ simulator, attempt tracking
  analytics/        Dashboard stats, topic performance, streaks, badges, roadmap
  ai_engine/        11-provider orchestrator (services.py), RAG pipeline
                    (rag_pipeline.py + sqlite_rag.py), document processor,
                    PYQ extractor, knowledge base scan
  textbooks/        Indexed textbook library + chapter list
  resources/        UPSC exam resource catalog
  video_engine/     edge-tts + moviepy slide video generation
  jobs/             Background job model + endpoints
  chroma_db/        rag_store.sqlite3 (TF-IDF chunks, NOT chromadb in name only)
  Medura_Train/     Drop textbooks/PYQ/web_knowledge here, then run _train_all.py
  scripts/, *.py    Ad-hoc loader scripts, fixtures, validators
```

### Key Architectural Patterns

1. **AI Provider Round-Robin** — `ai_engine/services.py` rotates across Groq → Cerebras → Gemini (2 models) → Cohere → OpenRouter ×2 → GitHub Models → HuggingFace → Mistral → NVIDIA Mistral → DeepSeek (paid, LAST) → Ollama (local fallback). Thread-safe counter with `threading.Lock`. 120 s deadline, 15–20 s per provider. Falls through on any error/timeout. **Never surface provider-error strings to users** — `_PROVIDER_ERROR_PHRASES` are filtered.

2. **RAG Pipeline** — `ai_engine/rag_pipeline.py` ingests PDFs/MD/TXT from `Medura_Train/{textbooks,PYQ,web_knowledge}/`, chunks (~200–500 tokens), stores in `chroma_db/rag_store.sqlite3` with TF-IDF + IDF cache. Query → cosine similarity → top-K chunks → context injection. Disable via `DISABLE_RAG=1` env var for memory-constrained hosts. PDFs >50 MB are auto-skipped — use `.md` summaries.

3. **Fixture-First Question Management** — `backend/questions_fixture.json` is the production source of truth (loaded by `build.sh` on Render). DB edits via Django admin / REST API / `_review_and_fix_answers.py` CSV workflow → run `_export_fixture.py` → commit JSON → push.

4. **Token Economy** — Each AI call costs 1 token. Daily (10/day, midnight reset) + Weekly (50/week, Sunday reset) + Purchased + Feedback reward (+2). Consumption priority: Free → Feedback → Purchased. Admin/staff bypass. Per-provider quota noted in `ai_engine/services.py` header.

5. **Auth Flow** — Hybrid Supabase-first with Django JWT backup. `frontend/src/lib/api.ts` attaches Supabase access token via interceptor; auto-clears local session on `session_invalid` (single-device enforcement). Backend `accounts/supabase_auth.py` + `supabase_rest_auth.py` bridge Supabase identities. `django-axes` locks accounts after 5 failed attempts (30 min).

6. **Multi-Base API Failover** — `api.ts` resolves base URL from `NEXT_PUBLIC_API_URL` (or localhost for dev) with automatic failover to `NEXT_PUBLIC_API_FALLBACK_URL` on 502/503/504. The legacy Render URL `crackcms-backend.onrender.com` is intentionally blacklisted as unhealthy; production uses the DigitalOcean URL `crackcms-vsthc.ondigitalocean.app/api` baked into `DEFAULT_PRODUCTION_API_URL`.

7. **Background Tasks** — `django-q2` broker for async work; `video_engine/tasks.py` and `questions/tasks.py` schedule enrichment + video generation.

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
| AI orchestration (11 providers, RAG) | `backend/ai_engine/services.py`, `rag_pipeline.py`, `sqlite_rag.py` |
| Question models + views (largest app) | `backend/questions/models.py`, `views.py` |
| Token wallet + admin grants | `backend/accounts/views.py` |
| Frontend Axios client (auth, failover, session) | `frontend/src/lib/api.ts` |
| Auth provider (React context) | `frontend/src/lib/auth.tsx` |
| Page routes | `frontend/src/app/*` |
| Build for Render | `backend/build.sh` |
| Vercel config + security headers | `frontend/vercel.json` |
| CI workflow (Python 3.12 / Node 20) | `.github/workflows/ci.yml` |
| AI API keys reference | `docs/setup/API_KEYS.md`, `backend/.env.example` |
| RAG training sources | `backend/Medura_Train/{textbooks,PYQ,web_knowledge}/` |
| RAG SQLite store | `backend/chroma_db/rag_store.sqlite3` |
| Production fixture | `backend/questions_fixture.json` |
| Mobile app | `mobile-app/` |

## Setup Gotchas

- **Frontend dev server uses `--webpack`** (not turbopack) — see `package.json` `dev` script.
- **`build.sh` is the deploy contract** — installs deps, migrates, runs `collectstatic`, imports NEET PG data via `python manage.py import_neet_pg`. Add new one-shot deploy steps there.
- **Venv path**: project uses both `.venv\` (root) and `backend/.venv\` — README activates root, then `cd backend`. Backend pip installs go in root venv.
- **AI provider env vars** in `backend/.env`: `GROQ_API_KEY`, `CEREBRAS_API_KEY`, `GEMINI_API_KEY`, `GITHUB_TOKEN`, `OPENROUTER_API_KEY`, `OPENROUTER_API_KEY2`, `COHERE_API_KEY`, `HUGGINGFACE_API_KEY`, `MISTRAL_API_KEY`, `NVIDIA_MISTRAL_API_KEY`, `DEEPSEEK_API_KEY`, `TOGETHER_API_KEY`, `AIML_API_KEY`. Missing keys = silent skip in round-robin.
- **Required backend env** in production: `DJANGO_SECRET_KEY`, all AI keys above, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, `FRONTEND_URL` (for password-reset links).
- **Required frontend env**: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_API_FALLBACK_URL`, `NEXT_PUBLIC_USE_API_PROXY` (optional), Supabase keys.
- **PDF handling**: `**/textbooks/*.pdf` and `*.sqlite3` are tracked via **Git LFS** (see `.gitattributes`).
- **`.gitignore` exceptions**: `db.sqlite3`, `chroma_db/rag_store.sqlite3`, and `chroma_db/chroma.sqlite3` ARE committed (deployment needs them); other `*.sqlite3` are ignored.
