# Project Overview

> **Crack_Me_AI** — AI-Powered UPSC Combined Medical Services (CMS) Exam Preparation Platform

---

## 1. Product Vision

CrackLabs' flagship product is a vertically-integrated medical exam-preparation platform that fuses a curated UPSC CMS question bank with multi-provider AI tutoring. The platform's long-term vision is to become the **default AI co-pilot for Indian medical competitive exam aspirants** — replacing scattered PDF dumps, Telegram groups, and offline coaching with a single, intelligent, adaptive study environment that:

- Grounds every AI response in **verified standard textbooks and prior-year questions (PYQs)** via Retrieval-Augmented Generation (RAG).
- Spreads AI load across **11 cloud providers + a local Ollama fallback** so the platform never hard-stops on a single provider outage or quota exhaustion.
- Persists user progress (attempts, streaks, bookmarks, flashcards) and converts it into actionable insights (weak-topic detection, score prediction, personalized study plans).
- Operates on a **token economy** that aligns free-tier usage with viral growth while monetizing heavy users via Razorpay subscriptions and token purchases.

---

## 2. Target Users

| Persona | Description | Primary Need |
|---|---|---|
| **UPSC CMS Aspirant** | Final-year MBBS / intern preparing for Combined Medical Services | High-yield MCQ practice + explanations |
| **NEET PG Aspirant** | Postgraduate medical entrance candidate | PYQ practice, adaptive tests, performance tracking |
| **Medical Student (general)** | Self-directed learner who wants to consolidate a topic | Concept explainers, mnemonics, RAG-grounded answers |
| **Coaching Admin / Content Owner** | EdTech operator seeding new content or moderating questions | Admin panel, knowledge-base upload, fixture export |
| **Premium Subscriber** | Paying user on Razorpay plan | Unlimited tokens, advanced analytics, deep study plans |

---

## 3. Business Goals

1. **Minimize vendor lock-in & cost risk** — 11-provider AI rotation + Ollama local fallback means a single API outage cannot take the platform offline.
2. **Monetize via freemium** — Daily/weekly free tokens drive acquisition; Razorpay subscriptions + token purchases drive revenue.
3. **Build a defensible moat** — The RAG store (TF-IDF over indexed textbooks and PYQs) is proprietary training data that becomes more valuable with every document ingested.
4. **Operate at low infra cost** — SQLite + free-tier AI quotas + Render free + Vercel free keep monthly burn near zero at low traffic.
5. **Ship a feature-complete product fast** — Fixture-first question workflow, CSV-driven answer review, and admin tooling compress content-update cycles from weeks to hours.

---

## 4. Core Value Proposition

> Every UPSC CMS aspirant gets a **personal AI tutor** that has read all the standard textbooks and last eight years of PYQs — and a **token-metered AI co-pilot** that explains any answer in seconds.

Four interlocking value layers:

1. **Question Bank** — 2,000+ verified MCQs with explanations, mnemonics, high-yield points, textbook references.
2. **AI Tutor** — RAG-grounded chat tutor, concept explainer, mnemonic generator, AI explain-after-answer with JSON-typed payload.
3. **Adaptive Testing** — Custom + PYQ-simulator tests with timed sessions, review mode, and analytics.
4. **Progress Intelligence** — Streaks, badges, leaderboards, topic-wise performance, weak-topic detection, score prediction, study roadmap.

---

## 5. Tech Stack

### Frontend

| Layer | Technology |
|---|---|
| Framework | Next.js **16.1.6** (App Router, `--webpack` dev server) |
| UI Runtime | React **19.2.4** |
| Language | TypeScript 5 |
| Styling | Tailwind CSS **4** + Radix UI primitives |
| State / Data | SWR, React Context (Dock, ExamTrack, Auth) |
| HTTP | Axios with interceptors + failover |
| Auth | `@supabase/ssr`, `@supabase/supabase-js`, `jwt-decode` |
| Charts | `recharts` |
| Markdown | `react-markdown` + `remark-breaks` |
| Theming | `next-themes` |
| Icons | `lucide-react` + custom icon manifest pipeline |
| Observability | `@datadog/browser-logs`, `@datadog/browser-rum` |
| Tests | `@playwright/test` |
| Lint | ESLint 9 + `eslint-config-next` |

### Backend

| Layer | Technology |
|---|---|
| Framework | Django **5.x** + DRF |
| Auth | `djangorestframework-simplejwt` + `django-axes` + Supabase bridge |
| Database | SQLite3 (default), Postgres-ready via `dj_database_url` |
| Background Tasks | `django-q2` |
| Cache | `django-redis` (optional; LocMem fallback) |
| Security | `django-axes`, `django-cors-headers`, security headers in `vercel.json` |
| RAG | Custom SQLite + TF-IDF implementation |
| PDF | PyMuPDF |
| TTS / Video | `edge-tts`, `moviepy` |
| Payments | `razorpay` |
| Observability | `sentry-sdk[django]`, `ddtrace`, `python-json-logger` |
| Server | `gunicorn` + `whitenoise` |

---

## 6. External Services

| Service | Purpose |
|---|---|
| **Render** | Backend hosting (gunicorn) |
| **Vercel** | Frontend hosting (Next.js) |
| **Supabase** | Identity provider + alternative Postgres DB |
| **Sentry** | Error tracking & tracing |
| **Datadog** | RUM + browser logs |
| **Google Analytics** | Web analytics |
| **Razorpay** | Subscriptions + token purchases |
| **Gmail SMTP** | Password-reset email |
| **GitHub LFS** | PDF textbook + sqlite storage |
| **GitHub Actions** | CI/CD |

---

## 7. AI Integrations (11 providers + local fallback)

| # | Provider | Model | Quota | Cost |
|---|---|---|---|---|
| 1 | Groq | Llama 3.3 70B | 30 RPM, 14,400 RPD | Free |
| 2 | Cerebras | Llama 3.1 8B | 30 RPM, ~1M tok/day | Free |
| 3 | Gemini | `gemini-2.0-flash`, `gemini-2.0-flash-lite` | 15 RPM, 1,500 RPD/model | Free |
| 4 | Cohere | Command-A | 20 RPM, 1,000 req/mo | Free |
| 5 | OpenRouter | Free models | 20 RPM | Free |
| 6 | OpenRouter2 | Free models (2nd key) | 20 RPM | Free |
| 7 | GitHub Models | GPT-4o Mini | 150 RPM, 15K RPD | Free (PAT) |
| 8 | HuggingFace | Llama 3.3 70B | ~10 RPM | Free |
| 9 | Mistral | `mistral-small` | ~30 RPM | Free |
| 10 | NVIDIA Mistral | Mistral 7B (NVIDIA API) | TBD | Free |
| 11 | DeepSeek | `deepseek-chat` | Pay-as-you-go | **Paid — tried LAST** |
| fallback | **Ollama** | `llama3.2:3b` (default) | Local, unlimited | Free |

Implementation: `backend/ai_engine/services.py` — round-robin counter (`threading.Lock`), 120 s deadline per request, 15–20 s per provider.

---

## 8. Third-Party APIs

| API | Used For |
|---|---|
| Supabase REST | Sign-up / sign-in / token issuance for Supabase-first auth |
| Razorpay Orders + Webhook | Subscription billing, token-pack purchases |
| Gmail SMTP (App Password) | Password reset emails |
| Google Tag Manager / GA4 | Funnel analytics |
| Google Apps Script (`google_apps_script.js`) | Sheet-driven content review / exports |
| Sentry DSN | Server + browser error reporting |

---

## 9. Repository Structure

```
crack_cms/
├── README.md                   # User-facing setup & API reference
├── CLAUDE.md                   # Claude Code orientation
├── docs/                       # Documentation (this folder — single source of truth)
├── frontend/                   # Next.js 16 app
├── backend/                    # Django 5 backend
│   ├── crack_cms/              # Project (settings, root URLs)
│   ├── accounts/               # Users, JWT, tokens, devices
│   ├── questions/              # MCQ bank, flashcards, discussions
│   ├── tests_engine/           # Adaptive + PYQ tests
│   ├── analytics/              # Stats, streaks, roadmap, feedback
│   ├── ai_engine/              # 11-provider orchestrator + RAG
│   ├── textbooks/              # Indexed textbook library
│   ├── resources/              # UPSC exam resource catalog
│   ├── video_engine/           # edge-tts + moviepy slides
│   ├── jobs/                   # Career / job listings
│   ├── chroma_db/              # rag_store.sqlite3 (TF-IDF vectors)
│   ├── Medura_Train/           # Source documents for RAG ingestion
│   ├── build.sh                # Render deploy contract
│   └── requirements.txt
├── mobile-app/                 # Companion mobile
├── scripts/                    # Root-level utility scripts
├── data_dump*.json             # Periodic DB dumps
└── .github/                    # CI workflows + Copilot + skills + agents
```

---

## 10. Folder Organization Philosophy

- **`backend/`** follows Django's app-per-bounded-context convention (`accounts`, `questions`, `ai_engine`, …). Each app owns its models, views, serializers, urls, admin, and migrations.
- **`frontend/src/app/`** mirrors user-facing features as Next.js routes. Shared primitives live under `src/components/` and `src/lib/`.
- **`backend/Medura_Train/`** is the ingestion source of truth for RAG — place new PDFs/MD/TXT in `textbooks/`, `PYQ/`, or `web_knowledge/` and run `_train_all.py`.
- **`backend/chroma_db/`** holds the materialized TF-IDF index (committed via Git LFS) — the cache layer between source documents and the live AI calls.
- **`backend/questions_fixture.json`** is the production seed; the deploy pipeline (`build.sh`) loads it after migrations. **All question edits must end with `_export_fixture.py`**.
- **`docs/`** is the single documentation source — no parallel directories (no `.docs/`).
