/**
 * NEET PG player — visual regression screenshots.
 *
 * Captures the first question at four combinations:
 *   - Desktop (1280×800) light / dark
 *   - Mobile  (390×844)  light / dark
 *
 * These are the viewports NOT covered by neet-pg-qa.spec.ts (which uses
 * 1280×800 light only). They exist so a human reviewer can eyeball the
 * "Apple / Linear / premium" feel at every breakpoint without running
 * the full QA suite.
 *
 * Credentials are read from env vars at runtime — never hardcoded.
 *   QA_TEST_USER_EMAIL
 *   QA_TEST_USER_PASSWORD
 *
 * Run against production (no local dev server needed):
 *   BASE_URL=https://www.cracklabs.app \
 *   QA_TEST_USER_EMAIL=... QA_TEST_USER_PASSWORD=... \
 *   PLAYWRIGHT_SKIP_WEBSERVER=1 \
 *   npx playwright test tests/e2e/neet-pg-screenshots.spec.ts
 *
 * Screenshots land in `test-results/` and a copy is also written to
 * `screenshots/neet-pg/` for easy review.
 */
import { test, expect, Page } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

const ROUTE = '/questions/neet-pg/practice?year=2021';
const OUT_DIR = path.join(process.cwd(), 'screenshots', 'neet-pg');

async function loginIfNeeded(page: Page) {
    if (!page.url().includes('/login')) return;
    const email = process.env.QA_TEST_USER_EMAIL;
    const password = process.env.QA_TEST_USER_PASSWORD;
    if (!email || !password) {
        test.skip(true, 'Set QA_TEST_USER_EMAIL + QA_TEST_USER_PASSWORD to enable authed screenshots');
        return;
    }
    await page.fill('input[name="identifier"], input[type="email"]', email);
    await page.fill('input[type="password"]', password);
    await page.click('button[type="submit"]');
    await page.waitForURL((url) => !url.toString().includes('/login'), { timeout: 20000 });
}

/**
 * Log in first (so the post-login redirect doesn't hijack our destination),
 * then navigate to the actual route we want to screenshot. Without this
 * step the post-login `router.push('/admin')` lands admin users on the
 * control tower regardless of where we tried to go.
 */
async function loginThenGoto(page: Page, route: string) {
    await page.goto('/login', { waitUntil: 'domcontentloaded', timeout: 30000 });
    await loginIfNeeded(page);
    await page.goto(route, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await expect(page.locator('text=/Q 1 \\/ \\d+/')).toBeVisible({ timeout: 30000 });
    // Allow CSR + auth hydrate + image fetch.
    await page.waitForTimeout(2500);
}

async function gotoAndSettle(page: Page) {
    await loginThenGoto(page, ROUTE);
}

async function shoot(page: Page, label: string) {
    fs.mkdirSync(OUT_DIR, { recursive: true });
    const file = path.join(OUT_DIR, `${label}.png`);
    await page.screenshot({ path: file, fullPage: false });
    return file;
}

test.describe('NEET PG — visual screenshots', () => {
    test('desktop 1280×800, light theme', async ({ page }) => {
        await page.setViewportSize({ width: 1280, height: 800 });
        await page.emulateMedia({ colorScheme: 'light' });
        await gotoAndSettle(page);
        const f = await shoot(page, 'desktop-light');
        expect(fs.existsSync(f)).toBeTruthy();
    });

    test('desktop 1280×800, dark theme', async ({ page }) => {
        await page.setViewportSize({ width: 1280, height: 800 });
        await page.emulateMedia({ colorScheme: 'dark' });
        await gotoAndSettle(page);
        const f = await shoot(page, 'desktop-dark');
        expect(fs.existsSync(f)).toBeTruthy();
    });

    test('mobile 390×844, light theme', async ({ page }) => {
        await page.setViewportSize({ width: 390, height: 844 });
        await page.emulateMedia({ colorScheme: 'light' });
        await gotoAndSettle(page);
        const f = await shoot(page, 'mobile-light');
        expect(fs.existsSync(f)).toBeTruthy();
    });

    test('mobile 390×844, dark theme', async ({ page }) => {
        await page.setViewportSize({ width: 390, height: 844 });
        await page.emulateMedia({ colorScheme: 'dark' });
        await gotoAndSettle(page);
        const f = await shoot(page, 'mobile-dark');
        expect(fs.existsSync(f)).toBeTruthy();
    });

    test('after clicking an option, the answer reveal renders', async ({ page }) => {
        await page.setViewportSize({ width: 1280, height: 800 });
        await page.emulateMedia({ colorScheme: 'light' });
        await gotoAndSettle(page);
        // Click the first non-empty option (A/B/C/D).
        const firstOpt = page.locator('[data-testid^="option-"]').first();
        await firstOpt.waitFor({ state: 'visible', timeout: 10000 });
        await firstOpt.click();
        // The "Why the correct answer is right" panel should appear.
        await expect(page.locator('[data-testid^="expl-"]')).toBeVisible({ timeout: 5000 });
        const f = await shoot(page, 'answer-reveal');
        expect(fs.existsSync(f)).toBeTruthy();
    });
});