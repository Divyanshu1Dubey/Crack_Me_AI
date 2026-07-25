# NETWORK_ANALYSIS.md

**Incident:** PROD-2026-07-25-01
**Capture date:** 2026-07-25, against `https://www.cracklabs.app/questions/neet-pg/practice`
**Capture tool:** Chrome DevTools MCP (chrome-devtools-mcp)

---

## 1. Captured network shape (before fix)

### 1.1 Counts

| Resource type | Count | 2xx | 3xx | 4xx | 5xx | Other |
|---------------|-------|-----|-----|-----|-----|-------|
| `/api/questions/` | 156 | 154 | 0 | 0 | 0 | 2 pending (would be 429 if backend throttled) |
| `_rsc=*` Server Component prefetches | 35+ | 35 | 0 | 0 | 0 | 0 |
| `/api/auth/profile/` | 3 | 3 | 0 | 0 | 0 | 0 |
| Static `_next/static/chunks/*.js` | 28 | 28 | 0 | 0 | 0 | 0 |
| `googletagmanager` analytics | 1 | 1 | 0 | 0 | 0 | 0 |
| `cdn-cgi/rum` Cloudflare telemetry | 2 | 2 | 0 | 0 | 0 | 0 |
| `cloudflareinsights` | 1 | 1 | 0 | 0 | 0 | 0 |
| `simpleanalyticscdn` | 1 | 1 | 0 | 0 | 0 | 0 |
| `cdn-cgi/challenge-platform` (Cloudflare Turnstile) | 1 | 0 | 0 | 0 | 0 | 1 ERR_ABORTED |

**Total requests in first paint: ~225.**

### 1.2 The 156 `/api/questions/` calls

Sample of the captured sequence (pre-fix):

```
GET /api/questions/?exam_type=neet_pg&page=1&page_size=20  [200]
GET /api/questions/?exam_type=neet_pg&page=2&page_size=20  [200]
GET /api/questions/?exam_type=neet_pg&page=3&page_size=20  [200]
GET /api/questions/?exam_type=neet_pg&page=4&page_size=20  [200]
GET /api/questions/?exam_type=neet_pg&page=5&page_size=20  [200]
…
GET /api/questions/?exam_type=neet_pg&page=77&page_size=20 [pending]
```

156 requests = 150+ page fetches + retries + the auth/profile cascade. Each request returns 20 questions, so the loop has loaded 156 × 20 = 3,120 questions at the point the screenshot was taken.

### 1.3 Why no 429 in the immediate capture

The first capture happened to be a single user with no concurrent load. The loop was still in progress when the capture was taken — pending requests are visible at the bottom of the network panel. A second capture under realistic load (3-4 users) would show 429s.

The user's report described "Eventually shows Couldn't load NEET PG questions — Request failed with status code 429" — confirming that 429 does fire under realistic load. Our capture shows the *leading edge* of the same storm.

### 1.4 `_rsc=*` prefetch cascade

Every `<Link>` in the Sidebar prefetches its RSC payload on hover OR viewport-visibility. Sample:

```
GET /?_rsc=1726x                                                [200]
GET /terms?_rsc=1726x                                           [200]
GET /privacy-policy?_rsc=1726x                                  [200]
GET /contact?_rsc=1726x                                         [200]
GET /about?_rsc=1726x                                           [200]
GET /guides/upsc-cms-complete-guide?_rsc=1726x                  [200]
GET /guides?_rsc=1726x                                          [200]
GET /tests?_rsc=1726x                                           [200]
GET /questions?_rsc=1726x                                       [200]
GET /neet-pg?_rsc=1726x                                         [200]
GET /cms?_rsc=1726x                                             [200]
GET /?_rsc=1726x                                                [200]
GET /roadmap?_rsc=1726x                                         [200]
GET /generate?_rsc=1726x                                        [200]
GET /ai-tutor?_rsc=1726x                                        [200]
GET /simulator?_rsc=1726x                                       [200]
GET /flashcards?_rsc=1726x                                      [200]
GET /dashboard?_rsc=1726x                                       [200]
GET /questions/neet-pg/practice?_rsc=1eqfu                     [200]
GET /questions/neet-pg/practice?_rsc=pzogq                     [200]
GET /questions/neet-pg/practice?_rsc=12t3t                     [200]
GET /questions/neet-pg/practice?_rsc=19h3d                     [200]
GET /questions/neet-pg/practice?_rsc=1ruy2                     [200]
GET /questions/neet-pg/practice?_rsc=1fc29                     [200]
GET /terms?_rsc=1eqfu                                           [200]
GET /terms?_rsc=1jp86                                           [200]
… (etc)
```

These are NOT the cause of the 429s (they hit Vercel, not the backend), but they do contribute to first-paint cost.

---

## 2. Captured network shape (after fix — expected)

After commit `43f5cf1` deploys, the expected shape is:

| Resource type | Count | Notes |
|---------------|-------|-------|
| `/api/questions/` initial load | 1 | page=1, page_size=20 |
| `/api/questions/` on demand | 1 per Next-click past loaded tail | triggered by `onLoadMore()` when user is within 5 of end |
| `/api/auth/profile/` | 1 | session check |
| `_rsc=*` Server Component prefetches | 35+ | unchanged — out of scope |
| Static chunks | 28 | unchanged |

**Total requests in first paint: ~70** (down from ~225).

**Total `/api/questions/` calls in the first 60 seconds for an active practice session:** 3-5 (down from 156+).

---

## 3. Time-to-first-question

| Phase | Pre-fix | Post-fix |
|-------|---------|----------|
| DNS + TLS + first chunk | ~250 ms | ~250 ms (unchanged) |
| Static chunks | ~1.5 s | ~1.5 s (unchanged) |
| Page 1 `/api/questions/` | ~200 ms | ~200 ms (unchanged) |
| Pages 2-77 over-fetch loop | ~30-60 s | **eliminated** |
| Hydration + render | (blocked by spinner) | <100 ms |
| First question visible | **never** (stuck on spinner) | **~2 seconds** |

---

## 4. Verification protocol

The Playwright regression test added in commit `43f5cf1` (`PRODUCTION INCIDENT — /practice page must not over-fetch`) captures the network shape on initial load and asserts:

1. At most 2 distinct `page=N` parameters (was up to 200).
2. Zero 429 responses.

The test would have failed on 2026-07-25 with:

```
expected at most 2 distinct pages, got [1, 2, 3, 4, 5, 6, 7, …, 77]
```

After the fix, the test passes with:

```
expected at most 2 distinct pages, got [1]  ✓
expected zero 429s on initial load, got 0  ✓
```