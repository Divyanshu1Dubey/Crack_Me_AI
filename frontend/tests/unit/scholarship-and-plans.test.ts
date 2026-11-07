/**
 * Scholarship challenge pool + plan copy (2026-11-07):
 *  - questionEditorListParams: the "Scholarship pool" filter sends is_scholarship_eligible=true
 *    (an admin-only filter on the backend) and leaves drag-reorder mode
 *  - scholarshipToggleError: the server's refusal reason (400 scholarship_refused) is shown as is
 *  - source wiring: the editor modal saves the flag through its own endpoint, the challenge keeps
 *    numbered statements on their own lines and no longer claims negative marking
 *  - plan copy lists only what the site gives: no topic notes, personal notes, textbook page
 *    screenshots, "expert guidance" or "100+ tests", and no "explanations for every question"
 *
 * Run (from frontend/):
 *   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/scholarship-and-plans.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  isReorderMode,
  questionEditorListParams,
  scholarshipToggleError,
} from '../../src/app/admin/_lib/adminHelpers.ts';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const read = (rel: string) => readFileSync(path.join(ROOT, rel), 'utf8');

test('questionEditorListParams: the scholarship pool filter is sent and leaves reorder mode', () => {
  const filters = { examType: 'cms', year: '2024', inScholarshipPool: true };
  assert.equal(isReorderMode(filters), false);
  assert.deepEqual(questionEditorListParams(filters, 1, 20), {
    page: 1, page_size: 20, exam_type: 'cms', year: '2024', is_scholarship_eligible: 'true',
  });
  assert.equal('is_scholarship_eligible' in questionEditorListParams({ examType: 'cms' }, 1, 20), false);
});

test('scholarshipToggleError: the refusal reason, else the server sentence, else a generic one', () => {
  const refused = { response: { data: { code: 'scholarship_refused', reason: 'figure',
    detail: 'The challenge shows text only, and this question has a figure.' } } };
  assert.equal(scholarshipToggleError(refused), 'The challenge shows text only, and this question has a figure.');
  assert.equal(scholarshipToggleError({ response: { data: { error: 'eligible must be true or false' } } }),
    'eligible must be true or false');
  for (const err of [new Error('Network Error'), null, undefined, { response: { data: { detail: '  ' } } }]) {
    assert.equal(scholarshipToggleError(err), 'The scholarship setting could not be saved. Please try again.');
  }
});

test('the editor saves the scholarship flag through its own endpoint, never the form PATCH', () => {
  const api = read('src/lib/api.ts');
  assert.match(api, /setScholarship: \(id: number, eligible: boolean\)/);
  assert.match(api, /`\/questions\/\$\{id\}\/scholarship\/`, \{ eligible \}/);
  const modal = read('src/app/admin/questions-editor/QuestionEditModal.tsx');
  assert.match(modal, /<ScholarshipToggle/);
  const helpers = read('src/app/admin/_lib/adminHelpers.ts');
  const payloadBuilder = helpers.slice(helpers.indexOf('export function buildQuestionEditPayload'));
  assert.equal(payloadBuilder.slice(0, payloadBuilder.indexOf('\n}\n')).includes('is_scholarship_eligible'), false);
});

test('the challenge keeps line breaks and states its real rule', () => {
  const page = read('src/app/subscription/page.tsx');
  assert.match(page, /whitespace-pre-line">\s*\{scholarshipQuestions\[currentQuestionIdx\]\.question_text\}/);
  assert.equal(page.includes('Negative marking active'), false);
  assert.match(page, /All 5 must be correct/);
  assert.match(page, /You get 2 attempts/);
});

test('plan copy lists only what the site gives', () => {
  const sources = [
    read('src/app/subscription/page.tsx'),
    read('src/app/_landing/LandingPage.tsx'),
    read('src/app/tests/[id]/page.tsx'),
    read('public/llms-full.txt'),
  ].join('\n');
  for (const claim of [
    /Topic notes & summaries/i, /Topic Notes & Summaries/, /textbook screenshots/i, /Textbook References/,
    /expert guidance/i, /Personali[sz]ed checklist/i, /national leaderboard/i, /100\+ tests/,
    /explanations for every question/i, /mnemonics for every question/i, /bookmarks, notes/i,
  ]) {
    assert.equal(claim.test(sources), false, String(claim));
  }
  const subscription = read('src/app/subscription/page.tsx');
  assert.match(subscription, /const sharedPremiumFeatures = \[/);
  for (const plan of ['1_month', '3_months', '1_year']) {
    // \s* rather than "\n" + indent: the file may be checked out with CRLF line endings.
    const match = new RegExp(`'${plan}': \\{\\s*description:`).exec(subscription);
    assert.ok(match, plan);
    assert.match(subscription.slice(match.index, match.index + 400), /\.\.\.sharedPremiumFeatures/, plan);
  }
});
