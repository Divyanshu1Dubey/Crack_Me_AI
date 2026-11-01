/**
 * Unit tests for the wave-3 admin fixes (frontend/src/app/admin/_lib/adminHelpers.ts):
 *  - createRequestSequence: Tests-tab responses that arrive after a scope
 *    switch / reload are dropped
 *  - questionEditorListParams / isReorderMode: reorder mode sends
 *    ordering=paper,display_number,id and is_active=true
 *  - computeDisplayRenumber with list rows that carry is_active (C10)
 *  - buildSystemActionRequest: scope=all sends the typed phrase as `confirm` (C9)
 *  - mergeGeneratedFields: dry-run AI output stays an unsaved edit
 *  - campaign / announcement state: expired rows are not live, and the
 *    "Publish now" message only claims "live" when it is
 *  - campaignPublishErrorNotice: send-now's 400 {code: 'expired'} refusal
 *    reads as one sentence (no ", expired" suffix)
 *  - toDateTimeLocalValue / parseExpiryInput (announcement expiry editor)
 *  - apiErrorSentence: {error, code} answers (503 backup_not_configured,
 *    400 confirmation_required) show the server sentence without the code
 *  - aiExplainResultMessage / regenerateResultMessage: AI output that removed
 *    the "Verified by Admin" mark (verification_cleared) says so
 *  - source wiring: no nested <main> in the AppShell-wrapped admin pages
 *    (C6), and each page uses the helpers above
 *
 * Run (from frontend/):
 *   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/admin-wave3.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  VERIFICATION_CLEARED_NOTE,
  aiExplainResultMessage,
  announcementStatus,
  apiErrorSentence,
  buildQuestionEditPayload,
  buildSystemActionRequest,
  campaignIsExpired,
  campaignIsLive,
  campaignPublishErrorNotice,
  campaignPublishNotice,
  computeDisplayRenumber,
  createRequestSequence,
  isReorderMode,
  listRows,
  mergeGeneratedFields,
  parseExpiryInput,
  questionEditorListParams,
  regenerateResultMessage,
  toDateTimeLocalValue,
} from '../../src/app/admin/_lib/adminHelpers.ts';

// ── Tests tab: stale responses are dropped ─────────────────────────────────

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => { resolve = r; });
  return { promise, resolve };
}

/**
 * The fetchAdminTests flow of admin/page.tsx with a fake API: take a ticket,
 * await the response, drop it unless it is still the latest request, then
 * replace (page 1) or extend (Load more) the rows.
 */
function makeTestsList() {
  const seq = createRequestSequence();
  const state = { rows: [] as string[], applied: 0 };
  const load = async (page: number, response: Promise<{ results: string[] }>) => {
    const ticket = seq.next();
    const data = await response;
    if (!seq.isCurrent(ticket)) return;
    const rows = listRows<string>(data);
    state.rows = page === 1 ? rows : [...state.rows, ...rows];
    state.applied += 1;
  };
  return { state, load };
}

test('createRequestSequence: only the latest ticket is current', () => {
  const seq = createRequestSequence();
  const a = seq.next();
  assert.equal(seq.isCurrent(a), true);
  const b = seq.next();
  assert.equal(seq.isCurrent(a), false);
  assert.equal(seq.isCurrent(b), true);
  // Independent sequences do not share tickets.
  const other = createRequestSequence();
  assert.equal(other.isCurrent(other.next()), true);
  assert.equal(seq.isCurrent(b), true);
});

test('a library response arriving after the switch to "My drafts" does not replace the drafts', async () => {
  const { state, load } = makeTestsList();
  const library = deferred<{ results: string[] }>();
  const drafts = deferred<{ results: string[] }>();
  const first = load(1, library.promise); // scope: library
  const second = load(1, drafts.promise); // admin switched to drafts
  drafts.resolve({ results: ['draft-1'] });
  await second;
  library.resolve({ results: ['lib-1', 'lib-2'] }); // the slow, older response
  await first;
  assert.deepEqual(state.rows, ['draft-1']);
  assert.equal(state.applied, 1);
});

test('a "Load more" page of the old scope is not appended after a scope switch', async () => {
  const { state, load } = makeTestsList();
  await load(1, Promise.resolve({ results: ['lib-1'] }));
  const more = deferred<{ results: string[] }>();
  const loadMore = load(2, more.promise); // Load more on the library
  const drafts = deferred<{ results: string[] }>();
  const switched = load(1, drafts.promise); // then switch to drafts
  more.resolve({ results: ['lib-21'] }); // the old page arrives first
  await loadMore;
  drafts.resolve({ results: ['draft-1'] });
  await switched;
  assert.deepEqual(state.rows, ['draft-1']);
});

test('Load more still appends when nothing superseded it', async () => {
  const { state, load } = makeTestsList();
  await load(1, Promise.resolve({ results: ['a'] }));
  await load(2, Promise.resolve({ results: ['b'] }));
  assert.deepEqual(state.rows, ['a', 'b']);
});

// ── Questions editor: reorder-mode list params ─────────────────────────────

test('questionEditorListParams: reorder mode orders by paper, display number, id and lists active rows only', () => {
  const filters = { examType: 'cms', year: '2024' };
  assert.equal(isReorderMode(filters), true);
  assert.deepEqual(questionEditorListParams(filters, 2, 20), {
    page: 2,
    page_size: 20,
    ordering: 'paper,display_number,id',
    exam_type: 'cms',
    year: '2024',
    is_active: 'true',
  });
});

test('questionEditorListParams: any other filter leaves reorder mode (default order, every row)', () => {
  const cases = [
    { examType: 'cms', year: '2024', search: 'renal' },
    { examType: 'cms', year: '2024', subjectId: '3' },
    { examType: 'cms', year: '2024', topicId: '9' },
    { examType: 'cms', year: '2024', difficulty: 'hard' },
    { examType: 'cms', year: '2024', needsReview: true },
    { examType: 'cms', year: '2024', isDropped: true },
    { examType: 'cms', year: '2024', isControversial: true },
    { examType: 'cms', year: '2024', isImageBased: true },
    { examType: 'cms' },
    { year: '2024' },
    {},
  ];
  for (const filters of cases) {
    assert.equal(isReorderMode(filters), false, JSON.stringify(filters));
    const params = questionEditorListParams(filters, 1, 20);
    assert.equal('ordering' in params, false, JSON.stringify(filters));
    assert.equal('is_active' in params, false, JSON.stringify(filters));
  }
  assert.deepEqual(
    questionEditorListParams({ needsReview: true, isDropped: true, isControversial: true, isImageBased: true, search: 'x', subjectId: '3', topicId: '9', difficulty: 'easy' }, 0, 20),
    {
      page: 1,
      page_size: 20,
      needs_review: 'true',
      is_dropped: 'true',
      subject: '3',
      topic: '9',
      difficulty: 'easy',
      is_controversial: 'true',
      is_image_based: 'true',
      search: 'x',
    },
  );
});

test('computeDisplayRenumber renumbers list rows that carry is_active=true (C10) and refuses an inactive one', () => {
  const rows = [
    { id: 1, display_number: 1, paper: 1, is_active: true },
    { id: 2, display_number: 2, paper: 1, is_active: true },
    { id: 3, display_number: 3, paper: 1, is_active: true },
  ];
  const ok = computeDisplayRenumber(rows, 2, 0);
  assert.equal(ok.ok, true);
  if (ok.ok) assert.deepEqual(ok.rows.map((r) => [r.id, r.display_number]), [[3, 1], [1, 2], [2, 3]]);
  const withRemoved = rows.map((r) => (r.id === 2 ? { ...r, is_active: false } : r));
  assert.equal(computeDisplayRenumber(withRemoved, 2, 0).ok, false);
});

// ── C9: platform-wide system actions send the typed phrase ─────────────────

test('buildSystemActionRequest: scope=all sends the phrase the admin typed as confirm', () => {
  const typed = buildSystemActionRequest('all', '', 'RESET ALL');
  assert.equal(typed.ok, true);
  if (typed.ok) {
    assert.deepEqual(typed.payload, { scope: 'all', confirm: 'RESET ALL' });
    assert.equal(typed.target, 'ALL USERS (platform-wide)');
  }
  const padded = buildSystemActionRequest('all', '', '  RESET ALL ');
  assert.equal(padded.ok && padded.payload.confirm, 'RESET ALL');
  for (const wrong of ['', 'reset all', 'RESET', 'RESET  ALL']) {
    const refused = buildSystemActionRequest('all', '', wrong);
    assert.equal(refused.ok, false, wrong);
    if (!refused.ok) assert.equal(refused.message, 'Type RESET ALL to run a platform-wide action.');
  }
});

test('buildSystemActionRequest: scope=user needs a positive integer id and sends no confirm', () => {
  const single = buildSystemActionRequest('user', ' 42 ', 'RESET ALL');
  assert.equal(single.ok, true);
  if (single.ok) {
    assert.deepEqual(single.payload, { scope: 'user', user_id: 42 });
    assert.equal(single.target, 'user #42');
  }
  for (const bad of ['', '0', '-3', '1.5', 'abc']) {
    const refused = buildSystemActionRequest('user', bad, '');
    assert.equal(refused.ok, false, bad);
    if (!refused.ok) assert.equal(refused.message, 'Enter the user ID for a single-user action.');
  }
});

// ── Questions editor: AI Generate is a dry run ─────────────────────────────

test('mergeGeneratedFields: dry-run output fills the form but not the baseline, so Save sends it', () => {
  const baseline = { correct_answer: 'B', explanation: 'Old', concept_keywords: '', why_correct: '', is_controversial: false };
  const form = { ...baseline, explanation: 'Old (edited meanwhile)' };
  const response = {
    saved: false,
    dry_run: true,
    generated_fields: { explanation: 'New', concept_keywords: ['shock', 'sepsis'], why_correct: 'Because', not_a_form_field: 'x' },
  };
  const merged = mergeGeneratedFields(form, baseline, response, 'B');
  assert.equal(merged.saved, false);
  assert.deepEqual(merged.applied, ['explanation', 'concept_keywords', 'why_correct']);
  assert.equal(merged.form.explanation, 'New');
  assert.equal(merged.form.concept_keywords, 'shock, sepsis');
  assert.equal('not_a_form_field' in merged.form, false);
  assert.equal(merged.baseline, baseline, 'the baseline is untouched');
  const payload = buildQuestionEditPayload(merged.form, merged.baseline);
  assert.equal(payload.explanation, 'New');
  assert.deepEqual(payload.concept_keywords, ['shock', 'sepsis']);
  assert.equal(payload.why_correct, 'Because');
  assert.equal(payload.correct_answer, 'B');
});

test('mergeGeneratedFields: output the server saved also moves the baseline (with the answer)', () => {
  const baseline = { correct_answer: '', explanation: '', mnemonic: '' };
  const merged = mergeGeneratedFields(baseline, baseline, { saved: true, generated_fields: { explanation: 'E' } }, 'C');
  assert.equal(merged.saved, true);
  assert.equal(merged.form.explanation, 'E');
  assert.equal(merged.baseline.explanation, 'E');
  assert.equal(merged.baseline.correct_answer, 'C');
  // Missing / malformed responses change nothing.
  const empty = mergeGeneratedFields(baseline, baseline, null, 'C');
  assert.deepEqual(empty.applied, []);
  assert.equal(empty.saved, false);
  assert.deepEqual(empty.form, baseline);
});

// ── Broadcast / announcements: expiry and live state ───────────────────────

const NOW = new Date('2026-11-01T12:00:00Z');
const fmt = (d: Date) => d.toISOString();

test('campaignIsLive mirrors _live_announcements: sent, active, unexpired, not scheduled later', () => {
  const live = { delivery_status: 'sent', is_active: true, is_expired: false, expires_at: null, scheduled_for: null };
  assert.equal(campaignIsLive(live, NOW), true);
  assert.equal(campaignIsLive({ ...live, is_expired: true }, NOW), false);
  // The list was loaded before it expired: expires_at decides.
  assert.equal(campaignIsLive({ ...live, expires_at: '2026-11-01T11:59:00Z' }, NOW), false);
  assert.equal(campaignIsLive({ ...live, expires_at: '2026-11-02T00:00:00Z' }, NOW), true);
  assert.equal(campaignIsLive({ ...live, is_active: false }, NOW), false);
  assert.equal(campaignIsLive({ ...live, delivery_status: 'draft' }, NOW), false);
  assert.equal(campaignIsLive({ ...live, delivery_status: 'scheduled' }, NOW), false);
  assert.equal(campaignIsLive({ ...live, scheduled_for: '2026-11-03T09:00:00Z' }, NOW), false);
  assert.equal(campaignIsLive({ ...live, scheduled_for: '2026-10-30T09:00:00Z' }, NOW), true);
  assert.equal(campaignIsLive(null, NOW), false);
  assert.equal(campaignIsExpired({ is_expired: true }, NOW), true);
  assert.equal(campaignIsExpired({ expires_at: 'not a date' }, NOW), false);
});

test('announcementStatus gives one admin-facing status per row', () => {
  const base = { delivery_status: 'sent', is_active: true, is_expired: false, expires_at: null, scheduled_for: null };
  assert.equal(announcementStatus(base, NOW), 'live');
  assert.equal(announcementStatus({ ...base, is_expired: true }, NOW), 'expired');
  assert.equal(announcementStatus({ ...base, is_active: false }, NOW), 'inactive');
  assert.equal(announcementStatus({ ...base, is_active: false, is_expired: true }, NOW), 'inactive');
  assert.equal(announcementStatus({ ...base, delivery_status: 'draft' }, NOW), 'draft');
  assert.equal(announcementStatus({ ...base, delivery_status: 'failed' }, NOW), 'failed');
  assert.equal(announcementStatus({ ...base, delivery_status: 'scheduled', scheduled_for: '2026-11-05T00:00:00Z' }, NOW), 'scheduled');
  assert.equal(announcementStatus({ ...base, scheduled_for: '2026-11-05T00:00:00Z' }, NOW), 'scheduled');
  assert.equal(announcementStatus({}, NOW), 'draft');
});

test('campaignPublishNotice never claims an expired campaign is live', () => {
  const expired = {
    title: 'Revision week', delivery_status: 'sent', is_active: true, delivery_count: 1234,
    is_expired: true, expires_at: '2026-10-31T18:00:00Z', scheduled_for: null,
  };
  const notice = campaignPublishNotice(expired, 7, NOW, fmt);
  assert.equal(notice.type, 'warn');
  assert.doesNotMatch(notice.text, /is live/);
  assert.match(notice.text, /^"Revision week" is marked published, but it expired on 2026-10-31T18:00:00\.000Z/);
  assert.match(notice.text, /Set a later expiry in Admin > Announcements/);
});

test('campaignPublishNotice: live, scheduled-later and not-live rows', () => {
  const live = { title: 'Mock test', delivery_status: 'sent', is_active: true, delivery_count: 1234, is_expired: false, expires_at: null, scheduled_for: null };
  assert.deepEqual(campaignPublishNotice(live, 3, NOW, fmt), { type: 'ok', text: '"Mock test" is live in-app for 1,234 users.' });
  const later = { ...live, scheduled_for: '2026-11-03T09:00:00Z' };
  const laterNotice = campaignPublishNotice(later, 3, NOW, fmt);
  assert.equal(laterNotice.type, 'warn');
  assert.match(laterNotice.text, /only see it from 2026-11-03T09:00:00\.000Z/);
  const odd = campaignPublishNotice({ ...live, is_active: false }, 3, NOW, fmt);
  assert.equal(odd.type, 'warn');
  assert.doesNotMatch(odd.text, /is live/);
  // No row in the response: the id names it.
  assert.match(campaignPublishNotice(null, 9, NOW, fmt).text, /^"Campaign #9" was published, but it is not live yet/);
});

test('campaignPublishErrorNotice: send-now 400 {code: expired} says why and what to do, without the code', () => {
  // AdminCampaignSendNowView's refusal of an expired row.
  const refusal = { error: 'This campaign has expired. Set a later expiry first.', code: 'expired' };
  assert.deepEqual(campaignPublishErrorNotice(refusal, 12), {
    type: 'warn',
    text: 'Could not publish campaign #12: it has expired, so students would not see it. ' +
      'Set a later expiry in Admin > Announcements, then publish it.',
  });
  assert.doesNotMatch(campaignPublishErrorNotice(refusal, 12)!.text, /, expired/);
  // Every other failure is left to extractApiErrorMessage (null).
  const others: unknown[] = [
    undefined, null, '', '<!doctype html><html></html>', [], ['expired'],
    { error: 'Campaign not found' }, { detail: 'Request was throttled.' },
    { code: 'not_expired' }, { error: 'expired' },
  ];
  for (const payload of others) assert.equal(campaignPublishErrorNotice(payload, 12), null, JSON.stringify(payload));
});

// ── Announcement expiry editor ─────────────────────────────────────────────

test('toDateTimeLocalValue round-trips through a datetime-local field (to the minute)', () => {
  const iso = '2026-11-05T08:30:45.000Z';
  const local = toDateTimeLocalValue(iso);
  assert.match(local, /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/);
  // A datetime-local value is parsed as local time, like the input does.
  assert.equal(new Date(local).getTime(), new Date('2026-11-05T08:30:00.000Z').getTime());
  assert.equal(toDateTimeLocalValue(null), '');
  assert.equal(toDateTimeLocalValue(''), '');
  assert.equal(toDateTimeLocalValue('garbage'), '');
});

test('parseExpiryInput only accepts a valid time in the future', () => {
  const future = toDateTimeLocalValue('2026-11-08T10:00:00Z');
  const ok = parseExpiryInput(future, NOW);
  assert.equal(ok.ok, true);
  if (ok.ok) assert.equal(ok.iso, '2026-11-08T10:00:00.000Z');
  const past = parseExpiryInput(toDateTimeLocalValue('2026-10-01T10:00:00Z'), NOW);
  assert.equal(past.ok, false);
  if (!past.ok) assert.match(past.message, /in the future/);
  assert.equal(parseExpiryInput('', NOW).ok, false);
  assert.equal(parseExpiryInput('not a date', NOW).ok, false);
});

// ── {error, code} answers: the server sentence, without the code ───────────

test('apiErrorSentence: 503 backup_not_configured and 400 confirmation_required show only the sentence', () => {
  // accounts.views._backup_not_configured_response (production without CORE_DATA_BACKUP_PATH).
  const notConfigured = {
    error: 'Backup is not available: CORE_DATA_BACKUP_PATH is not set. The default file would be on the '
      + 'container disk, which every redeploy wipes; point CORE_DATA_BACKUP_PATH at a persistent volume.',
    code: 'backup_not_configured',
  };
  assert.equal(apiErrorSentence(notConfigured), notConfigured.error);
  assert.equal(
    apiErrorSentence({ error: "Platform-wide actions need confirm='RESET ALL'.", code: 'confirmation_required' }),
    "Platform-wide actions need confirm='RESET ALL'.",
  );
  // error, then detail, then message; blank strings are skipped.
  assert.equal(apiErrorSentence({ detail: 'Request was throttled.' }), 'Request was throttled.');
  assert.equal(apiErrorSentence({ message: ' Restore failed ' }), 'Restore failed');
  assert.equal(apiErrorSentence({ error: '  ', detail: 'Not found.' }), 'Not found.');
  assert.equal(apiErrorSentence({ detail: 'B', error: 'A' }), 'A');
});

test('apiErrorSentence: payloads without a sentence return null (the page falls back to extractApiErrorMessage)', () => {
  const cases: unknown[] = [
    undefined, null, '', 'Server Error (500)', '<html>502 Bad Gateway</html>', ['x'],
    { user_id: ['This field is required.'] }, { error: 42 }, { error: ['list'] }, {},
  ];
  for (const payload of cases) assert.equal(apiErrorSentence(payload), null, JSON.stringify(payload));
});

// ── AI Explain / Regenerate AI: a removed "Verified by Admin" mark is named ─

test('aiExplainResultMessage: verification_cleared says the mark was removed (it no longer claims the mark is kept)', () => {
  // questions.views.generate_explanation for a verified question whose content changed.
  const cleared = {
    detail: 'Explanation generated and saved. The earlier "Verified by Admin" mark was removed: review the new text and verify again.',
    generated_fields: { explanation: 'New' },
    saved: true,
    dry_run: false,
    verification_cleared: true,
    question: { id: 12, is_verified_by_admin: false },
  };
  const text = aiExplainResultMessage(12, cleared, true);
  assert.equal(text, 'AI explanation generated and saved for Q#12. "Verified by Admin" was removed - review the new text and verify again.');
  assert.equal(text, `AI explanation generated and saved for Q#12. ${VERIFICATION_CLEARED_NOTE}`);
  assert.doesNotMatch(text, /keeps|still marked/);
});

test('aiExplainResultMessage: an unverified question shows the server detail', () => {
  const saved = {
    detail: 'Explanation generated and saved (not marked verified).',
    saved: true,
    dry_run: false,
    verification_cleared: false,
    question: { id: 5, is_verified_by_admin: false },
  };
  assert.equal(
    aiExplainResultMessage(5, saved, false),
    'Q#5: Explanation generated and saved (not marked verified). Review it, then use Verify once it is correct.',
  );
  assert.equal(
    aiExplainResultMessage(5, { saved: true }, false),
    'Q#5: AI explanation generated and saved (not marked verified). Review it, then use Verify once it is correct.',
  );
});

test('aiExplainResultMessage: "still verified" only when the returned row (or, without one, the list row) says so', () => {
  // Identical stored text: the server keeps the mark and clears nothing.
  const unchanged = {
    detail: 'Explanation generated and saved (not marked verified).',
    saved: true,
    verification_cleared: false,
    question: { is_verified_by_admin: true },
  };
  assert.equal(
    aiExplainResultMessage(7, unchanged, true),
    'AI explanation generated and saved for Q#7. It is still marked "Verified by Admin": review the text, and use Unverify if it needs work.',
  );
  // The returned row wins over a stale list row.
  assert.match(aiExplainResultMessage(7, { ...unchanged, question: { is_verified_by_admin: false } }, true), /^Q#7: Explanation generated and saved/);
  // A response without a row (or an older server): the list row decides.
  assert.match(aiExplainResultMessage(7, { saved: true, detail: 'Saved.' }, true), /still marked "Verified by Admin"/);
  assert.match(aiExplainResultMessage(7, { saved: true, detail: 'Saved.' }, false), /^Q#7: Saved\. Review it/);
});

test('aiExplainResultMessage: output that was not saved points to the editor', () => {
  assert.equal(
    aiExplainResultMessage(9, { saved: false, dry_run: true, verification_cleared: true }, true),
    'AI explanation generated for Q#9 but not saved. Open the question in the editor to review and save it.',
  );
});

test('regenerateResultMessage names a removed verified mark and stays silent otherwise', () => {
  // questions.views.force_regenerate (QE-03).
  assert.equal(
    regenerateResultMessage(3, { message: 'AI regeneration completed. The earlier mark was removed.', verification_cleared: true }),
    'AI regeneration completed for Q#3. "Verified by Admin" was removed - review the new text and verify again.',
  );
  assert.equal(regenerateResultMessage(3, { message: 'AI regeneration completed', verification_cleared: false }), null);
  assert.equal(regenerateResultMessage(3, { message: 'AI regeneration completed' }), null);
  assert.equal(regenerateResultMessage(3, undefined), null);
});

// ── Source wiring (the pages themselves have no unit harness) ──────────────

const FRONTEND = fileURLToPath(new URL('../../', import.meta.url));
const read = (rel: string) => readFileSync(path.join(FRONTEND, rel), 'utf8');

test('C6: admin pages inside an AppShell layout render no nested <main> and drop their own padding there', () => {
  const pages = [
    'src/app/admin/announcements/page.tsx',
    'src/app/admin/jobs/page.tsx',
    'src/app/admin/notes/page.tsx',
    'src/app/admin/questions-editor/page.tsx',
    'src/app/admin/recall/page.tsx',
    'src/app/admin/recall/search-analytics/page.tsx',
  ];
  for (const rel of pages) {
    const src = read(rel);
    assert.doesNotMatch(src, /<main\b/, rel);
    assert.match(src, /\[\.page-container_&\]:p-0/, rel);
    assert.doesNotMatch(src, /<Sidebar\b|<Header\b|<AppShell\b/, rel);
  }
});

test('wiring: scope=all announcements, 100 import jobs, dry-run AI Generate, typed confirm, blog and prompt notes', () => {
  assert.match(read('src/app/admin/announcements/page.tsx'), /getAnnouncements\(\{ scope: 'all' \}\)/);
  assert.match(read('src/app/admin/recall/page.tsx'), /\/imports\/neetpg\/jobs\/", \{ params: \{ page_size: ADMIN_PAGE_SIZE \} \}/);
  const modal = read('src/app/admin/questions-editor/QuestionEditModal.tsx');
  assert.match(modal, /dry_run: true/);
  assert.doesNotMatch(modal, /unverify\(/);
  assert.match(read('src/app/admin/questions-editor/page.tsx'), /questionEditorListParams\(listFilters, page, PAGE_SIZE\)/);
  const admin = read('src/app/admin/page.tsx');
  assert.match(admin, /buildSystemActionRequest\(systemScope, systemUserId, systemConfirmText\)/);
  assert.match(admin, /campaignPublishNotice\(updated, id\)/);
  // A refused (expired) publish shows the helper's sentence and reloads the stale list.
  assert.match(admin, /const expiredNotice = campaignPublishErrorNotice\(err\?\.response\?\.data, id\);\s*if \(expiredNotice\) \{\s*setCampaignMessage\(expiredNotice\);[\s\S]{0,160}?fetchCampaigns\(\);\s*return;/);
  assert.match(admin, /adminTestsRequests\.isCurrent\(ticket\)/);
  assert.match(admin, /Posts here are not shown on the public blog yet/);
  assert.match(admin, /Regenerate AI and AI Explain/);
  assert.doesNotMatch(admin, /AI Explain does not use it yet/);
});

test('wiring: AI Explain / Regenerate AI result lines and {error, code} sentences in the admin page', () => {
  const admin = read('src/app/admin/page.tsx');
  assert.doesNotMatch(admin, /keeps its earlier "Verified by Admin" mark/);
  assert.match(admin, /setQuestionActionMessage\(aiExplainResultMessage\(questionId, res\?\.data, Boolean\(q\.is_verified_by_admin\)\)\)/);
  assert.match(admin, /const note = regenerateResultMessage\(id, res\?\.data\);/);
  assert.match(admin, /apiErrorSentence\(data\) \?\? extractApiErrorMessage\(data, 'request failed'\)/);
  assert.match(admin, /apiErrorSentence\(e\?\.response\?\.data\) \?\? extractApiErrorMessage\(e\?\.response\?\.data \|\| 'Failed to backup data'\)/);
  assert.match(admin, /apiErrorSentence\(e\?\.response\?\.data\) \?\? extractApiErrorMessage\(e\?\.response\?\.data \|\| 'Failed to restore data'\)/);
  // C9: the typed phrase reaches the API (api.ts adds no default any more).
  assert.match(read('src/lib/api.ts'), /adminResetAttempts: \(data: SystemActionPayload\) => api\.post\('\/auth\/admin\/system\/reset-attempts\/', data\)/);
});
