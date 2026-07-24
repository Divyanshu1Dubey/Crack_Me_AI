# NEET-PG-2021 — Phase 1.5 Refinements (User Review)

> **Purpose.** Map every one of your eight review points to a concrete design change. No code yet — the design now reflects all eight. The numbered sections below correspond 1:1 to your review items.

This addendum is additive to `PHASE1_ARCHITECTURE.md`. Where the original doc already covered a point, I cross-reference it; where it was missing, I extend it.

---

## 1. Preserve educational structure, not just content

The 2021 PDF is a teaching instrument, not a question dump. Every teaching element gets its own structured row at every layer:

| Layer | Structure |
|---|---|
| **Stage 5 output** (`05_question_blocks/p{NN}.json`) | Every question block already separates `stem`, `options[A..F]`, `answer_labels`, `explanation`, `clinical_pearl`, `high_yield`, `mnemonic`, `references[]`, `tables[]`, `figures[]`, `captions[]`. Each field is a top-level key on the block object — never collapsed into `explanation`. |
| **Stage 7 output** (`07_structured/`) | Same fields, lifted into the `ParsedQuestion` dataclass. `ParsedQuestion` already has `options`, `answer_labels`, `explanation`, `subject`, `topic`, `subtopic`; **extending it now with** `clinical_pearl`, `high_yield_points: list[str]`, `mnemonic`, `references: list[str]`, `tables: list[AssetRef]`, `figures: list[ImageRef]`, `captions: list[str]`. |
| **DB layer** | Already: `Question` + `QuestionImage`. **Adding**: `QuestionAsset` (table / algorithm / flowchart / drug_chart), `QuestionPearl` (clinical_pearl / high_yield / mnemonic / memory_trick / pitfall), `QuestionReference` (textbook / journal / guideline / official_key). |

The Stage-7 JSONL output guarantees every field round-trips to the DB independently. The frontend renders each field as its own UI section (see point 8 below).

**Cross-ref:** `PHASE1_ARCHITECTURE.md §4` (data model), §5 (frontend render order).

---

## 2. Never silently discard content — the "unclassified block" is a first-class object

This is the most important architectural change. Today, anything the regex parser doesn't recognise falls into the `QuestionExtractionItem` review queue. The new pipeline treats that queue as a typed region on every page, not a side-channel.

**New typed region** in Stage 2 / 5 / 7:

```json
{
  "id": "p38.b17",
  "type": "unclassified",
  "bbox": [72, 720, 524, 760],
  "page_number": 38,
  "text_raw": "Harrison 21e p.1245 — HFE gene C282Y homozygotes",
  "ocr_confidence": 0.91,
  "layout_confidence": 0.0,
  "candidate_types": ["footnote", "reference"],
  "warnings": ["could not assign a typed role; routed to unclassified"]
}
```

**Stage-7 guarantees**:
* Every `unclassified` block is attached to the closest preceding `QuestionBlock` (or to the page itself if no preceding question exists) and persisted in the `ParsedQuestion.unclassified_blocks` list.
* If a question has **any** unclassified block attached, `Question.needs_review = True` and `Question.review_reason = "unclassified_block_attached"` — so the admin queue is populated without losing the block.
* The Stage-8 verification report lists every unclassified block per page: page, bbox, raw text, suggested type.

**Cross-ref:** §6 (verification), new §9 below.

---

## 3. Preserve page coordinates everywhere

Every extracted object — image, option, stem, table, pearl, reference, unclassified block — carries its source coordinates:

| Field | Type | Stored at |
|---|---|---|
| `page_number` | `int` (1-indexed) | All structured rows |
| `bbox` | `[x0, y0, x1, y1]` in PDF points (top-left origin) | All structured rows |
| `page_spans` | `[(page_number, bbox), …]` for multi-page content | `QuestionImage` |
| `pdf_coordinates` | `{ width, height }` of the source page | top of every artifact file |

**Schema enforcement** (DB layer):

```python
# Each new model gets a JSONField bbox default=[] with validator that
# rejects bboxes outside [0, page_width] / [0, page_height].
# QuestionAsset, QuestionPearl, QuestionReference, QuestionImage.page_spans
# ALL have the same validator.
```

The frontend can then offer a **"show on source page"** link that opens `/neet-pg/page/{pdf_sha16}/{page}?bbox=...` and overlays the bbox on the page render. This is the debugging surface the missing pixel-level traceability needs.

**Cross-ref:** `PHASE1_ARCHITECTURE.md §4` (data model).

---

## 4. Confidence scores on every extracted item

Four orthogonal confidence dimensions, recorded on every structured row:

| Score | Range | Meaning |
|---|---|---|
| `ocr_confidence` | 0.0 – 1.0 | Per-block Tesseract mean confidence; 1.0 = no OCR used (digital text). |
| `layout_confidence` | 0.0 – 1.0 | Stage-2 classifier's confidence in the assigned region type. 0.0 = unclassified. |
| `image_mapping_confidence` | 0.0 – 1.0 | Stage-7 confidence that an image belongs to this question (vs the page globally). Computed from bbox-overlap ratio + temporal-proximity heuristic. |
| `question_reconstruction_confidence` | 0.0 – 1.0 | Aggregate of the three above, plus option-count match, answer-detection match, explanation-presence match. Used by Stage 8 as the page-PASS threshold. |

**Storage:**
* Every `ParsedQuestion` row carries all four.
* `Question` gets `ocr_confidence`, `layout_confidence`, `image_mapping_confidence`, `question_reconstruction_confidence` columns (migration 0025).
* `Question.needs_review` is now driven by `question_reconstruction_confidence < 0.85` instead of the previous 0.70 threshold (loosened for one stage to give the LLM cleanup stage a chance, tightened back to 0.90 in the DB).

**Front-end:** a tiny `<ConfidenceBadge confidence={…} />` component shows a colored dot next to every question (green ≥ 0.9, amber 0.7-0.9, red < 0.7) so users can spot low-confidence rows without a separate report.

**Cross-ref:** §4 (data model), §5 (frontend).

---

## 5. Visual verification — debug pages

Stage 8 produces two distinct debug artefacts, not just a JSON report:

### 5a. Annotated page overlays (per-page)

`backend/_artifacts/neetpg2021/08_qa/overlays/p{NN}.png` — for every page:

| Overlay color | Meaning |
|---|---|
| **Green outline** | Region Stage-2 detected as `stem` / `option` / `explanation` (and matched the typed expectation) |
| **Yellow outline** | Region detected but confidence < 0.85 (flagged for review) |
| **Red outline** | Region unclassified — see unclassified-block report |
| **Magenta outline** | Image bbox from Stage 3 (embedded + render-region crops) |
| **Cyan outline** | Table / algorithm bbox from Stage 4 |
| **Orange outline** | Final image-to-question mapping (drawn on top of the image, with an arrow to the target question bbox) |

A single PNG per page lets you eyeball the entire pipeline's output at once.

### 5b. Final mapping grid (per-page)

`backend/_artifacts/neetpg2021/08_qa/grids/p{NN}.png` — a 3×2 grid showing, side-by-side:

| Slot | Content |
|---|---|
| Top-left | Original page render |
| Top-right | Stage-2 layout regions overlaid |
| Mid-left | Stage-3 image regions overlaid |
| Mid-right | Stage-4 table regions overlaid |
| Bot-left | Stage-7 question-block bboxes overlaid |
| Bot-right | Final image-to-question mapping arrows |

Every grid PNG is also stored at `08_qa/grids/_index.html` as a clickable thumbnail page so the user can flip through all 144 pages without opening files.

**Cross-ref:** §6 (verification), new §11 below.

---

## 6. Extensibility — Protocol interfaces

The pipeline is built around four `Protocol` interfaces (Python `typing.Protocol`, no inheritance required, swappable at runtime via `cfg.engine_registry`). Each is a small contract — under 50 lines.

```python
# backend/importers/neetpg/engines/__init__.py
class LayoutEngine(Protocol):
    name: str
    def detect(self, page_png: Path, page_text: list[WordSpan]) -> list[Region]: ...
    def is_available(self) -> bool: ...

class OCREngine(Protocol):
    name: str
    def ocr(self, image_path: Path, lang: str = "eng") -> tuple[str, float]: ...
    def is_available(self) -> bool: ...

class TableEngine(Protocol):
    name: str
    def extract(self, page_png: Path, page_text: list[WordSpan]) -> list[TableBlock]: ...
    def is_available(self) -> bool: ...

class CaptionEngine(Protocol):
    name: str
    def caption(self, image_path: Path, modality_hint: str) -> tuple[str, float]: ...
    def is_available(self) -> bool: ...
```

Default implementations:
* `LayoutEngine` → `HeuristicLayoutEngine` (pdfminer-bbox clustering)
* `OCREngine` → `TesseractOCREngine` (pytesseract + OpenCV preprocessing)
* `TableEngine` → `CamelotTableEngine` (lattice + stream)
* `CaptionEngine` → `OCRPlusLLMCaptionEngine` (OCR → LLM polish → fallback to "Fig.")

Tomorrow's swap path:
* Want a learned layout model? Implement `YoloLayoutEngine(LayoutEngine)`, register via `cfg.layout_engine = "yolo"`. No other file changes.
* Want a better OCR? Implement `EasyOCREngine(OCREngine)`. Register.
* Want a different table extractor? Implement `TableTransformerEngine(TableEngine)`. Register.

The CLI flag `--layout-engine heuristic|yolo --ocr-engine tesseract|easyocr` lets you A/B test engines against the same PDF without code changes.

**Cross-ref:** `PHASE1_ARCHITECTURE.md §3` (tool selection).

---

## 7. Separate NEET PG vs INI-CET from the start

Today, `db_writer.write_question` hardcodes `exam_type="neet_pg"`. That single line is the root cause of every future "the INI-CET subject got tagged as NEET PG" bug.

**New design:**

```python
# backend/importers/neetpg/config.py
class ExamProfile:
    """Distinct import policy per exam type."""
    exam_type: Literal["neet_pg", "ini_cet", "usmle", "fmge"]
    exam_source: str         # e.g. "NEET PG (recall)" / "INI-CET (recall)"
    subject_map: dict[str, str]
    default_year_source: Literal["filename", "pdf_metadata", "manual"]
    require_explanation: bool
    prefer_pua_decode: bool
    option_count_min: int = 4
    option_count_max: int = 5

PROFILES = {
    "neet_pg": ExamProfile(
        exam_type="neet_pg",
        exam_source="NEET PG (recall)",
        subject_map=NEET_PG_SUBJECT_MAP,
        default_year_source="filename",
        require_explanation=True,
        prefer_pua_decode=True,   # Marrow-style PDFs encode PUA
    ),
    "ini_cet": ExamProfile(
        exam_type="ini_cet",
        exam_source="INI-CET (recall)",
        subject_map=INI_CET_SUBJECT_MAP,
        default_year_source="filename",
        require_explanation=True,
        prefer_pua_decode=False,  # INI-CET PDFs typically don't
        option_count_min=4,
        option_count_max=4,       # INI-CET is strictly 4-option
    ),
}
```

The runner is invoked with `--exam-profile neet_pg` or `--exam-profile ini_cet`. The DB writer reads the profile and tags every row correctly. CLI auto-detects from filename if `--exam-profile auto`.

The CLI auto-detect heuristic: filename matches `(?i)neet[-_ ]?pg` → `neet_pg`; matches `(?i)ini[-_ ]?cet|aiims` → `ini_cet`; else falls back to `neet_pg` (the current default) with a warning.

**Cross-ref:** §4 (data model — `exam_type` + `exam_source` are set from profile, never hardcoded).

---

## 8. Frontend expectations — explicit verification checklist

After the first PDF (NEET-PG-2021) is imported, the following 12 manual checks must all pass on at least 10 sampled pages. They live in `docs/neetpg2021/FRONTEND_VERIFICATION.md` as a checklist the user walks through.

| # | Check | Pass criterion |
|---|---|---|
| 1 | Image questions display correctly | Every question with `QuestionImage.role='stem'` shows the image above the stem text |
| 2 | Multiple images per question are supported | A question with 3+ stem-images shows them as a horizontal carousel |
| 3 | Zoom works | Clicking an image opens a full-screen dialog with the high-res PNG |
| 4 | Fullscreen works | F-key or "View fullscreen" button in the dialog uses `requestFullscreen()` |
| 5 | Pan works inside the dialog | Drag-zoom on desktop, pinch-zoom on mobile |
| 6 | Pinch zoom works on mobile | Two-finger gesture scales the image inside the dialog |
| 7 | Explanations are formatted nicely | Bold key terms, bullet lists, paragraphs — no raw `\n` rendering |
| 8 | Tables are readable | `QuestionAsset.asset_type='table'` renders as a `<table>` with zebra-striping, NOT as an image |
| 9 | Captions appear with the correct figure | Caption text renders below its image, in italic, prefixed `Fig. N:` |
| 10 | Clinical pearls display in distinct card | `QuestionPearl.pearl_type='clinical_pearl'` renders in a colored card separate from the explanation |
| 11 | Mnemonics display in distinct card | `QuestionPearl.pearl_type='mnemonic'` renders in its own card with a `🧠` icon |
| 12 | References display with locator | `QuestionReference.locator='Harrison 21e p.1245'` renders as a small `📚` footnote with link |

**Required primitive components** (Phase 4 deliverables, all additive — no breaking changes to the existing API):

* `<ConfidenceBadge />` — confidence dot, from point 4 above
* `<ImageViewer />` — click-to-zoom, fullscreen, pan, pinch zoom
* `<ImageCarousel />` — prev/next + counter for multi-image groups
* `<ExplanationRenderer />` — markdown rendering with medical typography
* `<TableRenderer />` — renders `QuestionAsset.asset_type='table'` from JSON cells
* `<PearlCard />` — clinical_pearl / high_yield / mnemonic / memory_trick / pitfall
* `<ReferenceFootnote />` — small `📚` with citation + locator link
* `<PageOnSourceLink />` — "show on source page" link from point 3

**Verification report.** `FRONTEND_VERIFICATION.md` records the result of each of the 12 checks against the 10 sampled pages. Failed checks become Phase-N+1 work items.

**Cross-ref:** `PHASE1_ARCHITECTURE.md §5` (frontend render order).

---

## What this addendum does NOT change

* **The 8-stage pipeline topology** (`PHASE1_ARCHITECTURE.md §2`) is unchanged. All eight review points are accommodated within the existing stages — they sharpen the stages' contracts, not the topology.
* **The verification gate** (`§6`) is unchanged in spirit but stronger in output: the overlays and grids from point 5 are the visual evidence the gate produces.
* **The hard gate** — no other PDF in `material/neet-pg/` or `material/inicet-pg/` is processed until the user approves — is unchanged.

## Summary of new files

When Phase 2 lands, the following files are added under `backend/importers/neetpg/`:

```
engines/
  __init__.py             # the four Protocol contracts
  layout_heuristic.py     # default LayoutEngine
  ocr_tesseract.py        # default OCREngine
  table_camelot.py        # default TableEngine
  caption_ocr_llm.py      # default CaptionEngine
profiles.py               # ExamProfile + NEET_PG / INI_CET profiles
unclassified.py           # typed-region handler for Stage 5/7
confidence.py             # the four-dimension scoring helpers
debug_overlay.py          # Stage 8 overlay + grid image generator
pipeline.py               # the actual orchestrator (replaces runner.py for the 2021 path)
```

`runner.py` is kept for backward compatibility (the old `--source-dir` flow) but the new CLI path is `python -m backend.importers.neetpg.pipeline --pdf <path> --exam-profile auto`.
