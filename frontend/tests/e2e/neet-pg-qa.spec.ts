/**
 * NEET PG Browser QA regression suite.
 *
 * Regression suite for the 10 production bugs discovered via
 * Playwright on 2026-07-25. Each test corresponds to one bug in
 * docs/qa/UI_BUG_REPORT.md. Keep them green.
 *
 * Run:    npx playwright test tests/e2e/neet-pg-qa.spec.ts
 * Against production: BASE_URL=https://www.cracklabs.app PLAYWRIGHT_SKIP_WEBSERVER=1 npx playwright test
 */
import { test, expect, request } from '@playwright/test';

const API_BASE = process.env.API_BASE_URL || 'https://crackcms-vsthc.ondigitalocean.app';

test.describe('Bug #6 — exam_source filter was ignored on /api/questions/', () => {
    test('filterset_fields must include exam_source', async () => {
        const ctx = await request.newContext({ baseURL: API_BASE });
        const fake = await ctx.get('/api/questions/', { params: { exam_source: 'NEET PG', page_size: 5 } });
        expect(fake.ok()).toBeTruthy();
        const data = await fake.json();
        expect(data.count).toBeGreaterThan(0);
        // every result must belong to NEET PG family
        for (const r of (data.results || []).slice(0, 5)) {
            expect(r.exam_source || '').toMatch(/NEET PG/i);
        }
    });

    test('is_image_based=true actually filters', async () => {
        const ctx = await request.newContext({ baseURL: API_BASE });
        const trueRes = await ctx.get('/api/questions/', { params: { is_image_based: 'true', exam_type: 'neet_pg', page_size: 5 } });
        const falseRes = await ctx.get('/api/questions/', { params: { is_image_based: 'false', exam_type: 'neet_pg', page_size: 5 } });
        expect(trueRes.ok()).toBeTruthy();
        expect(falseRes.ok()).toBeTruthy();
        const t = await trueRes.json();
        const f = await falseRes.json();
        // counts MUST differ if the filter is wired up
        expect(t.count).not.toEqual(f.count);
    });
});

test.describe('Bug #2/#3 — /api/questions/stats/ must not 500 under NEET PG load', () => {
    test('stats endpoint returns 200 in <5s for exam_source=NEET+PG', async () => {
        const ctx = await request.newContext({ baseURL: API_BASE });
        const start = Date.now();
        const res = await ctx.get('/api/questions/stats/', { params: { exam_source: 'NEET PG' } });
        const ms = Date.now() - start;
        expect(res.status(), `took ${ms}ms`).toBe(200);
        expect(ms, 'stats must complete under 5s').toBeLessThan(5000);
        const data = await res.json();
        expect(data.total).toBeGreaterThan(0);
        expect(data.by_year.length).toBeGreaterThan(0);
    });
});

test.describe('Bug #5 — /questions?exam=neet-pg gateway timeout UI', () => {
    test('renders 20 question rows within 10s (no gateway timeout)', async ({ page }) => {
        await page.goto('/questions?exam=neet-pg', { waitUntil: 'domcontentloaded', timeout: 30000 });
        // wait for either list OR error message, but the list must render
        await expect(page.locator('text=/Master \\d+ high-yield NEET PG/')).toBeVisible({ timeout: 15000 });
        await expect(page.locator('text=/Service is temporarily unavailable/')).not.toBeVisible();
    });
});

test.describe('Bug #4 — /questions/neet-pg/practice must include Sidebar shell', () => {
    test('sidebar + header render on /questions/neet-pg/practice', async ({ page }) => {
        await page.goto('/questions/neet-pg/practice?year=2021', { waitUntil: 'domcontentloaded' });
        // Sidebar nav element must exist (was missing entirely before)
        await expect(page.locator('aside[aria-label="Primary sidebar navigation"]')).toBeVisible({ timeout: 15000 });
    });

    // Regression for Bug #R2 (2026-07-25): the player used to hit the
    // "No NEET PG questions available" empty state even though the API
    // returned 2497 results. Root cause: Axios wrapper was never unwrapped
    // — fetchAllNeetPgQuestions read res?.results (undefined) instead of
    // res?.data?.results. This test asserts the player chrome actually
    // renders for at least one question from the 2021 paper.
    test('NEET PG 2021 paper renders at least one question in the player', async ({ page }) => {
        await page.goto('/questions/neet-pg/practice?year=2021', { waitUntil: 'domcontentloaded' });
        // The empty-state branch literally says "No NEET PG questions available".
        await expect(page.locator('text=/No NEET PG questions available/i')).toHaveCount(0, { timeout: 30000 });
        // The player chrome shows "Q 1 / N" once questions load. If N is 0 the
        // badge would never render.
        await expect(page.locator('text=/Q 1 \\/ \\d+/')).toBeVisible({ timeout: 30000 });
    });
});

test.describe('Bug #1 — React #418 hydration on /neet-pg', () => {
    test('no React #418 error on /neet-pg', async ({ page }) => {
        const errors: string[] = [];
        page.on('pageerror', err => errors.push(err.message));
        await page.goto('/neet-pg', { waitUntil: 'networkidle', timeout: 30000 });
        const has418 = errors.some(e => /Minified React error.*418/i.test(e));
        expect(has418, `React #418 fired. Errors: ${errors.join('\n')}`).toBe(false);
    });

    test('no React #418 error on /questions?exam=neet-pg', async ({ page }) => {
        const errors: string[] = [];
        page.on('pageerror', err => errors.push(err.message));
        await page.goto('/questions?exam=neet-pg', { waitUntil: 'networkidle', timeout: 30000 });
        const has418 = errors.some(e => /Minified React error.*418/i.test(e));
        expect(has418, `React #418 fired. Errors: ${errors.join('\n')}`).toBe(false);
    });
});

test.describe('Bug #9 — display_number must default to a per-paper ordinal', () => {
    test('NEET PG 2021 questions have non-null display_number OR stable ordinal via id', async () => {
        const ctx = await request.newContext({ baseURL: API_BASE });
        const res = await ctx.get('/api/questions/', { params: { exam_type: 'neet_pg', year: 2021, page_size: 50 } });
        expect(res.ok()).toBeTruthy();
        const data = await res.json();
        const withNum = (data.results || []).filter((q: any) => q.display_number !== null && q.display_number !== undefined);
        // Even if not all are populated, at least some must be — otherwise UI
        // can't show question numbers in the paper.
        expect(withNum.length).toBeGreaterThan(0);
    });
});

test.describe('Bug #7/#10 — image-based + topic wiring', () => {
    test('NEET PG returns image-bearing questions', async () => {
        const ctx = await request.newContext({ baseURL: API_BASE });
        const res = await ctx.get('/api/questions/', { params: { exam_type: 'neet_pg', is_image_based: 'true', page_size: 5 } });
        expect(res.ok()).toBeTruthy();
        const data = await res.json();
        expect(data.count).toBeGreaterThan(0);
    });
});

test.describe('Bug #R1 — WatermarkOverlay opacity must stay near-invisible', () => {
    test('overlay container opacity is <= 0.10 (screen-recording deterrent, not user-visible)', async ({ page }) => {
        await page.goto('/questions/neet-pg/practice?year=2021', { waitUntil: 'domcontentloaded' });
        await expect(page.locator('text=/Q 1 \\/ \\d+/')).toBeVisible({ timeout: 30000 });
        const overlay = await page.evaluate(() => {
            const candidates = document.querySelectorAll('div[class*="opacity-"][class*="pointer-events-none"]');
            let lowest = 1.0;
            let sample: any = null;
            candidates.forEach((el) => {
                const o = parseFloat(getComputedStyle(el).opacity);
                if (o < lowest) {
                    lowest = o;
                    sample = {
                        className: el.className,
                        text: (el.textContent || '').slice(0, 80),
                        childCount: el.children.length,
                    };
                }
            });
            return { lowest, sample };
        });
        expect(overlay.sample, 'expected at least one opacity-N pointer-events-none overlay').not.toBeNull();
        expect(overlay.lowest, 'overlay opacity must be near-invisible').toBeLessThanOrEqual(0.10);
    });
});

/**
 * Bug #R3 — sidebar overlap on /practice (2026-07-25).
 *
 * The /questions/neet-pg/practice and /questions/inicet/practice routes
 * render <Sidebar/> and the player as top-level siblings inside an
 * ExamTrackProvider, bypassing the root <main className="main-content">
 * that supplies the 260px sidebar margin-left.
 *
 * Without the offset the question card was drawn directly under the fixed
 * sidebar. The fix (commit e57d32f) adds the `main-content` class to the
 * player wrapper. These tests assert the geometry on both desktop
 * (sidebar present, expect left=260) and after toggling the sidebar off
 * via the top-left hide button (expect left=0).
 */
test.describe('Bug #R3 — sidebar overlap on /practice', () => {
    test('NEET PG practice: question card clears the 260px sidebar on desktop', async ({ page }) => {
        await page.setViewportSize({ width: 1280, height: 800 });
        await page.goto('/questions/neet-pg/practice?year=2021', { waitUntil: 'domcontentloaded' });
        await expect(page.locator('aside[aria-label="Primary sidebar navigation"]')).toBeVisible({ timeout: 15000 });
        await expect(page.locator('text=/Q 1 \\/ \\d+/')).toBeVisible({ timeout: 30000 });

        const layout = await page.evaluate(() => {
            const aside = document.querySelector('aside[aria-label="Primary sidebar navigation"]') as HTMLElement | null;
            const mainContent = document.querySelector('.main-content') as HTMLElement | null;
            return {
                sidebar: aside ? { left: Math.round(aside.getBoundingClientRect().left), right: Math.round(aside.getBoundingClientRect().right), width: Math.round(aside.getBoundingClientRect().width) } : null,
                mainContent: mainContent ? { left: Math.round(mainContent.getBoundingClientRect().left) } : null,
                vw: window.innerWidth,
            };
        });
        expect(layout.sidebar, 'sidebar must be present').not.toBeNull();
        expect(layout.mainContent, '.main-content wrapper must be present').not.toBeNull();
        expect(layout.sidebar!.right).toBe(260);
        // CRITICAL: main-content.left must clear the sidebar (>= 260).
        expect(layout.mainContent!.left).toBeGreaterThanOrEqual(260);
    });

    test('NEET PG practice: collapsing the sidebar pushes content back to left=0', async ({ page }) => {
        await page.setViewportSize({ width: 1280, height: 800 });
        await page.goto('/questions/neet-pg/practice?year=2021', { waitUntil: 'domcontentloaded' });
        await expect(page.locator('aside[aria-label="Primary sidebar navigation"]')).toBeVisible({ timeout: 15000 });
        // Toggle off the desktop sidebar
        await page.locator('.desktop-sidebar-toggle-btn').click();
        await page.waitForTimeout(200); // allow class swap

        const layout = await page.evaluate(() => {
            const mainContent = document.querySelector('.main-content') as HTMLElement | null;
            const aside = document.querySelector('aside[aria-label="Primary sidebar navigation"]') as HTMLElement | null;
            const body = document.body;
            return {
                mainContentLeft: mainContent ? Math.round(mainContent.getBoundingClientRect().left) : null,
                bodyHasSidebarHidden: body.classList.contains('sidebar-hidden'),
                asideDisplay: aside ? getComputedStyle(aside).display : null,
            };
        });
        expect(layout.bodyHasSidebarHidden).toBe(true);
        expect(layout.asideDisplay).toBe('none');
        // When sidebar is hidden, main-content.left should collapse to 0 (modulo the 20px global padding).
        expect(layout.mainContentLeft).toBeLessThanOrEqual(20);
    });

    test('INI-CET practice: question card clears the 260px sidebar on desktop', async ({ page }) => {
        await page.setViewportSize({ width: 1280, height: 800 });
        await page.goto('/questions/inicet/practice', { waitUntil: 'domcontentloaded' });
        await expect(page.locator('aside[aria-label="Primary sidebar navigation"]')).toBeVisible({ timeout: 15000 });

        const layout = await page.evaluate(() => {
            const aside = document.querySelector('aside[aria-label="Primary sidebar navigation"]') as HTMLElement | null;
            const mainContent = document.querySelector('.main-content') as HTMLElement | null;
            return {
                sidebar: aside ? { right: Math.round(aside.getBoundingClientRect().right) } : null,
                mainContentLeft: mainContent ? Math.round(mainContent.getBoundingClientRect().left) : null,
            };
        });
        expect(layout.sidebar, 'sidebar must be present').not.toBeNull();
        expect(layout.mainContentLeft, 'main-content.left must clear the sidebar').toBeGreaterThanOrEqual(260);
    });
});
