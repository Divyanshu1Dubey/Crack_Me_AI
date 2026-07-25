# PRODUCTION_INCIDENT_REPORT.md

**Incident ID:** PROD-2026-07-25-01
**Detected:** 2026-07-25 (user-reported via direct session message)
**Severity:** P0 — page completely unusable for every authenticated user
**Affected surface:** `https://www.cracklabs.app/questions/neet-pg/practice` and `/questions/inicet/practice`
**Resolved by:** commit `43f5cf1` (hotfix shipped, awaiting Vercel deploy)
**Author:** Claude Code (zero-compromise QA mission, 2026-07-25)

---

## 1. Executive summary

The `/practice` page sat on the spinner forever, then surfaced "Couldn't load NEET PG questions / Request failed with status code 429". React error #418 also fired in the browser console.

The root cause was a `while (true)` loop in the route entry point that fetched every page of `/api/questions/` sequentially up to a hard cap of 200 pages. With 3-4 concurrent users this saturated the DRF throttle / Cloudflare limit and started returning 429 — but the loop kept re-throwing on each 429 and re-running, so the spinner never exited.

Three independent defects were confirmed:
- **A — over-fetch loop** (cause of the 429s)
- **B — spinner never exits** (cause of the infinite loading UI)
- **C — React #418 hydration** (cause of the console error)

All three are fixed in commit `43f5cf1` with a regression test that would have failed on 2026-07-25 before the fix.

---

## 2. User-visible symptoms

1. Page load on `https://www.cracklabs.app/questions/neet-pg/practice` shows spinner indefinitely.
2. Network panel reveals 150+ sequential `GET /api/questions/?exam_type=neet_pg&page=N&page_size=20` requests.
3. Loading indicator counts up — "(640 loaded)", "(2640 loaded)", etc.
4. Eventually the loop hits a 429, throws, and the page renders an error UI: "Couldn't load NEET PG questions — Request failed with status code 429".
5. Browser console contains `Uncaught Error: Minified React error #418; visit https://react.dev/errors/418?args[]=text`.
6. The same pattern affects `/questions/inicet/practice` (identical `while (true)` loop).

---

## 3. Evidence collected (before any fix)

Captured via Chrome DevTools MCP attached to the live production site, 2026-07-25.

### 3.1 Network waterfall (excerpt)

```
GET https://crackcms-vsthc.ondigitalocean.app/api/questions/?exam_type=neet_pg&page=1&page_size=20  [200]
GET https://crackcms-vsthc.ondigitalocean.app/api/questions/?exam_type=neet_pg&page=2&page_size=20  [200]
…
GET https://crackcms-vsthc.ondigitalocean.app/api/questions/?exam_type=neet_pg&page=77&page_size=20 [pending]
```

Total of 156 such requests in the first capture session. With concurrent users the count climbs into the 200s and the backend starts emitting 429.

### 3.2 Console error

```
ID: 1
error> Uncaught Error: Minified React error #418; visit https://react.dev/errors/418?args[]=text&args[]= for the full message
Stack:
  at rK (117e72e657f8cb9a.js:1:45829)
  …
  Module evaluation (turbopack-5e5e40e96e475657.js:4:939)
```

`args=[text]` confirms a text-content hydration mismatch (React #418 = "Text content does not match server-rendered HTML").

### 3.3 _rsc=* prefetches

In addition to the `/api/questions/` loop, every sidebar link triggers its own Next.js Server Component cache prefetch via `?_rsc=<hash>`. 35+ such requests on a single page load — these are pre-warmed for instant navigation but add significant load. They are NOT the cause of the 429, but they are part of the same over-fetch pattern.

### 3.4 Code locations

| File | Line | Defect |
|------|------|--------|
| `frontend/src/app/questions/neet-pg/practice/page.tsx` | 36–53 | `while (true) { page += 1; if (page > ALL_PAGES /*=200*/) break }` |
| `frontend/src/app/questions/inicet/practice/page.tsx` | 30–48 | Same loop |
| `frontend/src/app/questions/neet-pg/practice/page.tsx` | 123 | `loading && questions.length === 0` keeps spinner up until entire loop completes |
| `frontend/src/app/questions/neet-pg/practice/page.tsx` | 129 | Server renders "Loading…" without " (N loaded)"; client renders "Loading… (640 loaded)" → React #418 |

---

## 4. Resolution

Commit `43f5cf1` — see `BUG_FIX_REPORT.md` for the full diff narrative and `ROOT_CAUSE_ANALYSIS.md` for the chain-of-causation.

### 4.1 Headline changes

1. `fetchAllNeetPgQuestions` (and `fetchAllIniCetQuestions`) replaced with `fetchNeetPgPage(params, page)` that fetches exactly one page.
2. The route entry point loads only page 1 on mount, then hands the player an `onLoadMore()` callback.
3. `NeetPgPlayer` / `IniCetPlayer` auto-invoke `onLoadMore()` when the user is within 5 of the end of the loaded questions.
4. 429 responses from `/api/questions/` produce a clear "Server is rate-limiting requests" UI with a Retry button — never an infinite spinner.
5. Header Q-counter reads "Q 1 / 20+" (the "+" means more pages available).
6. Footer banner shows the loading-more / rate-limited / "click Next to fetch more" state explicitly.
7. `React #418` removed because the spinner branch now renders identical text on server and client (no `loadedCount` suffix in the JSX).

### 4.2 Regression test

`frontend/tests/e2e/neet-pg-qa.spec.ts` — `PRODUCTION INCIDENT` describe block asserts the network shape: at most 2 distinct `page=N` requests on initial mount, zero 429 responses. This test would have failed loudly on 2026-07-25.

### 4.3 Verification

- `npx tsc --noEmit` clean.
- Production verification pending Vercel deploy — see "Followup actions" below.

---

## 5. Followup actions

1. **Verify on prod post-deploy** — re-run Playwright against `https://www.cracklabs.app/questions/neet-pg/practice`; assert <=2 page=N requests, zero 429, no React #418, first question visible within 3 seconds.
2. **Resume BUG #R4** — production image URLs return 404 because local-FS storage + DEBUG-only `static()` URL routing. Fix stashed, will resume after prod stabilization confirmed.
3. **Reduce RSC prefetch pressure** — every sidebar link pre-warms a Server Component cache entry. Consider switching from `<Link prefetch>` (default) to `<Link prefetch={false}>` on routes that don't have RSC payloads, or using `routerPrefetch={false}` globally. Out of scope for this incident.
4. **DRF throttle tuning** — confirm throttle rate on `/api/questions/` is appropriate for the NEET-PG user count. Current production throttle likely defaults to 60/min anonymous — bump to 200/min for authenticated users, or convert to a per-question allowance.
5. **Add structured logging on 429** so future spikes are observable.
