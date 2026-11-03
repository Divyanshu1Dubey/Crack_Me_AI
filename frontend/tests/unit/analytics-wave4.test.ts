/**
 * Wave 4 Z3 (security / performance second pass), checked on the pure
 * helpers and the page sources:
 *  - leaderboard: a learner the API lists without a name (`username: null`:
 *    no handle of their own, e.g. a Google sign-up whose username came from
 *    the email address) is shown as "the top learner" / "Learner", never
 *    "@" or "@null"; the rival card and live board name learners only
 *    through learnerName
 *  - mistake notebook: "Due now" is paged through the list's ?due=true
 *    filter with Load more (the due/ call returned every due entry); the
 *    next page is counted from the entries still shown, and a page emptied
 *    by reviews offers the remaining ones instead of "Nothing due"
 *  - wave 4b: the viewer's card says which name other learners see
 *    (`me.public_username`) and links to Settings to change it
 *
 * Run (from frontend/):
 *   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/analytics-wave4.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { boardIdentity, learnerName } from '../../src/app/leaderboard/types.ts';
import { nextPageToLoad, notebookListParams } from '../../src/app/mistake-notebook/paging.ts';

const read = (path: string) => readFileSync(fileURLToPath(new URL(`../../src/${path}`, import.meta.url)), 'utf8');
const notebookPage = read('app/mistake-notebook/page.tsx');

test('learnerName shows a chosen handle, and the fallback for a learner without one', () => {
  assert.equal(learnerName('cardio_queen', 'the top learner'), '@cardio_queen');
  assert.equal(learnerName(null, 'the top learner'), 'the top learner');
  assert.equal(learnerName(undefined, 'Learner'), 'Learner');
  assert.equal(learnerName('   ', 'Learner'), 'Learner');
});

test('the rival card and the live board never print a username directly', () => {
  for (const file of ['app/leaderboard/components/RivalCard.tsx', 'app/leaderboard/components/LiveBoard.tsx']) {
    const source = read(file);
    assert.doesNotMatch(source, /@\{(rival|row)\.username\}/, file);
    assert.match(source, /learnerName\((rival|row)\.username, '/, file);
  }
  const types = read('app/leaderboard/types.ts');
  assert.equal(types.match(/username: string \| null;/g)?.length, 2, 'rival and live-board rows may be nameless');
});

test('the viewer is told the name other learners see, with a link to Settings', () => {
  assert.deepEqual(boardIdentity('learner_1a2b3c4d'), { label: 'Others see you as @learner_1a2b3c4d', action: 'Change' });
  const nameless = { label: 'Others see you without a name', action: 'Choose a username' };
  assert.deepEqual(boardIdentity(null), nameless);
  assert.deepEqual(boardIdentity('   '), nameless);
  assert.equal(boardIdentity(undefined), null); // an envelope cached before the field existed
  const card = read('app/leaderboard/components/MyRankCard.tsx');
  assert.match(card, /boardIdentity\(me\.public_username\)/);
  assert.match(card, /<Link href="\/settings"/);
});

test('each notebook tab asks for one page; "Due now" is the ?due=true filter', () => {
  assert.deepEqual(notebookListParams('due', 2, 20), { page: 2, page_size: 20, due: 'true' });
  assert.deepEqual(notebookListParams('all', 1, 20), { page: 1, page_size: 20 });
  assert.deepEqual(notebookListParams('learning', 3, 20), { page: 3, page_size: 20, review_status: 'learning' });
  assert.doesNotMatch(notebookPage, /mistakeNotebookAPI\.due\(/);
  assert.match(notebookPage, /mistakeNotebookAPI\.list\(notebookListParams\(nextFilter, nextPage, PAGE_SIZE\)\)/);
  // Load more is offered on every tab, "Due now" included.
  assert.match(notebookPage, /\{entries\.length < count && \(/);
  assert.doesNotMatch(notebookPage, /filter !== 'due' && entries\.length < count/);
});

test('the next page is counted from the entries still shown', () => {
  assert.equal(nextPageToLoad(20, 20), 2); // nothing reviewed yet
  assert.equal(nextPageToLoad(15, 20), 1); // 5 reviewed: page 1 now starts with the 15 shown
  assert.equal(nextPageToLoad(0, 20), 1);  // reviews emptied the page
  assert.equal(nextPageToLoad(40, 20), 3);
  assert.match(notebookPage, /loadEntries\(filter, nextPageToLoad\(entries\.length, PAGE_SIZE\)\)/);
});

test('a page emptied by reviews offers the remaining entries instead of the empty state', () => {
  const cleared = notebookPage.indexOf('entries.length === 0 && count > 0 && !error ? (');
  const empty = notebookPage.indexOf('entries.length === 0 && !error ? (');
  assert.ok(cleared >= 0 && empty > cleared, 'the cleared-page branch comes before "Nothing due right now"');
  assert.match(notebookPage.slice(cleared, empty), /onClick=\{loadMore\}/);
});
