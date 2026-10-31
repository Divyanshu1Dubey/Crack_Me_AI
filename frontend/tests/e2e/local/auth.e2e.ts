/**
 * Authentication (local mode): register, login, logout, bad credentials,
 * protected-route redirect. Runs on every viewport project.
 */
import { expect, test } from '@playwright/test';
import { apiRegister, expectNoHorizontalOverflow, prepareBrowser, SEED, seedPassword, snap, watchPage } from './support';

test.describe('auth', () => {
    test('home page renders cleanly for visitors', async ({ page }, testInfo) => {
        await prepareBrowser(page, null);
        const watch = watchPage(page);
        await page.goto('/');
        await expect(page.locator('body')).toContainText(/CMS|NEET|exam/i);
        await expectNoHorizontalOverflow(page);
        await snap(page, testInfo, 'home');
        watch.expectClean();
    });

    test('student logs in through the form and lands on the dashboard', async ({ page }, testInfo) => {
        await prepareBrowser(page, null);
        const watch = watchPage(page);
        await page.goto('/login');
        await page.locator('input[name="identifier"]').fill(SEED.student);
        await page.locator('input[name="password"]').fill(seedPassword());
        await page.locator('button[type="submit"]').click();
        await page.waitForURL(/\/dashboard/, { timeout: 60_000 });
        await expect(page.locator('main, body').first()).toContainText(/dashboard|welcome|today|streak/i);
        await expectNoHorizontalOverflow(page);
        await snap(page, testInfo, 'dashboard-after-login');
        watch.expectClean();
    });

    test('wrong password shows an error and stays on login', async ({ page }) => {
        await prepareBrowser(page, null);
        await page.goto('/login');
        await page.locator('input[name="identifier"]').fill(SEED.student);
        await page.locator('input[name="password"]').fill('definitely-not-the-password');
        await page.locator('button[type="submit"]').click();
        await expect(page.getByText(/invalid|incorrect|wrong|failed/i).first()).toBeVisible();
        await expect(page).toHaveURL(/\/login/);
    });

    test('new student registers through the form', async ({ page }, testInfo) => {
        await prepareBrowser(page, null);
        const watch = watchPage(page);
        const stamp = `${Date.now().toString(36)}${testInfo.project.name}`;
        const password = `E2e!${stamp}Pw9`;
        await page.goto('/register');
        await page.locator('input[name="first_name"]').fill('E2E');
        await page.locator('input[name="last_name"]').fill('Register');
        await page.locator('input[name="username"]').fill(`reg_${stamp}`);
        await page.locator('input[name="email"]').fill(`reg-${stamp}@local.test`);
        await page.locator('input[name="password"]').fill(password);
        await page.locator('input[name="password2"]').fill(password);
        await page.locator('button[type="submit"]').click();
        await page.waitForURL(/\/dashboard/, { timeout: 60_000 });
        await snap(page, testInfo, 'dashboard-after-register');
        watch.expectClean();
    });

    test('logged-out visitors are sent to login from protected pages', async ({ page }) => {
        await prepareBrowser(page, null);
        await page.goto('/mistake-notebook');
        await page.waitForURL(/\/login/, { timeout: 30_000 });
    });

    test('logout clears the session', async ({ page, request }) => {
        const session = await apiRegister(request, 'logout');
        await prepareBrowser(page, session);
        await page.goto('/dashboard');
        await expect(page).toHaveURL(/\/dashboard/);
        const stored = await page.evaluate(() => localStorage.getItem('crack_local_access'));
        expect(stored).toBeTruthy();
        // Sign out sits at the bottom of the sidebar; on phones the sidebar
        // is a drawer behind the floating "Open menu" button.
        const openMenu = page.getByRole('button', { name: 'Open menu' });
        if (await openMenu.isVisible().catch(() => false)) await openMenu.click();
        await page.getByRole('complementary', { name: 'Primary sidebar navigation' })
            .getByRole('button', { name: /sign ?out/i }).click();
        await expect.poll(() => page.evaluate(() => localStorage.getItem('crack_local_access'))).toBeNull();
        await page.goto('/dashboard');
        await page.waitForURL(/\/login/);
    });
});
