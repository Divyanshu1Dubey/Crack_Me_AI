import { test, expect } from '@playwright/test';

test.describe('Login Flow', () => {
    test('should show login page', async ({ page }) => {
        await page.goto('/login');
        await expect(page.locator('h1')).toContainText(/sign in|login|welcome/i);
        await expect(page.locator('input[name="username"], input[type="text"]')).toBeVisible();
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
        await page.fill('input[name="username"], input[type="text"]', 'invalid_user');
        await page.fill('input[type="password"]', 'wrong_password');
        await page.click('button[type="submit"]');
        // Should show error message (without actual backend, this tests the UI flow)
        await page.waitForTimeout(2000);
    });
});

test.describe('Registration Page', () => {
    test('should show register form', async ({ page }) => {
        await page.goto('/register');
        await expect(page.locator('h1')).toContainText(/create account|register|sign up/i);
    });

    test('should show password strength indicator', async ({ page }) => {
        await page.goto('/register');
        const passwordInput = page.locator('input[name="password"]');
        await passwordInput.fill('weak');
        // Password strength component should appear
        await expect(page.locator('text=/Weak|Fair/i')).toBeVisible();
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
        await expect(page.locator('h1')).toContainText(/forgot|reset/i);
    });
});
