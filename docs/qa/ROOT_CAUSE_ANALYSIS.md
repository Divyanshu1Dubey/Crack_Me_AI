# ROOT_CAUSE_ANALYSIS.md

**Incident:** PROD-2026-07-25-01 — `/practice` page infinite spinner + 429s
**Author:** Claude Code (zero-compromise QA mission, 2026-07-25)
**Reference:** `PRODUCTION_INCIDENT_REPORT.md`, `BUG_FIX_REPORT.md`, commit `43f5cf1`

This document walks the chain-of-causation for each of the three independent defects that combined into the user-visible outage.

---

## Defect A — Over-fetch loop (cause of the 429s)

### A.1 Original code

`frontend/src/app/questions/neet-pg/practice/page.tsx` (lines 27–53, pre-fix):

```tsx
const ALL_PAGES = 200; // DRF caps page_size at 20, so paginate to fetch everything.

async function fetchAllNeetPgQuestions(params, onProgress) {
    const results: any[] = [];
    let page = 1;
    while (true) {
        const res = await questionsAPI.list({ ...params, page, page_size: 20 });
        const body = res?.data ?? res;
        const chunk = body?.results ?? (Array.isArray(body) ? body : []);
        if (!chunk.length) break;
        results.push(...chunk);
        onProgress?.(results.length);
        const next = body?.next;
        if (!next) break;
        page += 1;
        if (page > ALL_PAGES) break;
    }
    return results;
}
```

### A.2 Why this exists

The author wanted the player to have ALL questions in memory so the palette could jump to any index. Backwards-compatibility with the existing palette UX, which lets users click any of N question tiles.

### A.3 Why it's wrong

Three compounding problems:

1. **No upper bound on requests.** The loop runs until either `body.next === null` (end of dataset) or `page > 200` (the hard cap). With ~3,000 NEET PG questions / 20-per-page = 150+ requests on every visit.
2. **Sequential, not parallel.** Each request waits for the previous one to finish, so a 200 ms per-request RTT × 150 requests = 30 seconds of wall-clock before the spinner exits.
3. **Every page returns 200 by default.** Until the throttle kicks in (or the dataset runs out), the loop happily continues. This is what made the bug invisible during local dev — the dev dataset is too small to trigger throttling.

### A.4 Chain of causation

```
over-fetch loop
  → 150+ sequential requests per page load
  → DRF throttle / Cloudflare rate limit exceeded
  → 429 response
  → Axios throws
  → catch block sets error state
  → page renders "Couldn't load NEET PG questions / status 429"
```

### A.5 Why a single user triggered 429

Even with a single user, **the user's screenshot showed `Loading… (2640 loaded)`**, implying the page reached a depth of 132 pages (20 × 132 = 2640). That alone is 132 requests on a single session — well past the typical DRF default of 60/min for anonymous. The user's auth session is also creating `/api/auth/profile/` requests (3 of them, see network capture), compounding the pressure.

### A.6 Fix

Replace `fetchAllNeetPgQuestions` (fetch-all) with `fetchNeetPgPage(params, page)` (fetch-one). The route entry point loads only page 1 on mount. The player gets an `onLoadMore()` callback it invokes when within 5 of the end of the loaded array. The player's Next button invokes `onLoadMore()` when clicked at the end of the loaded list.

See `BUG_FIX_REPORT.md` §1 for the full diff.

---

## Defect B — Spinner never exits on error

### B.1 Original code

`frontend/src/app/questions/neet-pg/practice/page.tsx` (lines 119–134, pre-fix):

```tsx
if (!mounted || (loading && questions.length === 0)) {
    return (
        <div className="min-h-screen …">
            <Loader2 className="…animate-spin…" />
            <p>Loading NEET PG Practice… {loadedCount > 0 ? `(${loadedCount} loaded)` : ''}</p>
        </div>
    );
}
```

### B.2 Why it's wrong

The `loadedCount > 0` suffix renders the **client-side text** `(640 loaded)` after the first page lands. The **server-side render** has no such suffix — `loadedCount` is always 0 on the server. React diff's the two strings and throws #418.

The spinner exits only when `loading === false && questions.length > 0`. The 429 throws inside `fetchAllNeetPgQuestions`, but the thrown error is caught by the `try { ... } catch (e) { setError(e); setLoading(false); }` block — so `loading` IS flipped to `false`. **However**, the spinner JSX above runs first if `loading && questions.length === 0`, then the error branch renders. The transition is fast, but in the brief moment between throw and re-render the user sees the spinner, then the error UI. The "infinite spinner" perception comes from the loop continuing to throw on page 2, 3, … before finally settling into the error branch.

### B.3 Chain of causation

```
loop hits 429 on page 5
  → catch block sets error state
  → user sees "Couldn't load" UI briefly
  → loop continues from page 5 (next iteration), hits 429 again
  → catches, sets error state again — but state is the same so no re-render
  → user is stuck on "Couldn't load" UI
```

In the user's report, the UI was the spinner rather than the error UI — likely because the screenshot was taken before the first 429 surfaced, or because `loadedCount > 0` keeps the spinner text on-screen until React re-renders.

### B.4 Fix

1. **Remove the `(N loaded)` suffix** from the spinner text — server and client now agree.
2. **Detect 429 explicitly** and render a distinct "Server is rate-limiting requests" UI with a Retry button.
3. **Auto-recover on retry** — `retryFromScratch()` re-fetches page 1.

See `BUG_FIX_REPORT.md` §2 for the full diff.

---

## Defect C — React #418 hydration mismatch

### C.1 Original code

The spinner JSX (shown in §B.1) renders different text on server vs client:

| Render | Text |
|--------|------|
| Server | `Loading NEET PG Practice…` |
| Client (after 1st page) | `Loading NEET PG Practice… (640 loaded)` |

### C.2 Why React throws #418

React 18 enforces server-render parity. Any text-node mismatch between SSR HTML and the client's first paint throws #418 to prevent the visible "flash of incorrect content". The component does NOT crash the page (it logs the error and continues), but the error is logged + surfaces in Sentry / console / observability dashboards.

### C.3 Why `ExamTrackProvider` is NOT the cause

`ExamTrackProvider` is correctly written to default `activeTrack='cms'` on the server and only update from `localStorage` inside a `useEffect`. Sidebar consumes the `hydrated` flag to gate client-only branching. The mismatch is exclusively in the `(N loaded)` text suffix.

### C.4 Fix

Remove the `(N loaded)` suffix from the spinner text. The Q-counter in the player header still shows "Q 1 / 20+" which is a separate component and a separate render boundary.

See `BUG_FIX_REPORT.md` §3 for the full diff.

---

## Defect D (root-cause upstream) — `_rsc=*` prefetch cascade

### D.1 Evidence

35+ `GET /?_rsc=<hash>` requests on a single page load. Each sidebar link's `<Link>` component prefetches its RSC payload to enable instant navigation.

### D.2 Why this is concerning (not the primary cause)

These prefetches hit the **Next.js frontend**, not the backend API. They do not directly cause 429s on `/api/questions/`. They DO however add 35+ requests to the first-paint budget, slowing hydration and increasing the window during which the spinner branch is visible.

### D.3 Fix

Out of scope for this incident. Recommend disabling RSC prefetch on the practice-route sidebar links in a follow-up commit — `prefetch={false}` on the navigation items the user is unlikely to click while in practice mode.

---

## Summary

| Defect | Cause | Fix commit | Regression test |
|--------|-------|-----------|-----------------|
| A. Over-fetch loop | `while (true)` fetches 200 pages sequentially | `43f5cf1` | `PRODUCTION INCIDENT — /practice page must not over-fetch` |
| B. Spinner never exits | error caught but state not surfaced to UI | `43f5cf1` | same describe block (covers 429 path) |
| C. React #418 | server vs client text mismatch in spinner | `43f5cf1` | `no React #418 error on /questions/neet-pg/practice` (existing) |
| D. RSC prefetch cascade | Next.js default prefetch + sidebar length | follow-up | follow-up |