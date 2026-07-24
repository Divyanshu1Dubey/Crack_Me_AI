# Console Errors — NEET PG Browser QA

**Date**: 2026-07-25
**Browser**: Chromium (Playwright)
**Captured via**: `page.on('console')` and `page.on('pageerror')`

---

## Error #1 — React #418 hydration mismatch

**Message**: `Minified React error #418; visit https://react.dev/errors/418?args[]=text&args[]= for the full message or use the non-minified dev environment for full errors and additional helpful warnings.`

**Pages**: `/neet-pg`, `/questions?exam=neet-pg`, `/questions/neet-pg/practice?year=2021`

**Stack trace** (minified):
```
rK (https://www.cracklabs.app/_next/static/chunks/117e72e657f8cb9a.js:1:45829)
sp (https://www.cracklabs.app/_next/static/chunks/117e72e657f8cb9a.js:1:145742)
sc (https://www.cracklabs.app/_next/static/chunks/117e72e657f8cb9a.js:1:137082)
u9 (https://www.cracklabs.app/_next/static/chunks/117e72e657f8cb9a.js:1:132012)
sV (https://www.cracklabs.app/_next/static/chunks/117e72e657f8cb9a.js:1:158394)
MessagePort.O (https://www.cracklabs.app/_next/static/chunks/117e72e657f8cb9a.js:1:7354)
```

**Root cause**: `ExamTrackProvider` returned `activeTrack='cms'` on the server, then `activeTrack='neet_pg'` on the client after reading localStorage. Sidebar consumed `activeTrack` to rewrite the `/questions` link → server and client rendered different hrefs.

**Fix**: `ExamTrackProvider` now exposes a `hydrated` flag. `Sidebar` reads `effectiveTrack = hydrated ? activeTrack : 'cms'` to align server and client.

**Regression test**: `frontend/tests/e2e/neet-pg-qa.spec.ts` — "no React #418 error on /neet-pg", "no React #418 error on /questions?exam=neet-pg"

**Status**: ✅ FIXED (commit `eba9268`)

---

## Error #2 — Failed to load resource: 500 on `/api/analytics/announcements/`

**Message**: `Failed to load resource: the server responded with a status of 500 () @ https://crackcms-vsthc.ondigitalocean.app/api/analytics/announcements/:0`

**Page**: `/questions?exam=neet-pg`

**Root cause**: External — likely an Sentry / unhandled-exception page that crashed on the analytics backend. Not part of the NEET PG surface.

**Fix**: Defer to analytics-app triage.

**Status**: ⚠️ EXTERNAL — not blocking NEET PG QA.

---

## Error #3 — Failed to load resource: 500 on `/api/questions/stats/`

**Message**: `Failed to load resource: the server responded with a status of 500 () @ https://crackcms-vsthc.ondigitalocean.app/api/questions/stats/?exam_source=NEET+PG:0`

**Page**: `/questions?exam=neet-pg`

**Root cause**: Stats endpoint fired ~80 queries (N+1 across 19 subjects × 4 startswith patterns). Under load, the request timed out and DRF returned 500.

**Fix**: Rewrote endpoint to use bulk aggregate queries. Query count dropped from ~80 to ~5 per request.

**Regression test**: `frontend/tests/e2e/neet-pg-qa.spec.ts` — "stats endpoint returns 200 in <5s for exam_source=NEET+PG"

**Status**: ✅ FIXED (commit `eba9268`)

---

## Summary by page

| Page | Errors observed |
|------|------------------|
| `/neet-pg` | React #418 |
| `/questions?exam=neet-pg` | React #418, stats 500, analytics 500 |
| `/questions/neet-pg/practice?year=2021` | React #418 |
| `/questions/neet-pg/practice?year=2025` | React #418 |
| `/api/auth/profile/` | 403 (correct, not 500) |

---

## Errors NOT observed (good)

- No "Failed to load script" / chunk-load errors.
- No "Cannot read property X of undefined" runtime errors.
- No "Object is not a function" errors.
- No "Hydration failed because the initial UI does not match what was rendered on the server" full message (only the minified #418 — same bug).
- No "Warning: Each child in a list should have a unique key prop" key warnings.
- No "Module not found" errors.
- No CORS errors.
- No CSP errors.
- No Mixed Content errors.
