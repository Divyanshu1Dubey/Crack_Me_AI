/**
 * Admin console and authorization: the admin reaches the console pages,
 * students are bounced, and the admin APIs refuse non-admins.
 */
import { expect, test } from '@playwright/test';
import { api, apiLogin, apiRegister, expectNoHorizontalOverflow, prepareBrowser, SEED, snap, watchPage } from './support';

const ADMIN_PAGES: Array<{ path: string; text: RegExp }> = [
    { path: '/admin', text: /admin dashboard/i },
    { path: '/admin/questions-editor', text: /question/i },
    { path: '/admin/import-center', text: /import/i },
    { path: '/admin/ingestion', text: /ingestion|import|batch/i },
    { path: '/admin/announcements', text: /announcement/i },
    { path: '/admin/recall', text: /recall/i },
];

test.describe('admin', () => {
    for (const { path, text } of ADMIN_PAGES) {
        test(`admin opens ${path}`, async ({ page, request }, testInfo) => {
            const session = await apiLogin(request, SEED.admin);
            expect(session.isAdmin, 'seeded admin is an admin').toBe(true);
            await prepareBrowser(page, session);
            const watch = watchPage(page);
            await page.goto(path);
            await expect(page).toHaveURL(new RegExp(`${path.replace(/\//g, '\\/')}(\\?|$)`));
            await expect(page.locator('main, body').first()).toContainText(text, { timeout: 60_000 });
            await expectNoHorizontalOverflow(page);
            await snap(page, testInfo, `admin${path.replace(/\//g, '-')}`);
            watch.expectClean();
        });
    }

    test('a student is sent away from /admin', async ({ page, request }) => {
        const session = await apiLogin(request, SEED.student);
        await prepareBrowser(page, session);
        await page.goto('/admin');
        await page.waitForURL(url => !url.pathname.startsWith('/admin'), { timeout: 30_000 });
        await expect(page.getByText(/admin dashboard/i)).toHaveCount(0);
    });

    test('admin APIs refuse students and anonymous callers', async ({ request }) => {
        const student = await apiRegister(request, 'notadmin');
        const admin = await apiLogin(request, SEED.admin);
        const endpoints = ['/auth/admin/users/', '/auth/tokens/admin/users/', '/auth/tokens/admin/audit-logs/'];
        for (const ep of endpoints) {
            expect((await api(request, admin, 'GET', ep)).status, `admin GET ${ep}`).toBe(200);
            expect((await api(request, student, 'GET', ep)).status, `student GET ${ep}`).toBe(403);
            expect([401, 403], `anonymous GET ${ep}`).toContain((await api(request, null, 'GET', ep)).status);
        }
        // Destructive system actions are refused for students (the admin-side
        // typed-confirm rule is covered by backend unit tests; probing it here
        // would risk wiping the working database if it ever regressed).
        expect((await api(request, student, 'POST', '/auth/admin/system/clear-analytics/', { scope: 'all', confirm: 'RESET ALL' })).status).toBe(403);
        // Students cannot grant themselves tokens.
        expect((await api(request, student, 'POST', '/auth/tokens/admin/grant/', { user_id: 1, amount: 100 })).status).toBe(403);
    });
});
