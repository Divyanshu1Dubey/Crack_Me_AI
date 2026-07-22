# Phase 5 — Technical Debt (updated 2026-07-23)

**Date:** 2026-07-23

This document tracks every item a Staff Engineer would flag for
post-launch work.  None of these block launch.  Phase 5 (NEET PG
end-to-end) closed all three P1 items from the original Phase 4
audit.

---

## P0 — Launch-blocker (none)

Nothing in this list prevents launch.  Every item below is a
deferred improvement.

---

## P1 — Should fix within 30 days post-launch

~~### 1. SearchLog model (`analytics.SearchLog`)~~ — **CLOSED** in
Phase 5; the new NEET PG stats endpoint supersedes SearchLog for
the question bank and falls back to the existing `recall_search`
cache for subject/year filtered views.

~~### 2. FTS5 mirror~~ — **CLOSED** in Phase 5; pdfplumber
fallback + question bank now indexed by `(year, subject,
exam_type)` (Phase 2 migration `0023`), which covers the
production query patterns without FTS5.

~~### 3. Strict JWT access-token TTL~~ — **CLOSED** in Phase 5;
`SIMPLE_JWT['ACCESS_TOKEN_LIFETIME']` is now 15 minutes in
`backend/crack_cms/settings.py` with refresh-token rotation,
revoked on password change in `accounts/views.py`.

### 4. Tesseract OCR install in production

* `tesseract/` source tree exists at the repo root but is not
  built / installed.
* Year-wise PDFs that have neither a digital text layer nor a
  hidden OCR layer yield 0 questions.
* Documented install path: `docs/launch/NEET_PG_LAUNCH_NOTES.md` §6.
* Effort: 1 hour (install + restart + re-run year-papers).

### 5. Recurring OCR sweep job

* `importers/admin.py::QuestionImageAdmin.action_re_ocr` is a stub.
* Production should run nightly OCR via `django_q` for any
  QuestionImage with empty `ocr_text`.
* Effort: 1 day.

---

## P2 — Should fix within 90 days

### 6. S3 / Supabase Storage for `MEDIA_ROOT`

* Currently `MEDIA_ROOT` is local disk; production uses single-disk
  storage which won't scale horizontally.
* Effort: 1-2 days + migration of existing files.

### 7. Frontend a11y enhancements

* Focus trap in `QuestionImageZoom` modal.
* `role="region"` on `RevealExplanation` panel.
* `aria-label` on every `<ul>` in `ProvenanceList` and `RelatedPanel`.
* `role="checkbox"` + `aria-checked` on filter chips in
  `RecallSearchBox`.
* Effort: 1 day.

### 8. Lighthouse / Core Web Vitals pass

* Verify LCP < 2.5s on `/`, `/practice`, `/recall/search`.
* Verify CLS < 0.1.
* Effort: 1 day.

---

## P2 — Should fix within 90 days

### 4. S3 / Supabase Storage for `MEDIA_ROOT`

* Currently `MEDIA_ROOT` is local disk; production uses single-disk
  storage which won't scale horizontally.
* Effort: 1-2 days + migration of existing files.

### 5. Re-OCR batch action

* `backend/importers/admin.py::QuestionImageAdmin.action_re_ocr` is
  currently a stub.
* Phase-5 should integrate with `importers.neetpg.ocr_engine.ocr_image()`
  and emit `QuestionImageOCRJob` rows.
* Effort: 1 day.

### 6. Re-OCR worker is admin-threaded

* Same scope as #5: production should run OCR via `django_q` so admin
  pages stay responsive.
* Effort: 1 day.

### 7. Frontend a11y enhancements

* Focus trap in `QuestionImageZoom` modal.
* `role="region"` on `RevealExplanation` panel.
* `aria-label` on every `<ul>` in `ProvenanceList` and `RelatedPanel`.
* `role="checkbox"` + `aria-checked` on filter chips in
  `RecallSearchBox`.
* Effort: 1 day.

### 8. Lighthouse / Core Web Vitals pass

* Verify LCP < 2.5s on `/`, `/practice`, `/recall/search`.
* Verify CLS < 0.1 (the lazy-load + skeleton states should already
  achieve this).
* Effort: 1 day.

---

## P3 — Nice-to-have

### 9. Composite index

* `Question(recall_status, exam_type, year)` for high-frequency
  recall-bank queries.
* Effort: 30 min.

### 10. Partial index

* `Question WHERE is_active=True` partial index — covers 99% of
  queries.
* Effort: 30 min.

### 11. Frontend E2E tests

* Playwright suite for `/practice`, `/recall/search`,
  `/analytics/dashboard_v3`.
* Effort: 1-2 days.

### 12. Frontend unit tests

* Jest + React Testing Library for `QuestionToolbar`, `RecallSearchBox`.
* Effort: 1 day.

### 13. Frontend per-route metadata

* `app/practice/layout.tsx`, `app/recall/search/layout.tsx`,
  `app/analytics/dashboard_v3/layout.tsx` should export `metadata`.
* Effort: 30 min.

### 14. Sentry data_scrubber

* Drop email/token fields from request bodies before they reach
  Sentry.
* Effort: 30 min.

### 15. Backup automation

* Daily logical Postgres dumps → S3 (or Supabase Storage).
* Effort: 1 day.

### 16. CI hardening

* Add `mypy --strict` (backend) and `eslint --max-warnings 0` (frontend).
* Add `bandit -r backend/` to CI.
* Effort: 1 day.
