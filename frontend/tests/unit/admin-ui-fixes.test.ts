/**
 * Unit tests for the wave-2 admin UI fixes:
 *  - computeDisplayRenumber refuses non-contiguous / inactive paper sets (QE-02)
 *  - formatCount / percentOf (overview stats and the answer-coverage bar)
 *  - loadErrorMessage (per-section errors on /admin/recall)
 *  - adminTestListParams (Tests tab: library / drafts / all, paginated)
 *  - resolveImageTokens cache: keyed by content, bounded (QE-04)
 *
 * Run (from frontend/; imageTokens.ts has an extension-less import, so the
 * alias hook is needed):
 *   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/admin-ui-fixes.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  adminTestListParams,
  computeDisplayRenumber,
  formatCount,
  loadErrorMessage,
  percentOf,
} from '../../src/app/admin/_lib/adminHelpers.ts';
import {
  IMAGE_TOKEN_CACHE_LIMIT,
  clearImageTokenCache,
  imageTokenCacheSize,
  resolveImageTokens,
} from '../../src/lib/imageTokens.ts';

// ── QE-02: drag-to-reorder must not renumber past questions the admin never saw ──

test('computeDisplayRenumber refuses a paper whose visible numbers have gaps (10, 49, 50, 98)', () => {
  const rows = [
    { id: 1, display_number: 10, paper: 1 },
    { id: 2, display_number: 49, paper: 1 },
    { id: 3, display_number: 50, paper: 1 },
    { id: 4, display_number: 98, paper: 1 },
  ];
  // Dragging #98 to the top used to make it #10 and push the old #10 to #49.
  const result = computeDisplayRenumber(rows, 3, 0);
  assert.equal(result.ok, false);
  if (!result.ok) assert.match(result.reason, /10-98/);
});

test('computeDisplayRenumber refuses repeated numbers within the paper', () => {
  const rows = [
    { id: 1, display_number: 5, paper: 2 },
    { id: 2, display_number: 5, paper: 2 },
    { id: 3, display_number: 6, paper: 2 },
  ];
  assert.equal(computeDisplayRenumber(rows, 2, 0).ok, false);
});

test('computeDisplayRenumber refuses when a removed (inactive) question of the paper is listed', () => {
  const rows = [
    { id: 1, display_number: 1, paper: 1, is_active: true },
    { id: 2, display_number: 2, paper: 1, is_active: false },
    { id: 3, display_number: 3, paper: 1, is_active: true },
  ];
  const result = computeDisplayRenumber(rows, 2, 0);
  assert.equal(result.ok, false);
  if (!result.ok) assert.match(result.reason, /Removed questions/);
});

test('computeDisplayRenumber only checks the dragged paper: gaps in another paper do not block it', () => {
  const rows = [
    { id: 1, display_number: 41, paper: 1 },
    { id: 2, display_number: 1, paper: 2 },
    { id: 3, display_number: 42, paper: 1 },
    { id: 4, display_number: 7, paper: 2 },
    { id: 5, display_number: 43, paper: 1, is_active: true },
  ];
  const result = computeDisplayRenumber(rows, 4, 0);
  assert.equal(result.ok, true);
  if (!result.ok) return;
  assert.deepEqual(
    result.rows.filter((r) => r.paper === 1).map((r) => [r.id, r.display_number]),
    [[5, 41], [1, 42], [3, 43]],
  );
  // Paper 2 is untouched.
  assert.deepEqual(result.rows.filter((r) => r.paper === 2).map((r) => [r.id, r.display_number]), [[2, 1], [4, 7]]);
  assert.deepEqual(result.changes, [
    { id: 5, display_number: 41 },
    { id: 1, display_number: 42 },
    { id: 3, display_number: 43 },
  ]);
});

// ── Overview numbers ────────────────────────────────────────────────────────

test('formatCount uses en-IN separators and never shows NaN/undefined', () => {
  assert.equal(formatCount(13788), '13,788');
  assert.equal(formatCount(137880), '1,37,880');
  assert.equal(formatCount('42'), '42');
  assert.equal(formatCount(0), '0');
  assert.equal(formatCount(null), '0');
  assert.equal(formatCount(undefined), '0');
  assert.equal(formatCount('abc'), '0');
});

test('percentOf drives the answer-coverage bar (the API has no answer_percentage field)', () => {
  assert.equal(Math.round(percentOf(13278, 13788) * 10) / 10, 96.3);
  assert.equal(percentOf(5, 0), 0);
  assert.equal(percentOf(5, undefined), 0);
  assert.equal(percentOf(undefined, 10), 0);
  assert.equal(percentOf(12, 10), 100);
  assert.equal(percentOf(-3, 10), 0);
});

// ── /admin/recall: one failing section must not blank the page ──────────────

test('loadErrorMessage maps HTTP status to admin-facing copy (no raw axios text)', () => {
  assert.equal(loadErrorMessage({ response: { status: 429 } }, 'recall sources'), 'Too many requests. Try again in a minute.');
  assert.equal(loadErrorMessage({ response: { status: 500 } }, 'import jobs'), "Couldn't load import jobs (server error).");
  assert.equal(loadErrorMessage({ response: { status: 503 } }, 'import jobs'), "Couldn't load import jobs (server error).");
  assert.equal(loadErrorMessage({ response: { status: 403 } }, 'import jobs'), 'You do not have access to import jobs.');
  assert.equal(loadErrorMessage({ response: { status: 404 } }, 'duplicate clusters'), "Couldn't load duplicate clusters.");
  assert.equal(
    loadErrorMessage(new Error('Network Error'), 'duplicate clusters'),
    "Couldn't load duplicate clusters. Check your connection and retry.",
  );
  assert.equal(loadErrorMessage(null, 'x'), "Couldn't load x. Check your connection and retry.");
});

// ── Tests tab (TE-14): library by default, drafts, everything; paginated ────

test('adminTestListParams scopes and pages the admin tests list', () => {
  assert.deepEqual(adminTestListParams('library', 1), { page: '1', scope: 'library' });
  assert.deepEqual(adminTestListParams('drafts', 2), { page: '2', scope: 'mine', is_published: 'false' });
  assert.deepEqual(adminTestListParams('all', 3), { page: '3' });
  assert.deepEqual(adminTestListParams('library', 0), { page: '1', scope: 'library' });
  assert.deepEqual(adminTestListParams('all', Number.NaN), { page: '1' });
});

// ── QE-04: image-token cache keyed by content and bounded ───────────────────

test('resolveImageTokens returns the new text for the same caller key (no stale cache hit)', () => {
  clearImageTokenCache();
  const images = [{ id: 7, url: '/api/questions/images/7/serve/' }];
  const first = resolveImageTokens('Old stem [[img:7]]', images, 'q1:v1');
  const second = resolveImageTokens('Edited stem [[img:7]]', images, 'q1:v1');
  assert.match(first, /^Old stem <img /);
  assert.match(second, /^Edited stem <img /);
  // Same text and images: served from the cache, identical output.
  assert.equal(resolveImageTokens('Edited stem [[img:7]]', images, 'q1:v1'), second);
});

test('resolveImageTokens re-renders when an image changes (caption / url), not just the count', () => {
  clearImageTokenCache();
  const text = 'See [[img:3]]';
  const a = resolveImageTokens(text, [{ id: 3, url: '/a.png', caption: 'ECG' }], 'q9');
  const b = resolveImageTokens(text, [{ id: 3, url: '/a.png', caption: 'Chest X-ray' }], 'q9');
  const c = resolveImageTokens(text, [{ id: 3, url: '/b.png', caption: 'Chest X-ray' }], 'q9');
  assert.match(a, /alt="ECG"/);
  assert.match(b, /alt="Chest X-ray"/);
  assert.match(c, /src="\/b\.png"/);
});

test('resolveImageTokens cache stays bounded during a long editing session', () => {
  clearImageTokenCache();
  for (let i = 0; i < IMAGE_TOKEN_CACHE_LIMIT + 75; i += 1) {
    resolveImageTokens(`Draft ${i} of a long stem`, [], 'qe:42');
  }
  assert.equal(imageTokenCacheSize(), IMAGE_TOKEN_CACHE_LIMIT);
  // The most recent entry is still cached and correct.
  assert.equal(
    resolveImageTokens(`Draft ${IMAGE_TOKEN_CACHE_LIMIT + 74} of a long stem`, [], 'qe:42'),
    `Draft ${IMAGE_TOKEN_CACHE_LIMIT + 74} of a long stem`,
  );
  assert.equal(imageTokenCacheSize(), IMAGE_TOKEN_CACHE_LIMIT);
  clearImageTokenCache();
  assert.equal(imageTokenCacheSize(), 0);
});

test('resolveImageTokens still escapes admin-typed markup', () => {
  clearImageTokenCache();
  const out = resolveImageTokens('<img src=x onerror=alert(1)>', []);
  assert.equal(out.includes('<img src=x'), false);
  assert.match(out, /&amp;lt;img|&lt;img/);
});
