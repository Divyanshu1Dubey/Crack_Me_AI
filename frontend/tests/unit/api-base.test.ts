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
  delete process.env.NEXT_PUBLIC_USE_API_PROXY;
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

test('isLocalNetworkHost is exported for the API proxy (same rule as USE_API_PROXY)', async () => {
  const m = await load('www.cracklabs.app');
  for (const host of ['localhost', '127.0.0.1', '[::1]', '10.1.2.3', '172.16.0.1', '172.31.255.255', '192.168.0.10', 'box.local']) {
    assert.equal(m.isLocalNetworkHost(host), true, host);
  }
  for (const host of ['cracklabs.app', '172.32.0.1', '8.8.8.8', '192.169.1.1', '10.0.0']) {
    assert.equal(m.isLocalNetworkHost(host), false, host);
  }
});

test('a page opened on an unspecified address (0.0.0.0, [::]) keeps the local API', async () => {
  // What a browser reports for http://0.0.0.0:3000/ and http://[::]:3000/.
  const hosts = ['http://0.0.0.0:3000/', 'http://[::]:3000/'].map((url) => new URL(url).hostname);
  assert.deepEqual(hosts, ['0.0.0.0', '[::]']);
  for (const host of hosts) {
    const m = await load(host, { NEXT_PUBLIC_API_URL: LOCAL });
    assert.equal(m.isAppRunningLocally(), true, host);
    // Used to be ignored here, so the page talked to the production API.
    assert.equal(m.shouldIgnoreConfiguredApiUrl(LOCAL), false, host);
    assert.equal(m.API_BASE_URL, LOCAL, host);
    assert.equal(m.resolveFallbackApiBaseUrl(LOCAL, PROD), LOCAL, host);
  }
  const proxied = await load('0.0.0.0', { NEXT_PUBLIC_USE_API_PROXY: 'true' });
  assert.equal(proxied.USE_API_PROXY, true);
  assert.equal(proxied.API_BASE_URL, '/api/proxy');
});

test('unspecified addresses are local hosts only: look-alikes and the API-URL rule are unchanged', async () => {
  const m = await load('www.cracklabs.app', { NEXT_PUBLIC_USE_API_PROXY: 'true' });
  // A public page never turns the proxy on, whatever the flag says.
  assert.equal(m.USE_API_PROXY, false);
  for (const host of ['0.0.0.0', '::', '[::]']) {
    assert.equal(m.isLocalNetworkHost(host), true, host);
  }
  for (const host of ['0.0.0.0.example.com', 'example.0.0.0.0', '0.0.0.1', '[::2]', '::ffff:8.8.8.8']) {
    assert.equal(m.isLocalNetworkHost(host), false, host);
  }
  // isLocalhostApiUrl stays loopback-only (it decides "never fail over to a remote API").
  assert.equal(m.isLocalhostApiUrl('http://0.0.0.0:8000/api'), false);
  assert.equal(m.isLocalhostApiUrl('http://[::]:8000/api'), false);
  assert.equal(m.isLocalhostApiUrl(LOCAL), true);
});
