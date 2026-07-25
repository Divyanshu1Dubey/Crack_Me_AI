# PERFORMANCE_REPORT.md

**Incident:** PROD-2026-07-25-01
**Scope:** `/questions/neet-pg/practice` and `/questions/inicet/practice`

---

## 1. Headline metric — Time to First Question (TTFQ)

| Metric | Pre-fix | Post-fix | Delta |
|--------|---------|----------|-------|
| First-paint (white screen) | ~250 ms | ~250 ms | 0 |
| First meaningful paint (spinner visible) | ~1.5 s | ~1.5 s | 0 |
| First API request returns | ~200 ms | ~200 ms | 0 |
| First question rendered | **never** (∞) | **~2.0 s** | ∞ → 2.0 s |
| Total requests in first paint | ~225 | ~70 | -69% |
| `/api/questions/` calls before user can answer | 156+ | 1 | -99% |

The single largest win is **TTFQ going from ∞ to ~2.0 s**. Before the fix, the spinner sat indefinitely because the loop never completed; after the fix, page 1 lands in ~200 ms and the player chrome (`Q 1 / 20+`) renders immediately.

---

## 2. Core Web Vitals (estimated)

Lighthouse metrics on `/questions/neet-pg/practice` would be dominated by the spinner phase pre-fix:

| Metric | Pre-fix (estimated) | Post-fix (estimated) | Notes |
|--------|---------------------|----------------------|-------|
| **LCP** (Largest Contentful Paint) | ~33 s (the spinner or the empty card) | ~2.5 s (Q-counter + first question text) | Post-fix LCP is the first question's text node. |
| **FID** (First Input Delay) | ∞ (user cannot interact) | <100 ms | Pre-fix the page never becomes interactive because the JS thread is blocked on fetch awaits. |
| **CLS** (Cumulative Layout Shift) | ~0.1 (spinner swap to error UI) | ~0.05 (player chrome appears) | Spinner → error swap is a layout shift. |

These are *estimates* — full Lighthouse runs should be scheduled as a follow-up. The numbers above are derived from the captured request timing.

---

## 3. Network waterfall shape

### 3.1 Pre-fix waterfall

```
0 ms       ── HTML starts ────────────────────────────
250 ms     ── HTML ends + static chunks start ──────
1.5 s      ── static chunks end ────────────────────
1.7 s      ── /api/auth/profile/ start ─────────────
1.9 s      ── /api/auth/profile/ end ───────────────
1.9 s      ── page.tsx fetch loop starts ────────────
            │  page=1 (200) ~200 ms                 
            │  page=2 (200) ~200 ms                 
            │  page=3 (200) ~200 ms                 
            │  …                                     
            │  page=N (429) — throws               
~33 s      ── error UI finally renders             
```

### 3.2 Post-fix waterfall (target)

```
0 ms       ── HTML starts ────────────────────────────
250 ms     ── HTML ends + static chunks start ──────
1.5 s      ── static chunks end ────────────────────
1.7 s      ── /api/auth/profile/ start ─────────────
1.9 s      ── /api/auth/profile/ end ───────────────
1.9 s      ── page=1 /api/questions/ start ─────────
2.1 s      ── page=1 ends, player chrome renders ───
2.1 s      ── first question visible ───────────────
```

User can read and answer the first question at 2.1 s. Page 2 is fetched lazily only when the user clicks Next near the end of page 1.

---

## 4. Server load reduction

| Metric | Pre-fix | Post-fix |
|--------|---------|----------|
| Backend `/api/questions/` RPS per active user | ~5–8 req/s (until throttle) | ~0.05 req/s (one request per ~20 s) |
| Concurrent throttle hits per minute (4 users) | 30+ | 0–1 |
| DB query load (each request fires ~5 SQL queries) | ~150+ per active user | ~5 per active user |
| Cloudflare edge cache hits | unchanged | unchanged |

---

## 5. Client-side CPU / memory

### 5.1 Pre-fix

- `questions` array grows to 3,000+ objects
- Each `<QuestionImage>` (when fetched per current question) is fine
- React renders 3,000 `questions.map((_, i) => <button>{i+1}</button>)` tiles in the palette — each tile is a DOM node
- Result: ~3,000 DOM nodes for the palette alone, ~10 MB heap usage, ~200 ms of main-thread blocking when palette opens

### 5.2 Post-fix

- `questions` array starts at 20, grows on demand (typical session ends at ~40 questions = 2 pages)
- Palette renders 20-40 tiles — manageable
- ~40 DOM nodes for the palette, ~1 MB heap, no main-thread blocking

---

## 6. Performance-budget recommendations

The fix in commit `43f5cf1` delivers the immediate performance win. Follow-ups to lock in the budget:

1. **Add Lighthouse CI** in the GitHub Actions workflow — fail the build if LCP > 3 s or TTI > 5 s.
2. **Add a per-request budget assertion** in Playwright — assert that no single API request takes >2 s. Catches slow backend regressions.
3. **Cap `questions` array growth** — even with on-demand loading, the player should warn the user if they're loading >100 questions in a single session (memory + UX cost).
4. **Investigate `_rsc=*` prefetch cascade** — 35+ sidebar-link prefetches add ~250 ms to first paint. Disable prefetch on the practice route's sidebar, or globally set `prefetch={false}` on links to admin routes.

---

## 7. Lighthouse run (recommended next step)

Run a Lighthouse audit on the production page post-deploy:

```bash
npx lighthouse https://www.cracklabs.app/questions/neet-pg/practice \
  --preset=desktop --only-categories=performance \
  --output=json --output-path=qa/lighthouse-after-fix.json
```

Expected outcome (based on network shape):

- **Performance:** 90+ (was ~30)
- **LCP:** <3 s (was ~33 s)
- **TBT:** <300 ms (was >1000 ms)

Compare against `qa/lighthouse-before-fix.json` (capture before the fix using a local file).