# Crack_Me_AI — UPSC CMS Exam Preparation Platform

> AI-powered UPSC Combined Medical Services (CMS) exam prep platform with 10 AI providers, RAG-grounded tutoring, 2000+ PYQ questions, spaced repetition flashcards, and adaptive testing.

**Live**: [crack-me-ai1.vercel.app](https://crack-me-ai1.vercel.app/) | **API**: [crackcms-backend.onrender.com/api/](https://crackcms-backend.onrender.com/api/)

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Architecture](#architecture)
3. [Tech Stack](#tech-stack)
4. [AI System](#ai-system)
5. [Question Bank & Data Pipeline](#question-bank--data-pipeline)
6. [Token Economy](#token-economy)
7. [API Reference](#api-reference)
8. [Frontend Pages](#frontend-pages)
9. [Training the AI (Adding Content)](#training-the-ai-adding-content)
10. [Question Management](#question-management)
11. [API Keys Setup](#api-keys-setup)
12. [Gmail Setup (Password Reset)](#gmail-setup-password-reset)
13. [Ollama Setup (Local AI)](#ollama-setup-local-ai)
14. [Deployment](#deployment)
15. [Testing](#testing)
16. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Backend (Django)
```powershell
cd backend
..\\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py loaddata questions_fixture.json
python manage.py runserver 8000
```
Runs on **http://localhost:8000**

### Frontend (Next.js)
```powershell
cd frontend
npm install
npm run dev
```
Runs on **http://localhost:3000**

### Create Admin Account
```powershell
cd backend
python manage.py createsuperuser
```

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                   FRONTEND (Next.js 16)                       │
│  Dashboard │ Question Bank │ AI Tutor │ Flashcards │ Tests    │
│                    Axios (JWT Bearer)                         │
└────────────────────────┬─────────────────────────────────────┘
                         │
┌────────────────────────┼─────────────────────────────────────┐
│                   BACKEND (Django 5 + DRF)                    │
│  accounts │ questions │ ai_engine │ analytics │ tests_engine  │
│  (JWT +   │ (CRUD +   │ (10 AI    │ (topics,  │ (adaptive    │
│   tokens) │  discuss) │  providers│  streaks) │  tests)      │
│                                                               │
│  ┌──────────┐  ┌──────────────┐  ┌────────────┐              │
│  │ SQLite   │  │ RAG Store    │  │ Cache      │              │
│  │ Database │  │ (TF-IDF)     │  │ (LocMem)   │              │
│  └──────────┘  └──────────────┘  └────────────┘              │
└──────────────────────────────────────────────────────────────┘
```

### Backend Apps

| App | Purpose |
|-----|---------|
| **accounts** | CustomUser, JWT auth, token balance, password reset |
| **questions** | 2004+ PYQs, bookmarks, discussions, notes, flashcards (SM-2) |
| **ai_engine** | 10-provider round-robin AI, RAG pipeline, explain-after-answer |
| **analytics** | Topic performance, daily activity, streaks, badges |
| **tests_engine** | Adaptive tests, PYQ simulation, attempt tracking |
| **textbooks** | Textbook library, chapter indexing |
| **resources** | UPSC exam resources, document catalog |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS 4, Radix UI |
| Backend | Django 5.x, Django REST Framework, SimpleJWT |
| Database | SQLite3 |
| AI Providers | Groq, Cerebras, Gemini, Cohere, OpenRouter ×2, GitHub Models, HuggingFace, Mistral, DeepSeek |
| RAG | SQLite TF-IDF (4,972+ chunks from 79 sources) |
| Auth Security | django-axes (brute-force protection) |
| CI/CD | GitHub Actions → Render (backend) + Vercel (frontend) |

---

## AI System

### 10 AI Providers (Round-Robin)

| # | Provider | Model | Rate Limit |
|---|----------|-------|------------|
| 1 | Groq | Llama 3.3 70B | 30 RPM, 14,400 RPD |
| 2 | Cerebras | Llama 3.1 8B | 30 RPM |
| 3 | Gemini | Flash 2.0 | 15 RPM, 1,500 RPD/model |
| 4 | Cohere | Command-A | 20 RPM |
| 5 | OpenRouter | Free models | 20 RPM |
| 6 | OpenRouter2 | Free models (2nd key) | 20 RPM |
| 7 | GitHub Models | GPT-4o Mini | 150 RPM |
| 8 | HuggingFace | Llama 3.3 70B | ~10 RPM |
| 9 | Mistral | mistral-small | ~30 RPM |
| 10 | DeepSeek | deepseek-chat | Pay-as-you-go (LAST) |
| fallback | Ollama | llama3.2:3b | Local, unlimited |

**Deadline**: 120 seconds per request. Auto-failover to next provider on error/timeout.

### How Round-Robin Works

```
Request 1 → Groq (if fails → Cerebras → Gemini → ...)
Request 2 → Cerebras (if fails → Gemini → Cohere → ...)
Request N → provider[N % 10]
All 10 fail → Ollama (local fallback)
```

- Thread-safe rotation via `threading.Lock`
- Each provider wrapped with timeout (15-20s)
- DeepSeek tried last (paid)

### AI Features

| Feature | Endpoint | Description |
|---------|----------|-------------|
| AI Tutor | `POST /api/ai/tutor/` | RAG-enhanced chat tutoring |
| Explain After Answer | `POST /api/ai/explain-answer/` | Rich JSON explanation with mnemonic |
| Mnemonic Generator | `POST /api/ai/mnemonic/` | Memory aids for topics |
| Concept Explainer | `POST /api/ai/explain/` | Topic explanations at different levels |
| Question Generator | `POST /api/ai/generate-questions/` | AI-generated MCQs |
| Study Plan | `POST /api/ai/study-plan/` | Personalized study roadmap |

### Explain After Answer (JSON Response)

```json
{
  "is_correct": true,
  "correct_answer": "B",
  "why_correct": "Detailed explanation...",
  "why_others_wrong": {"A": "...", "C": "...", "D": "..."},
  "mnemonic": "Memory aid...",
  "high_yield_points": ["Fact 1", "Fact 2"],
  "textbook_reference": "Harrison's Ch. 15"
}
```

Cached for 24 hours (key: MD5 of question + answer).

### RAG Pipeline

```
User Query → TF-IDF Tokenization → SQLite RAG Store →
  Top-K Chunks (cosine similarity) → Context Injection → AI Prompt → Response
```

- **Storage**: `chroma_db/rag_store.sqlite3` (4,972+ chunks)
- **Sources**: 17 textbook notes, 16 PYQ papers, 51 web articles (79 total)
- **Chunk size**: ~200-500 tokens with overlap

---

## Question Bank & Data Pipeline

### Current Stats

- **2,004+ questions** from UPSC CMS 2018-2025
- **5 subjects**, **47 topics**
- All questions enriched with explanations, mnemonics, concept tags

### Data Flow

```
Source (PDF/TXT/MD) → Import Scripts → Django DB →
  AI Enrichment (answers, explanations) → Export Fixture →
    questions_fixture.json → Deploy (build.sh loads fixture)
```

### Enrichment Fields

| Field | Source | Description |
|-------|--------|-------------|
| `correct_answer` | AI voting (3 providers) | Multi-model consensus |
| `explanation` | AI | 3-4 sentence explanation |
| `mnemonic` | AI | Memory aid |
| `high_yield_points` | AI | Exam-relevant facts (JSON) |
| `textbook_reference` | AI | Standard textbook + chapter |
| `concept_tags` | AI | Topic tags (JSON) |
| `difficulty` | AI | easy/medium/hard |

### Validation

`validate_questions.py` checks: missing answers, invalid options, answer-option mismatch, fuzzy duplicates.

### Maintenance Commands

```bash
python validate_questions.py          # Quality checks
python _export_fixture.py             # Export DB → fixture JSON
python enrich_turbo.py                # Parallel AI enrichment
python _review_and_fix_answers.py     # CSV review workflow
python _check_db.py                   # Database integrity
```

---

## Token Economy

| Token Type | Allocation | Expiry |
|-----------|-----------|--------|
| Daily Free | 10/day | Midnight reset |
| Weekly Free | 50/week | Sunday reset |
| Purchased | Configurable | Never |
| Feedback Reward | +2 per verified report | Never |

- Each AI feature costs **1 token**
- Admin/staff users bypass token limits
- Consumption priority: Free → Feedback credits → Purchased

### Admin Token Management

| Endpoint | Description |
|----------|-------------|
| `GET /api/auth/tokens/admin/users/` | All users + balances |
| `POST /api/auth/tokens/admin/grant/` | Grant/revoke tokens |
| `POST /api/auth/tokens/admin/transfer/` | Transfer between users |

---

## API Reference

### Authentication (`/api/auth/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register/` | Register new user |
| POST | `/api/auth/login/` | Login (returns JWT) |
| GET | `/api/auth/profile/` | Get user profile |
| PUT | `/api/auth/profile/` | Update profile |
| GET | `/api/auth/tokens/` | Token balance |
| POST | `/api/auth/tokens/purchase/` | Purchase tokens |

### Questions (`/api/questions/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/questions/subjects/` | List subjects |
| GET | `/api/questions/topics/` | List topics |
| GET | `/api/questions/questions/` | List questions (filter by subject/year/difficulty) |
| POST | `/api/questions/questions/{id}/bookmark/` | Toggle bookmark |
| GET | `/api/questions/flashcards/` | List flashcards |
| POST | `/api/questions/flashcards/` | Create flashcard |
| POST | `/api/questions/flashcards/{id}/review/` | SM-2 review |

### AI Engine (`/api/ai/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/ai/tutor/` | AI tutor (RAG-enhanced) |
| POST | `/api/ai/mnemonic/` | Generate mnemonic |
| POST | `/api/ai/explain/` | Explain concept |
| POST | `/api/ai/analyze-answer/` | Analyze answer |
| POST | `/api/ai/explain-answer/` | Explain after answer |
| POST | `/api/ai/generate-questions/` | Generate MCQs |
| POST | `/api/ai/study-plan/` | Study plan |
| GET | `/api/ai/status/` | Provider status |
| GET | `/api/ai/test/` | Quick AI test |
| POST | `/api/ai/knowledge/upload/` | Upload to knowledge base |
| POST | `/api/ai/knowledge/scan/` | Scan & index new files |

### Tests (`/api/tests/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/tests/tests/` | List tests |
| POST | `/api/tests/tests/` | Create test |
| POST | `/api/tests/tests/{id}/submit/` | Submit answers |
| GET | `/api/tests/tests/{id}/review/` | Review results |

### Analytics (`/api/analytics/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/analytics/dashboard/` | Dashboard stats |
| GET | `/api/analytics/performance/` | Performance over time |
| GET | `/api/analytics/topics/` | Topic-wise performance |
| GET | `/api/analytics/roadmap/` | Study roadmap |

---

## Frontend Pages

| Route | Page | Description |
|-------|------|-------------|
| `/` | Landing | Hero section, features, CTA |
| `/login` | Login | JWT authentication |
| `/register` | Register | New user signup |
| `/dashboard` | Dashboard | Stats, streaks, quick actions |
| `/questions` | Question Bank | Filter, search, AI analysis, keyboard nav (A-D/N/P) |
| `/ai-tutor` | AI Tutor | 5-mode chat with RAG |
| `/flashcards` | Flashcards | SM-2 spaced repetition, CRUD, analytics |
| `/tests` | Tests | Create adaptive tests |
| `/tests/[id]` | Test Session | Timed MCQ + review mode |
| `/generate` | Question Generator | AI-generated MCQs |
| `/simulator` | PYQ Simulator | Real exam conditions |
| `/analytics` | Analytics | Performance charts, trends |
| `/roadmap` | Study Roadmap | AI-generated study plan |
| `/bookmarks` | Bookmarks | Saved questions |
| `/textbooks` | Textbook Library | Browse indexed textbooks |
| `/resources` | Resources | UPSC documents |
| `/upload` | Upload | Upload training content |
| `/tokens` | Token Wallet | Balance, purchase, history |
| `/settings` | Settings | Profile, preferences |

---

## Training the AI (Adding Content)

### Step 1: Place Files

| Content Type | Folder | Formats |
|---|---|---|
| Textbooks / Notes | `backend/Medura_Train/textbooks/` | `.pdf`, `.md`, `.txt` |
| PYQ Papers | `backend/Medura_Train/PYQ/` | `.pdf`, `.md`, `.txt` |
| Web Content | `backend/Medura_Train/web_knowledge/` | `.md`, `.txt` |

> PDFs > 50 MB are auto-skipped. Create `.md` summaries for large textbooks.

### Step 2: Run Training

```bash
cd backend
python _train_all.py
```

This scans all folders, skips already-indexed files, chunks new content (~200 words each), and rebuilds the TF-IDF index.

### Alternative: Upload via UI

- Go to `/upload` or `/textbooks` → Uploads tab
- Or via API: `POST /api/ai/knowledge/scan/`

### Tips

- **Markdown works best** — chunks cleanly on headers
- Use descriptive filenames: `pharmacology_autonomic_drugs.md`
- Use headers and bullet points for better searchability

---

## Question Management

### Fixture-First Workflow

`questions_fixture.json` is the production source of truth. `build.sh` loads it during deploy.

### Methods to Add/Edit Questions

| Method | Best For |
|--------|----------|
| Django Admin (`/admin/`) | Editing individual questions via GUI |
| REST API | Programmatic bulk imports |
| Direct fixture edit | Careful manual JSON edits |
| CSV review workflow | Systematic answer corrections |

### After Any Changes

```bash
python _export_fixture.py          # Export DB → fixture
git add questions_fixture.json
git commit -m "update questions"
git push                           # Auto-deploys
```

### Fix Wrong Answers (CSV Workflow)

```bash
python _review_and_fix_answers.py export --year 2018   # Export to CSV
# Review in Excel, fill "Correct_Answer" column
python _review_and_fix_answers.py import questions_review_2018.csv --fix  # Apply
python _export_fixture.py                               # Export fixture
```

---

## API Keys Setup

Add to `backend/.env`:

```env
GROQ_API_KEY=gsk_...
CEREBRAS_API_KEY=csk-...
GEMINI_API_KEY=AIza...
GITHUB_TOKEN=ghp_...
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_API_KEY2=sk-or-...
COHERE_API_KEY=...
HUGGINGFACE_API_KEY=hf_...
MISTRAL_API_KEY=...
DEEPSEEK_API_KEY=sk-...
```

### Get Keys At

| Provider | URL |
|----------|-----|
| Groq | https://console.groq.com/keys |
| Cerebras | https://cloud.cerebras.ai |
| Gemini | https://aistudio.google.com/apikey |
| GitHub Models | https://github.com/settings/tokens |
| OpenRouter | https://openrouter.ai |
| Cohere | https://dashboard.cohere.com |
| HuggingFace | https://huggingface.co/settings/tokens |
| Mistral | https://console.mistral.ai/api-keys |
| DeepSeek | https://platform.deepseek.com/api_keys |

### Test Keys

```bash
cd backend
python test_api_keys.py
```

---

## Gmail Setup (Password Reset)

1. Enable **2-Step Verification** at https://myaccount.google.com/security
2. Create an **App Password** at https://myaccount.google.com/apppasswords (select Mail → Other → "CrackCMS")
3. Add to `.env`:
   ```env
   EMAIL_HOST_USER=crackwith.ai@gmail.com
   EMAIL_HOST_PASSWORD=abcd efgh ijkl mnop
   FRONTEND_URL=http://localhost:3000
   ```
4. In production (Render), set `FRONTEND_URL=https://crack-me-ai1.vercel.app`

---

## Ollama Setup (Local AI)

Ollama runs AI locally as the final fallback when all cloud providers fail.

### Install

- **Windows**: Download from https://ollama.com/download/windows
- **macOS**: `brew install ollama`
- **Linux**: `curl -fsSL https://ollama.com/install.sh | sh`

### Pull Model

```bash
ollama pull llama3.2:3b
```

### Verify

```bash
curl http://localhost:11434/api/tags
```

No API key needed. CrackCMS connects to `http://localhost:11434` automatically. To change model: `OLLAMA_MODEL=llama3.1:8b` in `.env`.

---

## Deployment

### Backend (Render)

- **Build command**: `./build.sh` (installs deps, migrates, loads fixture)
- **Start command**: `gunicorn crack_cms.wsgi:application`
- **Config**: `render.yaml` has all env var definitions

Required Render environment variables:
```
DJANGO_SECRET_KEY, GEMINI_API_KEY, GROQ_API_KEY, DEEPSEEK_API_KEY,
CEREBRAS_API_KEY, OPENROUTER_API_KEY, OPENROUTER_API_KEY2,
COHERE_API_KEY, GITHUB_TOKEN, HUGGINGFACE_API_KEY, MISTRAL_API_KEY,
CORS_ALLOWED_ORIGINS=https://crack-me-ai1.vercel.app,
CSRF_TRUSTED_ORIGINS=https://crack-me-ai1.vercel.app
```

### Frontend (Vercel)

- **Framework**: Next.js (auto-detected)
- **Config**: `vercel.json` has rewrites + security headers

Required Vercel environment variable:
```
NEXT_PUBLIC_API_URL=https://crackcms-backend.onrender.com/api
```

### CI/CD (GitHub Actions)

`.github/workflows/ci.yml` runs on push to `main`/`develop`:
1. Backend tests & lint (Python 3.12)
2. Frontend build & lint (Node 20)
3. Security scanning (Bandit + Safety)

---

## Testing

### Comprehensive Test Suite

```bash
cd backend
python test_all.py              # Run all tests
python test_all.py --quick      # Skip slow AI tests
python test_all.py --endpoints-only  # Only HTTP endpoint tests
python test_all.py --auth-only  # Only auth flow tests
```

Tests cover: database health, fixture integrity, API key connectivity, AI service, HTTP endpoints, configuration, and full auth flow.

### API Key Test

```bash
python test_api_keys.py
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Module not found | `pip install -r requirements.txt` (activate venv first) |
| Database errors | `python manage.py migrate` |
| AI not responding | Check `.env` API keys; run `python test_api_keys.py` |
| AI spinner infinite | Cerebras/Cohere timeout fixed; check 120s deadline |
| Knowledge base empty | `python _train_all.py` |
| Frontend build fails | `cd frontend && npm install && npm run build` |
| Flashcard not saving | Ensure CORS allows your frontend URL in Render dashboard |
| Reset AI knowledge | Delete `chroma_db/rag_store.sqlite3`, re-run `_train_all.py` |

---

## Security

- JWT authentication (1-day access, 7-day refresh tokens)
- django-axes brute-force protection (5 attempts → 30min lockout)
- CORS restricted to allowed origins
- Security headers (X-Content-Type-Options, X-Frame-Options, Referrer-Policy)
- Dependency scanning via GitHub Actions (Bandit + Safety + npm audit)

---

## License

Private repository. All rights reserved.
