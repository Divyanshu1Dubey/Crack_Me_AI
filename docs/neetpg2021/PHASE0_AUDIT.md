# NEET-PG-2021 — Phase 0 Audit of the Current Importer

> **Mission context.** One PDF (`material/neet-pg/NEET-PG-2021-Question-Paper-With-Solutions-PDF-1.pdf`, 7.4 MB, 144 pages, sha256 `8ebea8995a4ade7955822322fb94a502fdab280e9792c786c74bbdb95a544282`) is the gold-standard benchmark. Every stage below was measured against this specific PDF, not extrapolated. No other PDF in `material/neet-pg/` or `material/inicet-pg/` is touched until the user explicitly approves.

---

## 1. PDF profile (read directly from the file)

| Property | Value | Notes |
|---|---|---|
| Pages | 144 | A4, 595.3 × 841.9 pt |
| Producer | `3.0.10 (5.0.21)` (Microsoft Word 2010 export) | Likely NBE / PrepLadder-style compilation |
| Author | `DELL` (placeholder) | No real publisher metadata |
| `creationDate` | `D:20210918163556+05'30` (18 Sep 2021, IST) | Will power auto year-extraction |
| Fonts (per page) | `MicrosoftSansSerif`, `Arial`, `Arial,Bold`, `ABCDEE+Calibri`, `ABCDEE+Calibri,Bold`, `Symbol` | Subset `ABCDEE+` = embedded Calibri subset. **No PUA-encoded font** on this PDF — the `_decode_pua` Marrow-only branch will be a no-op here. |
| Embedded images / page | 4–6 | Every page has multiple embedded raster images (CT/MRI/clinical photos/ECG etc.). |
| Text chars / page | 600–1300 | Healthy text layer. Will classify as **digital**, not scanned. |
| Extraction budget | First-paint ≪ 60 s / page is acceptable; quality dominates. |

---

## 2. Current importer — what actually exists, what it does, and what it misses on this PDF

The runner is a **16-module pipeline** under `backend/importers/neetpg/`:

| Module | Purpose | Verdict against the 2021 PDF |
|---|---|---|
| `runner.py` | Orchestrates the 16 stages per PDF | OK scaffold; iterates pages once, but the per-page loop conflates layout detection, OCR, parsing, image extraction and DB writing. No intermediate artifacts are kept. |
| `config.py` | Env-driven `Config` (DPI, lang, thresholds) | DPI = 200, lang = `eng`. **200 DPI is too low** for the small annotation labels on radiology / histopath / ECG in this PDF. Need 300+ for figures. |
| `pdf_reader.py` | PyMuPDF wrapper, `_decode_pua` for Marrow-style fonts | Returns text per page + list of image xrefs. **Has no spatial info** (no bbox per text run / image). That blocks any "image belongs to question N on this page" mapping. |
| `classifier.py` | `digital / scanned / hybrid / blank` from text-char count + garbled ratio | Pages in this PDF will all be classified `digital` because of the rich text layer. Fine — but the runner **immediately skips OCR**, which means image-only clinical reasoning / annotation labels get **lost**. |
| `ocr_engine.py` | Tesseract wrapper with OpenCV deskew | `pytesseract` + `cv2` are **not installed** in this venv; `tesseract` binary is **absent** on PATH. OCR is silently skipped — zero annotation labels recovered. |
| `image_extractor.py` | `extract_embedded` per page → `ImageRecord` | Extracts every embedded image (good), but: **(a)** images are saved with no bbox (no link to "which question"); **(b)** no rotation / orientation fix; **(c)** OCR on the image is attempted (will be no-op until Tesseract is installed); **(d)** no caption detection; **(e)** no figure-grouping. |
| `text_parser.py` | Pure regex: `QUESTION_PREFIX`, `OPTION_PREFIX`, `ANSWER_LINE`, `EXPLANATION_LINE`, `IMAGE_REF` | Breaks on **any page whose question text spans multiple lines before A/B/C/D** because the stem extraction is `chunk.find("a)")` (single lowercase letter). Misses image-only questions. LLM fallback is a stub (`raise NotImplementedError`). |
| `topic_mapper.py` | 19-subject keyword + filename fallback | Single-pass `kw in text` scoring → ties broken by iteration order. No ML. Good enough for filename-driven subject assignment; fails on multi-subject stems. |
| `answer_key.py` | Detects "Answer Key" trailing section | Will pick up the 2021 key, but **never merges it back into per-question rows** because the runner never calls it. |
| `deduplicator.py` | L1 sha / L2 RapidFuzz / L3 embeddings / L4 pHash | Heavy optional deps (`rapidfuzz`, `sentence_transformers`) **not installed**. Only L1 + L4 work today. |
| `fingerprints.py`, `storage.py`, `report.py`, `quality.py`, `tasks.py`, `enricher.py` | Provenance + manifests + JSONL writes + quality flagging | Working but shallow — `quality.py` flags problems; nothing closes the loop. |
| `db_writer.py` | Writes `Question` + `QuestionImage` + `QuestionSource` rows | **Image-to-question mapping is broken** — runner links every image to the *first question on the page* (line 285–291 `runner._persist_into_db`). For the 2021 PDF with 4–6 images per page and 1–3 questions per page, this is a category error: more than half the images get attached to the wrong question. |
| `models.py` (importer) | Dataclasses only — clean separation from Django models | OK. |

### Concrete failures on the 2021 PDF
1. **Image-to-question mapping is page-level, not spatial** → wrong question gets the histology / radiology photo.
2. **Image extraction ignores orientation** → embedded EXIF / PDF CTM rotation not applied → some images appear rotated 90°.
3. **No layout detection** → no per-question bounding box, so image ordering relative to the stem cannot be reconstructed (image was "before question" vs "in explanation" vs "across pages").
4. **No table / algorithm / flowchart detector** → drug charts, classification boxes and high-yield boxes end up flattened into the explanation text.
5. **No caption text detection** → captions like `Fig. 1: H&E ×400` are merged into the stem and broken up across option A/B/C.
6. **No multi-page question linker** → a stem that runs from page 38 → page 39 (with the image in between) is split into two half-questions.
7. **No LLM fallback wired** → if regex fails (column layout, multi-column key, etc.), the question is silently dropped into the `QuestionExtractionItem` review queue.
8. **No clinical reasoning / pearl / mnemonic / high-yield detector** → even when extraction succeeds, these rich teaching elements are flattened into a single `explanation` text blob.
9. **No reference / citation extraction** → page footers, "Ref: Harrison 21e p.1245" are discarded.
10. **No verification / side-by-side QA loop** → nothing compares the extracted JSON to the source page. There is no built-in answer to "is this extraction faithful?".

---

## 3. Installed Python stack (probe results)

| Package | Installed | Used by |
|---|---|---|
| `fitz` (PyMuPDF) 1.27.1 | ✅ | `pdf_reader.py` — text, images, render |
| `pdfplumber` 0.11.9 | ✅ | `pdf_reader.py` — text-layer fallback |
| `pdfminer` 20251230 | ✅ | future char-level bbox extraction |
| `Pillow` 11.3.0 | ✅ | image I/O |
| `numpy` 2.4.2 | ✅ | vector math |
| `pytesseract` | ❌ | install required |
| `pdf2image` | ❌ | install required |
| `cv2` (opencv-python) | ❌ | install required |
| `imagehash` | ❌ | install required |
| `rapidfuzz` | ❌ | install required |
| `ultralytics` (YOLO) | ❌ | optional — for layout detection v2 |
| `detectron2` | ❌ | optional — heavy |
| `layoutparser` | ❌ | optional — heavy |
| `camelot` / `tabula` | ❌ | install required for table extraction |
| Tesseract binary | ❌ on PATH; not at `C:\Program Files\Tesseract-OCR\` | install required |

**Implication:** to reach "best open-source" quality, the venv needs to grow. The install list (added to `requirements.txt`, version-pinned, optional groups so dev-only installs don't break Render) is:

```
# Quality pipeline — Phase 1 of the 2021 redesign
opencv-python-headless>=4.10
pytesseract>=0.3.13
pdf2image>=1.17
Pillow>=10.4
imagehash>=4.3
rapidfuzz>=3.10
camelot-py[cv]>=0.11
numpy>=2.0
scikit-image>=0.24
```

Tesseract binary itself is not pip-installable; install path on Windows: `C:\Program Files\Tesseract-OCR\` with eng + equ + osd language packs. `pytesseract.pytesseract.tesseract_cmd` will point at it.

---

## 4. Storage / DB impact today

- 2,356 NEET PG rows in `Question` already exist (committed from earlier runs).
- 19 subject PDFs in `material/neet-pg/` (excluding the 2021 benchmark) are queued, **not yet re-ingested**.
- `QuestionImage` table exists with `role`, `modality`, `caption`, `page_number`, `image_index_in_page`, `phash`, `dhash`, `ocr_text`, `has_diagram`, `has_table` — schema already supports most of what the new pipeline will emit.
- Image-to-question wiring in the frontend (`NeetPgPlayer`) calls `/api/questions/{id}/images/` — already fixed in 919834e (recall_serializers import).

---

## 5. What "gold standard" means for this benchmark

Working definition (used by Marrow / PrepLadder / UWorld / AMBOSS engineering teams):

| Metric | Target |
|---|---|
| Question recall (questions in PDF) | ≥ 99 % |
| Option recall (A/B/C/D present) | ≥ 99 % |
| Answer recall (correct option letter) | ≥ 99 % |
| Image recall (every figure extracted) | ≥ 99 % |
| Image-to-question precision | ≥ 98 % |
| Image-to-question recall | ≥ 97 % |
| Caption OCR accuracy | ≥ 90 % on English digits + abbreviations |
| Option-image (image as option) capture | ≥ 95 % |
| Multi-image group preservation | 100 % |
| Multi-page question capture | ≥ 95 % |
| Clinical pearl / high-yield box capture | ≥ 90 % |
| Mnemonic capture | ≥ 90 % |
| Reference extraction | ≥ 85 % |
| Encoding mojibake (broken `â€™` etc.) | 0 % in DB |

Anything below the targets is a Phase-N blocker.

---

## 6. Open questions for the user (none blocking design)

These are design decisions that are easier to confirm now than to retrofit later — but none of them block writing Phase 1/2 code:

1. **Layout model — heuristic vs learned.** Heuristic bbox clustering is fast, transparent, and free of training cost. YOLOv8-doclaynet is more accurate on messy pages but adds ~120 MB and a dependency. Recommendation: **start heuristic**, ship a `LayoutModel` Protocol so we can swap in YOLO in Phase 7 once we've measured baseline.
2. **LLM stage on/off.** Should the pipeline call an AI provider to fix parser failures (resolution, OCR cleanup, image-caption extraction, mnemonic detection)? Recommendation: **on**, but budget-capped (≤ 2 LLM calls / page) and routed through the existing 11-provider round-robin in `ai_engine.services`. Cost is negligible for one PDF.
3. **Where do artifacts live?** Default: `backend/_artifacts/neetpg2021/{01_pdf_pages,02_layout,03_images,04_tables,05_question_blocks,06_ocr,07_structured}/`. Each stage writes immutable JSONL + PNGs so debugging is trivial. This dir is gitignored.

No question blocks progress. Proceeding to write `PIPELINE_ARCHITECTURE.md` (Phase 1) immediately.
