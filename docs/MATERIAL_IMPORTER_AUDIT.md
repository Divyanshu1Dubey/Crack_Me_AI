# Material Importer — Architecture & Audit

> Snapshot: 2026-07-27. Source of truth for the new `backend/material_importer/` app introduced to ingest `cms_exclusive_material/` (≈100 DOCX study docs).

---

## 1. Why this app exists

The previous `questions` ingestion pipeline (`backend/questions/management/commands/import_neet_pg.py` and friends) was exam-specific and tightly coupled to the `Question` table. The team needed:

1. A **format-agnostic** importer for DOCX, PDF, PPTX and text study material.
2. A **staging** workflow: nothing publishes to the live question bank without human/AI approval.
3. **Provenance**: every question knows which file it came from, what batch, and whether it was deduped against existing content.
4. **Optional AI classification** (heuristic fast-path + 9-provider round-robin fallback) and **AI enrichment** (explanations, mnemonics) without coupling to the AI service's internal models.
5. A **safety net** (`:hold` review queue, admin actions for promote/reject) before new questions reach students.

`material_importer` sits between raw documents and the live `questions.Question` table. Admins curate the staging rows; only approved rows are published.

---

## 2. Module map

```
backend/material_importer/
├── models.py                # 5 additive tables; never modifies existing schema
├── ingest_service.py        # ingest_path() — walks folder, parses, persists
├── duplicate_detector.py    # 2-stage: exact content hash → 6-gram shingle Jaccard
├── ai_classifier.py         # HeuristicClassifier + AIClassifier (lazy, opt-in)
├── publishing.py            # publish_extracted_question() — staging → live Question
├── enrichment.py            # explain_after_answer() bridge for staged rows
├── semantic_search.py       # index approved docs into the existing RAG store
├── mock_test_builder.py     # build_for_batch() — auto-generate subject/topic/PYQ tests
├── quality.py               # build_qa_report() — count missing options, dup images, etc.
├── admin.py                 # Django admin for all 5 tables
├── apps.py                  # AppConfig
├── parser/
│   ├── dataclasses.py       # ParsedDocument/ParsedQuestion/ParsedTheory/ParsedImage
│   ├── parser_factory.py    # file-extension → parser adapter
│   ├── docx_parser.py       # 4 extractors: classic / boxed / statement / theory
│   ├── pdf_parser.py        # lazy-imported (pypdf/pdfplumber)
│   ├── pptx_parser.py       # lazy-imported (python-pptx)
│   ├── text_parser.py       # .txt / .md
│   ├── subject_classifier.py# regex-based subject/difficulty heuristics
│   └── text_utils.py        # clean_text, content_hash, extract_year_hint, …
└── management/commands/
    ├── ingest_cms_material.py     # python manage.py ingest_cms_material --path … --use-ai
    ├── qa_report.py               # python manage.py qa_report --batch 12 [--out f.json]
    ├── enrich_pending_questions.py# python manage.py enrich_pending_questions --batch 12
    └── build_auto_tests.py        # python manage.py build_auto_tests --batch 12
```

### Data model (additive; no migrations on existing tables)

| Table               | Purpose                                                                 |
|---------------------|-------------------------------------------------------------------------|
| `ImportBatch`       | One folder/zip/file ingestion run. Counters + status.                   |
| `ImportMaterial`    | One source file inside a batch (per-file parse status, sha256, counts). |
| `ExtractedQuestion` | Staging row for a parsed MCQ. Has status: pending/approved/rejected/published/duplicate. |
| `ExtractedTheory`   | Theory/note block from theory-style docs (callouts, tables, lists).     |
| `ImportedImage`     | Extracted image bytes → stored under MEDIA_ROOT/imported/.../img_NNN.ext.|
| `ImportAuditLog`    | Per-event log (info/warn/error) tied back to batch + material.          |

Indexes: `(material, parse_status)`, `(file_sha256)`, `(content_hash)`, `(status)`, `(inferred_subject)`, `(level, code)`.

---

## 3. The ingestion pipeline

```
                      ┌────────────────────┐
                      │  CMS material dir  │
                      │   (.docx / .pdf /  │
                      │    .pptx / .md)    │
                      └──────────┬─────────┘
                                 │  ingest_path()
                                 ▼
   ┌─────────────────────────────────────────────────────────────┐
   │ 1. walk folder, file_format detector (ParserFactory)       │
   │ 2. _seed_existing_dedup() — prime DuplicateDetector from   │
   │    Question.question_text; very slow on first call         │
   │ 3. for each file:                                          │
   │      ├─ _docx_read / _pdf_read / _pptx_read                │
   │      ├─ detect_format(paragraphs, tables)                  │
   │      ├─ classic / boxed / statement / theory extractor     │
   │      ├─ _persist_parsed_document:                           │
   │      │     ├─ ImportedImage rows (sha256 dedup, default_storage)
   │      │     ├─ ExtractedQuestion rows (after dedup check)    │
   │      │     └─ ExtractedTheory rows                          │
   │      └─ ImportAuditLog.info("parsed …")                    │
   │ 4. ImportBatch totals + status partial/completed.           │
   └─────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
              ┌──────────────────────────────────┐
              │   Staging (admin review queue)   │
              │   status = pending / approved    │
              └────────────────┬─────────────────┘
                               │  Admin action or
                               │  publish_extracted_question
                               ▼
                  ┌──────────────────────────────┐
                  │  questions.Question (live)   │
                  └──────────────────────────────┘
```

---

## 4. Stage-by-stage details (verified by reading code)

### 4.1 `ParserFactory` (`parser/parser_factory.py`)
- Maps `.docx` → `DOCXParser`, `.pdf` → `PDFParser`, `.pptx` → `PPTXParser`, `.txt`/`.md` → `TextParser`.
- PDF/PPTX/Text are **lazy-imported** so deploying without those packages still works for DOCX.
- `parser_for(path)` returns `None` for unsupported extensions — those files are skipped silently.

### 4.2 DOCX pipeline (`parser/docx_parser.py`)
- One orchestrator class `DOCXParser`, four extractor classes.
- **Format detection** runs on first 60-200 paragraphs plus the first 30 tables. Returns one of: `mcq_boxed`, `mcq_classic`, `mcq_statement`, `theory`, `unknown`.
- **Classic extractor** — handles `Q1. … A. … Answer: B Explanation: …`. Option labels may span multiple lines.
- **Boxed extractor** — handles Meduraa's Word-table layout (`Question | <text>`, `Option | <text> | correct/incorrect`, `Solution | <text>`). Reads column 3 as the correct/incorrect flag.
- **Statement extractor** — handles "I./II./III./IV." code-style questions with a "Select using the code below" prompt and `A./B./C./D.` codes.
- **Theory extractor** — splits paragraphs into heading/paragraph/list/index blocks; converts tables into typed blocks.
- **Images** — extracts every `word/media/*` file from the DOCX zip; reads dims via PIL when image type supports it.

### 4.3 `DuplicateDetector` (`duplicate_detector.py`)
- **Stage 1**: exact content_hash match (sha256 of normalized question text → cheap, catches re-imports).
- **Stage 2**: 6-gram shingle match via inverted-index → catches trivial edits. Threshold `0.85` Jaccard.
- For an 8 K-question corpus the inverted index keeps per-question check at `O(matching_docs)`.
- Each batch's `DuplicateDetector` instance is seeded once via `_seed_existing_dedup()` with all live Question rows. **This is a one-time full-table scan per batch — see bug §6.1**.

### 4.4 `HeuristicClassifier` (`ai_classifier.py` + `parser/subject_classifier.py`)
- Regex-driven subject buckets (Medicine/Surgery/OBGY/Pediatrics/PSM/Anesthesia/Orthopaedics/Dermatology/Ophthalmology/ENT/Psychiatry).
- Confidence = `matched_tokens / max(20, total_tokens)` clamped to `[0.05, 0.95]`.
- Difficulty heuristic: `<80` chars → easy, `>240` → hard, presence of `except / not correct / false / true` → hard, otherwise medium.

### 4.5 `AIClassifier`
- Single AI call per question with a tightly-constrained JSON prompt.
- Wrapped in try/except so a provider failure falls back to heuristic.
- If `ai_service` is unavailable, returns the heuristic result.

### 4.6 `publishing.py:publish_extracted_question`
- Creates a real `questions.Question` from an `ExtractedQuestion` row.
- Resolves subject: prefers `eq.subject` → fallback `Subject.objects.filter(name='Imported')` → auto-creates with `exam_track='cms'`.
- Year detection: scans question text for years 2010…current_year; the *earliest* plausible PYQ year wins.

### 4.7 `enrichment.enrich_batch`
- Streams all `ExtractedQuestion.status='pending'` rows for a batch, one at a time.
- Calls `ai_service.explain_after_answer(...)` (preferred) or one-shot `ask()`.
- Persists `ai_explanation`, `ai_mnemonic`, `concept_keywords`, `textbook_reference`, `ai_error` into the staging row's `classification_meta` JSON.

### 4.8 `mock_test_builder.build_for_batch`
- Generates **subject**, **topic**, **PYQ-year**, and **mixed** tests from staged rows.
- **Idempotency** for subject/topic tests: pre-deletes any existing `Test.title__icontains="batch {batch_id}"`.
- **§6 bug**: the *Mixed* test reuses the same delete predicate, so re-runs are idempotent. But `_ensure_test` **overwrites `is_published` to False** for every rebuild — see §6.4.

### 4.9 `semantic_search.add_to_rag_index`
- Pushes each approved question + theory block into the existing `chroma_db/rag_store.sqlite3` TF-IDF store.
- Silently no-ops when RAG is disabled by the production `DEBUG` gate (intentional).

### 4.10 `quality.build_qa_report`
- Counts: missing options, missing correct answer, missing question text, in-batch image dupes, empty theory blocks.
- Already produced and saved at `docs/qa_report_batch13.json` (Batch #13, 103 files, 1,667 extracted questions, 1,208 images, 24,113 theory blocks).

---

## 5. What's already done this session (verified to work)

| Item | Status |
|---|---|
| `material_importer` registered in `INSTALLED_APPS` | ✅ diff in `crack_cms/settings.py` |
| Initial migration `0001_initial.py` | ✅ created in repo, dependencies correct |
| Admin `ImportBatchAdmin` / `ImportMaterialAdmin` / `ExtractedQuestionAdmin` (approve/reject/publish) | ✅ |
| Mock-test builder callable | ✅ |
| QA report on Batch #13 (the 103-DOCX cms_exclusive_material run) | ✅ see `docs/qa_report_batch13.json` |

QA Batch #13 numbers: **102/103 files parsed, 1,667 questions extracted, 1,208 images, 24,113 theory blocks, 1 file failed (`merged_notes-document (1).docx`, namespace prefix error in DOCX), 544 image dupes inside the batch, 480 questions without correct answer**.

---

## 6. Bugs / risks found (severity ordered)

### 6.1 `_seed_existing_dedup` is O(N) and blocking — moderate
`ingest_service.py:76-95` runs a full-table `Question.objects.all().only().iterator(chunk_size=500)` over the entire bank on every `ingest_path()` call to prime in-memory shingles. With 1,920+8 K question banks this is fast enough but fragile:
- **Effect**: blocks the request thread for several seconds on the first batch of each session.
- **Mitigation**: serialize the inverted index to `MEDIA_ROOT/_cache/dedup_index.json` after first build; or move it to a separate background command that precomputes once.
- **Risk**: low (still completes); latency: ~2-4 s extra per fresh ingest call.

### 6.2 `Name_or_code` typo + full-table scan per resolution — low
`ingest_service.py:110` defines the subject resolver as `Name_or_code` (PascalCase) and re-runs `Subject.objects.all()` for every extracted question to build the alias map (`ingest_service.py:113`).
- **Effect**: insert 1,000 questions → 1,000 full-table scans of `questions_subject` (tiny table in practice, but still wasteful).
- **Fix**: rename to `_resolve_subject_alias(n)`, cache the lookup dict at module level, and avoid the recursive call.

### 6.3 `duplicate_detector.check` doesn't store the canonical hash → re-checked on rerun — low
`duplicate_detector.py:80` computes the hash from `q.question_text`, but the *same hash* computed from a slightly different spell (e.g. trailing whitespace) won't match an existing live Question. Acceptable, but the function should expose the normalization step's output for logging.

### 6.4 `_ensure_test` resets `is_published=False` on every rebuild — **high**
`mock_test_builder.py:79` uses `Test.objects.update_or_create(title=name, defaults=defaults)` with `defaults={"is_published": False, ...}`. This is intentional for new tests but it silently un-publishes existing tests that match by title.
- **Fix**: pass only writable fields when `t.is_published` is already `True`. Concretely, change `defaults` to omit `is_published` if a previous row exists.

### 6.5 `_resolve_topic` doesn't create missing topics — low (intended)
The resolver returns `None` rather than creating. This is correct: we don't want the importer to invent topics. Admin must create or live with `topic=null`. Note in admin docs.

### 6.6 Pyhton-docx unavailable on Render when importing DOCX without extras — low
`docx_parser._docx_read` raises a `RuntimeError` if `python-docx` is missing. Confirm `python-docx` is in `requirements.txt` (it is — keep it pinned).

### 6.7 DOCX namespace error on `merged_notes-document (1).docx` — observable, known
QA report flags this file. `_docx_read` crashes when an Office namespace prefix isn't declared. Add a `try/except` around `python_docx` parse and degrade to a "structured paragraphs + zip-only image extraction" fallback (the doc is still openable as zip → `word/document.xml` is raw XML; can be parsed with regex on `<w:t>`).

### 6.8 `ingest_service` writes no transactional boundary per material — low
A single corrupt material write can leave the batch in a partial state (already implemented as `partial` status, which is correct). The code catches every Exception per file but doesn't clean up half-created rows. Acceptable trade-off for ingestion correctness.

### 6.9 `enrichment.enrich_batch` has no progress checkpoints — low
A 1,000-question batch enrichment consumes AI tokens serially with one DB write per question. Add a periodic `.save(update_fields=...)` batch commit every 50 rows.

### 6.10 `ai_classifier.py:AIClassifier` prompt does not validate `exam_track` returned from AI — low
The model occasionally returns strings outside `cms|neet_pg|ini_cet|inicet`. Normalize to a known track or default to `cms`.

---

## 7. Performance & cost observations

- 102-DOCX ingest already produced 1,667 questions + 24 K theory blocks in <minutes. The bottleneck today is **AI enrichment** (one provider call per question). At 9 providers in round-robin with a 15-20 s per-provider deadline and 120 s total budget, enrichment at scale (>10 K questions) is expensive.
- **Recommended**: cluster enrichment by topic; cache `_call_explain` results; only re-enrich when the question text changes (use `ai_generated_at` as the trigger).

---

## 8. Test coverage

No unit tests were committed alongside this app (searched the repo — no `test_*.py` files inside `material_importer/`). For a high-risk ingestion pipeline that **publishes to the live Question bank**, test coverage is the single biggest gap. At minimum:

- `parser/test_docx_parser.py` — fixture-driven parses of classic / boxed / statement / theory samples, asserting question counts and shape.
- `test_duplicate_detector.py` — exact-hash dedup, shingle dedup, false positive resistance.
- `test_publishing.py` — `publish_extracted_question` updates staging row, doesn't double-publish.
- `test_mock_test_builder.py` — re-running produces same test ids, preserves `is_published=True` on rerun.

---

## 9. Open follow-ups (in `NEXT_STEPS.md`)

- [ ] Fix `is_published` overwrite in `_ensure_test` (high-risk; test before merging)
- [ ] Add unit tests for the parser + duplicate_detector + mock_test_builder
- [ ] Cache the dedup index to disk (`MEDIA_ROOT/_cache/dedup_index.json`)
- [ ] Subject-alias dict cached at module load
- [ ] DOCX namespace fallback (regex on `<w:t>`)
- [ ] Enrichment batching + cache
