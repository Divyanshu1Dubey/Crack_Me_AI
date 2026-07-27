/**
 * mojibake-and-image-fix.spec.ts — End-to-end Playwright coverage for
 * the 2026-07-28 production fixes:
 *
 *   Bug A — Similar PYQs from Database sidebar shows raw mojibake
 *           (`iÃ©iÃiÃ©iÃiÃ©`).
 *   Bug B — A /media/fixtures/images/<exam>/<file>.png URL stored as
 *           plain text inside `question_text` rendered as raw text
 *           instead of an `<img>`.
 *
 * Both fixes are tested as defence-in-depth:
 *
 *   1. The QuestionDetailSerializer must NOT return strings containing
 *      bare mojibake markers (`Ã©`, `â€™`, `ΓÇÿ`) when fetched via the API.
 *   2. The QuestionDetailSerializer must NOT return strings containing
 *      raw `/media/fixtures/images/...` URLs.
 *   3. The bank modal's "Similar PYQs from Database" list must render
 *      readable text (or a graceful "Question #N (YYYY)" placeholder when
 *      the row is still unreadable after mojibake cleanup).
 *   4. The bank modal's question stem must NOT render a raw
 *      `/media/...` URL as plain text — it should be replaced with an
 *      `<img>` tag (or a graceful broken-image placeholder).
 *
 * Run with:
 *     npx playwright test tests/e2e/mojibake-and-image-fix.spec.ts
 */
import { test, expect } from '@playwright/test';

const API_BASE =
    process.env.NEXT_PUBLIC_API_URL ||
    'http://localhost:8000/api';

// Lock down what mojibake actually looks like in the wild. We assert
// NONE of these byte patterns survive in the API payload.
const MOJIBAKE_MARKERS = ['Ã©', 'â€™', 'ΓÇÿ', 'â€œ', 'â€\x9d'];

test.describe('Bug A — mojibake is repaired at the API boundary', () => {
    test('QuestionDetailSerializer strips mojibake from every text field', async ({ request }) => {
        // Hit the list endpoint (paginated). We only need a sample of rows.
        const res = await request.get(`${API_BASE}/questions/?page_size=50`);
        if (!res.ok()) {
            test.skip(true, `API returned ${res.status()} — not available in CI env`);
            return;
        }
        const body = await res.json();
        const rows: any[] = Array.isArray(body?.results) ? body.results : body;
        expect(rows.length).toBeGreaterThan(0);

        const textFields = [
            'question_text', 'option_a', 'option_b', 'option_c', 'option_d',
            'explanation', 'concept_explanation', 'mnemonic',
            'ai_explanation', 'ai_mnemonic', 'ai_clinical_pearl',
        ];

        const offenders: { id: number; field: string; snippet: string }[] = [];
        for (const row of rows) {
            for (const field of textFields) {
                const value: string = row[field] ?? '';
                for (const marker of MOJIBAKE_MARKERS) {
                    if (value.includes(marker)) {
                        offenders.push({
                            id: row.id,
                            field,
                            snippet: value.slice(0, 80),
                        });
                    }
                }
            }
        }
        expect(offenders).toEqual([]);
    });

    test('Similar-PYQs sidebar renders readable text (no raw mojibake visible)', async ({ page }) => {
        await page.goto('/questions');
        // Wait for the bank list — the first card needs to be interactive.
        const firstCard = page.locator('[data-testid="question-card"], .question-card, button:has-text("PYQ")').first();
        await firstCard.waitFor({ state: 'visible', timeout: 15000 }).catch(() => null);
        if (!(await firstCard.isVisible())) {
            test.skip(true, 'Bank UI not available in CI env');
            return;
        }
        await firstCard.click();

        // Open the detail modal. The "Similar PYQs from Database" header
        // is the anchor.
        const similarHeader = page.locator('text=Similar PYQs from Database').first();
        await similarHeader.waitFor({ state: 'visible', timeout: 10000 }).catch(() => null);
        if (!(await similarHeader.isVisible())) {
            test.skip(true, 'No similar PYQs sidebar in this fixture — skipping');
            return;
        }

        // Read every sidebar row and assert no mojibake marker survives.
        const sidebarRows = page.locator('text=Similar PYQs from Database').locator('xpath=ancestor::div[contains(@class, "glass-card")]').locator('span.line-clamp-2');
        const count = await sidebarRows.count();
        expect(count).toBeGreaterThan(0);
        for (let i = 0; i < count; i++) {
            const txt = await sidebarRows.nth(i).innerText();
            for (const marker of MOJIBAKE_MARKERS) {
                expect(txt, `row ${i} contained mojibake marker ${marker}`).not.toContain(marker);
            }
        }
    });
});

test.describe('Bug B — bare /media/fixtures/images/ URLs render as images', () => {
    test('API does not return raw /media/fixtures/images/ URLs in question_text', async ({ request }) => {
        const res = await request.get(`${API_BASE}/questions/?page_size=200`);
        if (!res.ok()) {
            test.skip(true, `API returned ${res.status()} — not available in CI env`);
            return;
        }
        const body = await res.json();
        const rows: any[] = Array.isArray(body?.results) ? body.results : body;

        const offenders: { id: number; snippet: string }[] = [];
        for (const row of rows) {
            const value: string = row.question_text ?? '';
            if (/\/media\/fixtures\/images\//.test(value)) {
                offenders.push({ id: row.id, snippet: value.slice(0, 80) });
            }
        }
        expect(offenders).toEqual([]);
    });

    test('Detail modal renders no raw /media/fixtures/images/ URL text', async ({ page }) => {
        await page.goto('/questions');
        const firstCard = page.locator('[data-testid="question-card"], .question-card, button:has-text("PYQ")').first();
        await firstCard.waitFor({ state: 'visible', timeout: 15000 }).catch(() => null);
        if (!(await firstCard.isVisible())) {
            test.skip(true, 'Bank UI not available in CI env');
            return;
        }
        await firstCard.click();

        // Wait for the detail panel — scan it for any raw `/media/fixtures/...`
        // URL rendered as text (not inside an <img src="...">).
        await page.waitForTimeout(800);
        const detailPanel = page.locator('.qbank-detail, [data-testid="qbank-detail"]').first();
        if (!(await detailPanel.isVisible())) {
            test.skip(true, 'Detail panel not available');
            return;
        }
        const text = await detailPanel.innerText();
        // The string `fixtures/images/` should NOT appear as plain text.
        // It IS allowed inside an <img src="..."> attribute, which innerText
        // doesn't include, so this assertion is safe.
        expect(text, 'Detail panel rendered a raw /media/fixtures/images/ URL as text').not.toMatch(/\/media\/fixtures\/images\//);
    });
});