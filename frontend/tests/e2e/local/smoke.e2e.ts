/**
 * Responsive smoke over the student app: every page renders inside the app
 * shell without horizontal overflow, console errors or 5xx responses, in
 * light mode on every viewport and in dark mode on desktop and mobile.
 */
import { expect, test } from '@playwright/test';
import { apiLogin, expectNoHorizontalOverflow, isProject, prepareBrowser, SEED, snap, watchPage } from './support';

const PAGES: Array<{ path: string; text: RegExp }> = [
    { path: '/dashboard', text: /dashboard|welcome|streak|today/i },
    { path: '/questions', text: /question|PYQ/i },
    { path: '/tests', text: /test/i },
    { path: '/analytics', text: /analytic|performance|accuracy/i },
    { path: '/flashcards', text: /flashcard/i },
    { path: '/mistake-notebook', text: /mistake notebook/i },
    { path: '/study-time', text: /study time/i },
    { path: '/quests', text: /quest/i },
    { path: '/leaderboard', text: /leaderboard|rank/i },
    { path: '/bookmarks', text: /bookmark/i },
    { path: '/ai-tutor', text: /tutor|ask/i },
    { path: '/subscription', text: /plan|premium|pass/i },
    { path: '/settings', text: /settings|profile|device/i },
    { path: '/tokens', text: /token/i },
    { path: '/roadmap', text: /roadmap|plan/i },
    { path: '/textbooks', text: /textbook|book/i },
    { path: '/topic-notes', text: /note/i },
    { path: '/practice', text: /practice|question/i },
];

const PUBLIC: Array<{ path: string; text: RegExp }> = [
    { path: '/', text: /CMS|NEET|exam/i },
    { path: '/cms', text: /CMS/i },
    { path: '/neet-pg', text: /NEET/i },
    { path: '/ini-cet', text: /INI-?CET/i },
    { path: '/about', text: /about|crack/i },
    { path: '/privacy-policy', text: /privacy/i },
];

test.describe('responsive smoke', () => {
    for (const { path, text } of PAGES) {
        test(`app page ${path}`, async ({ page, request }, testInfo) => {
            const session = await apiLogin(request, SEED.premium);
            const themes: Array<'light' | 'dark'> = isProject(testInfo, 'tablet') ? ['light'] : ['light', 'dark'];
            for (const theme of themes) {
                const fresh = theme === 'light' ? page : await page.context().newPage();
                await prepareBrowser(fresh, session, theme);
                const watch = watchPage(fresh);
                await fresh.goto(path);
                await expect(fresh).toHaveURL(new RegExp(`${path.replace(/\//g, '\\/')}(\\?|$)`));
                await expect(fresh.locator('main, body').first()).toContainText(text, { timeout: 60_000 });
                // Let lazy panels settle before measuring layout.
                await fresh.waitForLoadState('networkidle', { timeout: 30_000 }).catch(() => undefined);
                await expectNoHorizontalOverflow(fresh);
                // The app shell is present (sidebar landmark or the phone menu button).
                await expect(fresh.getByRole('complementary', { name: 'Primary sidebar navigation' })
                    .or(fresh.getByRole('button', { name: 'Open menu' })).first()).toBeAttached();
                await snap(fresh, testInfo, `${path.replace(/\//g, '_') || 'root'}-${theme}`);
                watch.expectClean();
                if (fresh !== page) await fresh.close();
            }
        });
    }

    for (const { path, text } of PUBLIC) {
        test(`public page ${path}`, async ({ page }, testInfo) => {
            await prepareBrowser(page, null);
            const watch = watchPage(page);
            await page.goto(path);
            await expect(page.locator('body')).toContainText(text, { timeout: 60_000 });
            await expectNoHorizontalOverflow(page);
            await snap(page, testInfo, `public${path === '/' ? '-home' : path.replace(/\//g, '-')}`);
            watch.expectClean();
        });
    }
});
