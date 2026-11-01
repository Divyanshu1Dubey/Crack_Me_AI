/**
 * Wave 4 Z4 (follow-ups of the security pass), checked on the pure helpers,
 * the api.ts request helpers (a capturing axios adapter, no network) and the
 * Settings page source:
 *  - Settings > Profile lets a learner change their public username. The
 *    PATCH carries `username` only when it changed, so a username from before
 *    the handle rules never blocks saving the other fields; format mistakes
 *    are shown before any request; the server's reason ("This username is
 *    taken.") replaces the generic failure message.
 *  - mistakeNotebookAPI.due pages like list() (?page=&page_size=).
 *
 * Run (from frontend/):
 *   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/settings-username.test.ts
 */
import { test, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import {
  USERNAME_MAX_LENGTH,
  profileUpdatePayload,
  usernameExposesEmail,
  usernameProblem,
} from '../../src/app/settings/username.ts';

process.env.NEXT_PUBLIC_AUTH_MODE = 'local'; // no Supabase client in this test

const mod = await import('../../src/lib/api.ts');
const api = mod.default;
const { authAPI, mistakeNotebookAPI } = mod;

const page = readFileSync(fileURLToPath(new URL('../../src/app/settings/page.tsx', import.meta.url)), 'utf8');

type Captured = { url?: string; method?: string; data?: unknown; params?: unknown };
let captured: Captured[] = [];

beforeEach(() => {
  captured = [];
  api.defaults.adapter = async (config) => {
    captured.push({ url: config.url, method: config.method, data: config.data, params: config.params });
    return { data: {}, status: 200, statusText: 'OK', headers: {}, config };
  };
});

test('format mistakes are explained before any request (same rules as accounts/handles.py)', () => {
  const email = 'Rahul.K@gmail.com';
  const cases: Array<[string, RegExp]> = [
    ['ab', /3 to 30 characters/],
    ['x'.repeat(31), /3 to 30 characters/],
    ['dr rahul', /letters, numbers/],
    ['dr-rahul', /letters, numbers/],
    ['rahul@clinic.org', /email address/],
    ['___', /at least one letter or number/],
    ['rahul.k', /part of your email/],
    ['RAHUL.K_2', /part of your email/],
  ];
  for (const [value, reason] of cases) {
    assert.match(usernameProblem(value, email) ?? '', reason, value);
  }
  assert.equal(usernameProblem('cardio_queen', email), null);
  assert.equal(usernameProblem('  dr.rahul_92  ', 'meera@gmail.com'), null);
  assert.equal(USERNAME_MAX_LENGTH, 30);
});

test('a username shows the address when it is its local part, a suffixed or cut copy, or holds an @', () => {
  const long = 'a'.repeat(150);
  assert.equal(usernameExposesEmail('Rahul.K_12', 'rahul.k@gmail.com'), true);
  assert.equal(usernameExposesEmail('a'.repeat(140), `${long}@x.com`), true);
  assert.equal(usernameExposesEmail(`${'a'.repeat(130)}_4`, `${long}@x.com`), true);
  assert.equal(usernameExposesEmail('someone@else.org', 'rahul@gmail.com'), true);
  assert.equal(usernameExposesEmail('rahul.k_x', 'rahul.k@gmail.com'), false);
  assert.equal(usernameExposesEmail('learner', 'learner_1@x.com'), false);
  assert.equal(usernameExposesEmail('rahul', ''), false);
});

test('the profile PATCH sends the username only when it changed', () => {
  const form = { username: 'rahul.k', first_name: 'Rahul', college: 'AIIMS' };
  assert.deepEqual(profileUpdatePayload(form, 'rahul.k'), { first_name: 'Rahul', college: 'AIIMS' });
  assert.deepEqual(profileUpdatePayload({ ...form, username: ' rahul.k ' }, 'rahul.k'), { first_name: 'Rahul', college: 'AIIMS' });
  assert.deepEqual(profileUpdatePayload({ ...form, username: ' cardio_queen ' }, 'rahul.k'), {
    first_name: 'Rahul', college: 'AIIMS', username: 'cardio_queen',
  });
  assert.deepEqual(profileUpdatePayload({ username: '', phone: '1' }, undefined), { phone: '1' });
});

test('the Settings profile form edits the username and shows the server reason on failure', () => {
  assert.match(page, /username: user\.username \|\| ''/);
  assert.match(page, /<input id="settings-username"[^>]*value=\{form\.username\}/);
  assert.match(page, /maxLength=\{USERNAME_MAX_LENGTH\}/);
  const save = page.slice(page.indexOf('const handleSave'), page.indexOf('const fetchDevices'));
  assert.match(save, /const payload = profileUpdatePayload\(form, user\?\.username\);/);
  assert.match(save, /'username' in payload \? usernameProblem\(payload\.username, user\?\.email\) : null/);
  assert.match(save, /if \(problem\) \{[\s\S]*?return;\s*\}/);
  assert.match(save, /await authAPI\.updateProfile\(payload\);/);
  assert.match(save, /extractApiErrorMessage\(data, PROFILE_SAVE_FAILED\)/);
  assert.doesNotMatch(save, /updateProfile\(form\)/);
});

test('authAPI.updateProfile sends the changed username', async () => {
  await authAPI.updateProfile({ username: 'cardio_queen' });
  assert.equal(captured.length, 1);
  assert.equal(captured[0].method, 'patch');
  assert.equal(captured[0].url, '/auth/profile/');
  const body = typeof captured[0].data === 'string' ? JSON.parse(captured[0].data) : captured[0].data;
  assert.deepEqual(body, { username: 'cardio_queen' });
});

test('mistakeNotebookAPI.due pages like list()', async () => {
  await mistakeNotebookAPI.due({ page: 2, page_size: 20 });
  await mistakeNotebookAPI.due();
  assert.equal(captured.length, 2);
  assert.equal(captured[0].url, '/analytics/mistake-notebook/due/');
  assert.deepEqual(captured[0].params, { page: 2, page_size: 20 });
  assert.equal(captured[1].params, undefined);
});
