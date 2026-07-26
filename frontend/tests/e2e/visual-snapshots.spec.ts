/**
 * tests/e2e/visual-snapshots.spec.ts — free, plugin-free visual regression
 * suite for cracklabs.app.
 *
 * Design
 * ------
 * Uses Playwright's built-in `expect(page).toHaveScreenshot()`, which is
 * shipped with @playwright/test (no extra npm dependency). Baselines live
 * under `tests/e2e/visual-snapshots/<project>/<theme>/<page>.png`. Run
 * `npx playwright test visual-snapshots.spec.ts --update-snapshots` to
 * regenerate baselines.
 *
 * Coverage
 * --------
 * For each public or auth-gated route we test two themes (light + dark).
 * The `chromium-mobile` project (added in playwright.config.ts) runs the
 * same spec at 390x844 DSR 2.
 *
 * Auth-gated routes gracefully skip if QA_TEST_USER_EMAIL / _PASSWORD are
 * not set, mirroring `fixtures/auth.ts` convention.
 *
 * Dynamic-content mitigation
 * --------------------------
 * - We `mask` the primary sidebar's user-avatar / greeting node so
 *   per-user state doesn't trigger false-positive diffs.
 * - We disable animations and hide the caret at the page level.
 * - `fullPage: false` (viewport only) so the snapshot is bounded by
 *   the screen — overlong pages would otherwise have huge diffs.
 */
import { test, expect, type Page } from '@playwright/test';
import { loginAs, ROLES, skipIfAnonymous } from './fixtures/auth';

const PUBLIC_PAGES = ['/', '/login', '/pricing'] as const;
const PRIVATE_PAGES = [
  '/dashboard',
  '/questions',
  '/questions/neet-pg/practice',
  '/questions/inicet/practice',
  '/tests',
  '/analytics',
  '/ai-tutor',
] as const;

const ALL_PAGES = [...PUBLIC_PAGES, ...PRIVATE_PAGES] as const;

type Theme = 'light' | 'dark';

async function setTheme(page: Page, theme: Theme) {
  await page.evaluate((t) => {
    // Mirror what frontend/src/components/ThemeSync.tsx does. We do this
    // directly so the next-themes localStorage roundtrip isn't required.
    const root = document.documentElement;
    root.classList.remove('dark');
    if (t === 'dark') root.classList.add('dark');
    root.setAttribute('data-theme', t);
    try {
      window.localStorage.setItem('crackcms-theme', t);
    } catch {
      /* private-mode / storage-disabled — ignore */
    }
  }, theme);
}

async function stabilizeForSnapshot(page: Page) {
  // Disable CSS animations / transitions so masking by region does not
  // produce intermediate frames.
  await page.addStyleTag({
    content: `
      *, *::before, *::after {
        animation: none !important;
        transition: none !important;
      }
      body { caret-color: transparent !important; }
    `,
  });
}

test.describe('visual snapshots — public pages', () => {
  for (const route of PUBLIC_PAGES) {
    for (const theme of ['light', 'dark'] as const) {
      test(`${theme} ${route}`, async ({ page }) => {
        await page.goto(route, { waitUntil: 'domcontentloaded' });
        await setTheme(page, theme);
        await stabilizeForSnapshot(page);
        await expect(page).toHaveScreenshot(`public/${theme}/${route.replace(/\//g, '_') || '_root'}.png`, {
          maxDiffPixels: 250,
          threshold: 0.2,
        });
      });
    }
  }
});

test.describe('visual snapshots — private pages (skipped without QA creds)', () => {
  for (const route of PRIVATE_PAGES) {
    for (const theme of ['light', 'dark'] as const) {
      test(`${theme} ${route}`, async ({ page }) => {
        const result = await loginAs(page, ROLES.STUDENT);
        if (skipIfAnonymous(result, test)) return;

        await page.goto(route, { waitUntil: 'domcontentloaded' });
        await setTheme(page, theme);
        await stabilizeForSnapshot(page);
        await expect(page).toHaveScreenshot(`private/${theme}/${route.replace(/\//g, '_')}.png`, {
          maxDiffPixels: 250,
          threshold: 0.2,
          // Mask per-user content in the sidebar so the baseline is
          // stable across different student accounts.
          mask: [page.locator('aside[aria-label="Primary sidebar navigation"]')],
        });
      });
    }
  }
});
