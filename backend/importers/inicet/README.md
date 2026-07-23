# NEET PG Importer

Standalone production-grade extraction pipeline for the NEET PG / INI-CET / AIIMS PG recall-based PDF dataset.

This package is **isolated** from the existing production code. It does not modify `INSTALLED_APPS`, models, migrations, settings, or the frontend. It writes JSONL + extracted images under `_output/` and emits a manifest for resumability.

## Goals

- Recall-safe: every question keeps provenance (PDF sha256 + page + OCR confidence).
- Resumable: a manifest tracks per-source progress; re-runs skip finished sources.
- Idempotent: deduplication runs across prior imports without overwriting provenance.
- Modular: each stage is a standalone module so future migrations only touch the relevant file.

## Layout

```
backend/importers/neetpg/
├── __init__.py
├── README.md
├── config.py                 # env-driven settings
├── fingerprints.py           # sha256 + page metadata
├── classifier.py             # digital / scanned / hybrid per page
├── pdf_reader.py             # PyMuPDF wrapper
├── ocr_engine.py             # tesseract + OpenCV preprocessing
├── image_extractor.py        # embedded + rendered images, pHash/dHash
├── text_parser.py            # question/option/answer/explanation regex
├── topic_mapper.py           # subject + topic + subtopic mapping
├── answer_key.py             # answer key detection (inline / trailing)
├── deduplicator.py           # sha + rapidfuzz + embedding + image-hash
├── enricher.py               # AI enrichment stub
├── quality.py                # quality checks
├── storage.py                # atomic JSONL + manifest writers
├── models.py                 # dataclasses for Question / Option / Image / Source
├── report.py                 # markdown report generators
├── runner.py                 # orchestration entrypoint
├── management/
│   └── commands/
│       ├── neetpg_scan.py
│       ├── neetpg_import.py
│       ├── neetpg_import_all.py
│       ├── neetpg_dedup.py
│       ├── neetpg_repair.py
│       └── neetpg_report.py
└── tests/
    ├── __init__.py
    ├── test_fingerprints.py
    ├── test_classifier.py
    ├── test_text_parser.py
    └── test_deduplicator.py
```

## Quick start

```bash
# Activate the project venv
.venv\Scripts\Activate.ps1

# Inventory + scan (no extraction)
python -m backend.importers.neetpg.runner --scan --source-dir "C:/Users/DIVYANSHU/Desktop/crack_cms/neet-pg_and_material"

# Import every PDF in the source dir
python -m backend.importers.neetpg.runner --source-dir "C:/Users/DIVYANSHU/Desktop/crack_cms/neet-pg_and_material"

# Import a single PDF
python -m backend.importers.neetpg.runner --pdf "C:/.../Anatomy pyqs.pdf"

# Re-run dedup over previously parsed JSONL
python -m backend.importers.neetpg.runner --dedup

# Generate reports from the latest run
python -m backend.importers.neetpg.runner --report
```

Or via Django management commands (requires wiring into `INSTALLED_APPS`; see `management/commands/`):

```bash
python manage.py neetpg_scan --source-dir <path>
python manage.py neetpg_import --pdf <file>
python manage.py neetpg_import_all
python manage.py neetpg_dedup
python manage.py neetpg_repair
python manage.py neetpg_report
```

## Environment variables

| Var | Default | Purpose |
|---|---|---|
| `NEETPG_OUTPUT_DIR` | `backend/importers/neetpg/_output` | output root |
| `NEETPG_OCR_DPI` | `200` | render DPI for OCR fallback |
| `NEETPG_OCR_LANG` | `eng` | tesseract language |
| `NEETPG_BATCH_SIZE` | `500` | DB bulk_create batch (phase 2) |
| `NEETPG_MIN_OCR_CONFIDENCE` | `60` | quality threshold |
| `NEETPG_ENABLE_LLM_FALLBACK` | `false` | opt-in AI parsing |
| `NEETPG_DEDUP_THRESHOLD` | `0.92` | fuzzy threshold |
| `NEETPG_IMAGE_PHASH_THRESHOLD` | `5` | Hamming distance |

## Optional dependencies

```
pip install pymupdf pdfplumber pytesseract opencv-python pillow imagehash rapidfuzz sentence-transformers tiktoken
```

The runner degrades gracefully when an optional dep is missing — it logs a warning and skips that stage.

## Output

```
backend/importers/neetpg/_output/
├── raw/<sha16>__<filename>.jsonl      # per-page text + image index
├── pages/<sha16>/p<NNNN>.png           # 200 DPI page renders (scanned only)
├── images/<sha16>/p<NNNN>_i<NN>.<ext>  # extracted embedded images
├── parsed/<sha16>.questions.jsonl      # parsed questions
├── manifest.json                       # resumable state
└── reports/<run_id>/*.md               # IMPORT_REPORT.md, OCR_REPORT.md, …
```

## Extending

- Plug a new AI provider into `enricher.py::enrich_question`.
- Add a new subject keyword list to `topic_mapper.py::SUBJECT_KEYWORDS`.
- Replace the keyword topic mapper with a zero-shot classifier in `topic_mapper.py::map_with_model`.
- Wire DB writes by switching `storage.py::Writer` to `DjangoWriter` in phase 2 (after stakeholder approval).

## Safety

- We never delete a question — soft-delete via `is_active=False`.
- We never overwrite provenance — append-only.
- We never embed images inside question text.
- We never claim recall content is official — disclaimer surfaces in every UI surface that displays a question.
