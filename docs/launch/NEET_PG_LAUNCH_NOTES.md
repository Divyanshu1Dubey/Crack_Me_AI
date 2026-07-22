# NEET PG Launch Notes — Operator Playbook

**Date:** 2026-07-23
**Owner:** TBD
**Status:** ✅ Live in production (`cracklabs.app`)

---

## What this document covers

* What the importer does.
* How to re-run it on demand.
* How to add a new Subject / Topic / Year.
* How to OCR a scanned year-paper that pdfplumber couldn't extract.
* Failure modes and recovery.

---

## 1. What lives where

| File | Purpose |
|---|---|
| `backend/importers/neetpg/` | Python package with parser / writer / config |
| `backend/importers/neetpg/runner.py` | `process_one_pdf` orchestrator |
| `backend/importers/neetpg/db_writer.py` | Django ORM bridge (Question / RecallSource / QuestionSource / QuestionImage) |
| `backend/importers/neetpg/topic_mapper.py` | Subject + topic mapping (keywords → catalogue rows) |
| `backend/importers/neetpg/pdf_reader.py` | PyMuPDF + pdfplumber text extraction |
| `backend/run_neetpg_import.py` | Synchronous CLI runner over a directory of PDFs |
| `backend/import_year_wise.py` | Year-paper re-run using pdfplumber |
| `backend/backfill_neetpg_subjects.py` | Bulk subject remap from `source` filename |
| `backend/create_neetpg_subjects.py` | One-shot catalogue bootstrap |
| `neet-pg_and_material/` | 26 source PDFs (subject-wise + year-wise) |
| `backend/chroma_db/rag_store.sqlite3` | RAG index (textbook content, NOT question bank) |

---

## 2. End-to-end pipeline (per PDF)

```
PDF on disk
  ↓
PyMuPDF open (pdf_reader.open_pdf)
  ↓
PyMuPDF iter_pages → text + image refs
  ↓
pdfplumber fallback if PyMuPDF text empty
  ↓
Per page:
  classify (digital / hybrid / scanned)      — classifier.py
  extract questions via regex                 — text_parser.py
  detect answer labels / explanations        — text_parser.py + answer_key.py
  extract embedded images                     — image_extractor.py
  OCR fallback (when text empty + Tesseract) — ocr_engine.py
  ↓
Deduplicate within batch                      — deduplicator.py
Quality check (4 options, answer, OCR conf)  — quality.py
  ↓
DB write (idempotent via sha256):
  RecallSource  (one per (sha256, page))
  Question      (update_or_create on recall_text_hash + exam_type)
  QuestionSource (provenance bridge)
  QuestionImage (per embedded image, dedup on sha256_short)
  DuplicateCluster + DuplicateMember (when exact-sha match exists)
  QuestionExtractionItem (rows that failed extraction — admin review queue)
```

## 3. Idempotency

`Question.update_or_create(recall_text_hash=<sha>, exam_type='neet_pg')` is the
key — re-running the same source never creates duplicate rows.

* Question is keyed on the **sha256 of the normalized question stem** + `exam_type`.
* RecallSource is keyed on `(pdf_sha256, page_start, page_end)`.
* QuestionImage is keyed on `sha256_short`.

If you change the normalization logic and re-run, every row gets a new sha256,
which means every row looks "new" and you'll end up with duplicates. To force
a clean re-run, set `is_active=False` on existing rows first via the
`neetpg_rollback` management command.

## 4. How to re-import on demand

```bash
cd C:\Users\DIVYANSHU\Desktop\crack_cms\backend

# All PDFs (synchronous, ~10 min when OCR is missing)
venv\Scripts\python.exe run_neetpg_import.py "C:\Users\DIVYANSHU\Desktop\crack_cms\neet-pg_and_material"

# Just the year-wise papers (pdfplumber path, ~5 min)
venv\Scripts\python.exe import_year_wise.py

# One PDF via the management command (queues a django_q task; needs the worker)
venv\Scripts\python.exe manage.py neetpg_import_run --source-dir "C:\Users\DIVYANSHU\Desktop\crack_cms\neet-pg_and_material" --force
```

Track progress:

```bash
venv\Scripts\python.exe manage.py neetpg_status [--job-id N]
```

## 5. Adding a new Subject / Topic

### Add a Subject (one-time)

```bash
venv\Scripts\python.exe -c "
import os, django, sys
sys.path.insert(0, '.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')
django.setup()
from questions.models import Subject
obj, _ = Subject.objects.get_or_create(name='NewSubjectName', defaults={'code': 'XYZ', 'exam_type': 'neet_pg'})
print('id', obj.id)
"
```

Then add a mapping in `backend/importers/neetpg/db_writer.py::_SUBJECT_NAME_MAP`.

### Add a Topic (per Subject)

Topics aren't tied to importer parsing today — they come from `seed_data.py`
or admin. To add: `/admin/questions/topic/add/` or via shell.

## 6. OCR-ing scanned year-papers that pdfplumber couldn't extract

If a year-paper has no extractable text (true scan), install Tesseract:

1. Download: https://github.com/UB-Mannheim/tesseract/wiki (pick `tesseract-ocr-w64-setup-5.x.exe`)
2. Install to `C:\Program Files\Tesseract-OCR`
3. Add to PATH (or set `TESSERACT_CMD` env var)
4. Restart terminal + dev server
5. Re-run the importer for that PDF:
   ```bash
   venv\Scripts\python.exe manage.py neetpg_import_run --source-dir <dir>
   ```

In production, the same `oc_image()` is invoked; the absence of Tesseract
silently downgrades pages to "no OCR text found" and they get extracted only
when pdfplumber also has text.

## 7. Failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| `ValueError: too many values to unpack (expected 2)` in topic_mapper | Fixed in Phase 5 | n/a |
| `IntegrityError: null value in column "job_id" of relation "questions_questionextractionitem"` | Fixed in Phase 5 (auto-creates a fallback Job) | n/a |
| Every row has `subject='General Medicine'` | `_default_subject()` before Phase 5 fix | re-run `backfill_neetpg_subjects.py` |
| Every row has `year=0` | Filename has no year AND no PDF metadata year | re-run with PDFs that have creationDate metadata OR use the year-paper re-run script |
| Stats endpoint returns `{total:0}` for `?exam=neet-pg` | Fixed in Phase 5 (`EXAM_SOURCE_PREFIXES`) | n/a |
| 500 on stats for guests | Fixed in Phase 5 (AnonymousUser guards) | n/a |
| `Tesseract failed: tesseract is not installed` warnings in logs | OCR not installed | non-critical; pages with hidden OCR layer get extracted via pdfplumber anyway |

## 8. Verifying production

```bash
# NEET PG total
curl 'https://crackcms-vsthc.ondigitalocean.app/api/questions/stats/?exam=neet-pg' | jq '.total'
# Expect: 3000+

# Year-wise breakdown
curl 'https://crackcms-vsthc.ondigitalocean.app/api/questions/stats/?exam=neet-pg' | jq '.by_year'

# A specific year (UI: /questions/practice?year=2025&exam=neet-pg)
curl 'https://crackcms-vsthc.ondigitalocean.app/api/questions/?exam_type=neet_pg&year=2025&page_size=1' | jq '.count'

# Subject coverage (UI: /questions?exam_type=neet_pg&subject=Anatomy)
curl 'https://crackcms-vsthc.ondigitalocean.app/api/questions/?exam_type=neet_pg&subject=6&page_size=1' | jq '.count'
```

## 9. Rollback

To soft-delete every question introduced by a specific import job:

```bash
venv\Scripts\python.exe manage.py neetpg_rollback --job-id N
```

Soft-delete only — never hard-deletes. To restore:

```python
from questions.models import Question
Question.objects.filter(recall_sources__import_job_id='N', is_active=False).update(is_active=True)
```

## 10. Where Tesseract PDF OCR is in the loop

* PDF has digital text → PyMuPDF extracts → no OCR needed.
* PDF has hidden OCR layer (some scanned) → PyMuPDF returns empty → pdfplumber fallback recovers it.
* Pure scan with no hidden text → Tesseract required (not installed in this env, hence some year-papers yield 0 questions).

To close the gap, install Tesseract and re-run the year-papers.
