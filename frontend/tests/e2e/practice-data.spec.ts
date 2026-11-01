/**
 * Unit tests for src/components/question/practiceData.ts — the helpers the
 * practice surfaces use to page through the question list, reveal the real
 * answer after a pick, hide backend template text and normalise the
 * related-topic / textbook-reference payloads — and for
 * src/components/recall/recallFacets.ts (recall search facet chips).
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
    classifyReveal,
    collectPages,
    examLabelFromParam,
    examTypeFromParam,
    examTypeLabel,
    examYearChip,
    hasBlankAnswerKey,
    isAiTemplateText,
    isPremiumUser,
    mergeRevealWithDetail,
    normaliseRelatedTopics,
    normaliseTextbookReferences,
    openInQueue,
    pickExplanation,
    placeInQueue,
    readAiField,
    readPage,
    resolveSubjectParam,
    retryAfterSeconds,
    retryTimeSpent,
    revealFromAttempt,
    revealNeedsDetail,
    upgradeRequiredFeature,
    type AnswerReveal,
    type SubjectOption,
} from '../../src/components/question/practiceData';
import { facetEntries, facetLabel, humaniseKey } from '../../src/components/recall/recallFacets';

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
    test('a student list row carries no key: the reveal comes from the attempt response', () => {
        // QuestionListSerializer sends no correct_answer for non-admins (the
        // old page compared the pick with this missing field).
        const listRow = { id: 7, question_text: 'Q', option_a: 'a', option_b: 'b', option_c: 'c', option_d: 'd' };
        const fromList = revealFromAttempt('C', listRow);
        expect(fromList.correctAnswer).toBe('');
        expect(fromList.isCorrect).toBeNull();
        expect(hasBlankAnswerKey(listRow)).toBe(false);
        expect(revealNeedsDetail(fromList)).toBe(true);
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

test.describe('explanation fallback (effective_explanation, wave 2)', () => {
    test('a blank curated explanation falls back to effective_explanation', () => {
        // The real attempt payload for an AI-explained PYQ: `explanation` is
        // always sent, as '' — `??` used to keep that '' and show nothing.
        const attempt = { is_correct: false, correct_answer: 'B', explanation: '', effective_explanation: 'AI: B because…' };
        expect(pickExplanation(attempt)).toBe('AI: B because…');
        const reveal = revealFromAttempt('A', attempt);
        expect(reveal.explanation).toBe('AI: B because…');
        // Curated text still wins when it exists.
        expect(pickExplanation({ explanation: 'Curated', effective_explanation: 'AI' })).toBe('Curated');
        // Fields present but blank → '' (no detail round-trip just for it);
        // fields absent (redacted / list payload) → undefined.
        expect(pickExplanation({ explanation: '  ', effective_explanation: '' })).toBe('');
        expect(pickExplanation({ explanation: null, effective_explanation: null })).toBeUndefined();
        expect(pickExplanation(undefined)).toBeUndefined();
    });

    test('the C1 attempt response (with mnemonic) completes the reveal without the detail', () => {
        const r = revealFromAttempt('C', {
            is_correct: true, correct_answer: 'C', explanation: '', effective_explanation: 'Override text', mnemonic: 'MNEMO',
        });
        expect(r).toEqual({ correctAnswer: 'C', isCorrect: true, explanation: 'Override text', mnemonic: 'MNEMO' });
        expect(revealNeedsDetail(r)).toBe(false);
    });

    test('a blank explanation from the attempt is filled from the detail', () => {
        const fromAttempt: AnswerReveal = { correctAnswer: 'D', isCorrect: false, explanation: '' };
        const merged = mergeRevealWithDetail('A', fromAttempt, {
            correct_answer: 'D', explanation: '', effective_explanation: 'Detail effective', mnemonic: 'm',
        });
        expect(merged.explanation).toBe('Detail effective');
        // A non-blank attempt explanation is kept.
        expect(mergeRevealWithDetail('A', { ...fromAttempt, explanation: 'From attempt' }, {
            effective_explanation: 'Detail effective',
        }).explanation).toBe('From attempt');
        // A redacted detail (fields null) leaves the attempt's value.
        expect(mergeRevealWithDetail('A', fromAttempt, { explanation: null, effective_explanation: null }).explanation).toBe('');
    });
});

test.describe('reveal outcome after a pick (/questions/practice states)', () => {
    const none: AnswerReveal = { correctAnswer: '', isCorrect: null };
    const keyed: AnswerReveal = { correctAnswer: 'B', isCorrect: true };
    const networkError = Object.assign(new Error('Network Error'), { request: {} });
    const serverError = { response: { status: 500, data: {} } };

    test('200 with a key → ready (also when only the detail had the key)', () => {
        expect(classifyReveal({ reveal: keyed, attemptOk: true, serverHasNoKey: false, gated: false })).toBe('ready');
        // Save failed but the detail graded it: ready (+ "couldn't save" note).
        expect(classifyReveal({ reveal: keyed, attemptOk: false, serverHasNoKey: false, gated: false })).toBe('ready');
    });

    test('200 with an empty key → no-key, not a retryable error', () => {
        const attempt = { is_correct: false, correct_answer: '', explanation: '', effective_explanation: '' };
        expect(hasBlankAnswerKey(attempt)).toBe(true);
        const reveal = revealFromAttempt('A', attempt);
        expect(reveal.correctAnswer).toBe('');
        expect(classifyReveal({ reveal, attemptOk: true, serverHasNoKey: hasBlankAnswerKey(attempt), gated: false })).toBe('no-key');
        // The detail can say the same when the attempt POST failed.
        expect(classifyReveal({ reveal: none, attemptOk: false, serverHasNoKey: true, gated: false })).toBe('no-key');
    });

    test('402 / redacted detail → locked; a failed save with a gated detail stays retryable', () => {
        expect(classifyReveal({ reveal: none, attemptOk: true, serverHasNoKey: false, gated: true })).toBe('locked');
        // The retry will get the 402 upgrade_required and lock properly.
        expect(classifyReveal({ reveal: none, attemptOk: false, serverHasNoKey: false, gated: true })).toBe('error');
        expect(upgradeRequiredFeature({ response: { status: 402, data: { code: 'upgrade_required', feature: 'PYQ answers' } } })).toBe('PYQ answers');
    });

    test('network error on both requests → error with Retry', () => {
        expect(classifyReveal({ reveal: none, attemptOk: false, serverHasNoKey: false, gated: false })).toBe('error');
    });

    test('a Retry after a lost response does not send the time again', () => {
        // No HTTP response: the server may have recorded the attempt.
        expect(retryTimeSpent(networkError, 42)).toBe(0);
        // The server answered with an error: resend the measured time.
        expect(retryTimeSpent(serverError, 42)).toBe(42);
        expect(retryTimeSpent(serverError, -3)).toBe(0);
    });

    test('a 429 retry waits for Retry-After when readable, else 5s (capped at 30s)', () => {
        expect(retryAfterSeconds({ response: { status: 429, headers: { 'retry-after': '12' } } })).toBe(12);
        expect(retryAfterSeconds({ response: { status: 429, headers: { 'retry-after': '600' } } })).toBe(30);
        expect(retryAfterSeconds({ response: { status: 429, headers: {} } })).toBe(5);
        expect(retryAfterSeconds({ response: { status: 429, headers: { 'retry-after': 'Wed, 21 Oct 2026 07:28:00 GMT' } } })).toBe(5);
        expect(retryAfterSeconds(networkError)).toBe(5);
    });
});

test.describe('exam / subject URL params (/questions, /questions/practice)', () => {
    test('exam values match case-insensitively, with enum values, slugs and labels', () => {
        for (const raw of ['cms', 'CMS', 'upsc-cms', 'UPSC CMS']) expect(examTypeFromParam(raw), raw).toBe('cms');
        for (const raw of ['neet-pg', 'neet_pg', 'NEET_PG', 'NEET PG', 'Neet-PG', 'neetpg']) expect(examTypeFromParam(raw), raw).toBe('neet_pg');
        for (const raw of ['ini-cet', 'ini_cet', 'INI_CET', 'inicet', 'INI-CET']) expect(examTypeFromParam(raw), raw).toBe('ini_cet');
        expect(examTypeFromParam('FMGE')).toBe('fmge');
        expect(examTypeFromParam('usmle')).toBe('usmle');
        expect(examTypeFromParam('medical_officer')).toBe('cms');
        expect(examTypeFromParam('CMS NEET PG')).toBeNull();
        expect(examTypeFromParam('')).toBeNull();
        expect(examTypeFromParam(null)).toBeNull();
    });

    test('exam labels', () => {
        expect(examLabelFromParam('NEET_PG')).toBe('NEET PG');
        expect(examLabelFromParam('ini-cet')).toBe('INI-CET');
        expect(examLabelFromParam('Medical-Officer')).toBe('Medical Officer');
        expect(examLabelFromParam('nope')).toBeNull();
        expect(examTypeLabel('neet_pg')).toBe('NEET PG');
        expect(examTypeLabel('other')).toBe('other');
    });

    test('the exam / year chip uses the question\'s own exam (was always "NEET PG")', () => {
        expect(examYearChip('UPSC CMS', 2019)).toBe('UPSC CMS 2019');
        expect(examYearChip('NEET PG (recall)', 2025)).toBe('NEET PG 2025');
        expect(examYearChip('INI-CET (recall)', 2024)).toBe('INI-CET 2024');
        expect(examYearChip(undefined, 2020)).toBe('PYQ 2020');
        expect(examYearChip('UPSC CMS', 0)).toBe('UPSC CMS');
    });

    test('subject params resolve ids, names, codes and public-page slugs', () => {
        const options: SubjectOption[] = [
            { id: 1, name: 'General Medicine', code: 'MED', count: 3155 },
            { id: 3, name: 'General Surgery', code: 'SUR', count: 1132 },
            { id: 4, name: 'Obstetrics & Gynaecology', code: 'OBG', count: 975 },
            { id: 5, name: 'Community Medicine', code: 'PSM', count: 1136 },
            { id: 6, name: 'Anatomy', code: 'ANA', count: 582 },
            { id: 14, name: 'ENT', code: 'ENT', count: 503 },
            { id: 17, name: 'Anaesthesia', code: 'ANS', count: 568 },
            { id: 18, name: 'Radiodiagnosis', code: 'RAD', count: 518 },
            { id: 291, name: 'Expert Curated', code: 'EXPERT', count: 1826 },
        ];
        // subjectHubData slugs
        expect(resolveSubjectParam('medicine', options)).toBe(1);
        expect(resolveSubjectParam('surgery', options)).toBe(3);
        expect(resolveSubjectParam('obg', options)).toBe(4);
        expect(resolveSubjectParam('psm', options)).toBe(5);
        expect(resolveSubjectParam('ent', options)).toBe(14);
        expect(resolveSubjectParam('anaesthesia', options)).toBe(17);
        // blog link
        expect(resolveSubjectParam('anatomy', options)).toBe(6);
        // ExamMicrosite subject names
        expect(resolveSubjectParam('General Medicine', options)).toBe(1);
        expect(resolveSubjectParam('Preventive & Social Medicine', options)).toBe(5);
        expect(resolveSubjectParam('Community Medicine / PSM', options)).toBe(5);
        expect(resolveSubjectParam('Obstetrics & Gynaecology', options)).toBe(4);
        expect(resolveSubjectParam('Radiology', options)).toBe(18);
        expect(resolveSubjectParam('OBGYN', options)).toBe(4);
        // ids
        expect(resolveSubjectParam('14', options)).toBe(14);
        expect(resolveSubjectParam('999', options)).toBeNull();
        // no match → no filter (never an id the API would reject)
        expect(resolveSubjectParam('Behavioural Science', options)).toBeNull();
        expect(resolveSubjectParam('', options)).toBeNull();
        expect(resolveSubjectParam('medicine', [])).toBeNull();
    });
});

test.describe('recall search facets (/recall/search)', () => {
    test('facet values get readable labels', () => {
        expect(facetLabel('exam_type', 'cms')).toBe('UPSC CMS');
        expect(facetLabel('exam_type', 'neet_pg')).toBe('NEET PG');
        expect(facetLabel('exam_type', 'ini_cet')).toBe('INI-CET');
        expect(facetLabel('question_type', 'single_best')).toBe('Single best answer');
        expect(facetLabel('question_type', 'multiple_correct')).toBe('Multiple correct');
        expect(facetLabel('question_type', 'assertion_reason')).toBe('Assertion–reason');
        expect(facetLabel('year', '0')).toBe('Undated');
        expect(facetLabel('year', '2025')).toBe('2025');
        expect(facetLabel('modality', 'x_ray')).toBe('X-ray');
        expect(facetLabel('modality', 'clinical_photo')).toBe('Clinical photo');
        expect(facetLabel('clinical_category', 'clinical')).toBe('Clinical');
        expect(facetLabel('difficulty', '')).toBe('Unspecified');
        expect(humaniseKey('clinical_system')).toBe('Clinical system');
    });

    test('years are listed newest first with the undated bucket last; other groups by count', () => {
        const years = { '0': 3641, '2014': 1, '2018': 235, '2019': 222, '2020': 239, '2021': 237, '2022': 234, '2023': 241, '2024': 237, '2025': 236 };
        expect(facetEntries('year', years, undefined).map(([k]) => k))
            .toEqual(['2025', '2024', '2023', '2022', '2021', '2020', '2019', '2018', '2014', '0']);
        const difficulty = { hard: 766, medium: 4153, easy: 604 };
        expect(facetEntries('difficulty', difficulty, undefined)).toEqual([['medium', 4153], ['hard', 766], ['easy', 604]]);
        expect(facetEntries('difficulty', difficulty, undefined, 2)).toHaveLength(2);
    });

    test('a single-value group is hidden unless it is the active filter', () => {
        expect(facetEntries('clinical_category', { clinical: 10013 }, undefined)).toEqual([]);
        expect(facetEntries('clinical_category', { clinical: 10013 }, '')).toEqual([]);
        expect(facetEntries('exam_type', { cms: 5523 }, 'cms')).toEqual([['cms', 5523]]);
        expect(facetEntries('modality', {}, undefined)).toEqual([]);
        expect(facetEntries('modality', undefined, undefined)).toEqual([]);
    });
});
