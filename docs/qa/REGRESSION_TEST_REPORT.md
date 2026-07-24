# Regression Test Report — NEET PG Browser QA

**Date**: 2026-07-25
**Suite**: `frontend/tests/e2e/neet-pg-qa.spec.ts` (8 tests)
**Driver**: Playwright (Chromium)

---

## How to run

```bash
# Local against a running dev server
cd frontend && npx playwright test tests/e2e/neet-pg-qa.spec.ts

# Against production (no local server needed)
BASE_URL=https://www.cracklabs.app \
API_BASE_URL=https://crackcms-vsthc.ondigitalocean.app \
PLAYWRIGHT_SKIP_WEBSERVER=1 \
  npx playwright test tests/e2e/neet-pg-qa.spec.ts
```

---

## Test matrix

| # | Test | Bug | Type | Expected |
|---|------|-----|------|----------|
| 1 | `exam_source` filter must filter | #6 | API | All results `exam_source` matches "NEET PG" |
| 2 | `is_image_based=true` filter must differ from `false` | #6 | API | `count(true) != count(false)` |
| 3 | `/api/questions/stats/` returns 200 in <5s | #11 | API | status=200, <5s |
| 4 | `/questions?exam=neet-pg` renders rows in <10s | #5 | UI | No "Service is temporarily unavailable" message |
| 5 | `/questions/neet-pg/practice` renders Sidebar | #4 | UI | `<aside aria-label="Primary sidebar navigation">` visible |
| 6 | No React #418 on `/neet-pg` | #1 | UI | `pageerror` does not contain "Minified React error #418" |
| 7 | No React #418 on `/questions?exam=neet-pg` | #1 | UI | Same |
| 8 | NEET PG 2021 questions have `display_number` populated | #9 | API | >0 rows with `display_number != null` |

---

## Test code

```ts
import { test, expect, request } from '@playwright/test';

const API_BASE = process.env.API_BASE_URL || 'https://crackcms-vsthc.ondigitalocean.app';

test.describe('Bug #6 — exam_source filter was ignored on /api/questions/', () => {
  test('filterset_fields must include exam_source', async () => {
    const ctx = await request.newContext({ baseURL: API_BASE });
    const res = await ctx.get('/api/questions/', {
      params: { exam_source: 'NEET PG', page_size: 5 },
    });
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    for (const r of (data.results || []).slice(0, 5)) {
      expect(r.exam_source || '').toMatch(/NEET PG/i);
    }
  });
  // ...
});

test.describe('Bug #1 — React #418 hydration on /neet-pg', () => {
  test('no React #418 error on /neet-pg', async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', err => errors.push(err.message));
    await page.goto('/neet-pg', { waitUntil: 'networkidle', timeout: 30000 });
    expect(errors.some(e => /Minified React error.*418/i.test(e))).toBe(false);
  });
});
```

---

## Status before this PR

| Test | Status |
|------|--------|
| 1 | ❌ FAIL — exam_source filter ignored |
| 2 | ❌ FAIL — both filters returned same count |
| 3 | ❌ FAIL — 500 under load |
| 4 | ❌ FAIL — "Service is temporarily unavailable" shown |
| 5 | ❌ FAIL — Sidebar absent |
| 6 | ❌ FAIL — React #418 fires |
| 7 | ❌ FAIL — React #418 fires |
| 8 | ❌ FAIL — display_number is null on every row |

**Pass rate before**: 0/8 (0%).

---

## Status after commit `eba9268`

| Test | Status |
|------|--------|
| 1 | ✅ PASS — exam_source filter now narrows to 2497 NEET PG questions |
| 2 | ✅ PASS — counts differ (true=0, false=2497) — see Bug #7 follow-up |
| 3 | ✅ PASS — stats endpoint returns 200 in <500ms |
| 4 | ✅ PASS — questions render after hydration fix |
| 5 | ✅ PASS — Sidebar visible on practice route |
| 6 | ✅ PASS — no React #418 |
| 7 | ✅ PASS — no React #418 |
| 8 | ❌ FAIL — display_number still null (data-side fix pending) |

**Pass rate after**: 7/8 (87.5%).

---

## Pre-deploy gate

Add this to `.github/workflows/ci.yml`:

```yaml
- name: NEET PG regression tests
  run: |
    BASE_URL=https://www.cracklabs.app \
    API_BASE_URL=https://crackcms-vsthc.ondigitalocean.app \
    PLAYWRIGHT_SKIP_WEBSERVER=1 \
      npx playwright test tests/e2e/neet-pg-qa.spec.ts
```

Run on every push to `main` to prevent any of these regressions from shipping again.

---

## Pre-deploy data gate

A separate Python data-integrity script should be added to `backend/qa/`:

```python
# backend/qa/check_neet_pg_data_integrity.py
def run():
    assert Question.objects.filter(exam_type='neet_pg', display_number__isnull=True).count() == 0, \
        'NEET PG questions missing display_number'
    assert Question.objects.filter(exam_type='neet_pg', is_image_based=True).count() > 100, \
        'NEET PG has <100 image-based questions'
    assert Question.objects.filter(exam_type='neet_pg', topic__isnull=True).count() < 50, \
        'NEET PG has too many topic=NULL rows'
```

Add as a Django management command and run on every deploy.
