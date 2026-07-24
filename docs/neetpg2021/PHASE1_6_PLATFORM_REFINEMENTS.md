# NEET-PG-2021 — Phase 1.6 Platform Refinements (bar raised to Medical Content Engine)

> **Status.** Phase 1 and Phase 1.5 are approved. This addendum captures the platform-grade requirements raised in the green-light message before any code is written.
>
> **What changed.** The importer is no longer a NEET-PG utility. It is the **CrackLabs Medical Content Engine (MCE)** — the single platform-wide pipeline that will ingest NEET PG, INI-CET, FMGE, USMLE, PLAB, and every future medical exam from now on. The 2021 PDF is its first and only customer until the benchmark clears the bar.
>
> **Hard rules still in force.** Only `material/neet-pg/NEET-PG-2021-Question-Paper-With-Solutions-PDF-1.pdf` is processed. No other PDF, no INI-CET, no bulk imports, no other exam.

---

## 1. From importer → platform

The new pipeline ships under a deliberately different namespace to make the scope shift explicit:

```
backend/mce/                                  ← Medical Content Engine (new)
  __init__.py
  profiles/                # ExamProfile + registry (NEET_PG, INI_CET, FMGE, USMLE, PLAB)
  engines/                 # Protocol-driven plug-in registry (layout, OCR, table, caption, modality, concept-graph)
  stages/                  # 8 numbered stages with explicit I/O contracts
  graph/                   # concept graph + related-question linker
  rag/                     # RAG-ready chunk emitter + future AI preparation
  api/                     # admin endpoints for review queue + verification grid
  cli.py                   # the entrypoint
  legacy/                  # old backend/importers/neetpg/*  (kept read-only for rollback only)
```

`backend/importers/neetpg/` is **frozen** at commit `919834e` for the duration of the benchmark. No further edits. The MCE is the new home for everything.

When the benchmark clears, the MCE is what every future exam import uses. The legacy folder is deleted in a single cleanup commit at platform-launch time.

---

## 2. Quality > speed (concrete consequences)

| Decision | Today (would-be-importer) | MCE |
|---|---|---|
| Render DPI | 300 | **400** for radiology / histology / ECG pages, **300** elsewhere (auto-decided per page by Stage 2) |
| OCR retry | none | 3-pass: page-level → region-level → image-level, picking the best-confidence result |
| LLM cleanup | opportunistic | **always on** for blocks with `ocr_confidence < 0.7` or `layout_confidence < 0.85`, capped at 4 calls/page |
| Image resolution cap | none | no cap — embedded image stored at its native PDF resolution; render-region crops at the highest DPI the page renders to without overflow |
| OCR languages | `eng` only | `eng+equ+osd` (math/equation + orientation/script detection) |
| Image preprocessing | one-pass deskew | **per-modality preprocessing** — radiograph gets CLAHE; histology gets color deconvolution; ECG gets line emphasis |
| Re-run cost | full re-import | **incremental** — every stage re-reads only its own artifact dir; only changed pages re-process |

If a stage takes 30 minutes per page, that is acceptable. Quality wins.

---

## 3. Source traceability — 8 fields, always

Every extracted object (block, image, asset, pearl, reference, unclassified region) carries these 8 fields without exception:

```python
class SourceTrace:
    pdf_filename: str
    pdf_sha256: str
    pdf_sha256_short: str
    page_number: int                     # 1-indexed
    bbox: list[float]                    # [x0, y0, x1, y1] in PDF points
    extraction_engine: str               # "layout_heuristic", "ocr_tesseract", "table_camelot", "llm_claude_opus", etc.
    confidence: float                    # stage-specific confidence 0.0-1.0
    pipeline_stage: str                  # "stage_2_layout" / "stage_3_images" / etc.
    extracted_at: datetime               # UTC, ISO 8601
```

The `SourceTrace` is a frozen dataclass — immutable, hashable, JSON-serialisable. It is the **first column** of every structured row. The platform can always answer "where exactly did this content come from?" — to the pixel, the engine, the second.

---

## 4. Pipeline debugging — every stage is a directory + manifest

Every stage writes its output to a typed folder + a stage manifest:

```
_artifacts/mce/neet_pg/2021/{pdf_sha16}/
  00_meta/
    pdf.json                # sha256, page count, author, creation date
    manifest.json           # full stage graph: which stage produced which files
  01_pdf_pages/
    p001.png ... p144.png   # 300/400 DPI page renders
    _index.json             # {page_number → png path, render_dpi, render_size_px}
  02_layout/
    p001.json ... p144.json # typed regions per page
    _index.json
  03_images/
    p001_img01.png ...      # high-fidelity embedded image + render-region crops
    _index.json             # {image_id → {path, page, bbox, modality, role, ...}}
  04_tables/
    p001_tbl01.json         # structured table cells
    p001_tbl01.png          # preview crop
    _index.json
  05_question_blocks/
    p001.json ...           # typed blocks per question
    _index.json
  06_ocr/
    p001.json ...           # OCR output per region + global
    _index.json
  07_structured/
    p001.json ...           # ParsedQuestion objects
    all_questions.jsonl     # flattened
    _index.json
  08_qa/
    overlays/p001.png       # annotated 6-color overlay
    grids/p001.png          # 3x2 side-by-side grid
    per_page_report.json
    summary.json
  09_graph/
    nodes.jsonl             # one row per concept node
    edges.jsonl             # one row per concept edge
    related_questions.jsonl
  10_rag/
    chunks.jsonl            # RAG-ready chunks (per Question + per Asset + per Pearl)
    _index.json
```

Every `_index.json` records the `source_trace` of every file it lists. The root `00_meta/manifest.json` is the single file you open when something looks wrong — it tells you exactly which stage's output to inspect.

---

## 5. Frontend expectations (now explicit, all 12 checks)

The 12 manual checks from Phase 1.5 §8 are unchanged but **graduated to acceptance criteria**:

| # | Check | Acceptance |
|---|---|---|
| 1 | Image questions display correctly | All stem-images render above the stem text — no image is rendered inline as a `<br>`-separated string |
| 2 | Multiple images per question | 3+ stem-images render as a horizontal carousel with prev/next + counter |
| 3 | Zoom | Click opens a full-screen dialog |
| 4 | Fullscreen | F-key or button uses `requestFullscreen()` |
| 5 | Pan | Drag-zoom on desktop |
| 6 | Pinch zoom | Two-finger gesture scales the image on mobile |
| 7 | Explanations formatted nicely | Bold key terms, bullet lists, paragraphs, no raw `\n` rendering |
| 8 | Tables readable | `QuestionAsset.asset_type='table'` renders as a `<table>` with zebra-striping from JSON cells, NOT an image |
| 9 | Captions with correct figure | Italic, prefixed `Fig. N:`, immediately below the image |
| 10 | Clinical pearls in distinct card | Separate card with colored border + icon |
| 11 | Mnemonics in distinct card | Separate card with 🧠 icon |
| 12 | References with locator | 📚 footnote with link |

### Required new primitives (Phase 4 deliverables)

* `<ConfidenceBadge />` — green ≥ 0.9 / amber 0.7-0.9 / red < 0.7
* `<ImageViewer />` — click-to-zoom, fullscreen, pan, pinch zoom
* `<ImageCarousel />` — multi-image horizontal carousel
* `<ExplanationRenderer />` — markdown, medical typography
* `<TableRenderer />` — JSON cells → accessible `<table>`
* `<PearlCard />` — clinical_pearl / high_yield / mnemonic / memory_trick / pitfall
* `<ReferenceFootnote />` — 📚 with citation + locator link
* `<PageOnSourceLink />` — opens the source page with the bbox overlay rendered on top
* `<ModalityBadge />` — radiograph / CT / MRI / ECG / histology / gross / etc., colored by modality

### UI identity — distinctly NOT UPSC CMS

The NEET PG site must read as a **medical-first platform**, not a generic exam-prep site:

* Color palette: emerald / teal / medical green + clinical accent (CT blue, histology magenta)
* Iconography: stethoscope, ECG waveform, microscope, X-ray, capsule — medical-specific
* Typography: high-readability sans for body, monospace for dose / lab values
* Hero: animated ECG waveform SVG overlay
* Subject grid: each card has its own icon + gradient + live PYQ count
* Image-first question cards: image occupies ≥ 35 % of the card height when present

Existing `/neet-pg` page from `919834e` already establishes the visual identity; the new primitives slot into `NeetPgPlayer.tsx` without changing the page chrome.

---

## 6. Knowledge graph — Phase 9 deliverable

Every imported question emits concept nodes + edges. Node types:

```
Subject       Topic         Subtopic
Disease       Drug          Investigation
Anatomy       Physiology    Biochemistry
Pathology     Radiology     Surgery
```

Edges (typed, weighted):

```
question → subject         (weight = 1.0)
question → topic           (weight = 1.0)
question → subtopic        (weight = 1.0)
question → disease         (weight = confidence)
question → drug            (weight = confidence)
question → investigation   (weight = confidence)
question → anatomy         (weight = confidence)
question → physiology      (weight = confidence)
question → biochemistry    (weight = confidence)
question → pathology       (weight = confidence)
question → radiology       (weight = confidence)
question → related_question (weight = similarity, computed at ingest time)
```

Concept extraction is **stage 9** of the pipeline, runs after Stage 7 (structured). It uses the existing `ai_engine.services.ai_complete()` round-robin to map question text + options + explanation into typed concepts. The graph is persisted in three new tables (`Concept`, `QuestionConcept`, `ConceptEdge`) and exposed via REST endpoints for the future RAG consumer.

Related-question linking is computed at ingest time using:
* Same `recall_text_hash` cluster (exact dupes)
* L4 pHash image dedup (image-level related)
* Embedding cosine ≥ 0.85 on stem text (semantic related)
* Explicit graph traversal (concept-overlap)

---

## 7. AI / RAG preparation — Phase 10 deliverable

Every Question emits a set of RAG-ready chunks the day it is ingested:

```
QuestionChunk {
  chunk_id: str
  question_id: int
  chunk_type: "stem" | "options" | "answer" | "explanation"
            | "clinical_pearl" | "high_yield" | "mnemonic"
            | "reference" | "table" | "image_caption"
  body: str
  image_refs: list[str]
  asset_refs: list[str]
  pearl_refs: list[str]
  reference_refs: list[str]
  source_trace: SourceTrace
  embedding_model: str = "pending-v1"
  embedding: list[float] | None = None
  indexed_at: datetime | None = None
}
```

Chunks are JSONL-persisted at `10_rag/chunks.jsonl`. The future embedding worker can re-read this file without re-running the pipeline. The chunk structure is deliberately aligned with the existing `ai_engine.rag_pipeline` schema so the existing RAG store can ingest the MCE output with no migration.

---

## 8. Verification — continuous, not final

Three verification layers run **continuously during the import**, not just at the end:

### 8a. Stage-internal sanity checks

Every stage asserts its output is sane:
* Stage 2 — every page has ≥ 1 region
* Stage 3 — image counts match `page.get_images()` count ± 0
* Stage 4 — every table has ≥ 2 rows and ≥ 2 columns
* Stage 5 — every question block has a `stem` + ≥ 2 options
* Stage 6 — every region with `type != 'image'` has OCR text
* Stage 7 — every `ParsedQuestion` has `page_number`, `bbox`, `source_trace`

Any assertion failure stops the run with a stage-specific exit code (e.g. `MCE_STAGE_3_FAIL`).

### 8b. Stage-8 page-level QA

Per-page PASS/FAIL gate:
* PASS = `question_reconstruction_confidence ≥ 0.85` AND `unclassified_blocks.count ≤ 2` AND `image_mapping_recall ≥ 0.95`
* FAIL = anything else; DB writes blocked for that page

The 3×2 debug grid PNGs (per Phase 1.5 §5) are written for **both PASS and FAIL** pages — FAIL pages get a red border.

### 8c. Continuous extraction-vs-PDF diff

Every 10 pages, the pipeline samples 1 page and:
* Renders the original page to PNG
* Renders a "reconstructed" page (all blocks re-typeset from the structured JSON) to PNG
* Computes a `pixel_diff_score` (Pillow `ImageChops.difference`)
* Computes a `text_diff_score` (per-region character-level edit distance)
* Writes the diff to `08_qa/continuous_diff/p{NN}.json`

If the running average of `text_diff_score` drops below 0.90, the pipeline **halts** and reports the failing page. The user decides whether to fix the pipeline or accept the degradation.

---

## 9. The 7 reports — file paths

| Report | Path |
|---|---|
| Extraction report | `docs/neetpg2021/NEET2021_EXTRACTION_REPORT.md` |
| Image mapping report | `docs/neetpg2021/IMAGE_MAPPING_REPORT.md` |
| OCR pipeline report | `docs/neetpg2021/OCR_PIPELINE_REPORT.md` |
| Quality comparison report | `docs/neetpg2021/QUALITY_COMPARISON_REPORT.md` |
| Importer redesign report | `docs/neetpg2021/IMPORTER_REDESIGN_REPORT.md` |
| Pipeline architecture | `docs/neetpg2021/PIPELINE_ARCHITECTURE.md` (consolidated from PHASE1 + PHASE1_5 + PHASE1_6) |
| Validation report | `docs/neetpg2021/VALIDATION_REPORT.md` |

The **Validation report** is the one that answers "did we hit the success criteria?" It contains the side-by-side comparison the user manually walks through.

---

## 10. Hard gates (the user said STOP; I obey)

1. Only `material/neet-pg/NEET-PG-2021-Question-Paper-With-Solutions-PDF-1.pdf` is processed.
2. No other PDF in `material/neet-pg/` is touched.
3. No PDF in `material/inicet-pg/` is touched.
4. No bulk import commands are run.
5. No INI-CET, FMGE, USMLE, or PLAB imports.
6. After Phase 6 (reports), the pipeline stops and waits for user approval.
7. After approval, the same pipeline is reused for every remaining PDF — no per-exam forks.

---

## 11. Phase 2 code plan (independently testable stages)

Phase 2 is split into 12 sub-stages, each independently testable. After each sub-stage, the pipeline can be invoked on a single page (e.g. page 38 of the 2021 PDF) and the artefact tree is verified by the user before the next sub-stage starts.

| # | Sub-stage | Test surface |
|---|---|---|
| 2.1 | `mce/profiles/` — ExamProfile + registry | `pytest tests/mce/test_profiles.py` — profile for neet_pg / ini_cet loads |
| 2.2 | `mce/stages/stage_1_render.py` + 4-stage DPI selector | `python -m mce.cli --pdf <path> --pages 38` → check `01_pdf_pages/p038.png` |
| 2.3 | `mce/engines/layout_heuristic.py` + Protocol | `python -m mce.cli --pdf <path> --pages 38` → check `02_layout/p038.json` |
| 2.4 | `mce/stages/stage_2_layout.py` | verify every page has ≥ 1 region |
| 2.5 | `mce/engines/ocr_tesseract.py` + Protocol | unit test on a known PNG |
| 2.6 | `mce/stages/stage_3_images.py` | `03_images/` artifact count matches `page.get_images()` |
| 2.7 | `mce/engines/table_camelot.py` | unit test on a synthetic table page |
| 2.8 | `mce/stages/stage_4_tables.py` + `stage_5_question_blocks.py` | `05_question_blocks/p038.json` has stem + ≥ 4 options for known Q |
| 2.9 | `mce/stages/stage_6_ocr.py` | `06_ocr/p038.json` has OCR text for every non-image region |
| 2.10 | `mce/stages/stage_7_structured.py` | `07_structured/all_questions.jsonl` line count matches question count |
| 2.11 | `mce/stages/stage_8_qa.py` + `debug_overlay.py` | `08_qa/overlays/p038.png` opens; color legend matches |
| 2.12 | `mce/stages/stage_9_graph.py` + `stage_10_rag.py` + DB writer | DB rows present + `10_rag/chunks.jsonl` written |

After all 12 sub-stages pass on page 38 alone, the full 144-page run is executed end-to-end. After it succeeds, Phase 3 (DB migrations), Phase 4 (frontend), Phase 5 (manual QA), and Phase 6 (7 reports) begin.

---

## 12. What success looks like

When Phase 2-6 complete, the user should be able to:

1. Open `http://localhost:3000/neet-pg` and see a medical-first premium landing page (already shipped).
2. Click "2021" → see the practice grid.
3. Open any question and see:
   * Image carousel if multiple images
   * Clinical pearl card (colored)
   * Mnemonic card (🧠)
   * Reference footnote (📚) with locator
   * Table renderer for any tables
   * Explanation with medical typography
   * Confidence badge (colored)
   * "Show on source page" link → source page render with bbox overlay
4. Compare every page against `material/neet-pg/NEET-PG-2021-Question-Paper-With-Solutions-PDF-1.pdf` and struggle to find missing content.
5. Read `docs/neetpg2021/VALIDATION_REPORT.md` and see measured confidence per stage + remaining limitations documented honestly.
6. Approve. Then the same pipeline runs on every remaining NEET PG and INI-CET PDF. No per-exam forks.

Begin.
