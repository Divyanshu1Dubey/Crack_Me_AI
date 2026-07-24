# NEET-PG-2021 — Phase 1 Target Architecture (the Medical Content Intelligence Pipeline)

> Companion to `PHASE0_AUDIT.md`. Phase 0 said *what's broken*; Phase 1 says *what we build instead*. No PDF is processed in this phase. All artifacts land under `backend/_artifacts/neetpg2021/` (gitignored) so every stage's output is inspectable and re-runnable.

---

## 1. Design principles

1. **Quality over speed.** No DPI / OCR / LLM budget chosen because it's "fast enough" — chosen because it's the highest fidelity we can get from open-source tools locally.
2. **Every stage is artifact-bearing.** No stage mutates the previous stage's output. Every stage writes its own folder. Re-runs are idempotent.
3. **Provenance is sacred.** Every extracted row knows its source PDF, source SHA-256, source page, source bbox, and confidence at each stage. Nothing is silently fused.
4. **Layout is a first-class object.** Not a string we infer — a `(region_type, bbox, page_number)` tuple with a typed schema (`stem | option | explanation | image | table | algorithm | footnote | header | footer | answer_key`).
5. **Images have roles.** Every image is tagged `role ∈ {stem, option, explanation, table, cover, watermark, logo, other}` so the frontend can render it in the right slot.
6. **Quality verification is a stage, not an afterthought.** Stage 8 takes the structured output and pixel-diffs / text-diffs it against the source page. Any drop below the threshold from `PHASE0_AUDIT.md §5` fails the run.
7. **Frontend parity.** The premium rendering (zoom, carousel, captions, clinical-pearl box, mnemonic cards, reference panel) ships in the same phase as the importer, so we can verify extraction *as the user sees it*, not just in the DB.

---

## 2. The seven stages + their artifacts

```
PDF
 ↓
Stage 1  Render every page to PNG @ 300 DPI
 ↓      → 01_pdf_pages/p{001..144}.png
 ↓
Stage 2  Char-level layout detection (heuristic v1, swappable later)
 ↓      → 02_layout/p{001..144}.json
 ↓
Stage 3  Extract embedded images + render-region crops (highest practical DPI)
 ↓      → 03_images/p{NN}_img{kk}.{png|jpg}   +   03_images/_index.json
 ↓
Stage 4  Detect tables / algorithms / drug charts
 ↓      → 04_tables/p{NN}.json  + 04_tables/p{NN}_tbl{kk}.png
 ↓
Stage 5  Group layout blocks into question-block candidates
 ↓      → 05_question_blocks/p{NN}.json
 ↓
Stage 6  OCR + text extraction per block (Tesseract / pdfplumber fallback / LLM cleanup)
 ↓      → 06_ocr/p{NN}.json  + 06_ocr/p{NN}_block{kk}.txt
 ↓
Stage 7  Reconstruct ParsedQuestion objects with image order, captions, mnemonics
 ↓      → 07_structured/p{NN}.json  +  07_structured/all_questions.jsonl
 ↓
Stage 8  Verification & QA (side-by-side diff vs source PNG)
         → 08_qa/per_page_report.json  +  08_qa/FAIL.png  +  08_qa/PASS.png
 ↓
DB write  (idempotent; only PASS rows go to Question / QuestionImage / QuestionSource)
```

Every `NN.json` in stages 2 / 4 / 5 / 6 / 7 has the same shape:

```json
{
  "page_number": 38,
  "pdf_sha256_short": "8ebea8995a4ade7",
  "blocks": [
    {"id": "p38.b1", "type": "stem", "bbox": [72, 200, 524, 410], "text": "...", "conf": 0.98, "images": ["p38_img03"]},
    {"id": "p38.b2", "type": "option", "label": "A", "bbox": [72, 420, 524, 460], "text": "...", "conf": 0.97},
    ...
  ],
  "warnings": []
}
```

`bbox` is `(x0, y0, x1, y1)` in PDF points (origin = top-left, x = horizontal). The frontend renderer uses these bboxes to crop the page PNG at exactly the same coordinates the parser saw, so the user can see *which pixels* drove every decision.

---

## 3. Tool selection per stage

| Stage | Tool | Why |
|---|---|---|
| 1 Render | **PyMuPDF (`page.get_pixmap(dpi=300, alpha=False)`)** | Lossless, fast, gives PNG bytes directly. 300 DPI matches the embedded raster resolution of the 2021 PDF and exceeds the legibility threshold for tesseract OCR on small annotation labels. |
| 2 Layout (v1) | **Heuristic char-clustering on pdfminer.six bbox stream** | We have `pdfminer.six` already. For this 2021 PDF the layout is single-column with consistent margins — a small set of rules (line clustering, indent detection, font-weight inference) gives > 95 % region accuracy without ML deps. Keeps the pipeline transparent and re-runnable on Render. |
| 2 Layout (v2 — future) | **YOLOv8-doclaynet via `ultralytics`** | Drop-in replacement behind a `LayoutModel` Protocol. Triggers only if v1 falls below target metrics. |
| 3 Embedded images | **PyMuPDF `page.get_images(full=True)` + `doc.extract_image(xref)`** | Highest-fidelity copy of the original embedded raster (DCTDecode for JPEGs, FlateDecode for PNGs). |
| 3 Render-region crops | **PyMuPDF `page.get_pixmap(clip=fitz.Rect(*bbox))`** at 300 DPI | For images that are not separately embedded but live inside the rendered page (vector graphics, charts), we crop the high-res render so the user still gets a viewable image. |
| 3 Orientation fix | **PyMuPDF `page.get_image_bbox(xref)` + CTM-aware rotation** | Some xrefs are stored rotated; we read `xref_object['width']/['height']` and the page CTM and rotate to upright before saving. |
| 3 Caption detection | **pdfplumber words near image bbox + pdfminer line spans** | Captions are usually within 80 pt below the figure in left-aligned single-column PDFs. We pick the nearest text line whose font matches the body and tag it as `caption`. |
| 4 Tables / algorithms | **Camelot `lattice` mode for bordered tables; `stream` mode for borderless; pdfplumber for line-extraction fallback** | Drug charts in NEET-PG-2021 are mostly bordered tables — Camelot handles them well. |
| 5 Question grouping | **Custom block-grouping on Stage 2 bboxes** | We group all blocks between two consecutive `QUESTION_PREFIX` regex hits (or two consecutive big-block boundaries) into one `QuestionBlock`. Handles multi-page stems by chaining across page breaks. |
| 6 OCR | **Tesseract 5 (eng + equ + osd) via `pytesseract` after OpenCV preprocessing** (deskew, adaptive threshold, morphological denoise) | Highest-quality open-source OCR. The `equ` (math / equation) language pack handles `Na+`, `β`, `Δ`, `×`. |
| 6 Text layer | **pdfplumber words / lines + bbox** for digital text, falling back to OCR for scanned blocks | pdfplumber preserves word positions and font metadata which we use for layout. |
| 6 LLM cleanup | **`ai_engine.services.ai_complete()` through the 11-provider round-robin** (capped at 2 calls / page) | Used for: (a) image caption polish, (b) clinical-reasoning paragraph reconstruction when OCR mangles a stem, (c) mnemonic / high-yield-box detection. Routed through the existing `ai_engine` so the round-robin + token accounting already work. |
| 7 Reconstruction | **Pure code — no LLM in the hot path** | LLM is only called on low-confidence blocks (parse_confidence < 0.6 or ocr_confidence < 50). |
| 8 QA | **Pillow ImageChops + custom text-diff** | Pixel-diff at 5 % tolerance + char-level edit-distance ≥ 0.85 for every block → PASS/FAIL. |
| DB write | **Existing `DjangoWriter` (db_writer.py), extended with `role` + `caption_source` fields** | Already supports `role` (illustration / stem / option / etc.). The new pipeline emits these values explicitly. |

### Why this combination, not a single tool

* **PyMuPDF** for rendering + embedded-image extraction — nothing else matches its speed + fidelity on PDFs with mixed text/image layers.
* **pdfplumber + pdfminer.six** for char-level bbox — pdfplumber alone gives words but not font; pdfminer gives spans with font names; together we can infer headings, captions, answer-key sections, and option labels.
* **Tesseract** for OCR — only mature open-source OCR with extensive language packs; the `equ` pack is critical for medical notation.
* **Camelot** for tables — its `lattice` mode is the most reliable for NEET-PG-style drug / classification boxes.
* **OpenCV** for preprocessing — deskew + adaptive threshold is the difference between tesseract returning 60 % vs 92 % accuracy on a 300 DPI render of a sub-150 pt figure.
* **`ai_engine.services.ai_complete()`** for selective LLM cleanup — already has provider rotation + token accounting, so we get free reliability.

We are **NOT** using: Detectron2 / layoutparser / PaddleOCR / EasyOCR — each is ≥ 500 MB, requires CUDA-friendly wheels, and adds nothing the heuristic + Tesseract combo can't deliver on this single-column, mostly-digital 2021 PDF.

---

## 4. Data model additions

`QuestionImage` already has the right shape. We will:

1. Use `role` strictly per the enum `{stem, option, explanation, table, cover, watermark, logo, other}`.
2. Use `modality` strictly per the enum `{radiograph, ct, mri, ultrasound, ecg, echo, fundus, pathology_gross, pathology_micro, dermatology, histology, hematology, blood_smear, embryology, anatomy_diagram, flow_chart, table, drug_chart, clinical_photo, generic, other}`.
3. Use `caption_source` per the enum `{none, pdf_text_near_image, ocr_on_image, llm, admin}`.
4. Add **one new field** to `QuestionImage`: `page_spans = JSONField(default=list)` — `[(page_number, bbox), ...]` for images reconstructed across pages.
5. Add **two new models**:

```python
class QuestionAsset(models.Model):
    """Non-image structured content (tables, algorithms, flowcharts) saved as JSON + image preview."""
    question = FK(Question)
    asset_type = CharField(choices=["table", "algorithm", "flowchart", "drug_chart", "box"])
    payload_json = JSONField()         # structured cells / steps
    preview_image = FileField(blank=True)
    page_number = PositiveIntegerField()
    bbox = JSONField(default=list)
    confidence = DecimalField(max_digits=4, decimal_places=3)
    extraction_source = CharField(choices=["camelot", "pdfplumber", "llm", "admin"])
    created_at = DateTimeField(auto_now_add=True)


class QuestionPearl(models.Model):
    """Clinical pearls / high-yield boxes / memory tricks captured per question."""
    question = FK(Question)
    pearl_type = CharField(choices=["clinical_pearl", "high_yield", "mnemonic", "memory_trick", "pitfall"])
    body = TextField()
    source = CharField(choices=["pdf", "llm", "admin"])
    page_number = PositiveIntegerField(null=True, blank=True)
    confidence = DecimalField(max_digits=4, decimal_places=3)
    created_at = DateTimeField(auto_now_add=True)


class QuestionReference(models.Model):
    """References cited in the explanation (Harrison, Robbins, NEET-PG key, etc.)."""
    question = FK(Question)
    citation_text = CharField(max_length=512)
    source_type = CharField(choices=["textbook", "journal", "guideline", "official_key", "other"])
    locator = CharField(blank=True)     # e.g. "Harrison 21e p.1245"
    page_number = PositiveIntegerField(null=True, blank=True)
    created_at = DateTimeField(auto_now_add=True)
```

These are additive migrations; no existing fields change.

---

## 5. Frontend parity (Phase 4 deliverable)

Each extracted question renders in this order — strictly:

```
1. Cover image(s) for the question, if any
2. Image(s) tagged role=stem
3. Stem text (with inline footnote links)
4. Option list  A. <text> [option image, if any]  B. ...
5. Correct-answer reveal (after submit/expand)
6. Explanation text
7. Images tagged role=explanation, in original page-order
8. Tables / algorithms (QuestionAsset preview images, expandable)
9. Clinical pearls / high-yield boxes / mnemonics (distinct card UI)
10. References (NEET-PG key, textbook citations)
```

UI primitives required:
* Image zoom on click (full-screen dialog) with pinch-zoom on mobile
* Image carousel (prev / next / counter) for multi-image groups
* Inline captions
* Expand / collapse for explanation, pearls, references
* Markdown rendering for the explanation (bold key terms, bullet lists)
* Loading skeleton on slow networks
* Premium typography (variable font, ample line-height, ≥ 16 px base)

Phase 4 wires these into `frontend/src/components/neet-pg/NeetPgPlayer.tsx` (and the INI-CET sister) without changing the API contract (still hits `/api/questions/{id}/images/`).

---

## 6. Verification system

`backend/_artifacts/neetpg2021/08_qa/` produces:

* `per_page_report.json` — every page's PASS/FAIL with reason
* `PASS/p{NN}.png` — annotated page image where green outlines = matched regions, blue = parser regions, red = unmatched
* `FAIL/p{NN}.png` — same annotation when an extraction dropped below threshold
* `summary.json` — counts: PASS pages, FAIL pages, top failure modes

Run gate (hard): **no DB write happens for any question on a FAIL page** until the user reviews.

---

## 7. Roll-out

* **Phase 2** — code the seven stages + artifacts.
* **Phase 3** — wire `QuestionAsset`, `QuestionPearl`, `QuestionReference` migrations + Django admin.
* **Phase 4** — frontend render order + zoom / carousel / pearl / reference UI.
* **Phase 5** — run on the 2021 PDF, sample 30 random pages manually, side-by-side with the original PDF.
* **Phase 6** — write `NEET2021_EXTRACTION_REPORT.md`, `IMAGE_MAPPING_REPORT.md`, `OCR_PIPELINE_REPORT.md`, `QUALITY_COMPARISON_REPORT.md`, `IMPORTER_REDESIGN_REPORT.md`, `PIPELINE_ARCHITECTURE.md` (this file), `VALIDATION_REPORT.md`.
* **Hard gate.** Other PDFs in `material/neet-pg/` (19 subject PDFs, ~199 MB) and `material/inicet-pg/` (19 subject PDFs) are **not processed** until the user says "looks good — process the rest".

---

## 8. Why this beats the current importer

| Concern | Today | New pipeline |
|---|---|---|
| Image-to-question mapping | First question on the page | Spatial bbox intersection, with confidence + role |
| Image orientation | Unchecked | CTM-aware rotation before saving |
| Layout awareness | None | Char-level bbox → typed regions |
| Tables / algorithms | Lost in `explanation` | Typed assets, preserved as image + JSON |
| Multi-page questions | Split into halves | Re-linked via cross-page block grouping |
| Captions | Merged into stem | Detected + tagged `caption_source=pdf_text_near_image` |
| Mnemonics / pearls | Lost | Distinct `QuestionPearl` rows |
| References | Lost | Distinct `QuestionReference` rows |
| Verification | None | Stage 8 PASS/FAIL per page, gates DB write |
| Re-runnable / debuggable | JSONL output only | Full per-page artifact tree on disk |
| Quality budget | Implicit | Explicit ≥ 99 % recall + ≥ 98 % image precision targets |

This is the design the rest of the phases will build against.
