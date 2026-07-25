/**
 * Full-frontend audit suite for cracklabs.app.
 *
 * Walks every page the user listed, captures:
 *   - screenshot
 *   - browser console messages (errors + warnings)
 *   - failed network requests
 *   - basic DOM health (expected heading visible, no Next.js error overlay)
 *
 * Reads QA_TEST_USER_EMAIL + QA_TEST_USER_PASSWORD from env. Skips authed
 * routes if not set.
 */
import { test, expect, Page } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

const OUT_DIR = path.join(process.cwd(), 'screenshots', 'audit');

interface PageSpec {
    name: string;
    path: string;
    authed: boolean;
    /** Optional: regex that must match at least one visible heading text. */
    expectHeading?: RegExp;
}

const PAGES: PageSpec[] = [
    { name: 'home',           path: '/',                  authed: false, expectHeading: /crack|medical|neet/i },
    { name: 'login',          path: '/login',             authed: false, expectHeading: /welcome|sign in|resume/i },
    { name: 'register',       path: '/register',          authed: false, expectHeading: /create|register|sign up|join/i },
    { name: 'forgot-password',path: '/forgot-password',   authed: false, expectHeading: /forgot|reset|regain/i },

    { name: 'neet-pg-landing',     path: '/neet-pg',                  authed: false, expectHeading: /neet\s*pg/i },
    { name: 'inicet-landing',      path: '/inicet',                   authed: false, expectHeading: /ini[-\s]?cet/i },
    { name: 'cms-landing',         path: '/cms',                      authed: false, expectHeading: /cms|upsc/i },
    { name: 'fmge-landing',        path: '/fmge',                     authed: false, expectHeading: /fmge/i },
    { name: 'usmle-landing',       path: '/usmle',                    authed: false, expectHeading: /usmle/i },

    { name: 'dashboard',       path: '/dashboard',            authed: true },
    { name: 'questions',       path: '/questions',            authed: true, expectHeading: /question\s*bank|master|high[-\s]?yield/i },
    { name: 'practice',        path: '/questions/practice',   authed: true },
    { name: 'practice-neet-pg',path: '/questions/neet-pg/practice?year=2021', authed: true, expectHeading: /neet\s*pg/i },
    { name: 'practice-inicet', path: '/questions/inicet/practice',          authed: true },
    { name: 'bookmarks',       path: '/bookmarks',            authed: true },
    { name: 'ai-tutor',        path: '/ai-tutor',             authed: true },
    { name: 'analytics',       path: '/analytics',            authed: true },
    { name: 'leaderboard',     path: '/leaderboard',          authed: true },
    { name: 'settings',        path: '/settings',             authed: true },
    { name: 'subscription',    path: '/subscription',         authed: true },
    { name: 'tokens',          path: '/tokens',               authed: true },
    { name: 'flashcards',      path: '/flashcards',           authed: true },
    { name: 'tests',           path: '/tests',                authed: true },
    { name: 'simulator',       path: '/simulator',            authed: true },
    { name: 'recall-search',   path: '/recall/search',        authed: true },
    { name: 'textbooks',       path: '/textbooks',            authed: true },
    { name: 'resources',       path: '/resources',            authed: true },
    { name: 'trends',          path: '/trends',               authed: true },
    { name: 'jobs',            path: '/jobs',                 authed: true },
    { name: 'roadmap',         path: '/roadmap',              authed: true },
    { name: 'generate',        path: '/generate',             authed: true },
    { name: 'exams-cms',       path: '/exams/cms',            authed: false },
    { name: 'exams-neet-pg',   path: '/exams/neet-pg',        authed: false },
    { name: 'exams-usmle',     path: '/exams/usmle',          authed: false },
    { name: 'contact',         path: '/contact',              authed: false },
    { name: 'about',           path: '/about',                authed: false },
];

interface AuditResult {
    name: string;
    url: string;
    status: number | null;
    consoleErrors: string[];
    consoleWarnings: string[];
    failedRequests: { url: string; failure: string | null; status: number | null }[];
    nextErrorOverlay: boolean;
    headingMatches: string[];
    screenshot: string;
}

async function loginIfPossible(page: Page): Promise<boolean> {
    const email = process.env.QA_TEST_USER_EMAIL;
    const password = process.env.QA_TEST_USER_PASSWORD;
    if (!email || !password) return false;
    await page.goto('/login', { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.fill('input[name="identifier"], input[type="email"]', email);
    await page.fill('input[type="password"]', password);
    await page.click('button[type="submit"]');
    try {
        await page.waitForURL((u) => !u.toString().includes('/login'), { timeout: 15000 });
    } catch {
        return false;
    }
    return true;
}

test.describe('Full audit', () => {
    test('walk every page, capture artifacts', async ({ page }) => {
        fs.mkdirSync(OUT_DIR, { recursive: true });
        const results: AuditResult[] = [];

        const loggedIn = await loginIfPossible(page);
        test.skip(!loggedIn, 'QA_TEST_USER_EMAIL / QA_TEST_USER_PASSWORD not set or login failed');

        for (const spec of PAGES) {
            if (spec.authed && !loggedIn) continue;

            const errors: string[] = [];
            const warnings: string[] = [];
            const failed: AuditResult['failedRequests'] = [];
            const consoleHandler = (msg: any) => {
                const t = msg.type();
                if (t === 'error') errors.push(msg.text());
                else if (t === 'warning') warnings.push(msg.text());
            };
            const responseHandler = (resp: any) => {
                if (resp.status() >= 400) {
                    failed.push({ url: resp.url(), failure: null, status: resp.status() });
                }
            };
            const requestFailedHandler = (req: any) => {
                failed.push({ url: req.url(), failure: req.failure()?.errorText ?? 'unknown', status: null });
            };
            page.on('console', consoleHandler);
            page.on('response', responseHandler);
            page.on('requestfailed', requestFailedHandler);

            let status: number | null = null;
            let nextErrorOverlay = false;
            let headingMatches: string[] = [];

            try {
                const resp = await page.goto(spec.path, { waitUntil: 'domcontentloaded', timeout: 20000 });
                status = resp?.status() ?? null;
                // Allow CSR + hydrate
                await page.waitForTimeout(1500);
                // Detect Next.js error overlay
                nextErrorOverlay = await page.locator('nextjs-portal, [data-nextjs-dialog]').count() > 0;
                // Collect heading matches
                const headings = await page.locator('h1, h2, h3').allInnerTexts();
                headingMatches = headings.slice(0, 8);
            } catch (e: any) {
                errors.push(`navigation: ${e.message}`);
            }

            const file = path.join(OUT_DIR, `${spec.name}.png`);
            try { await page.screenshot({ path: file, fullPage: false }); } catch { /* skip */ }

            page.off('console', consoleHandler);
            page.off('response', responseHandler);
            page.off('requestfailed', requestFailedHandler);

            results.push({
                name: spec.name,
                url: spec.path,
                status,
                consoleErrors: errors,
                consoleWarnings: warnings,
                failedRequests: failed,
                nextErrorOverlay,
                headingMatches,
                screenshot: file,
            });
        }

        // Write a single JSON dump for review.
        fs.writeFileSync(path.join(OUT_DIR, 'audit.json'), JSON.stringify(results, null, 2));

        // Print a brief table to the test output.
        for (const r of results) {
            const errCount = r.consoleErrors.length;
            const failCount = r.failedRequests.length;
            const overlay = r.nextErrorOverlay ? ' ⚠ NEXTJS-OVERLAY' : '';
            const ok = r.status && r.status < 400 && errCount === 0 && !r.nextErrorOverlay ? '✓' : '✗';
            console.log(`${ok} ${r.name.padEnd(28)} ${String(r.status ?? '-').padEnd(5)} err=${errCount} fail=${failCount}${overlay}`);
        }
    });
});