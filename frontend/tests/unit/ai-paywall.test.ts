/**
 * Wave 3 (group Z5-ai) — AI wallet, paywall copy and Topic Notes:
 *  - isUnmeteredAi (contract C12): admins, staff and unlimited-AI plans are
 *    not token-metered; the wallet's `unlimited_ai` wins over the plan.
 *  - UpgradeModal (C14 + unbacked claims): no "deep analytics", adaptive
 *    tests, mock-test counts, user counts, provider counts or PDF export.
 *  - UsageBanner: readable in light mode (dark text on the light tint),
 *    visible dismiss button, storage access cannot throw.
 *  - /topic-notes: login redirect via useRequireAuth, no own app shell
 *    (contract C6), admin library paging, no double gutter inside the
 *    AppShell.
 *  - /topic-notes, /feedback and /tokens call the typed api.ts helpers.
 *
 * Run (from frontend/):
 *   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/ai-paywall.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { UNLIMITED_AI_PLANS, isUnmeteredAi } from '../../src/hooks/unmeteredAi.ts';

const FRONTEND = fileURLToPath(new URL('../../', import.meta.url));
const read = (rel: string) => readFileSync(path.join(FRONTEND, rel), 'utf8');

// ── C12: unmetered AI ──────────────────────────────────────────────────────

test('isUnmeteredAi: admins and staff are never metered', () => {
  assert.equal(isUnmeteredAi({ is_admin: true }, null), true);
  assert.equal(isUnmeteredAi(null, { is_admin: true }), true);
  assert.equal(isUnmeteredAi(null, { is_staff: true }), true);
  // An admin stays unmetered even if the wallet says the plan is metered.
  assert.equal(isUnmeteredAi({ unlimited_ai: false }, { is_admin: true }), true);
});

test('isUnmeteredAi: the wallet flag wins over the profile plan', () => {
  const yearly = { subscription_info: { plan: '1_year', is_active: true } };
  const monthly = { subscription_info: { plan: '1_month', is_active: true } };
  assert.equal(isUnmeteredAi({ unlimited_ai: true }, monthly), true);
  assert.equal(isUnmeteredAi({ unlimited_ai: false }, yearly), false);
});

test('isUnmeteredAi: falls back to an active unlimited-AI plan', () => {
  for (const plan of ['1_year', 'legacy', 'admin_grant']) {
    assert.ok(UNLIMITED_AI_PLANS.has(plan));
    assert.equal(isUnmeteredAi({}, { subscription_info: { plan, is_active: true } }), true, plan);
    assert.equal(isUnmeteredAi({}, { subscription_info: { plan, is_active: false } }), false, plan);
  }
  for (const plan of ['1_month', '3_months', 'scholarship_1_month']) {
    assert.equal(isUnmeteredAi({}, { subscription_info: { plan, is_active: true } }), false, plan);
  }
  assert.equal(isUnmeteredAi(null, null), false);
  assert.equal(isUnmeteredAi(undefined, { subscription_info: null }), false);
});

test('useTokenWallet re-exports the shared rule', () => {
  const src = read('src/hooks/useTokenWallet.ts');
  assert.match(src, /export \{ isUnmeteredAi, UNLIMITED_AI_PLANS \} from '\.\/unmeteredAi'/);
  assert.doesNotMatch(src, /export function isUnmeteredAi/);
});

// ── UpgradeModal copy ──────────────────────────────────────────────────────

test('UpgradeModal makes no unbacked premium claims', () => {
  const src = read('src/components/paywall/UpgradeModal.tsx');
  const copy = src.replace(/\{\/\*[\s\S]*?\*\/\}/g, ''); // drop JSX comments
  for (const claim of [
    /deep analytics/i,          // C14: /analytics is free
    /adaptive/i,                // no adaptive-test UI exists
    /100\+/,                    // no data source for a mock-test count
    /10,000\+/,                 // no data source for a user count
    /11-provider/i,             // the rotation has 10 entries; not a feature
    /PDF export/i,              // not implemented
    /Cancel anytime/i,          // passes are one-time payments, nothing to cancel
    /Unlimited AI Tutor/,       // unlimited AI is the 1-year plan only
    /unlimited access/i,
  ]) {
    assert.doesNotMatch(copy, claim, String(claim));
  }
  assert.match(copy, /unlimited on the 1-year plan/);
  assert.match(copy, /No auto-renewal/);
});

// ── UsageBanner ────────────────────────────────────────────────────────────

test('UsageBanner text is readable in light and dark mode', () => {
  const src = read('src/components/paywall/UsageBanner.tsx');
  assert.match(src, /text-rose-900 dark:text-rose-100/);
  assert.match(src, /text-amber-900 dark:text-amber-100/);
  // No light-only text colour left on the tinted banner.
  assert.doesNotMatch(src, /['\s]text-(rose|amber)-100['\s`]/);
  assert.doesNotMatch(src, /text-current\/70/);
  assert.match(src, /hover:bg-black\/5 dark:hover:bg-white\/10/);
  assert.match(src, /aria-label="Dismiss banner"/);
  assert.doesNotMatch(src, /unlimited AI Tutor/);
});

test('UsageBanner never lets storage access throw', () => {
  const src = read('src/components/paywall/UsageBanner.tsx');
  for (const fn of ['readDismissed', 'writeDismissed']) {
    const body = src.slice(src.indexOf(`function ${fn}`));
    const block = body.slice(0, body.indexOf('\n}\n'));
    assert.match(block, /try \{/, `${fn} guards storage`);
    assert.match(block, /catch/, `${fn} guards storage`);
  }
});

// ── /topic-notes ───────────────────────────────────────────────────────────

test('/topic-notes redirects logged-out visitors and renders no own shell', () => {
  const page = read('src/app/topic-notes/page.tsx');
  assert.match(page, /useRequireAuth\(\)/);
  assert.doesNotMatch(page, /from '@\/components\/(Sidebar|Header)'/);
  assert.doesNotMatch(page, /<main[\s>]/);
  assert.match(read('src/app/topic-notes/layout.tsx'), /<AppShell>/);
});

test('/topic-notes pages through the published notes; admins manage them at /admin/notes', () => {
  const page = read('src/app/topic-notes/page.tsx');
  assert.match(page, /notesAPI\.published\(\{ \.\.\.noteListParams\(\{ exam, subject, topic, q: search, page: next \}\), page_size: PAGE_SIZE \}\)/);
  assert.match(page, /href="\/admin\/notes"/);
  assert.doesNotMatch(page, /topicNotesAPI\.adminList/);
});

test('/topic-notes: page padding collapses inside the AppShell (no double gutter)', () => {
  for (const rel of ['src/app/topic-notes/page.tsx', 'src/app/topic-notes/[id]/page.tsx']) {
    const page = read(rel);
    assert.match(page, /className="mx-auto max-w-(?:4xl|3xl) space-y-\d p-4 text-foreground md:p-6 \[\.page-container_&\]:p-0"/, rel);
    assert.doesNotMatch(page, /<main[\s>]/, rel);
  }
});

test('/topic-notes, /feedback and /tokens call the typed api.ts helpers', () => {
  const api = read('src/lib/api.ts');
  // The helpers request exactly what the pages requested before.
  assert.match(api, /api\.get\('\/questions\/topic-notes\/published\/', \{ params \}\)/);
  assert.match(read('src/lib/notesAPI.ts'), /api\.get\('\/questions\/topic-notes\/published\/', \{ params \}\)/);
  assert.match(api, /api\.get\('\/analytics\/feedback\/', \{ params \}\)/);
  assert.match(api, /api\.get\('\/auth\/tokens\/admin\/users\/', \{ params \}\)/);

  const pages: Record<string, [string, RegExp]> = {
    'topic-notes': [read('src/app/topic-notes/page.tsx'), /notesAPI\.published\(\{ \.\.\.noteListParams\(/],
    feedback: [read('src/app/feedback/page.tsx'), /analyticsAPI\.getFeedback\(\{ page, page_size: FEEDBACK_PAGE_SIZE \}\)/],
    tokens: [read('src/app/tokens/page.tsx'), /authAPI\.adminGetAllUsers\(offset > 0 \? \{ offset \} : undefined\)/],
  };
  for (const [name, [src, helper]] of Object.entries(pages)) {
    assert.match(src, helper, name);
    assert.doesNotMatch(src, /import api\b/, name);
    assert.doesNotMatch(src, /\bapi\.(get|post|patch|put|delete)\(/, name);
  }
});
