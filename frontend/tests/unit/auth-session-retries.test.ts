/**
 * Unit tests for two api.ts retries added with the backend's token / device
 * hardening (accounts/supabase_rest_auth.py):
 *
 * BUSY   429 `auth_verification_busy`: the token could not be checked with
 *        Supabase right now. Answered during authentication, before any view
 *        runs, so the client retries once after Retry-After.
 * STALE  `device_inactive` for a request that still carried an OLDER
 *        session's token (another tab after signing in again) is retried
 *        with the current token instead of signing the current session out.
 *
 * Run (from frontend/):
 *   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/auth-session-retries.test.ts
 */
import { test, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { AxiosError, AxiosHeaders, type InternalAxiosRequestConfig } from 'axios';

process.env.NEXT_PUBLIC_AUTH_MODE = 'local'; // no Supabase client in this test

const mod = await import('../../src/lib/api.ts');
const api = mod.default;
const { AUTH_BUSY_CODE, authBusyRetryDelayMs, staleSessionRetryToken } = mod;

let calls: string[] = [];

const answer = (config: InternalAxiosRequestConfig, status: number, data: unknown) => {
  const response = {
    data, status, statusText: String(status), config,
    headers: new AxiosHeaders({ 'retry-after': '0' }),
  };
  if (status >= 400) {
    throw new AxiosError(`Request failed with status code ${status}`, AxiosError.ERR_BAD_REQUEST, config, null, response);
  }
  return response;
};

/** The adapter answers the given (status, body) pairs in order, then 200. */
const script = (...steps: Array<[number, unknown]>) => {
  api.defaults.adapter = async (config) => {
    calls.push(`${config.method} ${config.url}`);
    const [status, data] = steps.shift() ?? [200, { ok: true }];
    return answer(config, status, data);
  };
};

const BUSY: [number, unknown] = [429, { detail: 'Too many sign-in checks right now.', code: AUTH_BUSY_CODE }];

beforeEach(() => {
  calls = [];
});

test('a busy token check is retried once, for reads and writes alike', async () => {
  script(BUSY);
  const read = await api.get('/auth/profile/');
  assert.equal(read.status, 200);
  assert.deepEqual(calls, ['get /auth/profile/', 'get /auth/profile/']);

  calls = [];
  script(BUSY);
  const write = await api.post('/auth/subscribe/order/', { plan: '1_month' });
  assert.equal(write.status, 200);
  assert.equal(calls.length, 2);
});

test('only once: a second busy answer is returned to the caller', async () => {
  script(BUSY, BUSY, BUSY);
  await assert.rejects(api.get('/auth/tokens/'), (error: AxiosError) => error.response?.status === 429);
  assert.equal(calls.length, 2);
});

test('other 429s are not retried', async () => {
  script([429, { detail: 'Request was throttled.' }]);
  await assert.rejects(api.get('/questions/'), (error: AxiosError) => error.response?.status === 429);
  assert.equal(calls.length, 1);
});

test('the wait follows Retry-After, capped at 2 s', () => {
  assert.equal(authBusyRetryDelayMs('0'), 0);
  assert.equal(authBusyRetryDelayMs('1'), 1000);
  assert.equal(authBusyRetryDelayMs(30), 2000);
  assert.equal(authBusyRetryDelayMs(undefined), 1000);
  assert.equal(authBusyRetryDelayMs('soon'), 1000);
});

test('STALE: device_inactive for an older token is retried with the current one', () => {
  assert.equal(staleSessionRetryToken('device_inactive', 'old-session-token', 'current-token'), 'current-token');
});

test('STALE: the current session itself refused, or no session, ends it as before', () => {
  assert.equal(staleSessionRetryToken('device_inactive', 'current-token', 'current-token'), null);
  assert.equal(staleSessionRetryToken('device_inactive', 'old-session-token', null), null);
  assert.equal(staleSessionRetryToken('device_inactive', null, 'current-token'), null);
  assert.equal(staleSessionRetryToken('account_blocked', 'old-session-token', 'current-token'), null);
  assert.equal(staleSessionRetryToken(undefined, 'old-session-token', 'current-token'), null);
});
