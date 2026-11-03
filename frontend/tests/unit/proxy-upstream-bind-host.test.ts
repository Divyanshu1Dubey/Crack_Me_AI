/**
 * Unit tests for src/app/api/proxy/upstream.ts under a self-hosted
 * `next start -H 0.0.0.0` (wave 3): Next builds request.nextUrl from the
 * server's bind host (resolve-routes.js: `${protocol}://${hostname}:${port}`),
 * so the proxy sees '0.0.0.0' / '::' instead of the browser's LAN address and
 * used to target the production API.
 *
 * Run (from frontend/):  npm run test:unit
 *   or  node --test tests/unit/proxy-upstream-bind-host.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  DEFAULT_BACKEND_API_URL,
  DEFAULT_LOCAL_BACKEND_API_URL,
  isLocalNetworkHost,
  resolveBackendApiBaseUrls,
} from '../../src/app/api/proxy/upstream.ts';

/** The hostname Next's router gives route handlers for a bind address. */
const nextUrlHostnameFor = (bindHost: string, port = 3000) => {
  const host = bindHost.includes(':') && !bindHost.startsWith('[') ? `[${bindHost}]` : bindHost;
  return new URL(`http://${host}:${port}/api/proxy/questions/`).hostname;
};

test('a production server bound to an unspecified address stays on the local backend', () => {
  for (const bind of ['0.0.0.0', '::']) {
    const hostname = nextUrlHostnameFor(bind);
    assert.equal(isLocalNetworkHost(hostname), true, hostname);
    assert.deepEqual(
      resolveBackendApiBaseUrls(hostname, { NODE_ENV: 'production' }),
      { primary: DEFAULT_LOCAL_BACKEND_API_URL, fallback: '' },
      hostname,
    );
  }
});

test('public hosts are unaffected', () => {
  for (const host of ['cracklabs.app', '0.0.0.0.example.com', '8.8.8.8']) {
    assert.equal(isLocalNetworkHost(host), false, host);
    assert.deepEqual(
      resolveBackendApiBaseUrls(host, { NODE_ENV: 'production' }),
      { primary: DEFAULT_BACKEND_API_URL, fallback: '' },
      host,
    );
  }
});
