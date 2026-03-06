# Crack CMS — Complete Project Documentation

> UPSC CMS (Combined Medical Services) Exam Preparation Platform
> Django Backend + Next.js Frontend + AI-Powered RAG System

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [How to Start the App](#how-to-start-the-app)
3. [Adding New Content (Training the AI)](#adding-new-content-training-the-ai)
4. [Adding New Questions to the Question Bank](#adding-new-questions-to-the-question-bank)
5. [Folder Structure Explained](#folder-structure-explained)
6. [File-by-File Reference](#file-by-file-reference)
7. [All Management Commands](#all-management-commands)
8. [API Endpoints](#api-endpoints)
9. [AI System Architecture](#ai-system-architecture)
10. [Frontend Pages](#frontend-pages)
11. [Token System](#token-system-ai-usage-limits--revenue)
12. [API Keys & Daily Limits](#api-keys--daily-limits)
13. [Super Admin Token Management](#super-admin-token-management)
14. [Database Info](#database-info)
15. [Current Content Stats](#current-content-stats)
16. [Troubleshooting](#troubleshooting)

---

## Project Overview

- **Backend**: Django 5.x + Django REST Framework, SQLite database
- **Frontend**: Next.js 16, React 19, TypeScript, Tailwind CSS 4, Recharts
- **AI Models**: Google Gemini 2.0 Flash + Groq LLama 3.3 70B + DeepSeek Chat — round-robin load balanced
- **RAG System**: SQLite-based TF-IDF retrieval — searches through indexed textbooks/notes to give AI grounded, accurate answers
- **Training Data**: 79 books/sources, 4,972+ chunks in the knowledge base

---

## How to Start the App

### Backend (Django API Server)
```powershell
cd c:\Users\DIVYANSHU\Desktop\crack_cms\backend
.\venv\Scripts\Activate.ps1
python manage.py runserver 8000
```
Runs on: **http://localhost:8000**

### Frontend (Next.js)
```powershell
cd c:\Users\DIVYANSHU\Desktop\crack_cms\frontend
npm run dev
```
Runs on: **http://localhost:3000**

### Build Frontend for Production
```powershell
cd frontend
npm run build
npm start
```

---

## Adding New Content (Training the AI)

This is the most important section. When you find new textbooks, notes, or question papers, here's exactly what to do:

### Step 1: Place the File in the Right Folder

| Content Type | Where to Put It | Supported Formats |
|---|---|---|
| **Textbook / Notes** | `backend/Medura_Train/textbooks/` | `.pdf`, `.md`, `.txt` |
| **Previous Year Questions (PYQ)** | `backend/Medura_Train/PYQ/` | `.pdf`, `.md`, `.txt` |
| **General Knowledge / Web Content** | `backend/Medura_Train/web_knowledge/` | `.md`, `.txt` |

**Examples:**
- Found a Robbins Pathology PDF? → Put it in `Medura_Train/textbooks/`
- Found CMS 2026 question paper? → Put it in `Medura_Train/PYQ/`
- Found useful medical notes online? → Save as `.md` file in `Medura_Train/web_knowledge/`

> **PDF Size Limit**: PDFs larger than 50 MB are automatically skipped (full textbook PDFs like Ghai, Nelson are too large). For big textbooks, create `.md` summary notes instead — they work much better for the AI anyway.

### Step 2: Run the Training Script

```powershell
cd c:\Users\DIVYANSHU\Desktop\crack_cms\backend
.\venv\Scripts\Activate.ps1
python _train_all.py
```

**What this does:**
1. Scans all 3 folders (textbooks, PYQ, web_knowledge)
2. Skips files already indexed (won't duplicate)
3. Chunks each file into small searchable pieces (200 words each)
4. Stores chunks in `chroma_db/rag_store.sqlite3`
5. Rebuilds the search index (TF-IDF)

**Output will show:**
```
Found 87 files to index:
  [textbook] Your New Book Name
  ...
[1/87] Indexing: Your New Book Name
  [OK] Added 12 new chunks
...
Training complete!
New chunks added: 12
Total chunks in knowledge base: 4984
```

### Step 3: That's It!

The AI tutor, mnemonic generator, question generator, and all AI features will now automatically use the new content. No restart needed — the RAG pipeline reads from the database live.

### Alternative: Upload via Website

You can also upload files through the website:
1. Go to **http://localhost:3000/upload** (Upload page)
2. Or go to **http://localhost:3000/textbooks** → Uploads tab
3. Upload your PDF/MD/TXT file
4. It gets auto-indexed into the knowledge base

### Alternative: Scan for New Files via API

```powershell
# Scans Medura_Train/ for any new unindexed files
Invoke-RestMethod -Uri 'http://localhost:8000/api/ai/knowledge/scan/' -Method POST
```

---

## Adding New Questions to the Question Bank

### Method 1: From Text File
If you have questions in a text file format:
```powershell
python manage.py import_txt --file "path/to/questions.txt" --year 2025 --subject Medicine
```

### Method 2: From PYQ PDFs
If you have UPSC CMS question paper PDFs:
```powershell
# Put PDFs in Medura_Train/PYQ/ first, then:
python manage.py import_pyqs
# Or for a specific year:
python manage.py import_pyqs --year 2026
```


### Method 3: AI-Generated Questions
Use the website: **http://localhost:3000/generate**
- Select subject, topic, difficulty
- AI generates new questions using textbook knowledge
- Questions are saved to the database


### Method 4: Scrape from Markdown Notes
```powershell
python manage.py scrape_pyqs
```
This parses markdown files in Medura_Train/ for MCQ-formatted questions.

### Method 5: Django Admin Panel (Manual Entry)
1. Go to **http://localhost:8000/admin/**
2. Login with your superuser account
3. Navigate to **Questions → Questions** → click **Add Question**
4. Fill in:
   - **Subject** — select from dropdown (Medicine, Surgery, PSM, OBG, Pediatrics)
   - **Topic** — select the topic within the subject
   - **Question text** — the full question stem (supports markdown: `**bold**`, `*italic*`)
   - **Option A/B/C/D** — the four options
   - **Correct answer** — `A`, `B`, `C`, or `D`
   - **Explanation** — detailed explanation shown after answering
   - **Year** — e.g., 2025. Questions with years show as "PYQ 2025" in the question bank
   - **Difficulty** — easy / medium / hard
   - **Mnemonic** — optional memory trick
   - **Book name / Chapter / Page** — optional textbook reference
   - **Concept tags** — optionally add tags like "Craniosynostosis", "Neonatology"
5. Click **Save** — question is immediately visible in the Question Bank page

### Method 6: API (Programmatic)
```bash
curl -X POST http://localhost:8000/api/questions/questions/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "subject": 1,
    "topic": 5,
    "question_text": "Which of the following is the most common cause of...?",
    "option_a": "Option A text",
    "option_b": "Option B text",
    "option_c": "Option C text",
    "option_d": "Option D text",
    "correct_answer": "B",
    "explanation": "B is correct because...",
    "difficulty": "medium",
    "year": 2025
  }'
```

---

## Folder Structure Explained

```
crack_cms/
├── backend/                          # Django Backend
│   ├── manage.py                     # Django management entry point
│   ├── _train_all.py                 # ⭐ MAIN TRAINING SCRIPT
│   ├── db.sqlite3                    # Main database (users, questions, tests)
│   ├── venv/                         # Python virtual environment
│   │
│   ├── Medura_Train/                 # ⭐ ALL TRAINING DATA GOES HERE
│   │   ├── textbooks/                # Textbook notes & PDFs
│   │   │   ├── anatomy_cms_notes.md
│   │   │   ├── physiology_cms_notes.md
│   │   │   ├── biochemistry_cms_notes.md
│   │   │   ├── pharmacology_extended_cms_notes.md
│   │   │   ├── pathology_cms_notes.md
│   │   │   ├── microbiology_extended_cms_notes.md
│   │   │   ├── forensic_medicine_extended_cms_notes.md
│   │   │   ├── ophthalmology_cms_notes.md
│   │   │   ├── ent_cms_notes.md
│   │   │   ├── dermatology_cms_notes.md
│   │   │   ├── psychiatry_cms_notes.md
│   │   │   ├── anesthesia_cms_notes.md
│   │   │   ├── radiology_cms_notes.md
│   │   │   ├── ghai_pediatrics_cms_notes.md
│   │   │   ├── harrisons_medicine_cms_notes.md
│   │   │   ├── parks_psm_cms_notes.md
│   │   │   └── surgery_obg_cms_notes.md
│   │   ├── PYQ/                      # Previous Year Question Papers
│   │   │   ├── 2018 Paper 1.pdf
│   │   │   ├── ...through...
│   │   │   ├── 2025 Paper 2.pdf
│   │   │   └── cms_pyq_database_2018_2024.md
│   │   └── web_knowledge/            # 51 scraped medical knowledge articles
│   │       ├── med_diabetes.md
│   │       ├── med_hypertension.md
│   │       ├── surg_appendicitis.md
│   │       └── ... (51 files)
│   │
│   ├── chroma_db/                    # AI Knowledge Base Storage
│   │   └── rag_store.sqlite3         # ⭐ The indexed knowledge (4,972 chunks)
│   │
│   ├── ai_engine/                    # AI Module
│   │   ├── services.py               # AI Service (Gemini + Groq integration)
│   │   ├── rag_pipeline.py           # RAG search engine
│   │   ├── document_processor.py     # PDF/MD text extraction & chunking
│   │   ├── views.py                  # AI API endpoints
│   │   └── management/commands/      # AI-related commands
│   │
│   ├── questions/                    # Question Bank Module
│   ├── tests_engine/                 # Test/Exam Module
│   ├── analytics/                    # Performance Analytics Module
│   ├── accounts/                     # User Auth Module
│   ├── textbooks/                    # Textbook Library Module
│   └── resources/                    # UPSC Resources Module
│
├── frontend/                         # Next.js Frontend
│   └── src/
│       ├── app/                      # All pages (21 routes)
│       ├── components/               # Sidebar, shared components
│       └── lib/                      # API client, auth context
│
└── DOCUMENTATION.md                  # ⭐ This file
```

---

## File-by-File Reference

### Frontend — Key Files

| File | Purpose |
|------|---------|
| `frontend/src/lib/api.ts` | Centralized Axios API client with all endpoint functions (questions, AI, tests, analytics, auth tokens). JWT auto-attached. |
| `frontend/src/lib/auth.tsx` | AuthProvider context — login, register, logout, token refresh. Wraps entire app. |
| `frontend/src/components/Sidebar.tsx` | Navigation sidebar — logo, user card, token balance widget, nav links, theme toggle, settings, logout. Responsive. |
| `frontend/src/components/ThemeToggle.tsx` | Dark/Light theme toggle button (Midnight Aurora / Crystal Cloud). Uses next-themes. |
| `frontend/src/components/ThemeProvider.tsx` | Wraps next-themes ThemeProvider for the app. |
| `frontend/src/app/layout.tsx` | Root layout — HTML wrapper, fonts, ThemeProvider, AuthProvider. |
| `frontend/src/app/page.tsx` | Landing page — hero section, features, CTA. |
| `frontend/src/app/login/page.tsx` | Login form with JWT authentication. |
| `frontend/src/app/register/page.tsx` | Registration form for new users. |
| `frontend/src/app/dashboard/page.tsx` | Dashboard — stats cards, performance charts, subject progress, recent tests. |
| `frontend/src/app/questions/page.tsx` | **Question Bank** — filterable question list (left), detail view with AI analysis (right). Helper functions: `FormattedText`, `stripMarkdown`, `cleanOptionText`, `cleanAiText`. |
| `frontend/src/app/tests/page.tsx` | Test list — create new tests, view past test scores. |
| `frontend/src/app/tests/[id]/page.tsx` | **Test Session** — timed MCQ test mode + review mode with AI deep analysis. |
| `frontend/src/app/ai-tutor/page.tsx` | AI Tutor — real-time chat with Gemini/Groq AI. Markdown responses. |
| `frontend/src/app/generate/page.tsx` | AI Question Generator — generate MCQs by subject/topic/difficulty. |
| `frontend/src/app/simulator/page.tsx` | CMS exam simulator — simulate real exam conditions. |
| `frontend/src/app/analytics/page.tsx` | Performance analytics — accuracy trends, subject breakdown, study streaks. |
| `frontend/src/app/roadmap/page.tsx` | AI-generated study roadmap based on weak topics. |
| `frontend/src/app/bookmarks/page.tsx` | Bookmarked questions list. |
| `frontend/src/app/textbooks/page.tsx` | Textbook library — browse indexed textbooks and chapters. |
| `frontend/src/app/resources/page.tsx` | UPSC resources — exam docs, guides. |
| `frontend/src/app/upload/page.tsx` | Upload training content to AI knowledge base. |
| `frontend/src/app/tokens/page.tsx` | **Token Wallet** — balance cards, usage bars, purchase options, transaction history. |
| `frontend/src/app/trends/page.tsx` | PYQ exam trend analysis. |
| `frontend/src/app/settings/page.tsx` | User settings & preferences. |
| `frontend/src/app/globals.css` | All CSS — theme variables, glass-card, sidebar, review options, animations, token widgets. |

### Backend — Key Files

| File | Purpose |
|------|---------|
| `backend/manage.py` | Django management entry point. |
| `backend/_train_all.py` | **Master training script** — indexes all textbooks, PYQs, web articles into RAG knowledge base. |
| `backend/crack_cms/settings.py` | Django settings — installed apps, middleware, database config, JWT config. |
| `backend/crack_cms/urls.py` | Root URL router — maps `/api/auth/`, `/api/questions/`, `/api/tests/`, `/api/ai/`, etc. |
| `backend/accounts/models.py` | **User model** (`CustomUser`) + Token models (`TokenBalance`, `TokenConfig`, `TokenTransaction`). |
| `backend/accounts/views.py` | Auth views — register, login, profile, token balance, token purchase, transaction history. |
| `backend/accounts/serializers.py` | DRF serializers for user, tokens, transactions. |
| `backend/accounts/urls.py` | Auth URL patterns — `/register/`, `/login/`, `/tokens/`, etc. |
| `backend/accounts/admin.py` | Admin panel config for users and token models. |
| `backend/ai_engine/services.py` | **Core AI Service** — `AIService` class with Gemini/Groq integration, RAG retrieval, prompt engineering, JSON parsing with fallback. |
| `backend/ai_engine/views.py` | AI API views — tutor, explain, mnemonic, analyze-answer, generate-questions. All consume 1 token. Admin bypass. |
| `backend/ai_engine/rag_pipeline.py` | **RAG engine** — TF-IDF search across SQLite knowledge chunks. |
| `backend/ai_engine/sqlite_rag.py` | SQLite-based vector store for RAG chunks. |
| `backend/ai_engine/document_processor.py` | PDF/Markdown text extraction and chunking for indexing. |
| `backend/ai_engine/pyq_extractor.py` | Extracts MCQs from PYQ PDF papers using AI. |
| `backend/ai_engine/auto_ingest.py` | Auto-scan and index new files in Medura_Train/. |
| `backend/ai_engine/similar_questions.py` | Find similar PYQs based on content similarity. |
| `backend/questions/models.py` | Question, Subject, Topic, QuestionFeedback models. |
| `backend/questions/views.py` | Question CRUD, filtering, bookmarks, feedback. |
| `backend/tests_engine/models.py` | Test, TestResult models (test creation, submission, scoring). |
| `backend/tests_engine/views.py` | Test API — create, submit, review results. |
| `backend/analytics/models.py` | DailyActivity, TopicPerformance models. |
| `backend/analytics/views.py` | Dashboard stats, performance data, study roadmap. |
| `backend/textbooks/models.py` | Textbook, TextbookChapter models. |
| `backend/resources/views.py` | UPSC resources, exam guide, document catalog. |

---

## All Management Commands

Run these from `backend/` with venv activated:

| Command | What It Does |
|---------|-------------|
| `python _train_all.py` | **⭐ Master training — indexes ALL content into AI knowledge base** |
| `python manage.py train_ai` | Alternative training via Django command (same effect) |
| `python manage.py index_textbooks` | Index only textbook PDFs/notes |
| `python manage.py import_pyqs` | Import PYQ questions from PDFs into question bank |
| `python manage.py import_pyq_pdfs --dir <path>` | Import MCQs from a directory of PYQ PDFs |
| `python manage.py import_txt --file <path>` | Import questions from a text file |
| `python manage.py scrape_pyqs` | Scrape questions from markdown notes |
| `python manage.py process_pdfs --file <path>` | Process PDFs (both index + extract questions) |
| `python manage.py reclassify_pyqs` | Re-classify questions into correct subjects |
| `python manage.py seed_data` | Seed database with sample subjects/topics/questions |
| `python manage.py runserver 8000` | Start the backend API server |
| `python manage.py createsuperuser` | Create admin account |
| `python manage.py migrate` | Apply database migrations |

---

## API Endpoints

### Authentication (`/api/auth/`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register/` | Register new user |
| POST | `/api/auth/login/` | Login (returns token) |
| GET | `/api/auth/profile/` | Get user profile |
| PUT | `/api/auth/profile/` | Update profile |
| GET | `/api/auth/tokens/` | Get token balance & limits |
| POST | `/api/auth/tokens/purchase/` | Purchase tokens |
| GET | `/api/auth/tokens/history/` | Token transaction history |

### Questions (`/api/questions/`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/questions/subjects/` | List all subjects |
| GET | `/api/questions/topics/` | List topics (filter by subject) |
| GET | `/api/questions/questions/` | List questions (filter by subject/topic/difficulty) |
| POST | `/api/questions/questions/{id}/bookmark/` | Toggle bookmark |
| GET | `/api/questions/questions/my_bookmarks/` | Get bookmarked questions |

### Tests (`/api/tests/`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/tests/tests/` | List user's tests |
| POST | `/api/tests/tests/` | Create new test |
| POST | `/api/tests/tests/{id}/submit/` | Submit test answers |
| GET | `/api/tests/tests/{id}/review/` | Review test results |

### AI Engine (`/api/ai/`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/ai/tutor/` | Ask AI tutor (RAG-enhanced) |
| POST | `/api/ai/mnemonic/` | Generate mnemonic |
| POST | `/api/ai/explain/` | Explain a concept |
| POST | `/api/ai/analyze-answer/` | Analyze user's answer |
| POST | `/api/ai/rag-answer/` | Direct RAG search + answer |
| POST | `/api/ai/rag-search/` | Raw RAG search (returns chunks) |
| POST | `/api/ai/study-plan/` | Generate study plan |
| POST | `/api/ai/high-yield/` | Get high-yield topics |
| POST | `/api/ai/generate-questions/` | AI-generate new questions |
| POST | `/api/ai/knowledge/upload/` | Upload file to knowledge base |
| POST | `/api/ai/knowledge/scan/` | Scan & index new files |
| GET | `/api/ai/knowledge/stats/` | Knowledge base statistics |

### Analytics (`/api/analytics/`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/analytics/dashboard/` | Dashboard stats |
| GET | `/api/analytics/performance/` | Performance over time |
| GET | `/api/analytics/topics/` | Topic-wise performance |
| GET | `/api/analytics/roadmap/` | Study roadmap |

### Textbooks (`/api/textbooks/`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/textbooks/books/` | List textbooks |
| POST | `/api/textbooks/uploads/` | Upload textbook PDF |

### Resources (`/api/resources/`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/resources/catalog/` | List UPSC documents |
| GET | `/api/resources/download/{id}/` | Download a resource |
| GET | `/api/resources/exam-guide/` | CMS exam guide info |

---

## AI System Architecture

```
User Question
     │
     ▼
┌─────────────┐     ┌──────────────────┐
│  AI Service  │────▶│  RAG Pipeline     │
│ (services.py)│     │ (rag_pipeline.py) │
└──────┬──────┘     └────────┬─────────┘
       │                     │
       │              ┌──────▼──────┐
       │              │ SQLite DB    │
       │              │ rag_store    │
       │              │ (4,972 chunks│
       │              │  79 books)   │
       │              └──────┬──────┘
       │                     │
       │         Top 3-5 relevant chunks
       │                     │
       ▼                     ▼
┌─────────────────────────────────┐
│  Combined Prompt:                │
│  System Prompt + RAG Context +   │
│  User Question                   │
└──────────────┬──────────────────┘
               │
    ┌──────────▼──────────┐
    │ Gemini 2.0 Flash    │──── Primary
    │ (Google AI)         │
    └──────────┬──────────┘
               │ (if fails)
    ┌──────────▼──────────┐
    │ Groq LLama 3.3 70B  │──── Fallback
    │ (Groq Cloud)        │
    └─────────────────────┘
```

### How RAG Works:
1. **Indexing** (one-time): Each document is split into ~200-word chunks → stored in SQLite with TF-IDF tokens
2. **Search** (every query): User's question is tokenized → TF-IDF score calculated against all chunks → top matches returned
3. **Answer** (every query): Top chunks are included in the AI prompt as context → AI generates answer grounded in actual textbook content

---

## Frontend Pages (21 Routes)

| Route | Page | Description |
|-------|------|-------------|
| `/` | Home/Landing | Welcome page |
| `/login` | Login | User authentication |
| `/register` | Register | New user signup |
| `/dashboard` | Dashboard | Overview stats, recent activity |
| `/questions` | Question Bank | Browse & practice questions, search, filter |
| `/tests` | Tests | Create and take timed tests |
| `/tests/[id]` | Test Session | Active test with timer, review mode |
| `/ai-tutor` | AI Tutor | Chat with AI, ask medical questions |
| `/generate` | Question Generator | AI-powered question generation |
| `/simulator` | PYQ Simulator | Simulate real CMS exam conditions |
| `/analytics` | Analytics | Performance charts, accuracy trends |
| `/roadmap` | Study Roadmap | AI-generated study plan, weak topics |
| `/bookmarks` | Bookmarks | Saved/bookmarked questions |
| `/textbooks` | Textbook Library | Browse textbooks, upload PDFs |
| `/resources` | Resources | UPSC documents, exam guide |
| `/upload` | Upload | Upload training content |
| `/settings` | Settings | Profile, preferences |
| `/tokens` | AI Tokens | View balance, buy tokens, transaction history |
| `/trends` | Exam Trends | PYQ trend analysis |

---

## Database Info

- **Main DB**: `backend/db.sqlite3` — users, questions, tests, analytics
- **RAG DB**: `backend/chroma_db/rag_store.sqlite3` — AI knowledge chunks
- **Admin Panel**: http://localhost:8000/admin/ (need superuser account)

### Create Admin Account:
```powershell
cd backend
.\venv\Scripts\Activate.ps1
python manage.py createsuperuser
```

---

## Current Content Stats

### Knowledge Base (RAG)
- **4,972 chunks** across **79 books/sources**
- 17 textbook note files (Anatomy, Physiology, Biochemistry, Pharmacology, Pathology, Microbiology, Forensic Medicine, Ophthalmology, ENT, Dermatology, Psychiatry, Anesthesia, Radiology, Medicine, Pediatrics, PSM, Surgery & OBG)
- 16 PYQ papers (2018-2025, both papers)
- 51 web knowledge articles
- Covering ALL UPSC CMS subjects

### Question Bank
- 806+ questions
- 5 subjects, 47 topics
- Questions from 2018-2025

### Subjects Covered
| Subject | Paper | Key Topics |
|---------|-------|------------|
| General Medicine | Paper 1 | Cardiology, Nephrology, Endocrinology, Neurology, Respiratory, GI, Hematology, Infectious Disease |
| Pediatrics | Paper 1 | Growth & Development, Immunization, Neonatology, Genetics, Nutrition |
| Surgery | Paper 2 | General Surgery, Orthopedics, Urology, Plastic Surgery, ENT, Ophthalmology |
| Obstetrics & Gynaecology | Paper 2 | Antenatal, Labor, High-Risk Pregnancy, Gynaecological Disorders |
| Preventive & Social Medicine | Paper 2 | Epidemiology, Biostatistics, Health Programs, Nutrition, Environmental Health |

---

## Token System (AI Usage Limits & Revenue)

### Overview
Every AI-powered feature (tutor, mnemonics, explain, analyze, generate questions, study plan) costs **1 token** per request. This prevents API cost overrun and creates a revenue stream.

### How It Works

| Feature | Free Tokens | Details |
|---------|-------------|---------|
| **Daily Free Tokens** | 10/day | Resets at midnight (auto-detected) |
| **Weekly Free Tokens** | 50/week | Resets every 7 days |
| **Purchased Tokens** | Never expire | Used after free tokens are exhausted |
| **Feedback Credits** | +2 per correct report | Earned by reporting question errors (verified by admin) |
| **Admin Accounts** | Unlimited | Admins (superusers or `is_staff`) bypass all token limits |

### Token Consumption Priority
1. **Free daily/weekly tokens** are consumed first
2. **Feedback credits** are consumed next
3. **Purchased tokens** are consumed last

### AI Features That Cost Tokens (1 token each)
- AI Tutor (`/api/ai/tutor/`)
- Mnemonic Generator (`/api/ai/mnemonic/`)
- Concept Explainer (`/api/ai/explain/`)
- Question Analyzer (`/api/ai/analyze/`)
- Answer Explanation (`/api/ai/explain-answer/`)
- RAG Answer (`/api/ai/rag-answer/`)
- Study Plan (`/api/ai/study-plan/`)
- AI Question Generator (`/api/ai/generate-questions/`)

### Features That Are FREE (no token cost)
- RAG Search (vector search only, no AI generation)
- Knowledge Upload/Scan/Stats (admin operations)
- High-Yield Topics (GET endpoint)
- All Question Bank browsing, test-taking, analytics

### Configuring Token Limits (Admin Panel)

1. Go to **http://localhost:8000/admin/**
2. Navigate to **Accounts → Token configs**
3. Edit the single config record to change:
   - `free_daily_tokens` — default: 10
   - `free_weekly_tokens` — default: 50
   - `token_price` — default: ₹1.00
   - `feedback_reward` — default: 2 tokens per correct report
   - `min_purchase` / `max_purchase` — purchase limits

### Making Your Account Admin (Unlimited Tokens)

```powershell
cd backend
.\venv\Scripts\Activate.ps1
python manage.py shell
```
```python
from accounts.models import CustomUser
u = CustomUser.objects.get(username='your_username')
u.is_staff = True  # This gives admin token bypass
u.save()
```
Or use `python manage.py createsuperuser` to create an admin account.

### Revenue: Token Purchases

When users buy tokens:
1. Frontend sends `POST /api/auth/tokens/purchase/` with `{ amount: 50 }`
2. Backend credits the tokens to the user's balance
3. A `TokenTransaction` record is created for audit

**TODO**: Integrate Razorpay/Stripe for real payment processing. Currently, the purchase endpoint credits tokens directly (for testing). In production:
1. Create a Razorpay order on the backend
2. Frontend opens Razorpay checkout
3. On success, Razorpay sends `payment_id` to your backend
4. Backend verifies payment with Razorpay API
5. Only then credits the tokens

### How Feedback Credits Work

1. User reports a question error (via the Flag button on question pages)
2. Admin reviews at **http://localhost:8000/admin/** → Question Feedbacks
3. Admin marks feedback as resolved: `PATCH /api/questions/feedback/{id}/resolve/`
4. System auto-credits 2 tokens to the reporter
5. A `TokenTransaction` (type: `feedback_reward`) is created

### Frontend Token Integration

- **Sidebar**: Shows live token balance widget (updates on every page navigation)
- **Tokens page** (`/tokens`): Full balance view, usage bars, purchase options, transaction history
- **AI buttons**: "Generate AI Analysis" button appears after answering questions (click-only, not auto)
- **429 Error Handling**: When tokens are exhausted, a friendly "Buy Tokens" banner appears instead of a generic error

---

## API Keys & Daily Limits

### Configured Providers (Round-Robin Load Balanced)

The AI system rotates across **3 providers** to maximize throughput and prevent any single provider from being exhausted first. Each request goes to the next provider in rotation (Gemini → Groq → DeepSeek → Gemini → ...). If one provider fails, it automatically tries the next.

| Provider | Model | Free Tier Limit | Rate Limit | Cost (Paid) |
|----------|-------|-----------------|------------|-------------|
| **Google Gemini** | gemini-2.0-flash, gemini-2.0-flash-lite, gemini-1.5-flash, gemini-1.5-pro | **1,500 requests/day per model** (×4 models = ~6,000/day) | 15 requests/minute | Free tier only |
| **Groq** | llama-3.3-70b-versatile | **14,400 requests/day** | 30 requests/minute | Free tier only |
| **DeepSeek** | deepseek-chat | **Unlimited** (pay-as-you-go) | 60 requests/minute | $0.14/M input tokens, $0.28/M output tokens |

### Combined Daily Capacity

| Scenario | Calls/Day | Notes |
|----------|-----------|-------|
| All 3 providers healthy | **~20,400** | Gemini 6K + Groq 14.4K + DeepSeek unlimited |
| Gemini + Groq only | **~20,400** | Both free tier |
| Gemini only | **~6,000** | 4 models × 1,500 RPD each |
| DeepSeek only | **Unlimited** | Requires account balance |

### How the Round-Robin Works

```
Request 1 → Gemini (if fails → Groq → DeepSeek)
Request 2 → Groq   (if fails → DeepSeek → Gemini)
Request 3 → DeepSeek (if fails → Gemini → Groq)
Request 4 → Gemini (cycle repeats)
```

- Thread-safe: uses `threading.Lock` for the counter
- Auto-disables a provider if its API key is expired (401) or balance is zero (402)
- Gemini tries 4 models before giving up (handles per-model 429 rate limits)

### How to Configure API Keys

Edit `backend/.env`:
```
GEMINI_API_KEY=AIzaSy...your_key
GROQ_API_KEY=gsk_...your_key
DEEPSEEK_API_KEY=sk-...your_key
```

Get your keys at:
- **Gemini**: https://aistudio.google.com/apikey
- **Groq**: https://console.groq.com/keys
- **DeepSeek**: https://platform.deepseek.com/api_keys

### How Many Students Can We Handle?

Assuming an average student makes 20 AI calls/day:

| Daily Calls/Student | Max Students Supported | Provider Mix |
|---------------------|----------------------|--------------|
| 10 | ~2,000 | All 3 free tiers |
| 20 | ~1,000 | All 3 free tiers |
| 50 | ~400 | All 3 free tiers |
| 20 | Unlimited | With DeepSeek balance ($0.14/M tokens) |

---

## Super Admin Token Management

### What Super Admin Can Do

From the **Tokens page** (`/tokens`), admin users see an expanded management panel with 3 tabs:

1. **Overview** — See all users, their token balances, daily/weekly usage, total consumed, and platform-wide stats (tokens in circulation, total API capacity)
2. **Grant/Revoke** — Give tokens to any user (positive amount) or take tokens away (negative amount)
3. **Transfer** — Move tokens from one user to another (or create from system if no source user)

### Admin API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/auth/tokens/admin/users/` | All users with balances + platform stats |
| POST | `/api/auth/tokens/admin/grant/` | Grant or revoke tokens for a user |
| POST | `/api/auth/tokens/admin/transfer/` | Transfer tokens between users |

### Grant Tokens (Example)
```json
POST /api/auth/tokens/admin/grant/
{
    "user_id": 5,
    "amount": 50,
    "note": "Bonus for active participation"
}
```

### Revoke Tokens (Example)
```json
POST /api/auth/tokens/admin/grant/
{
    "user_id": 5,
    "amount": -20,
    "note": "Correcting an over-grant"
}
```

### Transfer Tokens Between Users
```json
POST /api/auth/tokens/admin/transfer/
{
    "from_user_id": 5,
    "to_user_id": 8,
    "amount": 20,
    "note": "Redistributing tokens"
}
```

### System Grant (No Source User)
```json
POST /api/auth/tokens/admin/transfer/
{
    "to_user_id": 8,
    "amount": 100,
    "note": "Welcome bonus"
}
```

### Token Circulation Dashboard

The admin overview shows platform-wide stats:
- **Total Users** — how many registered users
- **Tokens In Circulation** — sum of all available tokens across all users
- **Total Consumed** — total AI calls made platform-wide
- **API Calls/Day** — combined daily capacity from all providers (~20,400)
- Per-user breakdown table with: username, email, available, purchased, credits, daily used, total used

---

## Troubleshooting

### "Module not found" errors
```powershell
cd backend
.\venv\Scripts\Activate.ps1    # Must activate virtualenv first!
pip install -r requirements.txt
```

### Database errors
```powershell
python manage.py migrate
```

### AI not responding
- Check `.env` file has valid API keys:
  ```
  GEMINI_API_KEY=your_key_here
  GROQ_API_KEY=your_key_here
  DEEPSEEK_API_KEY=your_key_here
  ```
- Verify Groq key isn't expired at https://console.groq.com/keys
- Verify DeepSeek has balance at https://platform.deepseek.com
- Gemini free tier resets daily — if exhausted, other providers handle requests
- Test: Go to http://localhost:3000/ai-tutor and ask a question

### Knowledge base empty
```powershell
python _train_all.py
```

### Frontend build fails
```powershell
cd frontend
npm install
npm run build
```

### Want to reset the AI knowledge base
Delete `backend/chroma_db/rag_store.sqlite3` and run `python _train_all.py` again.

---

## Quick Reference: Adding New Content

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│  1. Put your file in the right folder:                  │
│                                                         │
│     Textbook/Notes → Medura_Train/textbooks/            │
│     Question Paper → Medura_Train/PYQ/                  │
│     Web Article    → Medura_Train/web_knowledge/        │
│                                                         │
│  2. Run the training:                                   │
│                                                         │
│     cd backend                                          │
│     .\venv\Scripts\Activate.ps1                         │
│     python _train_all.py                                │
│                                                         │
│  3. Done! AI now knows the new content.                 │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Tips for Better Content:
- **Markdown (.md) files work BEST** — they chunk cleanly into searchable pieces
- **Use headers** (`# Section`, `## Subsection`) — the chunker splits on them
- **Use bullet points** — each fact becomes easily searchable
- **Keep facts concise** — "Drug X causes Side Effect Y" is more searchable than long paragraphs
- **Name files descriptively** — `pharmacology_autonomic_drugs.md` not `notes1.md`
- **PDFs under 50 MB** — larger ones are auto-skipped (create .md notes instead)

