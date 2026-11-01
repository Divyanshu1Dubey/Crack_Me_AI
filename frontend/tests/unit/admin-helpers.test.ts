/**
 * Unit tests for the admin page helpers (frontend/src/app/admin/_lib/adminHelpers.ts).
 *
 * Run with Node's built-in runner (Node >= 22.18 strips TypeScript types):
 *   node --test tests/unit/admin-helpers.test.ts
 *
 * `tests/` is excluded from tsconfig, so the explicit `.ts` import below does
 * not affect `tsc --noEmit -p .`.
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  PLATFORM_WIDE_CONFIRM_PHRASE,
  SIMILAR_ENDPOINT_LIMIT,
  buildQuestionEditPayload,
  buildYearOptions,
  computeDisplayRenumber,
  curatedRelatedIds,
  fetchAllPages,
  hasNextPage,
  isPlatformWideConfirmed,
  isValidAnswerLetter,
  listCount,
  listRows,
  matchesQuestionConfirm,
  parseConceptKeywords,
  parseRelatedIds,
  questionSearchParams,
  sameIdSet,
  unpersistedEditFields,
} from '../../src/app/admin/_lib/adminHelpers.ts';

// A fake DRF list endpoint: `pageSize` rows per page, `next` while more remain.
function fakeDrfEndpoint(total: number, pageSize: number) {
  const calls: number[] = [];
  const fetchPage = async (page: number) => {
    calls.push(page);
    const start = (page - 1) * pageSize;
    const results = Array.from({ length: Math.max(0, Math.min(pageSize, total - start)) }, (_, i) => ({ id: start + i + 1 }));
    const next = start + pageSize < total ? `http://api.example/x/?page=${page + 1}` : null;
    return { count: total, next, previous: null, results };
  };
  return { fetchPage, calls };
}

// ── ADM-04 / ADM-09 / NOTES-01: paginated lists ────────────────────────────

test('listRows / hasNextPage / listCount handle paginated, bare and empty payloads', () => {
  const paged = { count: 41, next: 'http://x/?page=2', results: [{ id: 1 }, { id: 2 }] };
  assert.deepEqual(listRows(paged), [{ id: 1 }, { id: 2 }]);
  assert.equal(hasNextPage(paged), true);
  assert.equal(listCount(paged), 41);

  assert.deepEqual(listRows([{ id: 3 }]), [{ id: 3 }]);
  assert.equal(hasNextPage([{ id: 3 }]), false);
  assert.equal(listCount([{ id: 3 }]), 1);

  assert.deepEqual(listRows(null), []);
  assert.deepEqual(listRows({ detail: 'nope' }), []);
  assert.equal(hasNextPage({ results: [], next: null }), false);
});

test('fetchAllPages follows `next` until exhausted (backend ignoring page_size: 45 rows, 20 per page)', async () => {
  const { fetchPage, calls } = fakeDrfEndpoint(45, 20);
  const rows = await fetchAllPages<{ id: number }>(fetchPage);
  assert.equal(rows.length, 45);
  assert.deepEqual(rows.map((r) => r.id), Array.from({ length: 45 }, (_, i) => i + 1));
  assert.deepEqual(calls, [1, 2, 3]);
});

test('fetchAllPages makes one request when page_size=100 is honoured for ~40 subjects', async () => {
  const { fetchPage, calls } = fakeDrfEndpoint(40, 100);
  const rows = await fetchAllPages(fetchPage);
  assert.equal(rows.length, 40);
  assert.deepEqual(calls, [1]);
});

test('fetchAllPages loads a 712-topic subject in full (was clipped to the first 20)', async () => {
  const { fetchPage } = fakeDrfEndpoint(712, 20);
  const rows = await fetchAllPages(fetchPage);
  assert.equal(rows.length, 712);
});

test('fetchAllPages stops at maxPages, on an empty page and for unpaginated endpoints', async () => {
  const runaway = async (page: number) => ({ count: 9999, next: 'http://x/?page=again', results: [{ id: page }] });
  const capped = await fetchAllPages(runaway, 3);
  assert.equal(capped.length, 3);

  let emptyCalls = 0;
  const empty = async () => { emptyCalls += 1; return { count: 5, next: 'http://x/?page=2', results: [] }; };
  assert.deepEqual(await fetchAllPages(empty), []);
  assert.equal(emptyCalls, 1);

  let bareCalls = 0;
  const bare = async () => { bareCalls += 1; return [{ id: 1 }, { id: 2 }]; };
  assert.equal((await fetchAllPages(bare)).length, 2);
  assert.equal(bareCalls, 1);
});

test('fetchAllPages propagates request errors (callers keep their previous state)', async () => {
  const failing = async (page: number) => {
    if (page === 2) throw new Error('429');
    return { count: 40, next: 'http://x/?page=2', results: [{ id: 1 }] };
  };
  await assert.rejects(fetchAllPages(failing), /429/);
});

// ── ADM-02: related PYQ links are only rewritten when the field changed ────

test('parseRelatedIds keeps positive integers only', () => {
  assert.deepEqual(parseRelatedIds('12, 45,90'), [12, 45, 90]);
  assert.deepEqual(parseRelatedIds(' 12 , abc, -3, 0, 4.5, 7 '), [12, 7]);
  assert.deepEqual(parseRelatedIds(''), []);
});

test('sameIdSet: an untouched or reordered field is "unchanged" (no linkRelatedPyqs call)', () => {
  // The inline save calls linkRelatedPyqs only when !sameIdSet(current, initial).
  assert.equal(sameIdSet(parseRelatedIds(''), parseRelatedIds('')), true);
  assert.equal(sameIdSet(parseRelatedIds('12, 45'), parseRelatedIds('45,12')), true);
  assert.equal(sameIdSet(parseRelatedIds('12, 45, 45'), parseRelatedIds('12,45')), true);
  assert.equal(sameIdSet(parseRelatedIds('12, 45'), parseRelatedIds('12')), false);
  assert.equal(sameIdSet(parseRelatedIds(''), parseRelatedIds('12')), false);
});

test('curatedRelatedIds picks the admin-curated rows of /questions/<id>/similar/', () => {
  const similar = [
    { id: 5, similarity_reason: 'curated' },
    { id: 9, similarity_reason: 'same_topic' },
    { id: 11, similarity_reason: 'curated' },
    { id: 'x', similarity_reason: 'curated' },
  ];
  assert.deepEqual(curatedRelatedIds(similar), [5, 11]);
  assert.deepEqual(curatedRelatedIds(null), []);
  assert.equal(SIMILAR_ENDPOINT_LIMIT, 8);
});

// ── ADM-01: platform-wide actions need the typed phrase ────────────────────

test('isPlatformWideConfirmed requires the exact phrase', () => {
  assert.equal(PLATFORM_WIDE_CONFIRM_PHRASE, 'RESET ALL');
  assert.equal(isPlatformWideConfirmed('RESET ALL'), true);
  assert.equal(isPlatformWideConfirmed('  RESET ALL '), true);
  assert.equal(isPlatformWideConfirmed('reset all'), false);
  assert.equal(isPlatformWideConfirmed('RESET'), false);
  assert.equal(isPlatformWideConfirmed(''), false);
});

test('matchesQuestionConfirm accepts what the remove dialog asks for ("Q123")', () => {
  assert.equal(matchesQuestionConfirm('Q123', 123), true);
  assert.equal(matchesQuestionConfirm('q123', 123), true);
  assert.equal(matchesQuestionConfirm(' 123 ', 123), true);
  assert.equal(matchesQuestionConfirm('Q124', 123), false);
  assert.equal(matchesQuestionConfirm('Q', 123), false);
  assert.equal(matchesQuestionConfirm('', 123), false);
});

// ── ADM-06: numeric search is an id lookup only ────────────────────────────

test('questionSearchParams sends question_id alone for ids and search for text', () => {
  assert.deepEqual(questionSearchParams('4521'), { question_id: 4521 });
  assert.deepEqual(questionSearchParams(' Q4521 '), { question_id: 4521 });
  assert.deepEqual(questionSearchParams('#77'), { question_id: 77 });
  assert.deepEqual(questionSearchParams('renal artery stenosis'), { search: 'renal artery stenosis' });
  assert.deepEqual(questionSearchParams('2024 paper 2'), { search: '2024 paper 2' });
  assert.deepEqual(questionSearchParams('   '), {});
});

// ── QE-05: years come from the bank, falling back to the current year ──────

test('buildYearOptions uses the API years (newest first) or the last 30 years', () => {
  assert.deepEqual(buildYearOptions([2024, 2026, '2025', 2025, null, 'abc']), [2026, 2025, 2024]);
  const fallback = buildYearOptions([], new Date('2026-11-01T00:00:00Z'));
  assert.equal(fallback.length, 30);
  assert.equal(fallback[0], 2026);
  assert.equal(fallback[29], 1997);
});

// ── QE-02: drag-to-reorder renumbers within the paper only ─────────────────

test('computeDisplayRenumber re-assigns the existing numbers of the paper in the new order', () => {
  const rows = [
    { id: 10, display_number: 1, paper: 1 },
    { id: 11, display_number: 2, paper: 1 },
    { id: 12, display_number: 3, paper: 1 },
    { id: 13, display_number: 4, paper: 1 },
  ];
  const result = computeDisplayRenumber(rows, 0, 2);
  assert.equal(result.ok, true);
  if (!result.ok) return;
  assert.deepEqual(result.rows.map((r) => [r.id, r.display_number]), [[11, 1], [12, 2], [10, 3], [13, 4]]);
  // Only the three moved rows are saved; #13 keeps its number.
  assert.deepEqual(result.changes, [
    { id: 11, display_number: 1 },
    { id: 12, display_number: 2 },
    { id: 10, display_number: 3 },
  ]);
});

test('computeDisplayRenumber keeps the page\'s own number range instead of page-relative 1..20', () => {
  // Page 3 of a paper: numbers 41..43 must stay 41..43.
  const rows = [
    { id: 1, display_number: 41, paper: 2 },
    { id: 2, display_number: 42, paper: 2 },
    { id: 3, display_number: 43, paper: 2 },
  ];
  const result = computeDisplayRenumber(rows, 2, 0);
  assert.equal(result.ok, true);
  if (!result.ok) return;
  assert.deepEqual(result.rows.map((r) => r.display_number), [41, 42, 43]);
  assert.deepEqual(result.rows.map((r) => r.id), [3, 1, 2]);
  assert.equal(result.changes.length, 3);
});

test('computeDisplayRenumber leaves other papers untouched and refuses cross-paper drops', () => {
  const rows = [
    { id: 1, display_number: 1, paper: 1 },
    { id: 2, display_number: 1, paper: 2 },
    { id: 3, display_number: 2, paper: 1 },
    { id: 4, display_number: 2, paper: 2 },
  ];
  const sameUp = computeDisplayRenumber(rows, 2, 0);
  assert.equal(sameUp.ok, true);
  if (sameUp.ok) {
    assert.deepEqual(sameUp.changes, [{ id: 3, display_number: 1 }, { id: 1, display_number: 2 }]);
    const paper2 = sameUp.rows.filter((r) => r.paper === 2).map((r) => [r.id, r.display_number]);
    assert.deepEqual(paper2, [[2, 1], [4, 2]]);
  }
  const cross = computeDisplayRenumber(rows, 0, 1);
  assert.equal(cross.ok, false);
});

test('computeDisplayRenumber refuses when a row of the paper has no number, and no-ops on same index', () => {
  const rows = [
    { id: 1, display_number: 1, paper: 1 },
    { id: 2, display_number: null, paper: 1 },
  ];
  assert.equal(computeDisplayRenumber(rows, 0, 1).ok, false);
  const noop = computeDisplayRenumber(rows, 1, 1);
  assert.equal(noop.ok, true);
  if (noop.ok) assert.deepEqual(noop.changes, []);
});

// ── QE-01 / QE-03: question edit modal payload ─────────────────────────────

test('parseConceptKeywords turns the comma string back into a list', () => {
  assert.deepEqual(parseConceptKeywords('hypertension, renal artery stenosis,, ACE inhibitor '), ['hypertension', 'renal artery stenosis', 'ACE inhibitor']);
  assert.deepEqual(parseConceptKeywords(['a', ' b ', '', 'a']), ['a', 'b']);
  assert.deepEqual(parseConceptKeywords(''), []);
  assert.deepEqual(parseConceptKeywords(null), []);
});

test('isValidAnswerLetter accepts A-D only', () => {
  for (const ok of ['A', 'b', ' C ', 'D']) assert.equal(isValidAnswerLetter(ok), true);
  for (const bad of ['', 'E', 'AB', null, undefined]) assert.equal(isValidAnswerLetter(bad), false);
});

test('buildQuestionEditPayload: keywords as a list, no silent answer, is_controversial only when toggled', () => {
  const baseline = { correct_answer: '', is_controversial: false, concept_keywords: 'a, b', why_correct: '' };
  const form = { ...baseline, question_text: 'Q?', concept_keywords: 'a, b, c', why_correct: 'because' };
  const payload = buildQuestionEditPayload(form, baseline);
  assert.equal(payload.admin_edited, true);
  assert.deepEqual(payload.concept_keywords, ['a', 'b', 'c']);
  assert.equal('correct_answer' in payload, false, 'an unset answer is not sent (no implicit "A")');
  assert.equal('is_controversial' in payload, false, 'an untouched flag is not sent');
  assert.equal(payload.why_correct, 'because');

  const toggled = buildQuestionEditPayload({ ...form, correct_answer: 'c', is_controversial: true }, baseline);
  assert.equal(toggled.correct_answer, 'C');
  assert.equal(toggled.is_controversial, true);

  // Unchecking a flag the admin had set in this session is sent too.
  const unset = buildQuestionEditPayload({ ...form, is_controversial: false }, { ...baseline, is_controversial: true });
  assert.equal(unset.is_controversial, false);
});

test('unpersistedEditFields reports edited fields missing from the save response', () => {
  const baseline = { why_correct: '', why_wrong_a: 'old', is_controversial: false };
  const payload = { why_correct: 'new', why_wrong_a: 'old', is_controversial: true, question_text: 'x' };
  // Detail serializer without the fields: both edits were dropped.
  assert.deepEqual(unpersistedEditFields(payload, baseline, { id: 1, question_text: 'x' }), ['why_correct', 'is_controversial']);
  // Once the serializer returns them, nothing is reported.
  assert.deepEqual(unpersistedEditFields(payload, baseline, { id: 1, why_correct: 'new', why_wrong_a: 'old', is_controversial: true }), []);
  // Unchanged fields are never reported.
  assert.deepEqual(unpersistedEditFields({ why_wrong_a: 'old' }, baseline, {}), []);
});
