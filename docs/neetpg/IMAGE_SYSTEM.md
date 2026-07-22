# Image System — Phase 2

> Multi-image per question. Zoom, fullscreen, lazy load, OCR, captions, deduplication. Existing `Question.page_screenshot` stays as the **primary** slot.

---

## 1. Storage

- **Local (dev):** `MEDIA_ROOT/recall_images/YYYY/MM/<sha16>.png` — wired via `ImageField(upload_to='recall_images/%Y/%m/')`.
- **Production:** existing `whitenoise` serves `MEDIA_URL` in DEBUG; a future DigitalOcean Spaces backend can be slotted in via Django `STORAGES` without model changes.
- **Filename:** `<sha16>_<p>NNNN_i<NN>.<ext>` for stable dedup.

---

## 2. New model: `QuestionImage`

See [DATABASE_MIGRATION_PLAN.md](DATABASE_MIGRATION_PLAN.md) §3.3 for the full field list.

Highlights:

- `phash` (perceptual hash) and `dhash` for visual dedup.
- `modality` (radiology / histopathology / ecg / ct / mri / x_ray / …).
- `ocr_text` for in-image text (ECG axis labels, X-ray markers).
- `caption` + `caption_source` for AI / human description.
- `role` (primary / option / illustration / explanation).

---

## 3. Deduplication

- **Exact sha256** → collapse to one row.
- **pHash Hamming ≤ 3** → collapse.
- **pHash 4–5** → flag for admin review; keep both rows.
- All duplicates share a single `QuestionImage` row; both questions link via `question_id`.

---

## 4. Delivery

`QuestionListSerializer` and `QuestionDetailSerializer` are extended (additive) with an `images` field that returns a list of `{ id, file_url, mime, modality, ocr_text, caption, width, height, role }`.

The existing `Question.page_screenshot` is mirrored into a `QuestionImage` row with `role='primary'` only when the importer runs (existing rows are NOT auto-migrated — that's a one-shot data migration script shipped in `importers/neetpg/management/commands/neetpg_mirror_screenshots.py`).

---

## 5. Frontend components (opt-in)

- `frontend/src/components/recall/QuestionImageZoom.tsx` — pinch-zoom, double-tap zoom, fullscreen button.
- `frontend/src/components/recall/ImageGallery.tsx` — carousel for multi-image questions.
- `frontend/src/components/recall/ProvenanceList.tsx` — list of source PDFs / pages for the question.

These are added to the repo but not wired into pages. Future work (Phase 3) opts them into the practice + dashboard flows.

---

## 6. Image-only revision (Phase 3 hook)

A future `frontend/src/app/recall/image-mode/page.tsx` would render one image-only question at a time using `QuestionImage` rows directly. Phase 2 lays the data foundation only.

---

## 7. Quality rules (auto-enforced)

| Issue | Action |
|---|---|
| Image sha already exists | Skip duplicate write |
| pHash Hamming ≤ 3 against an existing image | Skip duplicate write, log dedup event |
| Image file > 5 MB | Downsample via Pillow to 2 MB max; flag `was_downsampled=True` |
| Image format is TIFF | Convert to PNG via Pillow before saving |
| Missing modality tag | Default to `other`, flag in admin |
| Watermark detected (heuristic via OCR text matching coaching names) | Set `is_watermarked=True` |

---

## 8. OCR pipeline

Phase-1 `ocr_engine.ocr_image()` is reused. Tesseract returns `(text, avg_confidence)`. We store both; `ocr_confidence < 60` triggers `Question.needs_review=True` (existing field) and an `error_report` entry on the job.

---

## 9. Caption pipeline

Phase 2 ships a stub `importers.neetpg.caption.generate_caption(image, modality)` returning `(None, 'none')`. Phase 3 wires BLIP-2 / Florence-2 / Gemini Vision via the existing 9-provider rotation.

---

## 10. Out of scope (deliberately)

- We do not migrate existing `Question.page_screenshot` rows into `QuestionImage`. A separate optional command ships.
- We do not auto-caption via AI in Phase 2.
- We do not upload to DigitalOcean Spaces in this phase.
- We do not modify the existing `page_screenshot` ImageField.