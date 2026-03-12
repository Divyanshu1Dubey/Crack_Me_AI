# CrackCMS — System Architecture

## Overview

CrackCMS is a full-stack UPSC CMS exam preparation platform with AI-powered features.

```
┌─────────────────────────────────────────────────────────────────┐
│                    FRONTEND (Next.js 16)                         │
│  ┌──────────┬───────────┬──────────┬──────────┬──────────┐      │
│  │Dashboard │ Questions │ AI Tutor │Flashcards│  Admin   │      │
│  │          │ Bank      │          │          │  Panel   │      │
│  └────┬─────┴────┬──────┴────┬─────┴────┬─────┴────┬─────┘      │
│       │ Sidebar, Header, SearchDialog, ThemeToggle  │            │
│       └────────────────┬────────────────────────────┘            │
│                        │ Axios (JWT Bearer)                      │
└────────────────────────┼─────────────────────────────────────────┘
                         │
┌────────────────────────┼─────────────────────────────────────────┐
│                    BACKEND (Django 5 + DRF)                      │
│  ┌─────────┬───────────┼───────────┬──────────┬──────────┐      │
│  │accounts │ questions │ ai_engine │analytics │tests_eng │      │
│  │(JWT+    │(CRUD+     │(7 AI      │(topics,  │(test     │      │
│  │ tokens) │ bookmark+ │ providers │ streaks, │ engine)  │      │
│  │         │ discuss)  │ + RAG)    │ badges)  │          │      │
│  └────┬────┴────┬──────┴────┬──────┴────┬─────┴────┬─────┘      │
│       │         │           │           │          │             │
│  ┌────┴─────────┴───────────┴───────────┴──────────┴─────┐      │
│  │                    SQLite Database                      │      │
│  └────────────────────────────────────────────────────────┘      │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐       │
│  │ ChromaDB/    │  │ Medura_Train/│  │ Cache (Redis/    │       │
│  │ SQLite RAG   │  │ (textbooks,  │  │  LocMem)         │       │
│  │              │  │  PYQ, web)   │  │                  │       │
│  └──────────────┘  └──────────────┘  └──────────────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Frontend | Next.js (App Router) | 16.1 |
| UI Components | React + Radix UI + Tailwind CSS | 19 / 4 |
| State | React hooks + Axios | - |
| Backend | Django + DRF | 5.x |
| Auth | SimpleJWT | 5.3+ |
| Database | SQLite3 | - |
| AI Providers | Groq, Cerebras, Gemini, Cohere, OpenRouter, GitHub, DeepSeek | - |
| RAG | TF-IDF (SQLite) + ChromaDB | - |
| Cache | Redis (optional) / LocMemCache | - |
| Monitoring | Sentry (optional) | - |
| CI/CD | GitHub Actions | - |
| Deployment | Render (backend) + Vercel (frontend) | - |

## Backend Apps

### accounts
- `CustomUser` (AbstractUser) — role, phone, target_exam, avatar_url
- `TokenBalance` — free daily/weekly + purchased tokens, SM-2-style consumption
- `TokenConfig` (singleton) — platform-wide token limits
- JWT auth with access (1 day) + refresh (7 day) tokens
- Password reset via Gmail SMTP
- **Security**: django-axes brute-force protection (5 attempts, 30min lockout)

### questions
- `Question` — 2004+ PYQs with 15+ fields (options, explanation, mnemonic, textbook refs, concept_tags)
- `QuestionBookmark`, `QuestionFeedback`, `Discussion`, `DiscussionVote`
- `Note`, `Flashcard` (SM-2 spaced repetition)
- `FlashcardAnalyticsView` — retention rate, interval distribution

### ai_engine
- `AIService` — 7-provider round-robin with 60s deadline
- RAG pipeline (TF-IDF + ChromaDB) for textbook-grounded answers
- `explain_after_answer()` — rich JSON explanation with caching
- Multi-model voting for batch enrichment consensus
- Quality scoring function for AI response validation

### analytics
- `UserTopicPerformance`, `DailyActivity`, `StudyStreak`, `Badge`
- Dashboard, weak topics, score prediction, activity heatmap

### tests_engine
- Adaptive test generation, PYQ simulation, attempt tracking

## Frontend Pages

| Route | Component | Features |
|-------|-----------|----------|
| `/dashboard` | Dashboard | Stats, streaks, quick actions |
| `/questions` | QuestionBank | Filters, keyboard nav (A-D/N/P), AI analysis, discussions |
| `/ai-tutor` | AI Tutor | RAG-powered tutoring, study plans |
| `/flashcards` | Flashcards | SM-2 review, analytics, CRUD |
| `/tests` | Tests | Adaptive tests, PYQ simulation |
| `/analytics` | Analytics | Performance charts, weak topics |
| `/admin` | Admin | Users, tokens, feedback queue |

## API Architecture

- Base URL: `/api/`
- Auth: `Authorization: Bearer <jwt_token>`
- Rate limiting: django-axes (5 attempts, 30min lockout on login)
- Pagination: 20 items/page (PageNumberPagination)
- Filters: DjangoFilterBackend + SearchFilter + OrderingFilter

## AI Pipeline

```
User Question → Token Check → RAG Search (optional) →
  Round-Robin Provider Selection →
    Groq → Cerebras → Gemini → Cohere →
    OpenRouter → GitHub → DeepSeek →
  Response Parsing (JSON) → Quality Score Check → Cache → Return
```

## Security

- JWT authentication (1-day access, 7-day refresh)
- django-axes brute-force protection
- CORS configuration (allowed origins only)
- CSRF trusted origins
- Password strength validation (backend + frontend indicator)
- Content-Security headers via Django security middleware
- Dependency scanning via Dependabot + npm audit + safety
