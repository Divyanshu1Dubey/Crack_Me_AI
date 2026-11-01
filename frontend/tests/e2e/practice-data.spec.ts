/**
 * Unit tests for src/components/question/practiceData.ts — the helpers the
 * practice surfaces use to page through the question list, reveal the real
 * answer after a pick, hide backend template text and normalise the
 * related-topic / textbook-reference payloads.
 *
 * Pure Node: no `page` fixture, so no browser and no web server is needed.
 *   cd frontend
 *   PLAYWRIGHT_SKIP_WEBSERVER=1 npx playwright test tests/e2e/practice-data.spec.ts --project=chromium --reporter=line
 */
import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import {
    answerLetter,
    appendUniqueById,
    collectPages,
    isAiTemplateText,
    isPremiumUser,
    mergeRevealWithDetail,
    normaliseRelatedTopics,
    normaliseTextbookReferences,
    openInQueue,
    placeInQueue,
    readAiField,
    readPage,
    revealFromAttempt,
    revealNeedsDetail,
    upgradeRequiredFeature,
} from '../../src/components/question/practiceData';

type Row = { id: number };

/** Fake DRF list endpoint that ignores page_size and serves `pageSize` rows. */
function fakeList(total: number, pageSize: number) {
    const rows: Row[] = Array.from({ length: total }, (_, i) => ({ id: total - i }));
    const calls: number[] = [];
    const fetchPage = async (page: number) => {
        calls.push(page);
        const start = (page - 1) * pageSize;
        if (start >= total && page > 1) {
            const err = new Error('Invalid page.') as Error & { response?: { status: number } };
            err.response = { status: 404 };
            throw err;
        }
        return {
            count: total,
            next: start + pageSize < total ? `http://api/questions/?page=${page + 1}` : null,
            results: rows.slice(start, start + pageSize),
        };
    };
    return { fetchPage, calls };
}

test.describe('collectPages (exam-mode palette, EQB-01)', () => {
    test('follows next links when the server ignores page_size=100 and sends 20 rows', async () => {
        const api = fakeList(200, 20);
        const out = await collectPages<Row>(api.fetchPage, { maxItems: 600, maxPages: 30 });
        // The old loop stopped after page 1 because 20 < 100.
        expect(out.items).toHaveLength(200);
        expect(out.complete).toBe(true);
        expect(out.count).toBe(200);
        expect(api.calls).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
    });

    test('works when the server honours page_size=100', async () => {
        const api = fakeList(239, 100);
        const out = await collectPages<Row>(api.fetchPage, { maxItems: 600, maxPages: 30 });
        expect(out.items).toHaveLength(239);
        expect(api.calls).toEqual([1, 2, 3]);
    });

    test('stops at the item cap and the page cap', async () => {
        const capped = await collectPages<Row>(fakeList(3540, 100).fetchPage, { maxItems: 600, maxPages: 30 });
        expect(capped.items).toHaveLength(600);
        expect(capped.complete).toBe(false);

        const api = fakeList(3540, 20);
        const paged = await collectPages<Row>(api.fetchPage, { maxItems: 10_000, maxPages: 3 });
        expect(paged.items).toHaveLength(60);
        expect(api.calls).toEqual([1, 2, 3]);
    });

    test('keeps earlier pages when a later page fails; rejects when the first fails', async () => {
        let n = 0;
        const flaky = async (page: number) => {
            n += 1;
            if (page === 3) throw new Error('network');
            return { count: 100, next: 'more', results: [{ id: page * 10 + 1 }, { id: page * 10 + 2 }] };
        };
        const partial = await collectPages<Row>(flaky, { maxPages: 10 });
        expect(partial.items.map(r => r.id)).toEqual([11, 12, 21, 22]);
        expect(partial.complete).toBe(false);
        expect(n).toBe(3);

        await expect(collectPages<Row>(async () => { throw new Error('down'); })).rejects.toThrow('down');
    });

    test('stops on cancellation, on an empty page and dedupes ids across pages', async () => {
        let cancelled = false;
        const out = await collectPages<Row>(async (page) => {
            if (page === 2) cancelled = true;
            return { next: 'more', results: [{ id: page }] };
        }, { isCancelled: () => cancelled, maxPages: 10 });
        expect(out.items.map(r => r.id)).toEqual([1, 2]);

        const empty = await collectPages<Row>(async () => ({ next: 'more', results: [] }), { maxPages: 10 });
        expect(empty.items).toEqual([]);
        expect(empty.complete).toBe(true);

        const shifted = await collectPages<Row>(async (page) => ({
            next: page < 2 ? 'more' : null,
            results: page === 1 ? [{ id: 9 }, { id: 8 }] : [{ id: 8 }, { id: 7 }],
        }));
        expect(shifted.items.map(r => r.id)).toEqual([9, 8, 7]);
    });

    test('readPage accepts bare arrays and paginated objects', () => {
        expect(readPage<Row>([{ id: 1 }])).toEqual({ items: [{ id: 1 }], hasNext: false, count: 1 });
        expect(readPage<Row>({ count: 5, next: 'x', results: [{ id: 2 }] })).toEqual({ items: [{ id: 2 }], hasNext: true, count: 5 });
        expect(readPage<Row>(null)).toEqual({ items: [], hasNext: false, count: null });
        expect(appendUniqueById([{ id: 1 }], [{ id: 1 }, { id: 2 }])).toEqual([{ id: 1 }, { id: 2 }]);
    });
});

test.describe('answer reveal (/questions/practice, FE-STU-03)', () => {
    // A student's list row: QuestionListSerializer has no correct_answer /
    // explanation / mnemonic fields for non-admins.
    const listRow: Record<string, unknown> = { id: 7, question_text: 'Q', option_a: 'a', option_b: 'b', option_c: 'c', option_d: 'd' };

    test('the list payload alone cannot grade a pick (the old bug)', () => {
        const picked = 'C';
        // Old page logic: `selectedAnswer === currentQ.correct_answer`.
        expect(picked === listRow.correct_answer).toBe(false);
    });

    test('grades from the attempt response and fills explanation from the detail', () => {
        // Current backend attempt response shape.
        const fromAttempt = revealFromAttempt('c', { is_correct: true, correct_answer: 'C', is_subscribed: true });
        expect(fromAttempt).toEqual({ correctAnswer: 'C', isCorrect: true, explanation: undefined, mnemonic: undefined });
        expect(revealNeedsDetail(fromAttempt)).toBe(true);

        const full = mergeRevealWithDetail('C', fromAttempt, {
            id: 7, correct_answer: 'C', explanation: 'Because C.', mnemonic: 'See C', images: [{ id: 3 }],
        });
        expect(full).toEqual({ correctAnswer: 'C', isCorrect: true, explanation: 'Because C.', mnemonic: 'See C', images: [{ id: 3 }] });
        expect(revealNeedsDetail(full)).toBe(false);
    });

    test('a wrong pick shows the real key', () => {
        const r = revealFromAttempt('A', { is_correct: false, correct_answer: 'D' });
        expect(r.correctAnswer).toBe('D');
        expect(r.isCorrect).toBe(false);
    });

    test('uses explanation / mnemonic from the attempt response when present', () => {
        const r = revealFromAttempt('B', { is_correct: false, correct_answer: 'A', explanation: 'Why A', mnemonic: '' });
        expect(r.explanation).toBe('Why A');
        expect(revealNeedsDetail(r)).toBe(false);
    });

    test('a withheld key is still known when the pick was right; unknown otherwise', () => {
        expect(revealFromAttempt('B', { is_correct: true }).correctAnswer).toBe('B');
        const wrong = revealFromAttempt('B', { is_correct: false });
        expect(wrong.correctAnswer).toBe('');
        expect(revealNeedsDetail(wrong)).toBe(true);
    });

    test('detail fallback: explanation falls back to effective_explanation; verdict derived when missing', () => {
        const r = mergeRevealWithDetail('A', { correctAnswer: '', isCorrect: null }, {
            correct_answer: 'b', explanation: '  ', effective_explanation: 'Effective', mnemonic: null,
        });
        expect(r.correctAnswer).toBe('B');
        expect(r.isCorrect).toBe(false);
        expect(r.explanation).toBe('Effective');
        expect(r.mnemonic).toBe('');
    });

    test('recognises the freemium paywall payload', () => {
        expect(upgradeRequiredFeature({ response: { status: 402, data: { code: 'upgrade_required', feature: 'PYQ answers' } } })).toBe('PYQ answers');
        expect(upgradeRequiredFeature({ response: { status: 403, data: { code: 'upgrade_required' } } })).toBe('PYQ answers');
        expect(upgradeRequiredFeature({ response: { status: 403, data: { detail: 'Forbidden' } } })).toBeNull();
        expect(upgradeRequiredFeature(new Error('network'))).toBeNull();
    });

    test('answerLetter / isPremiumUser', () => {
        expect(answerLetter(' c ')).toBe('C');
        expect(answerLetter('Z')).toBe('');
        expect(answerLetter(3)).toBe('');
        expect(isPremiumUser({ is_premium: true })).toBe(true);
        expect(isPremiumUser({ subscription_info: { is_active: true } })).toBe(true);
        expect(isPremiumUser({ role: 'admin' })).toBe(true);
        expect(isPremiumUser({ is_premium: false, subscription_info: null })).toBe(false);
        expect(isPremiumUser(null)).toBe(false);
    });
});

test.describe('per-question AI panels (RevealExplanation, REV-01 / FE-STU-21)', () => {
    test('every backend template fallback is recognised', () => {
        // Read the canned strings straight from the backend so this test
        // fails if they change without the frontend list being updated.
        const src = readFileSync(path.resolve(__dirname, '../../../backend/questions/ai_per_question.py'), 'utf-8');
        // Join Python implicit string concatenation ("a "\n    "b") so a
        // literal re-wrapped across lines still matches.
        const flat = src.replace(/"\s*\n\s*"/g, '');
        const block = src.slice(src.indexOf('_FALLBACK = {'), src.indexOf('}', src.indexOf('_FALLBACK = {')));
        const strings = Array.from(block.matchAll(/^\s*"\w+":\s*"(.+)",\s*$/gm), m => m[1]);
        expect(strings.length).toBeGreaterThanOrEqual(5);
        for (const s of strings) expect(isAiTemplateText(s), s).toBe(true);

        // why_incorrect(): fixed strings plus one template line per distractor.
        expect(flat).toContain('Each wrong distractor fails because it does not satisfy the canonical definition referenced by the stem.');
        expect(isAiTemplateText('Each wrong distractor fails because it does not satisfy the canonical definition referenced by the stem.')).toBe(true);
        expect(isAiTemplateText('Distractors: each fails the canonical definition; cross-check with the textbook.')).toBe(true);
        expect(flat).toContain('— not the canonical answer because the stem requires');
        expect(isAiTemplateText('A: Aspirin — not the canonical answer because the stem requires a 45-year-old man...\nB: Heparin — not the canonical answer because the stem requires a 45-year-old man...')).toBe(true);
    });

    test('readAiField keeps real text and drops templates / flagged fallbacks', () => {
        expect(readAiField({ concept: 'Cushing reflex' }, 'concept')).toBe('Cushing reflex');
        expect(readAiField({ concept: "Core concept: review the textbook chapter covering the stem's keywords." }, 'concept')).toBe('');
        expect(readAiField({ concept: 'Real', is_fallback: true }, 'concept')).toBe('');
        // The API may answer `null` when there is no genuine content.
        expect(readAiField({ concept: null }, 'concept')).toBe('');
        expect(readAiField({ why_incorrect: null }, 'why_incorrect')).toBe('');
        expect(readAiField({ why_incorrect: 'x' }, 'concept')).toBe('');
        expect(readAiField(null, 'concept')).toBe('');
    });

    test('the concept and why_incorrect responses map to their own sections', () => {
        // RevealExplanation destructures [a, c, m, e, w, wn] from
        // [why_correct, clinical, mnemonic, exam_importance, concept, why_incorrect].
        const w = { concept: 'Beta blockade' };
        const wn = { why_incorrect: 'A: real reason the distractor fails' };
        expect(readAiField(w, 'concept')).toBe('Beta blockade');
        expect(readAiField(wn, 'why_incorrect')).toBe('A: real reason the distractor fails');
        // The old swapped lookups always produced ''.
        expect(readAiField(wn, 'concept')).toBe('');
        expect(readAiField(w, 'why_incorrect')).toBe('');
    });
});

test.describe('side panels', () => {
    test('related topics use topic_id / topic__name (no more "Topic #undefined")', () => {
        const rows = [
            { topic_id: 12, topic__name: 'Shock', c: 9 },
            { topic_id: null, topic__name: null, c: 40 },
            { topic_id: 13, topic__name: '  ', c: 3 },
        ];
        expect(normaliseRelatedTopics(rows)).toEqual([{ id: 12, name: 'Shock', count: 9 }]);
        expect(normaliseRelatedTopics(undefined)).toEqual([]);
    });

    test('textbook references read the {references: [...]} list (FE-STU-30 / AI-08)', () => {
        expect(normaliseTextbookReferences({
            references: [
                { book: 'Harrison', page: 1234, excerpt: 'Septic shock is…', relevance_score: 0.8 },
                { book: '', page: '', excerpt: '' },
            ],
        })).toEqual([{ book: 'Harrison', chapter: '', page: '1234', excerpt: 'Septic shock is…' }]);
        expect(normaliseTextbookReferences({ references: [] })).toEqual([]);
        // Legacy single-object shape.
        expect(normaliseTextbookReferences({ book_name: 'Bailey', chapter: '5', page_range: '10-12', reference: 'See ch 5' }))
            .toEqual([{ book: 'Bailey', chapter: '5', page: '10-12', excerpt: 'See ch 5' }]);
        expect(normaliseTextbookReferences({ error: true })).toEqual([]);
    });
});

test.describe('/practice deep links (FE-STU-21)', () => {
    test('a deep-linked id missing from the random queue is opened first', () => {
        expect(placeInQueue([4, 5, 6], 9, true)).toEqual({ ids: [9, 4, 5, 6], index: 0 });
        expect(placeInQueue([4, 5, 6], 5, true)).toEqual({ ids: [4, 5, 6], index: 1 });
        expect(placeInQueue([4, 5, 6], null, true)).toEqual({ ids: [4, 5, 6], index: 0 });
        // Queue rebuilds (mode change) don't drag the old question along.
        expect(placeInQueue([4, 5, 6], 9, false)).toEqual({ ids: [4, 5, 6], index: 0 });
    });

    test('a related-PYQ link while practising inserts after the current question', () => {
        expect(openInQueue([4, 5, 6], 0, 9)).toEqual({ ids: [4, 9, 5, 6], index: 1 });
        expect(openInQueue([4, 5, 6], 2, 9)).toEqual({ ids: [4, 5, 6, 9], index: 3 });
        expect(openInQueue([4, 5, 6], 0, 6)).toEqual({ ids: [4, 5, 6], index: 2 });
        expect(openInQueue([], 0, 9)).toEqual({ ids: [9], index: 0 });
    });
});
