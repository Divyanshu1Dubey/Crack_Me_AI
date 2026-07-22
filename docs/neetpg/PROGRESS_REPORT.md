# NEET PG / INI-CET Importer — End-to-End Progress Report

> Generated 2026-07-22. Reflects the scaffolding shipped today. Live
> counts will be filled in once `python docs/neetpg/_inventory.py` and
> `python -m backend.importers.neetpg.runner --source-dir <path>` are
> executed.

---

## 1. Deliverables shipped (this session)

### A. Documentation (canonical, under `docs/neetpg/`)

| File | Purpose | Status |
|---|---|---|
| `DATASET_ANALYSIS.md` | High-level dataset overview + provenance framing + per-PDF inventory table | ✅ shipped |
| `PDF_INDEX.md` | Per-PDF index with sizes, hashes, exam/subject routing | ✅ shipped |
| `QUESTION_SCHEMA.md` | Full DB schema for Question / Option / Image / Source / Provenance + dedup + ER diagram + indexes + migration plan | ✅ shipped |
| `IMAGE_SCHEMA.md` | Image-first schema (modality, hashes, OCR, captions) + storage + delivery | ✅ shipped |
| `IMPORT_PLAN.md` | End-to-end pipeline design (PDF→OCR→parse→dedup→DB→reports) + regex dictionary + topic keyword table + CLI + env vars | ✅ shipped |
| `DEDUPLICATION_PLAN.md` | 4-level dedup (sha + rapidfuzz + embedding + image-hash) + canonical model + re-import safety | ✅ shipped |
| `PROGRESS_REPORT.md` | This file | ✅ shipped |

### B. Code (under `backend/importers/neetpg/`)

| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `README.md` | Quick-start, env vars, optional deps, output layout |
| `config.py` | Env-driven settings (output dir, OCR DPI, batch size, dedup thresholds) |
| `models.py` | Dataclasses for `SourceRecord`, `ParsedQuestion`, `ParsedOption`, `ImageRecord`, `QualityIssue` |
| `fingerprints.py` | sha256 + page-text fingerprinting + normalisation |
| `classifier.py` | Per-page digital/scanned/hybrid/blank classification |
| `pdf_reader.py` | PyMuPDF wrapper (open, page count, metadata, iter pages, render PNG, extract image bytes) — degrades gracefully if PyMuPDF missing |
| `ocr_engine.py` | Tesseract wrapper + OpenCV deskew/denoise preprocessing — degrades gracefully if tesseract missing |
| `image_extractor.py` | Embedded + rendered image extraction + sha + pHash + dHash + OCR + caption placeholder |
| `text_parser.py` | Question / option / answer / explanation parser with full regex dictionary + Assertion-Reason detection + LLM fallback stub |
| `topic_mapper.py` | 19-subject keyword taxonomy + filename fallback + topic refinement |
| `answer_key.py` | Trailing-section answer key detector + inline-merge |
| `deduplicator.py` | sha + rapidfuzz + embedding + image-hash dedup with `DedupReport` |
| `enricher.py` | AI enrichment stub (concept / mnemonic / clinical pearl / why-correct) |
| `quality.py` | Quality checks (empty stem, missing options, low OCR conf, etc.) — flag-only |
| `storage.py` | Atomic JSONL writes + manifest load/save |
| `report.py` | Markdown report generators (`IMPORT_REPORT`, `OCR_REPORT`, `IMAGE_EXTRACTION_REPORT`, `QUALITY_REPORT`, `DEDUPLICATION_REPORT`, `MISSING_DATA_REPORT`) |
| `runner.py` | Orchestration entrypoint with `argparse` CLI (--scan / --source-dir / --pdf / --dedup / --report) |
| `management/__init__.py` | Django commands package |
| `management/commands/__init__.py` | Commands marker |
| `management/commands/neetpg_scan.py` | `python manage.py neetpg_scan --source-dir <path>` |
| `management/commands/neetpg_import.py` | `python manage.py neetpg_import --pdf <file>` |
| `management/commands/neetpg_import_all.py` | `python manage.py neetpg_import_all --source-dir <path>` |
| `management/commands/neetpg_dedup.py` | `python manage.py neetpg_dedup` |
| `management/commands/neetpg_repair.py` | `python manage.py neetpg_repair --min-confidence 0.7` |
| `management/commands/neetpg_report.py` | `python manage.py neetpg_report` |
| `tests/__init__.py` | Tests package |
| `tests/test_fingerprints.py` | Hash + normalisation tests |
| `tests/test_classifier.py` | Per-page classification tests |
| `tests/test_text_parser.py` | Question / option / answer / assertion-reason / image-ref tests |
| `tests/test_deduplicator.py` | sha + fuzzy + image-hash dedup tests |

---

## 2. Dataset summary

- **Source dir:** `C:\Users\DIVYANSHU\Desktop\crack_cms\neet-pg_and_material\`
- **PDFs:** 26
- **Total size:** ~210 MB
- **NEET PG year papers (6):** 2018, 2020, 2021, 2022, 2023, 2025
- **Subject bundles (20):** Anaesthesia, Anatomy, Biochem, Derma, ENT, FMT, Medicine, Micro, OBG, Ophthal, Ortho, PSM, Patho, Pediatrics, Pharm, Physiology, Psychiatry, Radiology, Surgery
- **Hashes / sha256:** filled by `python docs/neetpg/_inventory.py` → `docs/neetpg/_inventory.json`
- **Per-PDF stats (page count, scan ratio, image count):** filled by the same script after PyMuPDF probe

> Numbers in the live `PDF_INDEX.md` table will update once the inventory script runs.

---

## 3. Schema at a glance

24 tables designed. Highlights:

- `Question` — `source_text_hash` (sha of normalised text) is the dedup key. `confidence_score` is a weighted blend of OCR / parse / option completeness / answer / image integrity.
- `Provenance` — append-only. `(question_id, source_id, page_number)` indexes. Records OCR + parse confidence and original text.
- `Image` — modality-tagged (`radiology / histopathology / ecg / ct / mri / x_ray / ultrasound / clinical_photo / instrument / chart / flowchart / microbiology / slide / embryology / anatomy / biochem_pathway / dermatology / ophthalmology_fundus / other`).
- `DuplicateCluster` + `DuplicateMember` — keep canonical + member rows; never delete.

Full design: `QUESTION_SCHEMA.md`, `IMAGE_SCHEMA.md`.

---

## 4. Pipeline summary

```
PDF
 └─► fingerprints (sha256, page metadata)
     └─► classifier (digital / scanned / hybrid / blank)
         ├─► pdf_reader.get_text + get_images        (digital)
         ├─► render @ 200 DPI → tesseract OCR        (scanned/hybrid)
         └─► image_extractor (embedded + rendered)
             └─► text_parser (regex + heuristics + LLM fallback stub)
                 └─► topic_mapper (19 subjects + topic refinement)
                     └─► deduplicator (sha + fuzzy + embed + image-hash)
                         └─► enricher (stub)
                             └─► quality (flag-only)
                                 └─► storage (atomic JSONL + manifest)
                                     └─► report.md generators
```

Every stage is **idempotent** and **resumable** via `manifest.json`.

---

## 5. Quality controls (what we never do)

- We **never** delete a question. Soft-delete via `is_active=False`.
- We **never** overwrite provenance. `Provenance.original_text` is preserved forever.
- We **never** embed image bytes in `Question` text.
- We **never** auto-merge borderline dedup candidates — flag for review.
- We **never** claim recall content is official. UI surfaces a "Recall-based" disclaimer next to every question.

---

## 6. Live extraction (next step)

Once `bash` is back and the user runs:

```bash
.venv\Scripts\Activate.ps1

# Step 1 — inventory + tooling probe (writes _inventory.json)
python docs/neetpg/_inventory.py

# Step 2 — end-to-end import (writes JSONL + manifest + reports)
python -m backend.importers.neetpg.runner --source-dir "C:/Users/DIVYANSHU/Desktop/crack_cms/neet-pg_and_material"

# Step 3 — quick tests
python -m unittest discover -s backend/importers/neetpg/tests -v
```

…the per-PDF stats in `PDF_INDEX.md`, the schema column in
`DATASET_ANALYSIS.md`, and the report counts in this file will all
update from the JSONL outputs.

Expected ranges (subject to actual probe):

| Metric | Expected range |
|---|---:|
| Total questions parsed (raw, before dedup) | 5,000 – 12,000 |
| Total images extracted | 1,500 – 4,000 |
| Pages scanned (OCR fallback) | 30 – 60 % of total |
| Pages digital (text-layer only) | 40 – 70 % of total |
| Dedup savings | 20 – 45 % of raw questions |
| Avg OCR confidence | 70 – 90 |

---

## 7. Out-of-scope items (explicitly deferred)

- Django model writes (`backend/importer/`) — needs stakeholder approval before migrations.
- AI enrichment wiring (`enricher.enrich_question`) — stubbed; needs AI provider keys configured.
- LLM fallback in `text_parser.parse_with_llm` — `NotImplementedError` with TODO.
- INI-CET and AIIMS PG recall PDFs — not present in the supplied directory; pipeline handles them automatically when added.
- Production CDN delivery (`uploader.py` → DigitalOcean Spaces / Cloudflare) — phase 2.
- Frontend UI for image zoom / annotation / image-only revision — already shipped across the main site per `CLAUDE.md`; the recall bank will reuse the same components.

---

## 8. How to verify

```bash
# Syntax check on every importer file
python -c "import ast, pathlib; [ast.parse(p.read_bytes()) for p in pathlib.Path(r'C:\Users\DIVYANSHU\Desktop\crack_cms\backend\importers\neetpg').rglob('*.py')]; print('OK')"

# Smoke import
python -c "import sys; sys.path.insert(0, r'C:\Users\DIVYANSHU\Desktop\crack_cms\backend'); import importers.neetpg as n; print(n.__file__); print(n.__version__)"

# Tests
python -m unittest discover -s backend/importers/neetpg/tests -v
```

All three commands are safe and read-only.

---

## 9. File map (final)

```
crack_cms/
├── docs/neetpg/
│   ├── _inventory.py
│   ├── _inventory.json          # populated on first run
│   ├── DATASET_ANALYSIS.md      ✅
│   ├── PDF_INDEX.md             ✅
│   ├── QUESTION_SCHEMA.md       ✅
│   ├── IMAGE_SCHEMA.md          ✅
│   ├── IMPORT_PLAN.md           ✅
│   ├── DEDUPLICATION_PLAN.md    ✅
│   └── PROGRESS_REPORT.md       ✅ (this file)
└── backend/importers/neetpg/
    ├── __init__.py              ✅
    ├── README.md                ✅
    ├── config.py                ✅
    ├── models.py                ✅
    ├── fingerprints.py          ✅
    ├── classifier.py            ✅
    ├── pdf_reader.py            ✅
    ├── ocr_engine.py            ✅
    ├── image_extractor.py       ✅
    ├── text_parser.py           ✅
    ├── topic_mapper.py          ✅
    ├── answer_key.py            ✅
    ├── deduplicator.py          ✅
    ├── enricher.py              ✅ (stub)
    ├── quality.py               ✅
    ├── storage.py               ✅
    ├── report.py                ✅
    ├── runner.py                ✅
    ├── management/              ✅
    │   ├── __init__.py
    │   └── commands/
    │       ├── __init__.py
    │       ├── neetpg_scan.py
    │       ├── neetpg_import.py
    │       ├── neetpg_import_all.py
    │       ├── neetpg_dedup.py
    │       ├── neetpg_repair.py
    │       └── neetpg_report.py
    └── tests/                   ✅
        ├── __init__.py
        ├── test_fingerprints.py
        ├── test_classifier.py
        ├── test_text_parser.py
        └── test_deduplicator.py
```

---

**Status: SCAFFOLD COMPLETE. Live extraction pending `bash` access to run the importer.**