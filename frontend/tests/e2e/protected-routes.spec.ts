import { test, expect } from '@playwright/test';

const NAVIGATION_TIMEOUT_MS = 60000;
const PROTECTED_ROUTES = ['/dashboard', '/questions', '/tests'];

test.describe('Protected Routes', () => {
  for (const route of PROTECTED_ROUTES) {
    test(`redirects unauthenticated user from ${route} to login`, async ({ page }) => {
      await page.goto(route, { waitUntil: 'domcontentloaded', timeout: NAVIGATION_TIMEOUT_MS });

      await page.waitForURL(/login/, { timeout: NAVIGATION_TIMEOUT_MS });
      await expect(page).toHaveURL(/login/);
      await expect(page.getByRole('button', { name: /sign in/i })).toBeVisible();
    });
  }

  test('redirects unauthenticated users from admin to login', async ({ page }) => {
    await page.goto('/admin', { waitUntil: 'domcontentloaded', timeout: NAVIGATION_TIMEOUT_MS });

    await page.waitForURL(/login/, { timeout: NAVIGATION_TIMEOUT_MS });
    await expect(page).toHaveURL(/login/);
    await expect(page.getByRole('button', { name: /sign in/i })).toBeVisible();
  });
});
