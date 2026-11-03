/**
 * Wave 4b Z4: the sign-up form's username follows the Settings rules.
 *
 * The backend (accounts/handles.py username_for_new_account) keeps a name
 * chosen at sign-up only when it passes those rules; a team name ("admin",
 * "CrackLabs_Official"), HTML, more than 30 characters or part of the email
 * gets a generated learner_<hex> handle instead. The form says so before the
 * account is created: the HTML pattern / length limits, then the shared
 * usernameProblem() check in handleSubmit. Checked on the pure helpers and
 * the page source (no network).
 *
 * Run (from frontend/):
 *   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/register-username.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { USERNAME_MAX_LENGTH, USERNAME_PATTERN, usernameProblem } from '../../src/app/settings/username.ts';

const page = readFileSync(fileURLToPath(new URL('../../src/app/register/page.tsx', import.meta.url)), 'utf8');

// Browsers compile `pattern` with the `v` flag, anchored to the whole value.
const browserPattern = new RegExp(`^(?:${USERNAME_PATTERN})$`, 'v');

test('the HTML pattern accepts the well-formed handles and refuses the rest, like usernameProblem()', () => {
  for (const ok of ['cardio_queen', 'dr.rahul_92', 'abc', 'x'.repeat(USERNAME_MAX_LENGTH)]) {
    assert.equal(browserPattern.test(ok), true, ok);
    assert.equal(usernameProblem(ok, 'meera@gmail.com'), null, ok);
  }
  for (const bad of ['ab', 'x'.repeat(USERNAME_MAX_LENGTH + 1), 'dr rahul', 'dr-rahul', 'Dr Rahul <b>x</b>', 'me@x.org']) {
    assert.equal(browserPattern.test(bad), false, bad);
    assert.notEqual(usernameProblem(bad, 'meera@gmail.com'), null, bad);
  }
});

test('the sign-up username input carries the format rules and the public-name hint', () => {
  const start = page.indexOf('id="register-username"');
  assert.ok(start > 0, 'username input present');
  const input = page.slice(start, page.indexOf('/>', start));
  assert.match(input, /minLength=\{USERNAME_MIN_LENGTH\}/);
  assert.match(input, /maxLength=\{USERNAME_MAX_LENGTH\}/);
  assert.match(input, /pattern=\{USERNAME_PATTERN\}/);
  assert.match(input, /title="3–30 letters, numbers, _ or \."/);
  assert.match(input, /aria-describedby="register-username-hint"/);
  assert.match(input, /\brequired\b/);
  assert.match(page, /<p id="register-username-hint"[^>]*>\s*\{USERNAME_HINT\}\s*<\/p>/);
});

test('a username that breaks the rules or shows the email stops the sign-up before any request', () => {
  const submit = page.slice(page.indexOf('const handleSubmit'), page.indexOf('return ('));
  const check = submit.indexOf('usernameProblem(form.username, form.email)');
  assert.ok(check > 0, 'handleSubmit checks the username');
  assert.ok(check < submit.indexOf('await register(form)'), 'before register() is called');
  assert.match(submit, /if \(usernameIssue\) \{\s*setError\(usernameIssue\);\s*return;\s*\}/);
  // What the pattern alone lets through: the email's local part, no letter or digit.
  assert.match(usernameProblem('priya.n', 'Priya.N@gmail.com') ?? '', /part of your email/);
  assert.match(usernameProblem('___', 'meera@gmail.com') ?? '', /at least one letter or number/);
});
