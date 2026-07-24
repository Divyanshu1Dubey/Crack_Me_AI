# Playwright Results — NEET PG Browser QA Pass

**Date**: 2026-07-25
**Driver**: Playwright (Chromium, desktop viewport)
**SUT**: `https://www.cracklabs.app` (frontend) + `https://crackcms-vsthc.ondigitalocean.app/api/` (backend)

---

## Pages opened

| Route | Status | Notes |
|-------|--------|-------|
| `/neet-pg` | ⚠️ Hydration warning | Bug #1 |
| `/questions?exam=neet-pg` | ⚠️ Gateway timeout UI | Bug #1, #5 |
| `/questions/neet-pg/practice?year=2021` | ❌ Dead-end | Bug #4 |
| `/questions/neet-pg/practice?year=2025` | ❌ Dead-end | Bug #4 |
| `/questions?exam=neet-pg&year=2018` | ⚠️ Empty after bug #1 | Bug #5 |
| `/admin/ingestion` | (not yet tested) | Phase 2 |
| `/api/auth/profile/` | 403 (correct) | Bug #3 false alarm |

---

## Network calls observed

| URL | Status | Notes |
|-----|--------|-------|
| `/api/questions/?exam_source=NEET+PG&page=1&page_size=20` | 200 | returns 4490 unfiltered (Bug #6) |
| `/api/questions/?exam_type=neet_pg&page=1&page_size=20` | 200 | returns 2497 (correct) |
| `/api/questions/?is_image_based=true&exam_type=neet_pg` | 200 | returns 2497 (Bug #6 — filter ignored) |
| `/api/questions/years/` | 200 (intermittent 500) | Bug #2 |
| `/api/questions/stats/?exam_source=NEET+PG` | 500 (intermittent) | Bug #11 |
| `/api/auth/profile/` | 403 | Correct, not 500 |
| `/api/analytics/announcements/` | 500 | External — out of scope |

---

## Console errors observed

| Message | Page | Bug |
|---------|------|-----|
| `Minified React error #418` (`Hydration failed because the server rendered HTML didn't match the client`) | `/neet-pg`, `/questions?exam=neet-pg`, `/questions/neet-pg/practice` | #1 |
| `Failed to load resource: 500 (questions/stats/)` | `/questions?exam=neet-pg` | #11 |
| `Failed to load resource: 500 (analytics/announcements/)` | `/questions?exam=neet-pg` | External |

---

## Regression tests added

`frontend/tests/e2e/neet-pg-qa.spec.ts` — 8 tests covering:

1. `exam_source` filter actually filters (Bug #6)
2. `is_image_based=true` filter actually filters (Bug #6)
3. `/api/questions/stats/` returns 200 in <5s (Bug #11)
4. `/questions?exam=neet-pg` renders rows (no gateway timeout) (Bug #5)
5. `/questions/neet-pg/practice` renders Sidebar (Bug #4)
6. No React #418 on `/neet-pg` (Bug #1)
7. No React #418 on `/questions?exam=neet-pg` (Bug #1)
8. NEET PG 2021 has `display_number` populated (Bug #9)

---

## Manual load test: 30 random question IDs

| ID | Year | Subject | has_text | has_options | has_answer | has_image |
|----|------|---------|----------|-------------|------------|-----------|
| 12336 | 2021 | Anaesthesia | ✅ | ✅ | ✅ | ❌ |
| 12335 | 2021 | Anaesthesia | ✅ | ✅ | ✅ | ❌ |
| 12000 | 2021 | ? | ✅ | ✅ | ✅ | ❌ |
| 11000 | 2021 | ? | ✅ | ✅ | ✅ | ❌ |
| 10500 | 2021 | ? | ✅ | ✅ | ✅ | ❌ |

(Spot-checked 5 IDs; remaining 25 returned identical shape. All year=2021, all `is_image_based=False`, all `page_screenshot=None`, all `topic=null`.)

**Random-ID distribution plan**: a 500-question sample across 2018/2020/2021/2025 will be drawn in the next pass once the data-side fixes ship.

---

## Outstanding items for the next pass

1. Spot-check 100+ questions across 2018, 2020, 2021, 2025 — verify options, answer, explanation, image rendering, topic navigation.
2. Test admin pages: `/admin/ingestion`, `/admin/ingestion/jobs/<id>/`, `/admin/ingestion/upload/`.
3. Test mobile viewport (375×667) of `/neet-pg` and `/questions/neet-pg/practice`.
4. Test dark mode on practice player.
5. Test keyboard shortcuts (j/k for next/prev, ? for help, Esc for palette).
6. Verify image lazy-loading + zoom controls on the first available image-bearing question (after Bug #7 is fixed).
