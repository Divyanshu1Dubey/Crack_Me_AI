# Crack CMS — Complete Project Documentation

> UPSC CMS (Combined Medical Services) Exam Preparation Platform
> Django Backend + Next.js Frontend + AI-Powered RAG System

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [How to Start the App](#how-to-start-the-app)
3. [Adding New Content (Training the AI)](#adding-new-content-training-the-ai)
4. [Folder Structure Explained](#folder-structure-explained)
5. [All Management Commands](#all-management-commands)
6. [API Endpoints](#api-endpoints)
7. [AI System Architecture](#ai-system-architecture)
8. [Frontend Pages](#frontend-pages)
9. [Database Info](#database-info)
10. [Current Content Stats](#current-content-stats)
11. [Troubleshooting](#troubleshooting)

---

## Project Overview

- **Backend**: Django 5.x + Django REST Framework, SQLite database
- **Frontend**: Next.js 16, React 19, TypeScript, Tailwind CSS 4, Recharts
- **AI Models**: Google Gemini 2.0 Flash (primary) + Groq LLama 3.3 70B (fallback)
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
│       ├── app/                      # All pages (19 routes)
│       ├── components/               # Sidebar, shared components
│       └── lib/                      # API client, auth context
│
└── DOCUMENTATION.md                  # ⭐ This file
```

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

## Frontend Pages (19 Routes)

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
  ```
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

