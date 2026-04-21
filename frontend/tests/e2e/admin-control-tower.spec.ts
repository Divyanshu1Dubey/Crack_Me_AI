import { test, expect } from '@playwright/test';

const NAVIGATION_TIMEOUT_MS = 60000;

test.describe('Admin Control Tower Access', () => {
    test('redirects unauthenticated requests for admin dashboard to login', async ({ page }) => {
        await page.goto('/admin', { waitUntil: 'domcontentloaded', timeout: NAVIGATION_TIMEOUT_MS });

        await page.waitForURL(/login/, { timeout: NAVIGATION_TIMEOUT_MS });
        await expect(page).toHaveURL(/login/);
        await expect(page.getByRole('button', { name: /sign in/i })).toBeVisible();
    });
});
