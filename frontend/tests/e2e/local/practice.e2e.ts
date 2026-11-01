/**
 * Question bank: premium practice (answer -> key + explanation), the wrong
 * answer feeding the Mistake Notebook and Study Time, the free-tier lock,
 * and bookmarks. UI actions are checked against backend state.
 */
import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import { api, apiLogin, apiRegister, expectNoHorizontalOverflow, isProject, prepareBrowser, rowsOf, SEED, snap, watchPage, type Session } from './support';

type Row = Record<string, any>;

async function cmsQuestions(request: APIRequestContext, session: Session, extra = ''): Promise<Row[]> {
    const res = await api(request, session, 'GET', `/questions/?exam_type=cms&page_size=100${extra}`);
    expect(res.status, 'CMS question list').toBe(200);
    return rowsOf<Row>(res.body);
}

/** An unanswered, entitled question whose answer key the premium user may read. */
async function freshKeyedQuestion(request: APIRequestContext, session: Session, skip: number[] = []) {
    for (const q of await cmsQuestions(request, session)) {
        if (q.user_selected_answer || skip.includes(q.id)) continue;
        const detail = await api(request, session, 'GET', `/questions/${q.id}/`);
        const key = String(detail.body?.correct_answer || '').trim().toUpperCase();
        if (detail.status === 200 && /^[A-D]$/.test(key) && detail.body?.[`option_${key.toLowerCase()}`]) {
            return { id: q.id as number, key, detail: detail.body as Row };
        }
    }
    throw new Error('no unanswered CMS question with an answer key for the premium user');
}

/**
 * A forgiving matcher for a question stem as the UI renders it: five
 * consecutive words (every word, short ones too, so nothing is skipped
 * between them), after the first word (the UI strips "Q.12"-style labels);
 * image tokens and markdown are ignored and numbers / punctuation between
 * the words may differ.
 */
function stemMatcher(text: string): RegExp {
    const words = String(text || '')
        .replace(/\[\[[^\]]*\]\]|<[^>]+>|!?\[[^\]]*\]\([^)]*\)|[*_`#>|]/g, ' ')
        .split(/[^A-Za-z]+/)
        .filter(Boolean);
    const pick = words.length > 7 ? words.slice(1, 6) : words.slice(0, 5);
    return new RegExp(pick.join('[^A-Za-z]+'), 'i');
}

/** The option cards of the open question (letter badge first, then text). */
const optionCard = (page: Page, letter: string) =>
    page.locator('.qbank-detail div.cursor-pointer').filter({ hasText: new RegExp(`^\\s*${letter}`) }).first();

test.describe('question bank practice', () => {
    test('premium student answers correctly and sees the key and explanation', async ({ page, request }, testInfo) => {
        const session = await apiLogin(request, SEED.premium);
        const q = await freshKeyedQuestion(request, session);
        await prepareBrowser(page, session);
        const watch = watchPage(page);
        await page.goto(`/questions?q=${q.id}`);
        await expect(page.getByText(/Select an option to reveal the answer/i)).toBeVisible({ timeout: 60_000 });
        await expectNoHorizontalOverflow(page);
        await optionCard(page, q.key).click();
        await expect(page.getByText(new RegExp(`Correct Answer:\\s*${q.key}`))).toBeVisible();
        await expect(page.getByText(/✓ Correct/).first()).toBeVisible();
        await snap(page, testInfo, 'question-answered-correct');

        // Backend state: the attempt is stored with the chosen option.
        await expect.poll(async () => (await api(request, session, 'GET', `/questions/${q.id}/`)).body?.user_selected_answer).toBe(q.key);
        watch.expectClean();
    });

    test('a wrong answer lands in the Mistake Notebook and adds study time', async ({ page, request }, testInfo) => {
        test.skip(!isProject(testInfo, 'desktop'), 'state-changing flow runs once (desktop)');
        const session = await apiLogin(request, SEED.premium);
        const q = await freshKeyedQuestion(request, session);
        const wrong = ['A', 'B', 'C', 'D'].find(l => l !== q.key && q.detail[`option_${l.toLowerCase()}`]) as string;
        const today = new Date().toISOString().slice(0, 10);
        const secondsBefore = await studySeconds(request, session, today);

        await prepareBrowser(page, session);
        const watch = watchPage(page);
        await page.goto(`/questions?q=${q.id}`);
        await expect(page.getByText(/Select an option to reveal the answer/i)).toBeVisible({ timeout: 60_000 });
        // Spend a few seconds on the question so the attempt carries time.
        await page.waitForTimeout(3_000);
        await optionCard(page, wrong).click();
        await expect(page.getByText(new RegExp(`Correct Answer:\\s*${q.key}`))).toBeVisible();
        await expect(page.getByText(/✗ Wrong/).first()).toBeVisible();

        await expect.poll(async () => {
            const nb = await api(request, session, 'GET', '/analytics/mistake-notebook/?page_size=100');
            return rowsOf<Row>(nb.body).some(r => r.question === q.id);
        }, { message: 'mistake notebook entry for the wrong answer' }).toBe(true);
        await expect.poll(() => studySeconds(request, session, today), { message: 'study time grows' }).toBeGreaterThan(secondsBefore);

        await page.goto('/mistake-notebook');
        await expect(page.getByRole('heading', { name: /mistake notebook/i }).first()).toBeVisible();
        await expect(page.getByText(stemMatcher(q.detail.question_text)).first()).toBeVisible({ timeout: 30_000 });
        await expectNoHorizontalOverflow(page);
        await snap(page, testInfo, 'mistake-notebook');

        await page.goto('/study-time');
        await expect(page.getByRole('heading', { name: /study time/i }).first()).toBeVisible();
        await expectNoHorizontalOverflow(page);
        await snap(page, testInfo, 'study-time');
        watch.expectClean();
    });

    test('free student sees premium questions locked, server refuses the key', async ({ page, request }, testInfo) => {
        const session = await apiRegister(request, 'free');
        const rows = await cmsQuestions(request, session);
        const locked = rows.find(r => r.is_showcase === false);
        expect(locked, 'a non-showcase question in the first page').toBeTruthy();
        const detail = await api(request, session, 'GET', `/questions/${locked!.id}/`);
        // The free-tier gate answers 404 for the detail (it does not confirm the
        // question exists) and 402 upgrade_required for attempts.
        expect([402, 403, 404], `detail status for a locked question (got ${detail.status})`).toContain(detail.status);
        const attempt = await api(request, session, 'POST', `/questions/${locked!.id}/attempt/`, { selected_answer: 'A' });
        expect(attempt.status, 'attempt on a locked question').toBe(402);
        expect(JSON.stringify(attempt.body || {})).not.toMatch(/"correct_answer":"[A-D]"/);
        expect(JSON.stringify(detail.body || {})).not.toMatch(/"correct_answer":"[A-D]"/);

        await prepareBrowser(page, session);
        const watch = watchPage(page);
        await page.goto('/questions');
        // Free users get the questions they can open first (the showcase), so
        // locked cards start a few pages in: page forward until one shows.
        const lockedCard = page.locator('div.cursor-pointer', { hasText: 'Premium Question' }).first();
        await expect(page.getByRole('button', { name: /^(Add|Remove) bookmark for question/ }).first()).toBeVisible({ timeout: 60_000 });
        for (let i = 0; i < 8 && !(await lockedCard.isVisible().catch(() => false)); i++) {
            const next = page.getByRole('button', { name: 'Next page' });
            if (!(await next.isEnabled().catch(() => false))) break;
            await next.click();
            await page.waitForTimeout(1_500);
        }
        await expect(lockedCard).toBeVisible({ timeout: 30_000 });
        await expectNoHorizontalOverflow(page);
        await snap(page, testInfo, 'question-bank-free');
        await lockedCard.click();
        await expect(page.getByRole('dialog').getByText(/unlock/i).first()).toBeVisible();
        await snap(page, testInfo, 'paywall-dialog');
        // A 402/403 from the server is the expected product response here.
        watch.expectClean([/status of 40[23]/i]);
    });

    test('bookmark a question and find it on the bookmarks page', async ({ page, request }, testInfo) => {
        test.skip(!isProject(testInfo, 'desktop'), 'state-changing flow runs once (desktop)');
        const session = await apiRegister(request, 'bookmark');
        // Showcase questions are open to free users.
        const rows = await cmsQuestions(request, session);
        const open = rows.find(r => r.is_showcase === true) ?? rows[0];
        await prepareBrowser(page, session);
        const watch = watchPage(page);
        await page.goto('/questions');
        const button = page.getByRole('button', { name: `Add bookmark for question ${open.id}` });
        if (!(await button.isVisible().catch(() => false))) {
            // Not on the first screen: bookmark through the API instead and still check the page.
            expect((await api(request, session, 'POST', `/questions/${open.id}/bookmark/`)).status).toBeLessThan(300);
        } else {
            await button.click();
            await expect(page.getByRole('button', { name: `Remove bookmark for question ${open.id}` })).toBeVisible();
        }
        await expect.poll(async () => {
            const b = await api(request, session, 'GET', '/questions/bookmarks/');
            return JSON.stringify(b.body || '').includes(`"id":${open.id}`) || JSON.stringify(b.body || '').includes(`"question":${open.id}`);
        }, { message: 'bookmark stored' }).toBe(true);
        await page.goto('/bookmarks');
        await expect(page.getByText(stemMatcher(open.question_text)).first()).toBeVisible({ timeout: 30_000 });
        await expect(page.getByText('No bookmarks yet')).toHaveCount(0);
        await expectNoHorizontalOverflow(page);
        await snap(page, testInfo, 'bookmarks');
        watch.expectClean();
    });
});

async function studySeconds(request: APIRequestContext, session: Session, day: string): Promise<number> {
    const res = await api(request, session, 'GET', `/analytics/study-time/?start=${day}&end=${day}`);
    if (res.status !== 200) return 0;
    return rowsOf<Row>(res.body?.breakdown ?? []).reduce((sum, r) => sum + Number(r.seconds || 0), 0);
}
