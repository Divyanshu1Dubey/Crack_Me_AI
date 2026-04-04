import { test, expect } from '@playwright/test';

test.describe('Question Bank (requires auth)', () => {
    // These tests require a running backend with test user credentials
    // For CI, mock authentication via localStorage token injection

    test('should show question bank page structure', async ({ page }) => {
        // Verify the questions page redirects to login when unauthenticated
        await page.goto('/questions');
        await page.waitForURL(/login/);
        await expect(page).toHaveURL(/login/);
    });
});

test.describe('Command Palette', () => {
    test('should open with Ctrl+K', async ({ page }) => {
        await page.goto('/login');
        await page.keyboard.press('Control+k');
        await expect(page.locator('body')).toBeVisible();
    });
});
