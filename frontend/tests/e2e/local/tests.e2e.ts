/**
 * Mock tests: start a test, answer, submit through the confirm dialog, read
 * the result and the review, and check the stored attempt.
 */
import { expect, test } from '@playwright/test';
import { api, apiLogin, expectNoHorizontalOverflow, isProject, prepareBrowser, rowsOf, SEED, snap, watchPage } from './support';

test.describe('mock tests', () => {
    test('tests list renders', async ({ page, request }, testInfo) => {
        const session = await apiLogin(request, SEED.premium);
        await prepareBrowser(page, session);
        const watch = watchPage(page);
        await page.goto('/tests');
        await expect(page.getByRole('button', { name: /start test/i }).first()).toBeVisible({ timeout: 60_000 });
        await expectNoHorizontalOverflow(page);
        await snap(page, testInfo, 'tests-list');
        watch.expectClean();
    });

    test('premium student takes a test end to end', async ({ page, request }, testInfo) => {
        test.skip(!isProject(testInfo, 'desktop', 'mobile'), 'full attempt runs on desktop and mobile');
        const session = await apiLogin(request, SEED.premium);
        const before = rowsOf(await api(request, session, 'GET', '/tests/attempts/?page_size=100').then(r => r.body)).length;

        await prepareBrowser(page, session);
        const watch = watchPage(page);
        await page.goto('/tests');
        await page.getByRole('button', { name: /start test/i }).first().click();
        await page.waitForURL(/\/tests\/\d+/, { timeout: 60_000 });
        const testId = Number(/\/tests\/(\d+)/.exec(page.url())![1]);

        // A notice about a previous attempt may sit above the player.
        const options = page.locator('div.cursor-pointer.border-2');
        await expect(options.first()).toBeVisible({ timeout: 60_000 });
        await options.first().click();
        await page.getByRole('button', { name: /save & next/i }).click();
        await expect(options.first()).toBeVisible();
        await options.nth(1).click();
        await page.getByRole('button', { name: /save & next/i }).click();
        await snap(page, testInfo, 'test-player');

        await page.getByRole('button', { name: /submit test/i }).click();
        const dialog = page.getByRole('dialog', { name: /submit test/i });
        await expect(dialog).toBeVisible();
        await dialog.getByRole('button', { name: /confirm/i }).click();

        await expect(page.getByRole('button', { name: /review answers/i })).toBeVisible({ timeout: 60_000 });
        await expectNoHorizontalOverflow(page);
        await snap(page, testInfo, 'test-result');
        await page.getByRole('button', { name: /review answers/i }).click();
        await expect(page.getByRole('button', { name: /back to results/i })).toBeVisible();
        await snap(page, testInfo, 'test-review');

        await expect.poll(async () => {
            const attempts = rowsOf<Record<string, any>>((await api(request, session, 'GET', '/tests/attempts/?page_size=100')).body);
            return attempts.length > before && attempts.some(a => (a.test === testId || a.test_id === testId || a.test?.id === testId) && a.is_completed);
        }, { message: 'completed attempt stored for the test' }).toBe(true);
        watch.expectClean();
    });
});
