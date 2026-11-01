/**
 * Unit tests for src/lib/apiBase.ts (CFG-10: a local run must never be
 * switched to, or fail over to, the production API).
 *
 * Run (from frontend/):  node --test tests/unit/api-base.test.ts
 *
 * apiBase.ts reads `window` / env when it is imported, so every scenario
 * imports a fresh copy (cache-busting query string) after setting globals.
 */
import { test, afterEach } from 'node:test';
import assert from 'node:assert/strict';

type ApiBase = typeof import('../../src/lib/apiBase.ts');

const PROD = 'https://api.cracklabs.app/api';
const LOCAL = 'http://localhost:8000/api';
let counter = 0;

async function load(hostname: string | null, env: Record<string, string | undefined> = {}): Promise<ApiBase> {
  const g = globalThis as Record<string, unknown>;
  if (hostname === null) delete g.window;
  else g.window = { location: { hostname } };
  for (const [key, value] of Object.entries(env)) {
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  }
  counter += 1;
  return import(`../../src/lib/apiBase.ts?case=${counter}`) as Promise<ApiBase>;
}

afterEach(() => {
  delete (globalThis as Record<string, unknown>).window;
  delete process.env.VERCEL;
  delete process.env.NEXT_PUBLIC_API_URL;
  delete process.env.NEXT_PUBLIC_API_FALLBACK_URL;
});

test('a local run never fails over to the production API', async () => {
  const m = await load('localhost');
  // No NEXT_PUBLIC_API_FALLBACK_URL: the fallback used to be production.
  assert.equal(m.resolveFallbackApiBaseUrl(LOCAL, ''), LOCAL);
  // Even an explicitly configured remote fallback is ignored for a localhost API.
  assert.equal(m.resolveFallbackApiBaseUrl(LOCAL, PROD), LOCAL);
  // A second local backend is fine.
  assert.equal(m.resolveFallbackApiBaseUrl(LOCAL, 'http://127.0.0.1:8001/api'), 'http://127.0.0.1:8001/api');
});

test('a deployed site keeps its production fallback', async () => {
  const m = await load('www.cracklabs.app');
  assert.equal(m.resolveFallbackApiBaseUrl(PROD, ''), PROD);
  assert.equal(m.resolveFallbackApiBaseUrl('https://staging.example.com/api', PROD), PROD);
  // A deployed build with a stray localhost URL still uses production.
  assert.equal(m.shouldIgnoreConfiguredApiUrl(LOCAL), true);
});

test('LAN hosts count as local, so a localhost API is kept', async () => {
  for (const host of ['192.168.1.20', '10.0.0.5', '172.20.1.1', 'devbox.local', '127.0.0.1']) {
    const m = await load(host);
    assert.equal(m.isAppRunningLocally(), true, host);
    assert.equal(m.shouldIgnoreConfiguredApiUrl(LOCAL), false, host);
  }
  const pub = await load('172.32.0.1');
  assert.equal(pub.isAppRunningLocally(), false);
});

test('server render keeps a localhost API except on Vercel', async () => {
  const local = await load(null, { NEXT_PUBLIC_API_URL: LOCAL });
  assert.equal(local.shouldIgnoreConfiguredApiUrl(LOCAL), false);
  assert.equal(local.API_BASE_URL, LOCAL);

  const vercel = await load(null, { NEXT_PUBLIC_API_URL: LOCAL, VERCEL: '1' });
  assert.equal(vercel.shouldIgnoreConfiguredApiUrl(LOCAL), true);
  assert.equal(vercel.API_BASE_URL, PROD);
});
