/**
 * Wave 3 (group Z7-practice) — question bank / practice helpers and wiring:
 *  - pickExplanation: the curated text stays ahead of the effective
 *    explanation (usually the stored AI analysis) unless the payload flags
 *    an admin override / lock (`explanation_overridden: true`).
 *  - retryAfterSeconds: falls back to the wait DRF states in a throttled
 *    body when Retry-After is not readable cross-origin.
 *  - AI failures (C13): 402 paywall, empty token wallet, throttle, 503
 *    ai_unavailable ("AI is unavailable right now", never charged), and the
 *    per-question ai/* `rate_limited` flag.
 *  - detail failures: premium question on the free plan vs removed vs error.
 *  - stats strip: one PYQ definition for the headline and the progress bar.
 *  - C11 years: positive years only.
 *  - the `ai_explain_request` GA4 conversion is consent-gated.
 *
 * Run (from frontend/):
 *   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/practice-wave3.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
    aiFailureNotice,
    aiRateLimited,
    classifyAiFailure,
    detailFailureKind,
    mergeRevealWithDetail,
    normaliseYears,
    pickExplanation,
    retryAfterSeconds,
    revealFromAttempt,
    summariseBankStats,
} from '../../src/components/question/practiceData.ts';

const FRONTEND = fileURLToPath(new URL('../../', import.meta.url));
const read = (rel: string) => readFileSync(path.join(FRONTEND, rel), 'utf8');

/** An axios-style error with a response. */
const httpError = (status: number, data: unknown = {}, headers: Record<string, string> = {}) =>
    ({ response: { status, data, headers } });
const networkError = Object.assign(new Error('Network Error'), { request: {} });

// ── Explanation precedence ─────────────────────────────────────────────────

test('pickExplanation: the curated text stays ahead of the AI analysis (effective) explanation', () => {
    // effective_explanation_for: lock / override, then the stored AI
    // analysis, then curated — without the override flag the effective text
    // is the AI analysis, which the AI panels already show.
    assert.equal(pickExplanation({ explanation: 'Curated', effective_explanation: 'AI analysis' }), 'Curated');
    assert.equal(pickExplanation({ explanation: 'Curated', effective_explanation: 'AI analysis', explanation_overridden: false }), 'Curated');
    // A redacted / older payload (flag null or missing) keeps the same order.
    assert.equal(pickExplanation({ explanation: 'Curated', effective_explanation: 'AI analysis', explanation_overridden: null }), 'Curated');
    // Only a real boolean true flips it.
    assert.equal(pickExplanation({ explanation: 'Curated', effective_explanation: 'AI analysis', explanation_overridden: 'true' }), 'Curated');
    // A blank curated text falls back to the effective one.
    assert.equal(pickExplanation({ explanation: '  ', effective_explanation: 'AI analysis' }), 'AI analysis');
    assert.equal(pickExplanation({ explanation: null, effective_explanation: 'AI analysis' }), 'AI analysis');
    // Fields present but blank → ''; both absent / null → undefined.
    assert.equal(pickExplanation({ explanation: '', effective_explanation: '' }), '');
    assert.equal(pickExplanation({ explanation: null, effective_explanation: null }), undefined);
    assert.equal(pickExplanation({ explanation: null, effective_explanation: null, explanation_overridden: null }), undefined);
    assert.equal(pickExplanation(undefined), undefined);
});

test('pickExplanation: a flagged admin override / lock (explanation_overridden) wins over the curated text', () => {
    assert.equal(pickExplanation({
        explanation: 'Curated (wrong)', effective_explanation: 'Admin override', explanation_overridden: true,
    }), 'Admin override');
    // A blank effective text still falls back to the curated one.
    assert.equal(pickExplanation({ explanation: 'Curated', effective_explanation: '  ', explanation_overridden: true }), 'Curated');
    assert.equal(pickExplanation({ explanation: 'Curated', effective_explanation: null, explanation_overridden: true }), 'Curated');
    assert.equal(pickExplanation({ explanation: '', effective_explanation: '', explanation_overridden: true }), '');
});

test('the attempt reveal and the detail merge use the same precedence', () => {
    // An entitled attempt on a row with curated text and a stored AI analysis.
    const attempt = { is_correct: false, correct_answer: 'B', explanation: 'Curated', effective_explanation: 'AI analysis', mnemonic: '' };
    assert.equal(revealFromAttempt('A', attempt).explanation, 'Curated');
    // The answer responses send an admin override as `explanation` (with or
    // without the flag), so it is shown either way.
    assert.equal(revealFromAttempt('A', { ...attempt, explanation: 'Admin fix.', effective_explanation: 'Admin fix.' }).explanation, 'Admin fix.');
    assert.equal(revealFromAttempt('A', {
        ...attempt, explanation: 'Admin fix.', effective_explanation: 'Admin fix.', explanation_overridden: true,
    }).explanation, 'Admin fix.');
    // The detail payload's `explanation` is the raw curated field: an admin
    // override (in effective_explanation) beats it only when flagged.
    const blank = { correctAnswer: 'B', isCorrect: false, explanation: '' };
    assert.equal(mergeRevealWithDetail('A', blank, {
        correct_answer: 'B', explanation: 'Curated', effective_explanation: 'AI analysis',
    }).explanation, 'Curated');
    assert.equal(mergeRevealWithDetail('A', blank, {
        correct_answer: 'B', explanation: 'Curated', effective_explanation: 'Detail override', explanation_overridden: true,
    }).explanation, 'Detail override');
});

// ── 429 wait ───────────────────────────────────────────────────────────────

test('retryAfterSeconds: header, then the DRF throttle message, then 5s (cap 30s)', () => {
    assert.equal(retryAfterSeconds(httpError(429, {}, { 'retry-after': '12' })), 12);
    // Cross-origin the header is hidden (no CORS_EXPOSE_HEADERS): read the body.
    assert.equal(retryAfterSeconds(httpError(429, { detail: 'Request was throttled. Expected available in 17 seconds.' })), 17);
    assert.equal(retryAfterSeconds(httpError(429, { detail: 'Request was throttled. Expected available in 1 second.' })), 1);
    assert.equal(retryAfterSeconds(httpError(429, { detail: 'Request was throttled. Expected available in 59 seconds.' })), 30);
    assert.equal(retryAfterSeconds(httpError(429, { detail: 'Too many requests' })), 5);
    assert.equal(retryAfterSeconds(httpError(429, null)), 5);
    assert.equal(retryAfterSeconds(networkError), 5);
});

// ── AI failures (C13) ──────────────────────────────────────────────────────

test('classifyAiFailure tells the paywall, the wallet, the throttle and an outage apart', () => {
    assert.equal(classifyAiFailure(httpError(402, { code: 'upgrade_required', feature: 'PYQ answers' })), 'upgrade');
    assert.equal(classifyAiFailure(httpError(429, { error: 'insufficient_tokens', available: 0, required: 10 })), 'tokens');
    // DRF's ai_tutor throttle is not an empty wallet ("Buy Tokens" was wrong).
    assert.equal(classifyAiFailure(httpError(429, { detail: 'Request was throttled. Expected available in 9 seconds.' })), 'throttled');
    assert.equal(classifyAiFailure(httpError(503, { code: 'ai_unavailable', charged: false, offline: false })), 'unavailable');
    assert.equal(classifyAiFailure(httpError(503, '<html>Service Unavailable</html>')), 'unavailable');
    assert.equal(classifyAiFailure(httpError(500, { error: 'boom' })), 'error');
    assert.equal(classifyAiFailure(networkError), 'error');
});

test('aiFailureNotice: short notices, "not charged" only when the backend says so, never server text', () => {
    const outage = aiFailureNotice('unavailable', httpError(503, {
        code: 'ai_unavailable', charged: false,
        error: 'The AI tutor is unavailable right now and no grounded offline answer was found…',
    }));
    assert.equal(outage.title, 'AI is unavailable right now');
    assert.match(outage.message, /not charged/);
    // A gateway 503 says nothing about charging.
    assert.doesNotMatch(aiFailureNotice('unavailable', httpError(503, 'gateway')).message, /charged/);
    assert.equal(aiFailureNotice('throttled').title, 'Too many AI requests');
    // A raw server / provider error string is never surfaced.
    const generic = aiFailureNotice('error', httpError(500, { error: 'groq: 401 invalid api key sk-…' }));
    assert.doesNotMatch(`${generic.title} ${generic.message}`, /groq|api key|sk-/i);
    assert.equal(generic.message, 'AI service unavailable. Please try again.');
});

test('aiRateLimited: any per-question ai/* body with rate_limited: true', () => {
    assert.equal(aiRateLimited([{ why_correct: 'x' }, { concept: null, rate_limited: true }, null]), true);
    assert.equal(aiRateLimited([{ concept: null, locked: true }, { rate_limited: false }, undefined, 'x']), false);
    assert.equal(aiRateLimited([]), false);
});

// ── Question detail failures ───────────────────────────────────────────────

test('detailFailureKind: premium question on the free plan vs removed vs network', () => {
    // Free accounts get 404 for non-showcase questions (retrieve is gated).
    assert.equal(detailFailureKind(httpError(404, { detail: 'Not found.' }), false), 'locked');
    assert.equal(detailFailureKind(httpError(404, { detail: 'Not found.' }), true), 'missing');
    assert.equal(detailFailureKind(httpError(402, { code: 'upgrade_required' }), true), 'locked');
    assert.equal(detailFailureKind(httpError(403, { detail: 'Forbidden' }), false), 'locked');
    assert.equal(detailFailureKind(httpError(500), false), 'error');
    assert.equal(detailFailureKind(networkError, true), 'error');
});

// ── Stats strip (one PYQ definition) ───────────────────────────────────────

test('summariseBankStats: headline and progress use the dated rows only', () => {
    // CMS shape: 1,892 dated rows + 385 undated (year 0), total 2,277.
    const stats = {
        total: 2277,
        total_solved: 120,
        by_year: [
            { year: 2024, count: 1000, solved: 60 },
            { year: 2023, count: 892, solved: 40 },
            { year: 0, count: 385, solved: 20 },
        ],
    };
    const s = summariseBankStats(stats);
    assert.equal(s.pyqTotal, 1892);
    assert.equal(s.pyqSolved, 100, 'the undated attempts are not PYQ progress');
    assert.equal(s.undatedTotal, 385);
    assert.equal(s.hasRows, true);
    // Attempts on since-archived rows never push a year past 100%.
    assert.equal(summariseBankStats({ by_year: [{ year: 2020, count: 5, solved: 9 }] }).pyqSolved, 5);
});

test('summariseBankStats: no undated rows → no "incl. Expert Curated"; empty stats → nothing to show', () => {
    const allDated = summariseBankStats({ total: 101, by_year: [{ year: 2024, count: 101, solved: 3 }] });
    assert.equal(allDated.undatedTotal, 0);
    // INI-CET before the backend maps its labels: total 0, by_year [].
    const unmapped = summariseBankStats({ total: 0, total_solved: 0, by_year: [] });
    assert.equal(unmapped.hasRows, false);
    assert.equal(summariseBankStats(null).hasRows, false);
    // Without by_year the totals are the fallback.
    assert.deepEqual(summariseBankStats({ total: 50, total_solved: 70 }), { pyqTotal: 50, pyqSolved: 50, undatedTotal: 0, hasRows: true });
});

// ── C11 years ──────────────────────────────────────────────────────────────

test('normaliseYears: positive, unique years from a bare array or {results}', () => {
    assert.deepEqual(normaliseYears([2025, 2024, 0, -1, 2024, '2019']), [2025, 2024, 2019]);
    assert.deepEqual(normaliseYears({ results: [2023, 2022] }), [2023, 2022]);
    assert.deepEqual(normaliseYears(null), []);
    assert.deepEqual(normaliseYears({ detail: 'x' }), []);
});

// ── Wiring (source checks for the call sites the helpers feed) ─────────────

test('the question bank asks for its own exam\'s years and uses the shared stats summary', () => {
    const bank = read('src/components/question/ExamQuestionBank.tsx');
    assert.match(bank, /questionsAPI\.getYears\(\{ exam_type: examType \}\)/);
    assert.doesNotMatch(bank, /y === 0 \? 'Expert Curated'/, 'year 0 is no longer listed');
    assert.match(bank, /summariseBankStats\(qbankStats\)/);
    assert.doesNotMatch(bank, /qbankStats\.total_solved/, 'the progress bar no longer divides by the undated total');
    // C13: the attempt's 402 relocks; AI failures are classified; a failed
    // detail is a card, not an endless skeleton.
    assert.match(bank, /\.catch\(\(err: unknown\) => relockIfUpgradeRequired\(qId, err\)\)/);
    assert.match(bank, /classifyAiFailure\(err\)/);
    assert.match(bank, /detailFailureKind\(detailError\.error, isPremium\)/);
    assert.match(bank, /analytics\.aiExplainRequest\(/);
    // C3: the simulation asks for the bank's exam.
    assert.match(bank, /testsAPI\.pyqSimulation\(\{ year: Number\(modalYear\), exam_type: selectedExam \}\)/);
});

test('/questions/practice classifies AI failures and emits ai_explain_request', () => {
    const page = read('src/app/questions/practice/page.tsx');
    assert.match(page, /classifyAiFailure\(err\)/);
    assert.match(page, /aiFailureNotice\(failure, err\)/);
    assert.match(page, /analytics\.aiExplainRequest\(currentQ\.id, resolvedExamType, 'practice'\)/);
    assert.doesNotMatch(page, /status === 429\) \{\s*setTokenError/, 'a throttle 429 is not an empty wallet');
});

test('RevealExplanation says when the hourly AI budget is spent', () => {
    const panel = read('src/components/question/RevealExplanation.tsx');
    assert.match(panel, /aiRateLimited\(/);
    assert.match(panel, /AI limit reached for this hour/);
});

// ── ai_explain_request is consent-gated ────────────────────────────────────

test('ai_explain_request reaches GA only after analytics consent', async () => {
    const g = globalThis as Record<string, unknown>;
    const store = new Map<string, string>();
    g.window = globalThis;
    g.localStorage = {
        getItem: (k: string) => (store.has(k) ? store.get(k) : null),
        setItem: (k: string, v: string) => { store.set(k, String(v)); },
        removeItem: (k: string) => { store.delete(k); },
    };
    g.sessionStorage = g.localStorage;
    g.document = { referrer: '', title: 't' };
    g.location = { origin: 'https://www.example.test', pathname: '/questions', href: 'https://www.example.test/questions' };
    g.screen = { width: 1, height: 1 };
    Object.defineProperty(globalThis, 'navigator', { value: { userAgent: 'node', language: 'en' }, configurable: true });
    const bus = new EventTarget();
    g.addEventListener = bus.addEventListener.bind(bus);
    g.removeEventListener = bus.removeEventListener.bind(bus);
    g.dispatchEvent = bus.dispatchEvent.bind(bus);
    g.CustomEvent = class extends Event {
        detail: unknown;
        constructor(type: string, init?: { detail?: unknown }) { super(type); this.detail = init?.detail; }
    };
    const calls: unknown[][] = [];
    g.gtag = (...args: unknown[]) => { calls.push(args); };

    const { analytics } = await import('../../src/lib/analytics.ts');
    const { consent } = await import('../../src/lib/consent.ts');

    analytics.aiExplainRequest(7, 'cms', 'question_bank');
    assert.equal(calls.length, 0, 'nothing before the visitor decides');

    consent.update('analytics', true);
    analytics.aiExplainRequest(7, 'neet_pg', 'practice');
    const sent = calls.filter(c => c[0] === 'event' && c[1] === 'ai_explain_request');
    assert.equal(sent.length, 1);
    const params = sent[0][2] as Record<string, unknown>;
    assert.equal(params.question_id, 7);
    assert.equal(params.exam_slug, 'neet_pg');
    assert.equal(params.source, 'practice');
});
