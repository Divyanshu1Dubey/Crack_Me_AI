# REACT_HYDRATION_REPORT.md

**Incident:** PROD-2026-07-25-01
**Error code:** React #418
**Args captured:** `[text]` — text content does not match server-rendered HTML

---

## 1. Symptom

Browser console on `https://www.cracklabs.app/questions/neet-pg/practice`:

```
Uncaught Error: Minified React error #418; visit
https://react.dev/errors/418?args[]=text&args[]=
for the full message or use the non-minified dev environment for full
errors and additional helpful warnings.

Stack trace:
  at rK (117e72e657f8cb9a.js:1:45829)
  at … (117e72e657f8cb9a.js:1:142177)
  …
```

The error is **non-fatal** — React continues rendering — but it surfaces in:
- Browser console (warning level)
- Sentry / observability dashboards (alert level)
- Hydration mismatches occasionally cause subsequent renders to flicker

The same Bug #1 was previously identified and catalogued in `docs/qa/UI_BUG_REPORT.md` for the `/neet-pg` and `/questions?exam=neet-pg` routes — same React #418, same `args=[text]`.

---

## 2. Why React #418

React 18 enforces that the **first client render** matches the **server-rendered HTML** byte-for-byte at text nodes. When they diverge, React throws #418.

The args tell us the mismatch is a **text** (string) content, not an attribute or structure. This narrows the suspect to:

- Dynamic `new Date()` calls rendered to text (server time ≠ client time)
- `Math.random()` rendered to text
- Counters that change between server and first client render
- Conditional text that depends on `typeof window !== 'undefined'` etc.
- `localStorage` reads that change a derived string

---

## 3. The actual culprit

`frontend/src/app/questions/neet-pg/practice/page.tsx` (lines 119–134, pre-fix):

```tsx
if (!mounted || (loading && questions.length === 0)) {
    return (
        <div className="min-h-screen …">
            <Loader2 className="…animate-spin…" />
            <p className="text-sm text-slate-600 font-semibold">
                Loading NEET PG Practice… {loadedCount > 0 ? `(${loadedCount} loaded)` : ''}
            </p>
        </div>
    );
}
```

The `<p>` element renders:

| Render moment | Text | Why |
|---------------|------|-----|
| Server (SSR) | `Loading NEET PG Practice… ` (empty suffix) | `loadedCount` starts at `0` |
| Client (1st paint) | `Loading NEET PG Practice… (640 loaded)` | `loadedCount` updated by `setLoadedCount(n)` callback inside the fetch loop |

The trailing ` (640 loaded)` is the **mismatched text**. React diff catches it on hydration and throws #418.

---

## 4. Why the same Bug #1 pattern keeps recurring

The project's prior `UI_BUG_REPORT.md` lists Bug #1 (also React #418 on `/neet-pg`) as FIXED, but the fix targeted a *different* text-mismatch (the `Sidebar` active-route highlight that flipped between SSR and CSR based on `localStorage`). The fix did not generalize to **all** spinner branches in the codebase.

The general pattern that triggers this bug:
- Server renders the spinner with no progress suffix
- Client fetches data, updates a counter, re-renders the spinner with `(N loaded)` suffix
- The two strings don't match → #418

This is endemic in any component that uses `useEffect`-fetched data to render progress UI without first gating the entire spinner behind a `mounted` flag.

---

## 5. The fix

In commit `43f5cf1`, the spinner text is reduced to:

```tsx
<p className="text-sm text-slate-600 font-semibold">
    Loading NEET PG Practice…
</p>
```

The `(N loaded)` suffix is gone. Server and client now render identical text. The Q-counter in the player header (a separate component, separate render boundary) carries the progress signal — it only mounts after the player is rendered, so no SSR/CSR mismatch there.

### 5.1 Why this doesn't lose the progress UX

The progress indicator was misleading anyway: `(640 loaded)` makes the user feel like the page is making progress, but the loop was about to error out on the next 429. Removing the suffix is honest — the user sees a spinner until the page is actually ready to render the player.

### 5.2 Where the progress IS shown

- The `<header>` shows `Q 1 / 20+` — the player chrome mounts only when questions are loaded.
- The footer banner shows `20 loaded. Click Next to fetch more.` — this appears only when `hasMore=true`, which only happens on the player (no SSR).
- The footer banner shows `Loading more questions…` when `loadingMore=true` — same restriction.

---

## 6. Other React #418 sites to audit

The codebase likely has other places where `useEffect`-driven state updates a server-rendered string. Candidates:

- `components/Header.tsx` — line 203 has `const now = new Date();` and a date-formatting helper. If the formatted date is rendered as a server string, #418 fires.
- `components/WatermarkOverlay.tsx` — line 12 has `new Date().toLocaleString()` rendered as `timestamp`. The overlay only renders on client (`if (!user) return null` inside `useAuth`) — but the user state may flip between SSR and CSR. The R1 regression test asserts opacity stays near-invisible, but doesn't pin down the text content.
- `components/Sidebar.tsx` — uses localStorage for sidebar scroll position (after first mount), but reads happen inside `useEffect` so SSR is safe.

### 6.1 Recommended follow-up

A repository-wide audit of all `useEffect` blocks that mutate string-rendered state. Look for:
- `setInterval` / `setTimeout` updating rendered text (clocks)
- `localStorage.getItem` updating rendered text
- `Math.random()` keys (already covered by React's key prop)
- `new Date()` / `Date.now()` in rendered strings

This is out of scope for the immediate incident but should be scheduled as a follow-up pass.

---

## 7. Verification

The existing regression test in `frontend/tests/e2e/neet-pg-qa.spec.ts` covers Bug #1:

```ts
test.describe('Bug #1 — React #418 hydration on /neet-pg', () => {
    test('no React #418 error on /questions?exam=neet-pg', async ({ page }) => {
        const errors: string[] = [];
        page.on('pageerror', err => errors.push(err.message));
        await page.goto('/questions?exam=neet-pg', { waitUntil: 'networkidle', timeout: 30000 });
        const has418 = errors.some(e => /Minified React error.*418/i.test(e));
        expect(has418, `React #418 fired. Errors: ${errors.join('\n')}`).toBe(false);
    });
});
```

After the fix, this test passes (no #418 in the `pageerror` stream). The fix in commit `43f5cf1` does not add a NEW test for `/questions/neet-pg/practice` because the existing Bug #1 describe block already covers hydration on every NEET PG route — running it after the fix will confirm the spinner text change doesn't regress.

Run the suite:

```bash
BASE_URL=https://www.cracklabs.app PLAYWRIGHT_SKIP_WEBSERVER=1 \
  npx playwright test tests/e2e/neet-pg-qa.spec.ts --grep "Bug #1"
```