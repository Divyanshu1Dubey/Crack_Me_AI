/**
 * AI Question Generator batch size (frontend/src/components/QuestionComposer/limits.ts):
 * 15 and 20 MCQs per batch only for unlimited-AI users (1-year / lifetime / admin-granted plans,
 * admins, staff); everyone else up to 10, with 15 / 20 shown as locked 1-year plan options.
 * The backend (ai_engine.views.GenerateQuestionsView) enforces the same cap with a 402.
 *
 *   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/question-generator-limits.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { COUNT_OPTIONS } from '../../src/components/QuestionComposer/constants.ts';
import {
  LARGE_BATCH_FEATURE,
  PREMIUM_MAX_COUNT,
  STANDARD_MAX_COUNT,
  countOptions,
  isCountLocked,
  isUpgradeRequired,
  maxGenerationCount,
} from '../../src/components/QuestionComposer/limits.ts';
import { isUnmeteredAi } from '../../src/hooks/unmeteredAi.ts';

const FRONTEND = fileURLToPath(new URL('../../', import.meta.url));
const BACKEND = fileURLToPath(new URL('../../../backend/', import.meta.url));
const read = (root: string, rel: string) => readFileSync(path.join(root, rel), 'utf8');

test('the batch limit is 20 with unlimited AI and 10 otherwise', () => {
  assert.equal(STANDARD_MAX_COUNT, 10);
  assert.equal(PREMIUM_MAX_COUNT, 20);
  assert.equal(maxGenerationCount(true), 20);
  assert.equal(maxGenerationCount(false), 10);
  assert.equal(isCountLocked(20, false), true);
  assert.equal(isCountLocked(15, false), true);
  assert.equal(isCountLocked(10, false), false);
  assert.equal(isCountLocked(20, true), false);
  assert.ok(Math.max(...COUNT_OPTIONS) <= PREMIUM_MAX_COUNT);
});

test('without unlimited AI, 15 and 20 are listed as locked 1-year plan options', () => {
  const options = countOptions(false);
  assert.deepEqual(options.map((o) => o.value), [...COUNT_OPTIONS]);
  assert.deepEqual(options.filter((o) => o.locked).map((o) => o.value), [15, 20]);
  for (const o of options) {
    if (o.locked) assert.match(o.label, new RegExp(`^${o.value} · 1-year plan`));
    else assert.equal(o.label, String(o.value));
  }
});

test('with unlimited AI every count can be picked', () => {
  const options = countOptions(true);
  assert.equal(options.some((o) => o.locked), false);
  assert.deepEqual(options.map((o) => o.label), COUNT_OPTIONS.map(String));
});

test('who counts as unlimited is the shared isUnmeteredAi rule', () => {
  const yearly = { subscription_info: { plan: '1_year', is_active: true } };
  const monthly = { subscription_info: { plan: '1_month', is_active: true } };
  assert.equal(maxGenerationCount(isUnmeteredAi(null, yearly)), 20);
  assert.equal(maxGenerationCount(isUnmeteredAi(null, monthly)), 10);
  assert.equal(maxGenerationCount(isUnmeteredAi({ unlimited_ai: true }, monthly)), 20);
  assert.equal(maxGenerationCount(isUnmeteredAi(null, { is_admin: true })), 20);
  assert.equal(maxGenerationCount(isUnmeteredAi(null, { is_staff: true })), 20);
  assert.equal(maxGenerationCount(isUnmeteredAi(null, null)), 10);
});

test('isUpgradeRequired recognises the paywall answer only', () => {
  const refusal = { response: { status: 402, data: { code: 'upgrade_required', feature: LARGE_BATCH_FEATURE } } };
  assert.equal(isUpgradeRequired(refusal), true);
  assert.equal(isUpgradeRequired({ response: { status: 503, data: { code: 'ai_unavailable' } } }), false);
  assert.equal(isUpgradeRequired({ response: { status: 429, data: { error: 'insufficient_tokens' } } }), false);
  assert.equal(isUpgradeRequired(new Error('Network Error')), false);
  assert.equal(isUpgradeRequired(null), false);
  assert.equal(isUpgradeRequired(undefined), false);
});

test('frontend and backend agree on the cap and the paywall feature', () => {
  const view = read(BACKEND, 'ai_engine/views.py');
  assert.match(view, /STANDARD_MAX_COUNT = 10\b/);
  assert.match(view, /UNLIMITED_MAX_COUNT = 20\b/);
  assert.ok(view.includes(`LARGE_BATCH_FEATURE = '${LARGE_BATCH_FEATURE}'`));
  assert.match(view, /status=status\.HTTP_402_PAYMENT_REQUIRED/);
});

test('the composer locks counts above the limit and opens the upgrade modal instead', () => {
  const controls = read(FRONTEND, 'src/components/QuestionComposer/GenerateControls.tsx');
  assert.match(controls, /useGenerationLimit\(\)/);
  assert.match(controls, /countOptions\(unlimitedAi\)/);
  assert.match(controls, /showPaywall\(LARGE_BATCH_FEATURE\)/);
  assert.doesNotMatch(controls, /COUNT_OPTIONS\.map/);
  // The 402 is a message in the error banner, not a crash or a generic failure.
  const hook = read(FRONTEND, 'src/components/QuestionComposer/useGenerate.ts');
  assert.match(hook, /isUpgradeRequired\(err\)/);
});
