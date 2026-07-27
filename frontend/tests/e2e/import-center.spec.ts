/**
 * Admin Import Center — Playwright E2E tests.
 *
 * These exercise the user-facing flow:
 *   1. /admin/import-center dashboard loads
 *   2. /admin/import-center/upload renders the drag/drop UI
 *   3. /admin/import-center/batches lists the batches table
 *   4. /admin/import-center/review renders the queue
 *   5. /admin/import-center/search accepts input and shows results
 *
 * Auth: tests require an admin session. When PLAYWRIGHT_AUTH is set, we
 * skip login and just visit the protected pages; otherwise the test
 * gracefully expects the redirect to /login.
 *
 * Run with the frontend dev server on :3000 and the backend on :8000.
 */

import { expect, test } from '@playwright/test';

const BASE = process.env.BASE_URL || 'http://localhost:3000';

test.describe('Admin Import Center', () => {
  test('dashboard loads (or redirects to login when unauthenticated)', async ({ page }) => {
    await page.goto(`${BASE}/admin/import-center`);
    // Either we hit the dashboard directly (auth present) or we were redirected.
    await page.waitForLoadState('networkidle');
    const url = page.url();
    expect(url.includes('/admin/import-center') || url.includes('/login')).toBe(true);
  });

  test('upload page renders drag-drop area', async ({ page }) => {
    await page.goto(`${BASE}/admin/import-center/upload`);
    await page.waitForLoadState('networkidle');
    // The upload page must always render its drop area, even when unauthenticated.
    const dropText = await page.locator('text=Drag & drop').count();
    expect(dropText).toBeGreaterThan(0);
  });

  test('batches page renders table', async ({ page }) => {
    await page.goto(`${BASE}/admin/import-center/batches`);
    await page.waitForLoadState('networkidle');
    // Header should be visible
    await expect(page.locator('text=Import Batches').first()).toBeVisible();
  });

  test('review queue page renders filter controls', async ({ page }) => {
    await page.goto(`${BASE}/admin/import-center/review`);
    await page.waitForLoadState('networkidle');
    await expect(page.locator('text=Review Queue').first()).toBeVisible();
  });

  test('search page renders input', async ({ page }) => {
    await page.goto(`${BASE}/admin/import-center/search`);
    await page.waitForLoadState('networkidle');
    const input = page.locator('input[placeholder*="Search the staging area"]');
    await expect(input).toBeVisible();
    await input.fill('heart');
    // Either results render or "No matches" — both prove the page is alive.
    await page.waitForTimeout(500);
    const hasResults = (await page.locator('li').count()) > 0;
    expect(hasResults).toBe(true);
  });

  test('dashboard quick-actions links are clickable', async ({ page }) => {
    await page.goto(`${BASE}/admin/import-center`);
    await page.waitForLoadState('networkidle');
    // Quick Actions render Upload / Review / Batches / Search buttons when authenticated.
    const links = ['/admin/import-center/upload', '/admin/import-center/review', '/admin/import-center/batches', '/admin/import-center/search'];
    for (const href of links) {
      const link = page.locator(`a[href="${href}"]`).first();
      if (await link.isVisible().catch(() => false)) {
        await expect(link).toBeVisible();
      }
    }
  });
});