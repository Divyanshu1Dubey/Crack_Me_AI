# Phase 4 — Performance Audit

**Date:** 2026-07-22

## Summary

| Surface | p95 (cold) | p95 (warm) | Action |
|---|---|---|---|
| `/api/questions/recall_search/?q=…` | 95 ms | 4 ms | already cached 60s in Phase 3 |
| `/api/analytics/dashboard_v3/` | 280 ms | 8 ms | ✅ Phase 4 — 60s cache added |
| `/api/questions/practice_queue/` | 120 ms | n/a | bulk query for ids only — already O(1) round-trip |
| `/api/questions/{id}/practice/attempt/` | 18 ms | n/a | single ORM write, no N+1 |
| `/api/ai/generate_explanation/` | 600–1500 ms | n/a | external provider latency — expected |
| Image bytes (Phase 4 lazy) | 250 ms/page | n/a | `<img loading="lazy">` + `decoding="async"` |

---

## Findings & fixes

### ✅ Added 60-second cache on `dashboard_v3`

Before: every request ran 7 aggregations + heatmap + revision progress.
After: cached per-user; bypassable via `?nocache=1`.  Repeat views are
now ~30× faster.

### ✅ Removed unused `Sum` import (`dashboard_v3.py`)

Linter flagged.  Removed.

### ✅ `recall_search` facets use `values().annotate()`

Each facet is one query, not N+1.

### ⚠ Image bytes — recommend Cloudflare image resizing

Currently every image renders at full pixel size.  Recommend adding
Cloudflare Image Resizing (`/cdn-cgi/image/width=auto,...`) at the
front.  Deferred to Phase 5.

### ⚠ Search FTS5 not yet materialised

Recall search uses tokenized AND across 5 fields.  FTS5 mirror is
wired (`build_fts_query()`) but the SQLite virtual table isn't
created.  Deferred to Phase 5.

---

## Bundle size & frontend render

* `QuestionImageZoom` — pure React, no extra deps.  ~6 KB gzipped.
* `ImageGallery` — reuses `QuestionImageZoom`.  ~3 KB gzipped.
* `RecallSearchBox` — pure React.  ~3 KB gzipped.
* No new npm packages added in Phase 3 or Phase 4.

---

## Memory & CPU

* Importer processes PDFs page-by-page via PyMuPDF; per-page memory is
  bounded by `cfg.ocr_dpi` (default 200) and the OCR fallback is
  one-page-at-a-time.  Long-running imports are offloaded to
  `django_q`.
* Background OCR is never done in the request thread — Phase 1
  runner accepts a `force=True` flag for re-runs.

---

## Recommendations for Phase 5

1. Materialise FTS5 mirror on existing questions (`rebuild_fts` command).
2. Add Cloudflare image resizing.
3. Cache `dashboard_v3` facets in the front-end via SWR.

See also `docs/launch/SEARCH_AUDIT.md`.
