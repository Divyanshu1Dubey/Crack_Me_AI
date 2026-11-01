/**
 * Wave 4b follow-ups: three frontend pieces adapted to backend contracts.
 *  - RevealExplanation: the ai/why_correct, clinical, mnemonic and concept
 *    GETs answer HTTP 202 {<field>: null, pending: true} while a background
 *    job writes the text. Pending sections show "Generating…" and only they
 *    are fetched again, a few times with a growing delay, while the panel is
 *    open. Closing it, a new question or unmounting stops the retries, and
 *    after the last one the panel gives up with a note. rate_limited keeps
 *    its notice; a bare {<field>: null} stays hidden.
 *  - DiscussionThread: the API sends `username` (null when the name would
 *    come from an email address); the never-sent `user_name` is gone and
 *    null reads "Learner". The vote response has a `status`, no `user_vote`.
 *  - Subscription scholarship flow: verify-scholarship returns score 5 on a
 *    pass and null on a failure and refuses blanks with 400. The breakdown
 *    renders only for a numeric score; Submit needs every answer.
 *
 * The .tsx modules are transpiled with the TypeScript compiler and their
 * top-level helpers are read without React (imports are inert stubs).
 *
 * Run (from frontend/):
 *   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/contract-followups-wave4b.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';
import * as practiceData from '../../src/components/question/practiceData.ts';

const FRONTEND = fileURLToPath(new URL('../../', import.meta.url));
const BACKEND = fileURLToPath(new URL('../../../backend/', import.meta.url));
const read = (rel: string) => readFileSync(path.join(FRONTEND, rel), 'utf8');
const readBackend = (rel: string) => readFileSync(path.join(BACKEND, rel), 'utf8');

/** Stand-in for an import that is only used while rendering. */
const inert: any = new Proxy(function inert() {}, {
    get: (_target, prop) => (prop === '__esModule' ? true : prop === 'then' ? undefined : inert),
    apply: () => inert,
    construct: () => inert,
});

/**
 * The named top-level bindings of a .tsx module: the source is transpiled to
 * CommonJS with `export const __internals = { ...names }` appended, and each
 * import resolves to `stubs[specifier]` or the inert stub.
 */
function loadInternals(rel: string, names: string[], stubs: Record<string, unknown> = {}): Record<string, any> {
    const source = `${read(rel)}\nexport const __internals = { ${names.join(', ')} };\n`;
    const { outputText } = ts.transpileModule(source, {
        fileName: path.basename(rel),
        compilerOptions: {
            module: ts.ModuleKind.CommonJS,
            target: ts.ScriptTarget.ES2022,
            jsx: ts.JsxEmit.ReactJSX,
            esModuleInterop: true,
        },
    });
    const mod: { exports: Record<string, unknown> } = { exports: {} };
    const requireStub = (id: string) => (Object.prototype.hasOwnProperty.call(stubs, id) ? stubs[id] : inert);
    new Function('require', 'module', 'exports', outputText)(requireStub, mod, mod.exports);
    return mod.exports.__internals as Record<string, any>;
}

// ── RevealExplanation: pending sections ───────────────────────────────────

const REVEAL = 'src/components/question/RevealExplanation.tsx';
const reveal = loadInternals(REVEAL, ['readSections', 'pollPendingSections', 'PENDING_RETRY_DELAYS_MS'], {
    '@/components/question/practiceData': practiceData,
});
const SECTIONS = ['why_correct', 'clinical_significance', 'memory_trick', 'concept'];
const ok = (status: number, data: unknown) => ({ status: 'fulfilled', value: { status, data } });
const failed = () => ({ status: 'rejected', reason: new Error('Network Error') });
const noUpdate = { texts: {}, pending: [], rateLimited: false, stalled: false };

test('RevealExplanation reads stored text, 202 pending, rate_limited and empty sections', () => {
    assert.deepEqual(reveal.readSections(SECTIONS, [
        ok(200, { why_correct: 'The ductus closes within 72 h of birth.' }),
        ok(202, { clinical_significance: null, pending: true }),
        ok(200, { memory_trick: null, rate_limited: true }),
        ok(200, { concept: null }),
    ], false), {
        texts: { why_correct: 'The ductus closes within 72 h of birth.' },
        pending: ['clinical_significance'],
        rateLimited: true,
        stalled: false,
    });
    // HTTP 202 alone, or the flag alone, both mean "still generating".
    assert.deepEqual(reveal.readSections(['concept', 'memory_trick'], [
        ok(202, { concept: null }),
        ok(200, { memory_trick: null, pending: true }),
    ], false).pending, ['concept', 'memory_trick']);
    // Nothing stored (AI offline), locked for the plan, or a template
    // fallback: hidden, never pending.
    assert.deepEqual(reveal.readSections(SECTIONS, [
        ok(200, { why_correct: null }),
        ok(200, { clinical_significance: null, locked: true }),
        ok(200, { memory_trick: 'Mnemonic: look for the first-letter pattern across the four options.' }),
        ok(200, {}),
    ], false), noUpdate);
});

test('RevealExplanation: a failed GET hides the section on the first load, and is retried while polling', () => {
    assert.deepEqual(reveal.readSections(['concept'], [failed()], false), noUpdate);
    assert.deepEqual(reveal.readSections(['concept'], [failed()], true).pending, ['concept']);
});

test('RevealExplanation re-fetches only the pending sections, with a growing delay', async () => {
    const waits: number[] = [];
    const rounds: string[][] = [];
    const replies: Record<string, Array<{ status: number; data: unknown }>> = {
        clinical_significance: [
            { status: 202, data: { clinical_significance: null, pending: true } },
            { status: 200, data: { clinical_significance: 'Duct-dependent lesions need prostaglandin E1.' } },
        ],
        concept: [{ status: 200, data: { concept: 'Ductus arteriosus closure' } }],
    };
    const updates: unknown[] = [];
    await reveal.pollPendingSections(
        ['clinical_significance', 'concept'],
        async (field: string) => {
            rounds[rounds.length - 1].push(field);
            return replies[field].shift();
        },
        async (ms: number) => { waits.push(ms); rounds.push([]); },
        () => true,
        (update: unknown) => updates.push(update),
    );
    assert.deepEqual(waits, reveal.PENDING_RETRY_DELAYS_MS.slice(0, 2));
    assert.deepEqual(rounds, [['clinical_significance', 'concept'], ['clinical_significance']]);
    assert.deepEqual(updates, [
        { texts: { concept: 'Ductus arteriosus closure' }, pending: ['clinical_significance'], rateLimited: false, stalled: false },
        { texts: { clinical_significance: 'Duct-dependent lesions need prostaglandin E1.' }, pending: [], rateLimited: false, stalled: false },
    ]);
});

test('RevealExplanation gives up after a few tries when the job never finishes (no endless spinner)', async () => {
    const delays: number[] = [...reveal.PENDING_RETRY_DELAYS_MS];
    assert.ok(delays.length >= 2 && delays.length <= 5, 'a few tries');
    assert.ok(delays.every((ms, i) => ms >= 3000 && (i === 0 || ms > delays[i - 1])), 'polite, growing delays');
    assert.ok(delays.reduce((sum, ms) => sum + ms, 0) <= 120000, 'gives up within two minutes');

    const waits: number[] = [];
    let calls = 0;
    const updates: unknown[] = [];
    await reveal.pollPendingSections(
        ['why_correct', 'memory_trick'],
        async (field: string) => { calls += 1; return { status: 202, data: { [field]: null, pending: true } }; },
        async (ms: number) => { waits.push(ms); },
        () => true,
        (update: unknown) => updates.push(update),
    );
    assert.deepEqual(waits, delays);
    assert.equal(calls, delays.length * 2);
    assert.equal(updates.length, delays.length + 1);
    assert.deepEqual(updates[updates.length - 1], { ...noUpdate, stalled: true });
});

test('RevealExplanation stops retrying once the panel closes or the question changes', async () => {
    let active = true;
    let calls = 0;
    const updates: unknown[] = [];
    // Closed while waiting: no request, no update.
    await reveal.pollPendingSections(
        ['concept'],
        async () => { calls += 1; return { status: 200, data: { concept: 'Too late' } }; },
        async () => { active = false; },
        () => active,
        (update: unknown) => updates.push(update),
    );
    assert.equal(calls, 0);
    // Closed while the request was in flight: its answer is dropped.
    active = true;
    await reveal.pollPendingSections(
        ['concept'],
        async () => { calls += 1; active = false; return { status: 200, data: { concept: 'Too late' } }; },
        async () => {},
        () => active,
        (update: unknown) => updates.push(update),
    );
    assert.equal(calls, 1);
    assert.deepEqual(updates, []);
});

test('RevealExplanation: a retry can hit the hourly limit, empty out, or fail and be tried again', async () => {
    let conceptCalls = 0;
    const waits: number[] = [];
    const updates: unknown[] = [];
    await reveal.pollPendingSections(
        ['why_correct', 'memory_trick', 'concept'],
        async (field: string) => {
            if (field === 'why_correct') return { status: 200, data: { why_correct: null, rate_limited: true } };
            if (field === 'memory_trick') return { status: 200, data: { memory_trick: null } };
            conceptCalls += 1;
            if (conceptCalls === 1) throw new Error('Network Error');
            return { status: 200, data: { concept: 'Ductus arteriosus closure' } };
        },
        async (ms: number) => { waits.push(ms); },
        () => true,
        (update: unknown) => updates.push(update),
    );
    assert.equal(waits.length, 2);
    assert.deepEqual(updates, [
        { texts: {}, pending: ['concept'], rateLimited: true, stalled: false },
        { texts: { concept: 'Ductus arteriosus closure' }, pending: [], rateLimited: false, stalled: false },
    ]);
});

test('RevealExplanation wiring: Generating… while pending, retries cancelled on close / unmount', () => {
    const src = read(REVEAL);
    // The four generated sections go through fetchSection, and so the retries.
    assert.match(src, /why_correct: "why_correct",\s*clinical_significance: "clinical",\s*memory_trick: "mnemonic",\s*concept: "concept",/);
    assert.match(src, /api\.get\(`\/questions\/\$\{questionId\}\/ai\/\$\{SECTION_PATHS\[field\]\}\/`\)/);
    assert.match(src, /readSections\(\["why_correct", "clinical_significance", "memory_trick", "concept"\], \[a, c, m, w\], false\)/);
    assert.match(src, /if \(first\.pending\.length\) await pollPendingSections\(first\.pending, fetchSection, sleep, \(\) => alive, apply\);/);
    assert.match(src, /retryTimer = setTimeout\(resolve, ms\)/);
    assert.match(src, /return \(\) => \{\s*alive = false;\s*if \(retryTimer !== undefined\) clearTimeout\(retryTimer\);\s*\};\s*\}, \[open, questionId\]\);/);
    for (const field of ['concept', 'why_correct', 'clinical_significance', 'memory_trick']) {
        assert.match(src, new RegExp(`\\|\\| pending\\.includes\\("${field}"\\) \\?`), field);
    }
    assert.match(src, /Generating…/);
    assert.match(src, /aria-busy=\{pending\.length > 0\}/);
    assert.match(src, /\{stalled \? \(/);
    assert.match(src, /taking longer than usual/);
    // The hourly-budget notice stays (practice-wave3 covers its wording).
    assert.match(src, /setRateLimited\(aiRateLimited\(\[a, c, m, e, w, wn\]\.map\(body\)\)\)/);
});

test('backend contract: ai/* GETs answer 202 {field: null, pending: true} or {field: null, rate_limited: true}', () => {
    const views = readBackend('questions/views.py');
    assert.match(views, /return Response\(\{field: None, 'pending': True\}, status=status\.HTTP_202_ACCEPTED\)/);
    assert.match(views, /payload\['rate_limited'\] = True/);
    const route = (urlPath: string) => {
        const at = views.indexOf(`url_path='${urlPath}'`);
        assert.ok(at >= 0, urlPath);
        return views.slice(at, at + 600);
    };
    assert.match(route('ai/why_correct'), /request, "why_correct",/);
    assert.match(route('ai/clinical'), /request, "clinical_significance",/);
    assert.match(route('ai/mnemonic'), /request, "memory_trick",/);
    assert.match(route('ai/concept'), /request, "concept",/);
    // why_incorrect is never generated, so it is never pending.
    assert.match(route('ai/why_incorrect'), /generate=False\)/);
});

// ── DiscussionThread: username ────────────────────────────────────────────

const THREAD = 'src/components/DiscussionThread.tsx';
const thread = loadInternals(THREAD, ['authorName', 'voteAfter', 'ANONYMOUS_AUTHOR']);

test('DiscussionThread shows the username, or "Learner" when the API sends null', () => {
    assert.equal(thread.ANONYMOUS_AUTHOR, 'Learner');
    assert.equal(thread.authorName('dr_meera'), 'dr_meera');
    assert.equal(thread.authorName('  ortho.ace '), 'ortho.ace');
    for (const value of [null, undefined, '', '   ', 42]) assert.equal(thread.authorName(value), 'Learner', String(value));
    // The avatar initial of an anonymous author.
    assert.equal(thread.authorName(null).charAt(0).toUpperCase(), 'L');

    const src = read(THREAD);
    assert.doesNotMatch(src, /user_name/);
    assert.match(src, /username: string \| null;/);
    assert.match(src, /\{authorName\(d\.username\)\.charAt\(0\)\.toUpperCase\(\)\}/);
    assert.match(src, /<span className="text-xs font-medium">\{authorName\(d\.username\)\}<\/span>/);
    assert.match(src, /<span className="text-\[11px\] font-medium">\{authorName\(r\.username\)\}<\/span>/);
});

test('DiscussionThread takes the vote from the response status (it has no user_vote)', () => {
    assert.equal(thread.voteAfter({ status: 'voted', upvotes: 3, downvotes: 0 }, 'up', null), 'up');
    assert.equal(thread.voteAfter({ status: 'vote_switched' }, 'down', 'up'), 'down');
    assert.equal(thread.voteAfter({ status: 'already_voted' }, 'up', 'up'), 'up');
    assert.equal(thread.voteAfter({ status: 'vote_removed' }, 'up', 'up'), null);
    assert.equal(thread.voteAfter({}, 'up', 'down'), 'down', 'an unknown answer keeps the previous vote');
    assert.equal(thread.voteAfter(null, 'down', null), null);
    assert.match(read(THREAD), /user_vote: voteAfter\(res\.data, voteType, d\.user_vote\)/);
});

test('backend contract: discussions send username (a handle or null) and the vote status', () => {
    const serializers = readBackend('questions/serializers.py');
    const serializer = serializers.slice(serializers.indexOf('class DiscussionSerializer'), serializers.indexOf('class NoteSerializer'));
    assert.match(serializer, /username = PublicHandleField\(source='user'\)/);
    assert.match(serializer, /fields = \[[^\]]*'username'/);
    assert.doesNotMatch(serializer, /user_name/);

    const views = readBackend('questions/views.py');
    const vote = views.slice(views.indexOf('class DiscussionVoteView'), views.indexOf('class NoteListCreateView'));
    for (const status of ['voted', 'vote_switched', 'already_voted', 'vote_removed']) {
        assert.match(vote, new RegExp(`'status': '${status}'`), status);
    }
    assert.doesNotMatch(vote, /user_vote/);
});

// ── Subscription page: scholarship result ─────────────────────────────────

const SUBSCRIPTION = 'src/app/subscription/page.tsx';
const subscription = loadInternals(SUBSCRIPTION, ['readScholarshipResult', 'allScholarshipAnswered']);

test('verify-scholarship: score 5 on a pass, null on a failure', () => {
    assert.deepEqual(
        subscription.readScholarshipResult({ status: 'passed', score: 5, message: 'Congratulations!' }),
        { status: 'passed', score: 5, message: 'Congratulations!' },
    );
    assert.deepEqual(
        subscription.readScholarshipResult({ status: 'failed', score: null, message: 'You did not get all 5 right.' }),
        { status: 'failed', score: null, message: 'You did not get all 5 right.' },
    );
    assert.equal(subscription.readScholarshipResult({ status: 'failed' }).score, null);
    assert.equal(subscription.readScholarshipResult({ status: 'failed', score: '3' }).score, null);
    assert.deepEqual(subscription.readScholarshipResult(null), { status: 'failed', score: null, message: '' });
});

test('scholarship Submit needs an A-D answer for every question', () => {
    const questions = [{ id: 11 }, { id: 12 }, { id: 13 }, { id: 14 }, { id: 15 }];
    const four = { 11: 'A', 12: 'B', 13: 'C', 14: 'D' };
    assert.equal(subscription.allScholarshipAnswered(questions, { ...four, 15: 'A' }), true);
    assert.equal(subscription.allScholarshipAnswered(questions, four), false);
    assert.equal(subscription.allScholarshipAnswered(questions, { ...four, 15: '' }), false);
    assert.equal(subscription.allScholarshipAnswered(questions, { ...four, 15: 'E' }), false);
    // Five answers are not enough when one belongs to another question.
    assert.equal(subscription.allScholarshipAnswered(questions, { ...four, 99: 'A' }), false);
    assert.equal(subscription.allScholarshipAnswered([], {}), false);
});

test('scholarship result UI: a breakdown only for a numeric score, never "null / 5"', () => {
    const src = read(SUBSCRIPTION);
    assert.match(src, /type ScholarshipResult = \{ status: 'passed' \| 'failed'; score: number \| null; message: string \}/);
    assert.match(src, /useState<ScholarshipResult \| null>\(null\)/);
    assert.match(src, /const result = readScholarshipResult\(res\.data\);/);
    assert.match(src, /if \(result\.score !== null\) \{\s*generateAiTestAnalysis\(result\.score, submissionAnswers, result\.message\);\s*\} else \{\s*setAiAnalysis\(null\);\s*setGeneratingAnalysis\(false\);\s*\}/);
    assert.equal(src.match(/generateAiTestAnalysis\(/g)?.length, 1, 'called once, for a numeric score');
    assert.doesNotMatch(src, /data\.score/);
    assert.match(src, /\) : testResult\.score === null \? \(/);
    assert.doesNotMatch(src, /instant score breakdown/i);
    assert.match(src, /Results are instant: score a perfect 5\/5/);
});

test('scholarship Submit is gated on every question, in the button and in the handler', () => {
    const src = read(SUBSCRIPTION);
    assert.match(src, /const submitScholarshipTest = async \(\) => \{\s*if \(!allScholarshipAnswered\(scholarshipQuestions, selectedAnswers\)\) \{/);
    assert.match(src, /disabled=\{testSubmitting \|\| !challengeToken \|\| !allScholarshipAnswered\(scholarshipQuestions, selectedAnswers\)\}/);
    assert.doesNotMatch(src, /Object\.keys\(selectedAnswers\)\.length/);
    assert.match(src, /QUESTION \{currentQuestionIdx \+ 1\} OF \{scholarshipQuestions\.length\}/);
    assert.match(src, /currentQuestionIdx < scholarshipQuestions\.length - 1 \?/);
});

test('backend contract: verify-scholarship refuses blanks and sends score null on a failure', () => {
    const views = readBackend('accounts/views.py');
    const verify = views.slice(views.indexOf('class VerifyScholarshipView'), views.indexOf('PURCHASABLE_PLANS = '));
    assert.match(verify, /"Answer all 5 questions before submitting\."\}, status=status\.HTTP_400_BAD_REQUEST/);
    assert.match(verify, /"status": "passed",\s*"score": SCHOLARSHIP_QUESTION_COUNT,/);
    assert.equal(verify.match(/"status": "failed",\s*"score": None,/g)?.length, 2);
});
