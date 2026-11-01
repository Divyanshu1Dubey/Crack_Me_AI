/**
 * AI tutor in offline mode (AI_OFFLINE_MODE=1 on the local stack): the
 * answer is an extract from the indexed textbooks with citations, made
 * without any model call, and it is not charged.
 */
import { expect, test } from '@playwright/test';
import { api, apiLogin, apiRegister, expectNoHorizontalOverflow, prepareBrowser, profile, SEED, snap, watchPage } from './support';

test.describe('AI tutor (offline)', () => {
    test('premium student gets a cited offline answer', async ({ page, request }, testInfo) => {
        const session = await apiLogin(request, SEED.premium);
        await prepareBrowser(page, session);
        const watch = watchPage(page);
        await page.goto('/ai-tutor');
        const box = page.getByRole('textbox', { name: 'Message the AI tutor' });
        await expect(box).toBeVisible({ timeout: 60_000 });
        await expectNoHorizontalOverflow(page);
        await box.fill('What is the drug of choice for anaphylaxis and the dose of adrenaline?');
        await page.getByRole('button', { name: 'Send message' }).click();
        await expect(page.getByText(/Offline answer/i).first()).toBeVisible({ timeout: 90_000 });
        await expect(page.getByText(/Textbook References/i).first()).toBeVisible();
        await expect(page.locator('.ai-response').last()).not.toBeEmpty();
        // Retrieval quality, not plumbing: reported, does not fail the flow.
        await expect.soft(page.locator('.ai-response').last()).toContainText(/adrenaline|epinephrine/i);
        await snap(page, testInfo, 'ai-tutor-offline');
        watch.expectClean();
    });

    test('free student: offline answers do not use up the daily tutor allowance', async ({ request }) => {
        const session = await apiRegister(request, 'ai-free');
        const before = await profile(request, session);
        for (const question of ['What is the drug of choice for anaphylaxis?', 'Classify antihypertensive drugs with one example each.']) {
            const res = await api(request, session, 'POST', '/ai/tutor/', { question });
            // Contract: a grounded offline extract (200, offline: true, charged: false)
            // or 503 {code: 'ai_unavailable'} when nothing in the library matches.
            if (res.status === 200) {
                expect(res.body?.offline).toBe(true);
                expect(res.body?.charged).toBe(false);
                expect(JSON.stringify(res.body)).not.toMatch(/temporarily unavailable|provider error|traceback/i);
            } else {
                expect(res.status, JSON.stringify(res.body)).toBe(503);
                expect(res.body?.code).toBe('ai_unavailable');
                expect(String(res.body?.message || res.body?.error || '')).toMatch(/not charged/i);
            }
        }
        const after = await profile(request, session);
        expect(after.ai_tutor_used_today).toBe(before.ai_tutor_used_today);
    });
});
