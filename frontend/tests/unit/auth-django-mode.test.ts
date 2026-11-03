/**
 * src/lib/api.ts with NEXT_PUBLIC_AUTH_MODE=django (the Django-native
 * sign-in), against a scripted axios adapter and a stubbed fetch for the
 * refresh endpoint (no network):
 *  - no Supabase client exists, even with Supabase keys in the environment;
 *  - every request carries the stored access token and X-Session-ID,
 *    including the profile fetch;
 *  - concurrent 401s produce ONE refresh and are all retried;
 *  - a refused refresh clears the session and tells the AuthProvider; a
 *    backend blip keeps it;
 *  - session_revoked / device_inactive (401) sign this browser out and
 *    explain why on /login; the same codes in a view's 409 do not.
 *
 * Run (from frontend/):
 *   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/auth-django-mode.test.ts
 */
import { test, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { AxiosError, AxiosHeaders, type InternalAxiosRequestConfig } from 'axios';
import { fakeJwt, installFakeBrowser, jsonResponse } from './fake-browser.ts';

process.env.NEXT_PUBLIC_AUTH_MODE = 'django';
// Present on purpose: django mode must ignore them.
process.env.NEXT_PUBLIC_SUPABASE_URL = 'http://127.0.0.1:9';
process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = 'test-anon-key';
const browser = installFakeBrowser('http://localhost:3000/login');

const mod = await import('../../src/lib/api.ts');
const api = mod.default;
const { authAPI, getSessionEndingMessage } = mod;
const supabase = await import('../../src/lib/supabase.ts');
const { TOKEN_SESSION_ENDED_EVENT } = await import('../../src/lib/localAuth.ts');

const A1 = fakeJwt(5, 'access-1');
const R1 = fakeJwt(5, 'refresh-1');
const A2 = fakeJwt(5, 'access-2');
const R2 = fakeJwt(5, 'refresh-2');

type Seen = { method?: string; url?: string; authorization: string | null; sessionId: string | null };
let seen: Seen[] = [];
let refreshPosts: string[] = [];
let refreshAnswer: () => Response | Promise<Response> = () => jsonResponse(200, {});

const header = (config: InternalAxiosRequestConfig, name: string): string | null => {
  const value = config.headers instanceof AxiosHeaders ? config.headers.get(name) : (config.headers as Record<string, unknown>)?.[name];
  return typeof value === 'string' ? value : null;
};

const fail = (config: InternalAxiosRequestConfig, status: number, data: unknown) => {
  const response = { data, status, statusText: String(status), config, headers: new AxiosHeaders() };
  throw new AxiosError(`Request failed with status code ${status}`, AxiosError.ERR_BAD_REQUEST, config, null, response);
};

/** The API answers via `respond(config)`: [status, body]. */
const backend = (respond: (config: InternalAxiosRequestConfig) => [number, unknown]) => {
  api.defaults.adapter = async (config) => {
    seen.push({
      method: config.method,
      url: config.url,
      authorization: header(config, 'Authorization'),
      sessionId: header(config, 'X-Session-ID'),
    });
    const [status, data] = respond(config);
    if (status >= 400) return fail(config, status, data);
    return { data, status, statusText: 'OK', headers: {}, config };
  };
};

/** Answers 401 token_not_valid to an expired token (A1), 200 to the fresh one (A2). */
const expiresA1 = (config: InternalAxiosRequestConfig): [number, unknown] =>
  header(config, 'Authorization') === `Bearer ${A1}`
    ? [401, { detail: 'Given token not valid for any token type', code: 'token_not_valid' }]
    : [200, { ok: true, url: config.url }];

beforeEach(() => {
  browser.storage.clear();
  browser.cookies.clear();
  browser.events.length = 0;
  browser.setUrl('http://localhost:3000/login');
  seen = [];
  refreshPosts = [];
  refreshAnswer = async () => {
    await new Promise((resolve) => setTimeout(resolve, 10));
    return jsonResponse(200, { access: A2, refresh: R2, session_id: 'sid' });
  };
  globalThis.fetch = (async (input: RequestInfo | URL, init: RequestInit = {}) => {
    if (String(input).endsWith('/auth/native/refresh/')) refreshPosts.push(JSON.parse(String(init.body)).refresh);
    return refreshAnswer();
  }) as typeof fetch;
  browser.storage.setItem('crack_local_access', A1);
  browser.storage.setItem('crack_local_refresh', R1);
  browser.storage.setItem('crack_device_id', 'dev_django_test_device');
});

test('no Supabase client in django mode, even with Supabase keys set', () => {
  assert.equal(supabase.isSupabaseConfigured(), true);
  assert.equal(supabase.isSupabaseAuthEnabled(), false);
  assert.equal(supabase.getSupabaseBrowserClient(), null);
});

test('the stored token and X-Session-ID go with every request, the profile fetch included', async () => {
  browser.storage.setItem('crack_local_access', A2);
  backend(() => [200, { id: 5 }]);
  await authAPI.getProfile();
  await api.get('/questions/');
  assert.deepEqual(seen.map((s) => [s.url, s.authorization, s.sessionId]), [
    ['/auth/profile/', `Bearer ${A2}`, 'dev_django_test_device'],
    ['/questions/', `Bearer ${A2}`, 'dev_django_test_device'],
  ]);
});

test('concurrent 401s produce one refresh; every request is retried with the new token', async () => {
  backend(expiresA1);
  const results = await Promise.all([api.get('/auth/profile/'), api.get('/questions/'), api.post('/questions/1/attempt/', { selected_answer: 'A' })]);
  assert.deepEqual(refreshPosts, [R1]);
  assert.deepEqual(results.map((r) => r.status), [200, 200, 200]);
  assert.equal(seen.filter((s) => s.authorization === `Bearer ${A2}`).length, 3);
  assert.equal(browser.storage.getItem('crack_local_access'), A2);
  assert.equal(browser.storage.getItem('crack_local_refresh'), R2);
});

test('a request that failed with an older token reuses the stored new one without a refresh', async () => {
  browser.storage.setItem('crack_local_access', A2);
  backend(expiresA1);
  const response = await api.get('/questions/', { headers: { Authorization: `Bearer ${A1}` } });
  assert.equal(response.status, 200);
  assert.deepEqual(refreshPosts, []);
});

test('a refused refresh clears the session and tells the AuthProvider (TOKEN_SESSION_ENDED_EVENT)', async () => {
  refreshAnswer = () => jsonResponse(401, { detail: 'This sign-in token is invalid or has expired.', code: 'token_not_valid' });
  backend(expiresA1);
  await assert.rejects(api.get('/questions/'), (error: AxiosError) => error.response?.status === 401);
  assert.deepEqual(refreshPosts, [R1]);
  assert.equal(browser.storage.getItem('crack_local_access'), null);
  assert.equal(browser.storage.getItem('crack_local_refresh'), null);
  assert.ok(browser.events.includes(TOKEN_SESSION_ENDED_EVENT));
  // The device id survives: the next sign-in takes this browser's slot back.
  assert.equal(browser.storage.getItem('crack_device_id'), 'dev_django_test_device');
});

test('a backend blip during the refresh keeps the session', async () => {
  refreshAnswer = () => jsonResponse(503, {});
  backend(expiresA1);
  await assert.rejects(api.get('/questions/'), (error: AxiosError) => error.response?.status === 401);
  assert.equal(browser.storage.getItem('crack_local_refresh'), R1);
  assert.ok(!browser.events.includes(TOKEN_SESSION_ENDED_EVENT));
});

test('a view answering 409 account_link_required (Settings > Connect Google) does not sign out', async () => {
  browser.storage.setItem('crack_local_access', A2);
  backend(() => [409, { detail: 'This account must be verified by an administrator.', code: 'account_link_required' }]);
  await assert.rejects(authAPI.googleLink('id-token'), (error: AxiosError) => error.response?.status === 409);
  assert.equal(browser.storage.getItem('crack_local_access'), A2);
  assert.equal(getSessionEndingMessage({ response: { status: 409, data: { code: 'account_link_required' } } }), null);
  assert.match(getSessionEndingMessage({ response: { status: 401, data: { code: 'session_revoked' } } }) ?? '', /session has ended/);
});

test('signed-in calls of the native sign-in: password change, Google link / unlink, config', async () => {
  browser.storage.setItem('crack_local_access', A2);
  const bodies: unknown[] = [];
  api.defaults.adapter = async (config) => {
    seen.push({ method: config.method, url: config.url, authorization: header(config, 'Authorization'), sessionId: header(config, 'X-Session-ID') });
    bodies.push(typeof config.data === 'string' ? JSON.parse(config.data) : config.data);
    return { data: {}, status: 200, statusText: 'OK', headers: {}, config };
  };
  await authAPI.changePassword({ current_password: 'old', new_password: 'N3w!password' });
  await authAPI.googleLink('id-token');
  await authAPI.googleUnlink();
  await authAPI.authConfig();
  assert.deepEqual(seen.map((s) => `${s.method} ${s.url}`), [
    'post /auth/native/password/', 'post /auth/google/link/', 'delete /auth/google/link/', 'get /auth/config/',
  ]);
  assert.deepEqual(bodies[0], { current_password: 'old', new_password: 'N3w!password' });
  assert.deepEqual(bodies[1], { credential: 'id-token' });
  assert.ok(seen.every((s) => s.authorization === `Bearer ${A2}` && s.sessionId === 'dev_django_test_device'));
});

test('session_revoked on /login: signed out here, the error is left for the login form', async () => {
  browser.storage.setItem('crack_local_access', A2);
  backend(() => [401, { detail: 'This session has ended. Please sign in again.', code: 'session_revoked' }]);
  await assert.rejects(api.get('/auth/profile/'), (error: AxiosError) => error.response?.status === 401);
  assert.deepEqual(refreshPosts, []); // a revoked session is not refreshed
  assert.equal(browser.storage.getItem('crack_local_access'), null);
  assert.equal(browser.location.pathname, '/login');
});

test('device_inactive elsewhere: signed out, device id reset, /login explains why (runs last: navigates)', async () => {
  browser.setUrl('http://localhost:3000/dashboard');
  browser.storage.setItem('crack_local_access', A2);
  backend(() => [401, { detail: 'This device has been logged out or blocked.', code: 'device_inactive' }]);
  const pending = api.get('/analytics/dashboard/');
  for (let i = 0; i < 50 && browser.location.pathname !== '/login'; i++) {
    await new Promise((resolve) => setTimeout(resolve, 5));
  }
  assert.equal(browser.location.pathname, '/login');
  assert.match(decodeURIComponent(browser.location.search), /This device was signed out/);
  assert.equal(browser.storage.getItem('crack_local_access'), null);
  assert.equal(browser.storage.getItem('crack_device_id'), null);
  void pending; // never settles: the page is navigating away
});
