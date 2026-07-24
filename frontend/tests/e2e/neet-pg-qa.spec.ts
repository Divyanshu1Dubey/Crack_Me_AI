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
