/**
 * Wave 3 integration pass (group Z7-practice) — changes other groups asked
 * for in the practice files:
 *  - Z9: an attempt on a question with no answer key (`is_correct: null,
 *    correct_answer: ''`, nothing recorded) is ungraded: the bank's row
 *    says "Attempted" and the exam palette shows it neutral, not "wrong".
 *  - Z5: "Find in Textbook" falls back to GET /ai/screenshot/{id}/ (200
 *    {screenshot_url}; 202 rendering → one retry after ~3 s; 404 → no
 *    image) when the question has no stored page image or it fails to
 *    load; a 402 from the reference lookup opens the paywall, not an error.
 *  - Z1: /practice and /recall/search sit inside AppShell's .page-container
 *    and drop their own page padding there.
 *
 * Run (from frontend/):
 *   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/practice-integration.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
    SCREENSHOT_RETRY_MS,
    attemptVerdict,
    fetchPageScreenshot,
    screenshotUrlFrom,
} from '../../src/components/question/practiceData.ts';

const FRONTEND = fileURLToPath(new URL('../../', import.meta.url));
const read = (rel: string) => readFileSync(path.join(FRONTEND, rel), 'utf8');

/** An axios-style error with a response. */
const httpError = (status: number, data: unknown = {}) => ({ response: { status, data, headers: {} } });

// ── Attempt verdict (no answer key → ungraded) ─────────────────────────────

test('attemptVerdict: the server verdict wins; no answer key → null, never "wrong"', () => {
    assert.equal(attemptVerdict('A', { is_correct: true, correct_answer: 'A' }), true);
    assert.equal(attemptVerdict('A', { is_correct: false, correct_answer: 'B' }), false);
    // questions.views attempt() for a question without a key.
    assert.equal(attemptVerdict('A', { is_correct: null, correct_answer: '' }), null);
    // No boolean verdict: graded against the response's key (case-insensitive).
    assert.equal(attemptVerdict('b', { correct_answer: 'B' }), true);
    assert.equal(attemptVerdict('A', { correct_answer: 'b' }), false);
    // Nothing to grade against.
    assert.equal(attemptVerdict('A', {}), null);
    assert.equal(attemptVerdict('A', null), null);
    assert.equal(attemptVerdict('', { correct_answer: 'A' }), null);
});

// ── Textbook page screenshot ───────────────────────────────────────────────

test('screenshotUrlFrom: a URL only, never a server filesystem path', () => {
    assert.equal(screenshotUrlFrom({ screenshot_url: 'https://api.example.test/media/q7_p12.png' }), 'https://api.example.test/media/q7_p12.png');
    assert.equal(screenshotUrlFrom({ screenshot_url: ' http://127.0.0.1:8000/media/a.png ' }), 'http://127.0.0.1:8000/media/a.png');
    assert.equal(screenshotUrlFrom({ screenshot_url: '/media/q7.png' }), '/media/q7.png');
    assert.equal(screenshotUrlFrom({ screenshot_url: 'C:\\app\\media\\q7.png' }), '');
    assert.equal(screenshotUrlFrom({ screenshot_url: 'javascript:alert(1)' }), '');
    assert.equal(screenshotUrlFrom({ screenshot_path: '/app/backend/media/q7.png' }), '', 'the old path field is ignored');
    assert.equal(screenshotUrlFrom({ status: 'rendering' }), '');
    assert.equal(screenshotUrlFrom({ screenshot_url: 42 }), '');
    assert.equal(screenshotUrlFrom(null), '');
});

/** A fake aiAPI.getScreenshot answering from a script of responses / errors. */
function fakeGetScreenshot(script: Array<{ status: number; data: unknown } | { error: unknown }>) {
    const calls: number[] = [];
    const fn = async (id: number) => {
        calls.push(id);
        const step = script[Math.min(calls.length - 1, script.length - 1)];
        if ('error' in step) throw step.error;
        return step;
    };
    return { fn, calls };
}

test('fetchPageScreenshot: 200 → its URL, one request', async () => {
    const api = fakeGetScreenshot([{ status: 200, data: { screenshot_url: 'https://x.test/media/p.png' } }]);
    const waits: number[] = [];
    const url = await fetchPageScreenshot(api.fn, 7, { wait: async ms => { waits.push(ms); } });
    assert.equal(url, 'https://x.test/media/p.png');
    assert.deepEqual(api.calls, [7]);
    assert.deepEqual(waits, []);
});

test('fetchPageScreenshot: 202 rendering → asked once more after ~3 s', async () => {
    const api = fakeGetScreenshot([
        { status: 202, data: { status: 'rendering' } },
        { status: 200, data: { screenshot_url: 'https://x.test/media/p.png' } },
    ]);
    const waits: number[] = [];
    const url = await fetchPageScreenshot(api.fn, 7, { wait: async ms => { waits.push(ms); } });
    assert.equal(url, 'https://x.test/media/p.png');
    assert.deepEqual(api.calls, [7, 7]);
    assert.deepEqual(waits, [SCREENSHOT_RETRY_MS]);
    assert.equal(SCREENSHOT_RETRY_MS, 3000);
});

test('fetchPageScreenshot: a second 202 gives up (no third request)', async () => {
    const api = fakeGetScreenshot([{ status: 202, data: { status: 'rendering' } }]);
    const url = await fetchPageScreenshot(api.fn, 7, { wait: async () => {} });
    assert.equal(url, null);
    assert.equal(api.calls.length, 2);
});

test('fetchPageScreenshot: 404 / 402 / 429 / network → no image, no retry', async () => {
    for (const error of [
        httpError(404, { error: 'No screenshot available' }),
        httpError(402, { code: 'upgrade_required', feature: 'PYQ answers' }),
        httpError(429, { detail: 'Request was throttled.' }),
        Object.assign(new Error('Network Error'), { request: {} }),
    ]) {
        const api = fakeGetScreenshot([{ error }]);
        assert.equal(await fetchPageScreenshot(api.fn, 7, { wait: async () => {} }), null);
        assert.equal(api.calls.length, 1);
    }
});

test('fetchPageScreenshot: no retry for a question the student has left', async () => {
    const api = fakeGetScreenshot([
        { status: 202, data: { status: 'rendering' } },
        { status: 200, data: { screenshot_url: 'https://x.test/media/p.png' } },
    ]);
    const url = await fetchPageScreenshot(api.fn, 7, { wait: async () => {}, isCurrent: () => false });
    assert.equal(url, null);
    assert.equal(api.calls.length, 1);
});

test('fetchPageScreenshot: a 200 without a URL is no image', async () => {
    const api = fakeGetScreenshot([{ status: 200, data: { screenshot_path: '/srv/media/p.png' } }]);
    assert.equal(await fetchPageScreenshot(api.fn, 7, { wait: async () => {} }), null);
    assert.equal(api.calls.length, 1);
});

// ── Wiring (source checks) ─────────────────────────────────────────────────

test('the question bank grades picks with attemptVerdict and shows ungraded picks neutrally', () => {
    const bank = read('src/components/question/ExamQuestionBank.tsx');
    // Both handlers (practice pick and exam-mode submit).
    assert.equal((bank.match(/attemptVerdict\((opt|picked), res\?\.data\)/g) || []).length, 2);
    assert.doesNotMatch(bank, /typeof res\?\.data\?\.is_correct === 'boolean' \? res\.data\.is_correct : isCorrect/);
    // Exam mode: no key in the detail → ungraded until the server answers.
    assert.match(bank, /const isCorrect = key \? picked === key : null;/);
    // List card and palette.
    assert.match(bank, /q\.user_is_correct == null \?/);
    assert.match(bank, />\s*Attempted\s*</);
    assert.match(bank, /ans\.isCorrect === null \? 'answered'/);
    assert.match(bank, /answered: 'bg-primary\/15 text-primary border-primary\/40'/);
    assert.match(bank, /user_is_correct\?: boolean \| null;/);
});

test('"Find in Textbook" falls back to /ai/screenshot/ and treats a 402 as the paywall', () => {
    const bank = read('src/components/question/ExamQuestionBank.tsx');
    assert.match(bank, /fetchPageScreenshot\(aiAPI\.getScreenshot, qid, \{ isCurrent \}\)/);
    // Only without a stored image (or when it fails to load).
    assert.match(bank, /if \(storedShot\) setTextbookScreenshot\(storedShot\);\s*else requestTextbookScreenshot\(qid\);/);
    assert.match(bank, /onError=\{handleTextbookScreenshotError\}/);
    // Asked at most once per opened question.
    assert.match(bank, /if \(screenshotAskedFor\.current === qid\) return false;/);
    assert.match(bank, /screenshotAskedFor\.current = null;\s*screenshotSeq\.current \+= 1;/);
    // The 402 of the reference lookup returns before the error state.
    const lookup = bank.slice(bank.indexOf('const lookupTextbook = () => {'));
    const catchBlock = lookup.slice(lookup.indexOf('.catch((err: unknown) => {'), lookup.indexOf('.finally('));
    assert.match(catchBlock, /const feature = upgradeRequiredFeature\(err\);\s*if \(feature\) \{[\s\S]*?showPaywall\(feature\);\s*return;\s*\}\s*setTextbookRef\(\{ error: true \}\);/);
    // While the page is fetched the card says so instead of "No textbook mapping".
    assert.match(bank, /textbookRef\.references\.length === 0 && !textbookScreenshot && !textbookShotLoading/);
});

test('/practice and /recall/search drop their page padding inside the AppShell', () => {
    const practice = read('src/app/practice/page.tsx');
    assert.match(practice, /className="mx-auto max-w-5xl px-4 py-6 \[\.page-container_&\]:p-0 text-foreground"/);
    assert.match(practice, /<p className="p-6 \[\.page-container_&\]:px-0 text-muted-foreground">Loading…<\/p>/);
    assert.doesNotMatch(practice, /<main[\s>]/, 'the AppShell layout provides the landmark');
    const recall = read('src/app/recall/search/page.tsx');
    assert.match(recall, /className="mx-auto max-w-5xl px-4 py-6 \[\.page-container_&\]:p-0 text-foreground"/);
    assert.doesNotMatch(recall, /<main[\s>]/);
});
