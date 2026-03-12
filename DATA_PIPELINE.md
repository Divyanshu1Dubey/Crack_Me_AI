# CrackCMS — Data Pipeline Documentation

## Question Data Flow

```
                    ┌──────────────────┐
                    │  Source Data       │
                    │  (PYQ PDFs, TXT,  │
                    │   Markdown)        │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  Import Scripts    │
                    │  _import_pyq_md   │
                    │  _import_pyq_txt  │
                    │  _import_sample   │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  Django DB        │
                    │  (SQLite)         │
                    │  questions_       │
                    │  question table   │
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
     ┌────────▼──────┐ ┌────▼────┐ ┌───────▼────────┐
     │ Enrichment    │ │ Export  │ │ Validation     │
     │ (AI-powered)  │ │ Fixture │ │ Pipeline       │
     │ enrich_turbo  │ │ JSON    │ │ validate_      │
     │               │ │         │ │ questions.py   │
     └────────┬──────┘ └────┬────┘ └───────┬────────┘
              │              │              │
              │         ┌────▼────┐         │
              │         │ data_   │         │
              │         │ versions│         │
              │         │ (backup)│         │
              │         └─────────┘         │
              │                             │
     ┌────────▼──────────────────────────────▼───────┐
     │  API Layer (DRF ViewSets + Filters)           │
     │  GET /api/questions/?subject=&year=&search=   │
     └────────────────────┬──────────────────────────┘
                          │
     ┌────────────────────▼──────────────────────────┐
     │  Frontend (Next.js Question Bank)              │
     │  Pagination, Filters, Keyboard Nav, AI Tutor  │
     └───────────────────────────────────────────────┘
```

## Import Pipeline

### Source Formats

| Format | Script | Description |
|--------|--------|-------------|
| Markdown | `_import_pyq_md.py` | Structured PYQ papers with year/subject headers |
| Plain Text | `_import_pyq_txt.py` | Raw text PYQ format, uses `_index_pyq_txt.py` for parsing |
| Sample | `_import_sample.py` | Predefined sample questions from `sample_questions.txt` |

### Import Process

1. Parse source file into structured question dicts
2. Extract: question_text, option_a/b/c/d, correct_answer, year, subject
3. Deduplicate by question_text (exact match)
4. Create `Question` objects via Django ORM

## Enrichment Pipeline

### Overview

Takes questions with basic data (text + options) and adds AI-generated metadata.

### Scripts

- **`enrich_questions.py`** — Sequential enrichment, one provider at a time
- **`enrich_turbo.py`** — Parallel enrichment using ThreadPoolExecutor
- **`_fix_and_enrich_answers.py`** — Fix incorrect answers + enrich in batch
- **`_manual_fix_answers.py`** — Apply manual answer corrections from CSV

### Enrichment Fields

| Field | Source | Description |
|-------|--------|-------------|
| `explanation` | AI | 3-4 sentence detailed explanation |
| `mnemonic` | AI | Memory aid for the topic |
| `high_yield_points` | AI | Exam-relevant facts (JSON array) |
| `textbook_reference` | AI | Standard textbook + chapter |
| `concept_tags` | AI | Topic tags (JSON array) |
| `difficulty` | AI | easy/medium/hard classification |
| `correct_answer` | AI voting | Multi-model consensus (3 providers) |

### Progress Tracking

- Progress saved to `enrich_progress.json`
- Tracks: last processed ID, success/failure counts
- Resumable — skips already-enriched questions on restart

## Validation Pipeline

`validate_questions.py` performs 5 quality checks:

| Check | What It Catches |
|-------|----------------|
| Missing Answers | Questions with no correct_answer set |
| Missing Options | Questions with empty option_a/b/c/d |
| Invalid Answers | correct_answer not in {A, B, C, D} |
| Answer-Option Mismatch | correct_answer points to an empty option |
| Fuzzy Duplicates | Questions with ≥85% text similarity |

Output: Console summary + `validation_report.json`

## Export / Versioning

### Fixture Export

```bash
python _export_fixture.py
# Produces: questions_fixture.json (all questions as Django fixture)
```

### Dataset Versioning

```
backend/data_versions/
├── questions_v1_2024-01-15.json
├── questions_v2_2024-02-01.json
└── ...
```

- Export before any batch operation (enrichment, answer fixes)
- Enables rollback to any previous version via `loaddata`

## RAG Document Ingestion

### Pipeline

```
Medura_Train/
├── textbooks/     → PDF/text extraction → chunk → TF-IDF index
├── PYQ/           → Question extraction → chunk → TF-IDF index
└── web_knowledge/ → Web scrape → clean → chunk → TF-IDF index
```

### Scripts

| Script | Purpose |
|--------|---------|
| `ai_engine/auto_ingest.py` | Automatic document ingestion |
| `ai_engine/document_processor.py` | PDF/text parsing and chunking |
| `ai_engine/sqlite_rag.py` | TF-IDF vectorization + SQLite storage |
| `scripts/ocr_processor.py` | OCR for scanned PDFs |
| `scripts/scrape_cms_knowledge.py` | Web content scraping |

### Storage

- **SQLite RAG**: `chroma_db/rag_store.sqlite3` (4972+ chunks)
- **ChromaDB**: `chroma_db/chroma.sqlite3` (embedding-based, secondary)

## Database Schema (Key Tables)

### questions_question
```
id, question_text, option_a, option_b, option_c, option_d,
correct_answer, explanation, subject, year, difficulty,
mnemonic, high_yield_points, textbook_reference,
concept_tags, paper_category, similar_question_ids,
created_at, updated_at
```

### questions_flashcard
```
id, user_id (FK), question_id (FK),
ease_factor, interval, repetitions,
next_review, last_reviewed, created_at
```

### accounts_tokenbalance
```
id, user_id (FK), free_daily, free_weekly, purchased,
last_daily_reset, last_weekly_reset
```

## Maintenance Commands

```bash
# Validate questions
python validate_questions.py

# Export fixture (backup)
python _export_fixture.py

# Enrich unenriched questions
python enrich_turbo.py

# Fix answers via CSV
python _manual_fix_answers.py

# Check database integrity
python _check_db.py

# Compact database
python _compact.py
```
