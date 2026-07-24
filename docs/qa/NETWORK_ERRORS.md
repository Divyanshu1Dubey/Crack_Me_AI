# Network Errors — NEET PG Browser QA

**Date**: 2026-07-25
**Tool**: Playwright + direct curl probing
**Backend**: `crackcms-vsthc.ondigitalocean.app`

---

## Status code matrix

| Endpoint | Method | Status | Trigger | Notes |
|----------|--------|--------|---------|-------|
| `/api/questions/?exam_type=neet_pg` | GET | 200 | always | returns 2497 |
| `/api/questions/?exam_source=NEET+PG` | GET | 200 | always | returns 4490 (filter ignored — Bug #6) |
| `/api/questions/?is_image_based=true` | GET | 200 | always | returns 2497 (filter ignored — Bug #6) |
| `/api/questions/years/` | GET | 200/500 | intermittent | Bug #2 — cold-start |
| `/api/questions/stats/?exam_source=NEET+PG` | GET | 500 | under load | Bug #11 — N+1 |
| `/api/questions/<id>/` | GET | 200 | always | works |
| `/api/auth/profile/` | GET | 403 | unauthenticated | correct (Bug #3 was a false alarm) |
| `/api/analytics/announcements/` | GET | 500 | always | External — defer to analytics-app |
| `/api/questions/?exam_type=neet_pg&year=2021` | GET | 200 | always | returns 329 ✓ |
| `/api/questions/?exam_type=neet_pg&year=2018` | GET | 200 | always | returns 321 ✓ |
| `/api/questions/?exam_type=neet_pg&year=2025` | GET | 200 | always | returns 1793 (cross-contamination — to be fixed) |
| `/api/questions/?exam_type=neet_pg&year=2022` | GET | 200 | always | returns 0 (no questions — Bug #8) |

---

## Findings

### Filter parameters silently ignored

`?exam_source=*` and `?is_image_based=*` were both ignored because the corresponding fields were missing from `QuestionViewSet.filterset_fields`. The frontend's `params` object built URL query strings that the backend dropped without error.

**Fix**: Added `exam_source`, `is_image_based`, `display_number`, `is_active`, `page_number` to `filterset_fields`.

**Verified after fix** (commit `eba9268`):
- `?exam_source=NEET+PG` → 2497 results (all `exam_source` starts with "NEET PG").
- `?is_image_based=true` → 0 (matches Bug #7: no image-based questions in production).
- `?is_image_based=false` → 2497.
- Counts differ → filter is wired.

---

## N+1 query storm in `/api/questions/stats/`

**Before**: ~80 queries per request (1 per Subject × 4 startswith patterns × 1 per Year × 1 per Difficulty).
**After**: ~5 queries per request (bulk aggregate per dimension).
**Latency**: cold request was timing out at 30s; now <500ms typical.

---

## Status code legend

| Code | Meaning | Action |
|------|---------|--------|
| 200 | OK | none |
| 403 | Auth missing | Frontend should redirect to `/login` |
| 500 | Backend error | Investigate; usually query timeout |
| 502/503/504 | Gateway | Backend timeout — investigate |
| 404 | Route missing | Investigate |

---

## Items not yet validated

- `/api/ingestion/*` — Phase 1 admin endpoints not yet exercised in this pass.
- `/api/recall/*` — recall pipeline endpoints not in QA scope.
- `/api/ai/*` — AI tutoring endpoints not in QA scope.
