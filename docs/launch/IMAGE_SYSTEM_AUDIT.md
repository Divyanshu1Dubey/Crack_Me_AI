# Phase 4 — Image System Audit

**Date:** 2026-07-22

## Components

| Component | File | Purpose |
|---|---|---|
| `QuestionImage` | `backend/questions/models.py` | DB row per image (Phase 2) |
| `QuestionImageZoom` | `frontend/src/components/recall/QuestionImageZoom.tsx` | Fullscreen + zoom + pinch (Phase 3) |
| `ImageGallery` | `frontend/src/components/recall/ImageGallery.tsx` | Multi-image grid (Phase 3) |
| `ProvenanceList` | `frontend/src/components/recall/ProvenanceList.tsx` | Source rows (Phase 3) |
| `recall_question_images` | `backend/questions/recall_search.py` | List endpoint (Phase 2) |
| `images_facets` | `backend/questions/views.py` | Facet endpoint (Phase 3) |

## Verified ✅

* **Lazy-loading** — `loading="lazy"` + `decoding="async"` on every
  image element.
* **Pinch-zoom (mobile)** — `onTouchStart/onTouchMove/onTouchEnd`
  pointer events; distance math; zoom in `[1.0, 6.0]`.
* **Wheel-zoom (desktop)** — `onWheel` with `e.deltaY` factor.
* **Keyboard zoom** — `+`, `-`, `0` (reset), `Esc` (close).
* **OCR overlay toggle** — `Show OCR` button surfaces a `<pre>` block.
* **Modal close** — backdrop click + `Esc`.
* **Modality + body-region chip** — top-left of every image.
* **Captions** — from `QuestionImage.caption` (auto-AI).
* **Watermarked flag** — `is_watermarked` field; admin action
  `Mark selected images as watermarked`.

## Phase-4 spot-check — image integrity

* `QuestionImage.sha256` (full 64-char) and `sha256_short` (16-char)
  are computed and indexed at extraction time (Phase 1).
* `QuestionImage.bytes` (`BigIntegerField`) tracks file size.
* `QuestionImage.width` / `height` track pixel dimensions.
* Dedup by `sha256_short` (Phase 2) so duplicate embeds don't
  multiply rows.
* Filename fallback uses `Question.page_screenshot` if no
  `QuestionImage` rows exist (Phase 3 `ImageGallery`).

## Recommendations

* **Cloudflare Image Resizing** for production bandwidth (Phase 5).
* **WebP re-encoding** on upload (Phase 5).
* **Annotation layer** ready via `data-annotate-target="image"`
  (Phase 4 placeholder; Phase 5 wires the actual draw tool).
