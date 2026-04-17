import { test, expect } from '@playwright/test';

test.describe('Login Flow', () => {
    test('should show login page', async ({ page }) => {
        await page.goto('/login');
        await expect(page.locator('h2')).toContainText(/sign in|login|welcome|resume/i);
        await expect(page.locator('input[name="identifier"], input[type="email"]')).toBeVisible();
        await expect(page.locator('input[type="password"]')).toBeVisible();
        await expect(page.locator('button[type="submit"]')).toBeVisible();
    });

    test('should show registration link', async ({ page }) => {
        await page.goto('/login');
        const registerLink = page.locator('a[href="/register"]');
        await expect(registerLink).toBeVisible();
    });

    test('should show forgot password link', async ({ page }) => {
        await page.goto('/login');
        const forgotLink = page.locator('a[href="/forgot-password"]');
        await expect(forgotLink).toBeVisible();
    });

    test('should show error on invalid login', async ({ page }) => {
        await page.goto('/login');
        await page.fill('input[name="identifier"], input[type="email"]', 'invalid_user@example.com');
        await page.fill('input[type="password"]', 'wrong_password');
        await page.click('button[type="submit"]');
        await expect(
            page.locator('.text-destructive').filter({ hasText: /invalid|incorrect|credential|failed|error|unable to reach/i }).first()
        ).toBeVisible({ timeout: 15000 });
    });
});

test.describe('Registration Page', () => {
    test('should show register form', async ({ page }) => {
        await page.goto('/register');
        await expect(page.locator('h2')).toContainText(/create.*account|register|sign up|join/i);
        await expect(page.locator('input[name="username"]')).toBeVisible();
        await expect(page.locator('input[name="email"], input[type="email"]')).toBeVisible();
        await expect(page.locator('input[name="password"]')).toBeVisible();
    });

    test('should show password strength indicator', async ({ page }) => {
        await page.goto('/register');
        const passwordInput = page.locator('input[name="password"]');
        await passwordInput.fill('weak');
        // Password strength component should appear
        await expect(page.locator('p').filter({ hasText: /^Weak$|^Fair$|^Strong$/ }).first()).toBeVisible();
    });
});

test.describe('Public Pages', () => {
    test('should redirect unauthenticated users to login', async ({ page }) => {
        await page.goto('/dashboard');
        await page.waitForURL(/login/);
        await expect(page).toHaveURL(/login/);
    });

    test('should load forgot password page', async ({ page }) => {
        await page.goto('/forgot-password');
        await expect(page.locator('h2')).toContainText(/forgot|reset|regain/i);
        await expect(page.locator('input[name="email"], input[type="email"]')).toBeVisible();
    });
});
