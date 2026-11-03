/**
 * Unit tests for the token store and the Django-native sign-in client in
 * src/lib/localAuth.ts (NEXT_PUBLIC_AUTH_MODE=django), with fake browser
 * globals and a stubbed fetch (no network):
 *  - the build-mode helpers (lib/localSession.ts);
 *  - tokens in localStorage under the crack_local_* keys the E2E suite seeds,
 *    and the presence cookies the middleware gates on;
 *  - sign-in answers store the session; errors carry the backend's code;
 *  - logout clears this browser first, then ends the server session;
 *  - other tabs: sign-out / account switch are noticed, token rotation is not.
 *
 * Run (from frontend/):
 *   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/token-auth-store.test.ts
 */
import { test, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { fakeJwt, installFakeBrowser, jsonResponse } from './fake-browser.ts';

process.env.NEXT_PUBLIC_AUTH_MODE = 'django';
const browser = installFakeBrowser('https://www.cracklabs.app/login');

const session = await import('../../src/lib/localSession.ts');
const auth = await import('../../src/lib/localAuth.ts');

type FetchCall = { url: string; init: RequestInit };
let fetchCalls: FetchCall[] = [];
let answer: (call: FetchCall) => Response | Promise<Response> = () => jsonResponse(200, {});

beforeEach(() => {
  browser.storage.clear();
  browser.cookies.clear();
  browser.cookieWrites.length = 0;
  fetchCalls = [];
  answer = () => jsonResponse(200, {});
  globalThis.fetch = (async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const call = { url: String(input), init };
    fetchCalls.push(call);
    return answer(call);
  }) as typeof fetch;
});

const bodyOf = (call: FetchCall) => JSON.parse(String(call.init.body || '{}'));
const headersOf = (call: FetchCall) => (call.init.headers || {}) as Record<string, string>;

const tokens = (userId = 5, marker = '1') => ({
  access: fakeJwt(userId, `a${marker}`),
  refresh: fakeJwt(userId, `r${marker}`),
  session_id: '6f1c2c1e-3d0b-4a58-9c1e-1b2a3c4d5e6f',
  user: { id: userId, email: 'learner@example.com', role: 'student' },
});

test('build mode: NEXT_PUBLIC_AUTH_MODE picks supabase (default), local or django', () => {
  const saved = process.env.NEXT_PUBLIC_AUTH_MODE;
  try {
    for (const [value, mode] of [['', 'supabase'], ['supabase', 'supabase'], ['nonsense', 'supabase'],
      ['local', 'local'], [' Django ', 'django'], ['DJANGO', 'django']] as const) {
      process.env.NEXT_PUBLIC_AUTH_MODE = value;
      assert.equal(session.authBuildMode(), mode, value);
      assert.equal(session.isTokenAuthBuild(), mode !== 'supabase', value);
      assert.equal(session.isDjangoAuthBuild(), mode === 'django', value);
      assert.equal(session.isLocalAuthBuild(), mode === 'local', value);
    }
  } finally {
    process.env.NEXT_PUBLIC_AUTH_MODE = saved;
  }
});

test('the token store keeps the crack_local_* keys and the presence cookies', () => {
  auth.setLocalTokens('access-1', 'refresh-1');
  assert.equal(browser.storage.getItem('crack_local_access'), 'access-1');
  assert.equal(browser.storage.getItem('crack_local_refresh'), 'refresh-1');
  assert.equal(auth.getLocalAccessToken(), 'access-1');
  assert.equal(auth.getLocalRefreshToken(), 'refresh-1');
  assert.equal(auth.hasStoredTokenSession(), true);
  assert.equal(browser.cookies.get(session.LOCAL_SESSION_COOKIE), '1');
  // Django mode: 30-day presence cookie, Secure on https.
  assert.match(browser.cookieWrites.at(-1) ?? '', /^crack_local_session=1; Path=\/; SameSite=Lax; Max-Age=2592000; Secure$/);

  // A new access token alone (reuse-window refresh) keeps the refresh token.
  auth.setLocalTokens('access-2');
  assert.equal(auth.getLocalRefreshToken(), 'refresh-1');

  auth.syncPresenceCookies({ role: 'admin' });
  assert.equal(browser.cookies.get(session.LOCAL_ADMIN_COOKIE), '1');
  auth.syncPresenceCookies({ role: 'student' });
  assert.equal(browser.cookies.has(session.LOCAL_ADMIN_COOKIE), false);

  browser.storage.setItem('crack_device_id', 'dev_keep_me_12345');
  auth.clearLocalTokens();
  assert.equal(auth.getLocalAccessToken(), null);
  assert.equal(auth.getLocalRefreshToken(), null);
  assert.equal(auth.hasStoredTokenSession(), false);
  assert.equal(browser.cookies.has(session.LOCAL_SESSION_COOKIE), false);
  assert.equal(browser.cookies.has(session.LOCAL_ADMIN_COOKIE), false);
  // Only the session is forgotten: the device id keeps this browser's slot.
  assert.equal(browser.storage.getItem('crack_device_id'), 'dev_keep_me_12345');
});

test('nativeLogin posts the email (trimmed) and password and stores the new session', async () => {
  const body = { ...tokens(9), user: { id: 9, role: 'admin', is_admin: true } };
  answer = () => jsonResponse(200, body);
  const result = await auth.nativeLogin('  owner@example.com ', 'pw-123456');
  assert.equal(fetchCalls.length, 1);
  assert.match(fetchCalls[0].url, /\/auth\/native\/login\/$/);
  assert.equal(fetchCalls[0].init.method, 'POST');
  assert.deepEqual(bodyOf(fetchCalls[0]), { email: 'owner@example.com', password: 'pw-123456' });
  assert.equal(result.access, body.access);
  assert.equal(auth.getLocalAccessToken(), body.access);
  assert.equal(auth.getLocalRefreshToken(), body.refresh);
  assert.equal(browser.cookies.get(session.LOCAL_SESSION_COOKIE), '1');
  assert.equal(browser.cookies.get(session.LOCAL_ADMIN_COOKIE), '1');
});

test('sign-in errors are AuthApiError with the backend code, status and message', async () => {
  answer = () => jsonResponse(401, { detail: 'Incorrect email or password.', code: 'invalid_credentials' });
  await assert.rejects(auth.nativeLogin('a@example.com', 'nope'), (error: unknown) => {
    assert.ok(error instanceof auth.AuthApiError);
    assert.equal(error.code, 'invalid_credentials');
    assert.equal(error.status, 401);
    assert.equal(error.message, 'Incorrect email or password.');
    return true;
  });
  assert.equal(auth.hasStoredTokenSession(), false);

  answer = () => jsonResponse(401, { detail: 'Please confirm your email address: we sent you a link.', code: 'email_not_confirmed' });
  await assert.rejects(auth.nativeLogin('a@example.com', 'right'), { code: 'email_not_confirmed', status: 401 });

  // Throttled without a body code / a backend not running the native sign-in / a crash.
  answer = () => new Response('<html>Server Error (500)</html>', { status: 500 });
  await assert.rejects(auth.nativeLogin('a@example.com', 'x'), { status: 500, message: 'Something went wrong on our server. Please try again.' });
  answer = () => jsonResponse(404, { detail: 'Not found.' });
  await assert.rejects(auth.nativeLogin('a@example.com', 'x'), { status: 404, message: /not available right now/ });

  answer = () => { throw new TypeError('Failed to fetch'); };
  await assert.rejects(auth.nativeLogin('a@example.com', 'x'), { status: 0, code: 'network_error', message: /Unable to reach authentication server/ });

  // A 200 without tokens is not a session.
  answer = () => jsonResponse(200, { detail: 'ok' });
  await assert.rejects(auth.nativeLogin('a@example.com', 'x'), { code: 'invalid_response' });
  assert.equal(auth.hasStoredTokenSession(), false);
});

test('register never signs in: it reports the emailed confirmation', async () => {
  answer = () => jsonResponse(202, { needs_email_confirmation: true, detail: 'Check your inbox.' });
  const outcome = await auth.nativeRegister({ email: ' new@example.com ', password: 'Pw!12345678', username: ' cardio_q ', first_name: ' Meera ', last_name: '' });
  assert.deepEqual(outcome, { needsEmailConfirmation: true, detail: 'Check your inbox.' });
  assert.deepEqual(bodyOf(fetchCalls[0]), { email: 'new@example.com', username: 'cardio_q', password: 'Pw!12345678', first_name: 'Meera', last_name: '' });
  assert.match(fetchCalls[0].url, /\/auth\/native\/register\/$/);
  assert.equal(auth.hasStoredTokenSession(), false);

  answer = () => jsonResponse(400, { detail: 'This password is too short.', code: 'invalid_password', errors: { password: ['This password is too short.'] } });
  await assert.rejects(auth.nativeRegister({ email: 'x@example.com', password: 'short' }), { code: 'invalid_password', status: 400 });
});

test('emailed links: verify-email, password reset and connect-Google post the link values and sign in', async () => {
  const body = tokens(12, '2');
  answer = () => jsonResponse(201, { ...body, created: true });
  await auth.verifyEmailLink({ token: 'pending-token-abcdefgh' });
  assert.deepEqual(bodyOf(fetchCalls.at(-1)!), { token: 'pending-token-abcdefgh' });
  await auth.verifyEmailLink({ uid: 'MTI', token: 'cbm4qa-0f1e' });
  assert.deepEqual(bodyOf(fetchCalls.at(-1)!), { uid: 'MTI', token: 'cbm4qa-0f1e' });
  assert.match(fetchCalls.at(-1)!.url, /\/auth\/native\/verify-email\/$/);

  answer = () => jsonResponse(200, { ...body, password_reset: true });
  await auth.confirmPasswordReset({ uid: 'MTI', token: 'cbm4qa-0f1e', newPassword: 'N3w!password' });
  assert.match(fetchCalls.at(-1)!.url, /\/auth\/password-reset\/confirm\/$/);
  assert.deepEqual(bodyOf(fetchCalls.at(-1)!), { uid: 'MTI', token: 'cbm4qa-0f1e', new_password: 'N3w!password' });

  answer = () => jsonResponse(200, body);
  await auth.googleConfirmLink('.eJx:abc:def');
  assert.match(fetchCalls.at(-1)!.url, /\/auth\/google\/confirm-link\/$/);
  assert.deepEqual(bodyOf(fetchCalls.at(-1)!), { token: '.eJx:abc:def' });
  await auth.googleSignIn('google-id-token');
  assert.match(fetchCalls.at(-1)!.url, /\/auth\/google\/$/);
  assert.deepEqual(bodyOf(fetchCalls.at(-1)!), { credential: 'google-id-token' });
  assert.equal(auth.getLocalAccessToken(), body.access);

  answer = () => jsonResponse(409, { detail: 'We sent a link to that address.', code: 'google_link_required' });
  await assert.rejects(auth.googleSignIn('another-id-token'), { code: 'google_link_required', status: 409 });

  answer = () => jsonResponse(202, { detail: 'If an account exists for this email, we sent a link.' });
  await auth.requestPasswordReset(' someone@example.com ');
  assert.match(fetchCalls.at(-1)!.url, /\/auth\/password-reset\/$/);
  assert.deepEqual(bodyOf(fetchCalls.at(-1)!), { email: 'someone@example.com' });
  assert.equal(await auth.resendVerificationEmail('someone@example.com'), 'If an account exists for this email, we sent a link.');
});

test('logout clears this browser first, then ends the server session (refresh + bearer + X-Session-ID)', async () => {
  const body = tokens(5, '3');
  auth.setLocalTokens(body.access, body.refresh);
  browser.storage.setItem('crack_device_id', 'dev_logout_device_1');
  let storedAtRequest: string | null = 'unset';
  answer = () => {
    storedAtRequest = auth.getLocalAccessToken();
    return jsonResponse(200, { detail: 'Signed out.' });
  };
  auth.nativeLogout();
  assert.equal(auth.hasStoredTokenSession(), false);
  assert.equal(browser.cookies.has(session.LOCAL_SESSION_COOKIE), false);
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(fetchCalls.length, 1);
  assert.equal(storedAtRequest, null);
  assert.match(fetchCalls[0].url, /\/auth\/native\/logout\/$/);
  assert.deepEqual(bodyOf(fetchCalls[0]), { refresh: body.refresh });
  assert.equal(headersOf(fetchCalls[0]).Authorization, `Bearer ${body.access}`);
  assert.equal(headersOf(fetchCalls[0])['X-Session-ID'], 'dev_logout_device_1');
  assert.equal(fetchCalls[0].init.keepalive, true);

  // Nothing stored: no request; a failing request is swallowed.
  auth.nativeLogout();
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(fetchCalls.length, 1);
  auth.setLocalTokens('a', 'r');
  answer = () => { throw new TypeError('Failed to fetch'); };
  assert.doesNotThrow(() => auth.nativeLogout());
  await new Promise((resolve) => setTimeout(resolve, 0));
});

test('refreshAccessToken posts the stored refresh token once for concurrent callers', async () => {
  const first = tokens(5, '4');
  auth.setLocalTokens(first.access, first.refresh);
  const next = tokens(5, '5');
  answer = async () => {
    await new Promise((resolve) => setTimeout(resolve, 5));
    return jsonResponse(200, { access: next.access, refresh: next.refresh, session_id: next.session_id });
  };
  const outcomes = await Promise.all([auth.refreshAccessToken(first.access), auth.refreshAccessToken(first.access)]);
  assert.equal(fetchCalls.length, 1);
  assert.match(fetchCalls[0].url, /\/auth\/native\/refresh\/$/);
  assert.deepEqual(bodyOf(fetchCalls[0]), { refresh: first.refresh });
  for (const outcome of outcomes) assert.equal(outcome.ok && outcome.access, next.access);
  assert.equal(auth.getLocalRefreshToken(), next.refresh);

  // A revoked session clears the store; a 5xx keeps it.
  answer = () => jsonResponse(401, { detail: 'This session has ended.', code: 'session_revoked' });
  const revoked = await auth.refreshAccessToken(next.access);
  assert.deepEqual(revoked, { ok: false, definitive: true, status: 401, code: 'session_revoked' });
  assert.equal(auth.hasStoredTokenSession(), false);

  auth.setLocalTokens(first.access, first.refresh);
  answer = () => jsonResponse(502, {});
  const blip = await auth.refreshAccessToken(first.access);
  assert.equal(blip.ok, false);
  assert.equal(auth.getLocalRefreshToken(), first.refresh);
});

test('tokenSubject reads the user_id claim (unverified, only to tell accounts apart)', () => {
  assert.equal(auth.tokenSubject(fakeJwt(42)), '42');
  assert.equal(auth.tokenSubject(fakeJwt('7')), '7');
  for (const bad of [null, undefined, '', 'not-a-jwt', 'a.%%%.c', `x.${Buffer.from('[]').toString('base64url')}.y`]) {
    assert.equal(auth.tokenSubject(bad as string | null | undefined), null, String(bad));
  }
});

test('other tabs: a sign-out or another account is noticed; a rotated token of the same account is not', () => {
  const seen: string[] = [];
  const stop = auth.watchTokenSession({
    onSignedOut: () => seen.push('signed-out'),
    onAccountChanged: () => seen.push('account-changed'),
  });
  const storageEvent = (key: string | null, oldValue: string | null, storageArea: unknown = browser.storage) => {
    const event = new Event('storage') as Event & { key: string | null; oldValue: string | null; storageArea: unknown };
    Object.assign(event, { key, oldValue, storageArea });
    browser.dispatch(event);
  };

  // A sessionStorage event (another frame of this tab) is never about the tokens.
  storageEvent('crack_local_access', null, browser.sessionStorage);
  assert.deepEqual(seen, []);

  // Rotation in another tab: same user_id.
  const user5 = fakeJwt(5, 'old');
  auth.setLocalTokens(fakeJwt(5, 'new'), 'r');
  storageEvent('crack_local_access', user5);
  assert.deepEqual(seen, []);

  // Another account signed in there.
  auth.setLocalTokens(fakeJwt(8, 'b'), 'r');
  storageEvent('crack_local_access', fakeJwt(5, 'new'));
  assert.deepEqual(seen, ['account-changed']);

  // Signed in there while signed out here.
  storageEvent('crack_local_access', null);
  assert.deepEqual(seen, ['account-changed', 'account-changed']);

  // Unrelated keys are ignored; signing out there signs out here.
  storageEvent('theme', 'dark');
  auth.clearLocalTokens();
  storageEvent('crack_local_refresh', 'r');
  assert.deepEqual(seen, ['account-changed', 'account-changed', 'signed-out']);

  stop();
  storageEvent('crack_local_access', fakeJwt(5));
  assert.equal(seen.length, 3);
});

test('fetchLocalProfile (local mode) now sends X-Session-ID with the bearer token', async () => {
  process.env.NEXT_PUBLIC_AUTH_MODE = 'local';
  try {
    auth.setLocalTokens('local-access', 'local-refresh');
    browser.storage.setItem('crack_device_id', 'dev_profile_device_9');
    answer = () => jsonResponse(200, { id: 3, role: 'student' });
    const profile = await auth.fetchLocalProfile();
    assert.deepEqual(profile, { id: 3, role: 'student' });
    assert.equal(headersOf(fetchCalls[0]).Authorization, 'Bearer local-access');
    assert.equal(headersOf(fetchCalls[0])['X-Session-ID'], 'dev_profile_device_9');
    // Local mode keeps its old cookie exactly: 7 days, no Secure attribute.
    assert.ok(browser.cookieWrites.includes('crack_local_session=1; Path=/; SameSite=Lax; Max-Age=604800'));
    assert.ok(browser.cookieWrites.every((raw) => !raw.includes('Secure')), browser.cookieWrites.join(' | '));
  } finally {
    process.env.NEXT_PUBLIC_AUTH_MODE = 'django';
  }
});
