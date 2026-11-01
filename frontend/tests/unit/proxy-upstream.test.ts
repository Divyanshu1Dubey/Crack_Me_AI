/**
 * Unit tests for src/app/api/proxy/upstream.ts (CFG-10: the API proxy must
 * not send a local / LAN session to the production API).
 *
 * Run (from frontend/):  npm run test:unit
 *   or  node --test tests/unit/proxy-upstream.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  DEFAULT_BACKEND_API_URL,
  DEFAULT_LOCAL_BACKEND_API_URL,
  isLocalNetworkHost,
  resolveBackendApiBaseUrls,
} from '../../src/app/api/proxy/upstream.ts';

const LOCAL_ONLY = { primary: DEFAULT_LOCAL_BACKEND_API_URL, fallback: '' };
const PRODUCTION_ONLY = { primary: DEFAULT_BACKEND_API_URL, fallback: '' };

test('a production build opened from a LAN or local address stays on the local backend', () => {
  for (const host of ['192.168.1.20', '10.0.0.5', '172.16.4.2', '172.31.255.1', 'my-laptop.local', 'localhost', '127.0.0.1', '[::1]']) {
    assert.deepEqual(resolveBackendApiBaseUrls(host, { NODE_ENV: 'production' }), LOCAL_ONLY, host);
  }
});

test('the deployed site keeps the production API with no fallback', () => {
  for (const host of ['cracklabs.app', 'www.cracklabs.app', '172.32.0.1', '8.8.8.8', 'example.localhost.com']) {
    assert.deepEqual(
      resolveBackendApiBaseUrls(host, {
        NODE_ENV: 'production',
        BACKEND_API_URL: 'http://127.0.0.1:9000',
        BACKEND_API_FALLBACK_URL: 'https://api.cracklabs.app',
      }),
      PRODUCTION_ONLY,
      host,
    );
  }
});

test('a dev server is always local, whatever the host', () => {
  assert.deepEqual(resolveBackendApiBaseUrls('cracklabs.app', { NODE_ENV: 'development' }), LOCAL_ONLY);
});

test('configured local upstreams are normalised and a fallback is only used when distinct', () => {
  assert.deepEqual(
    resolveBackendApiBaseUrls('192.168.0.9', {
      NODE_ENV: 'production',
      BACKEND_API_URL: 'http://192.168.0.2:8000/',
      BACKEND_API_FALLBACK_URL: 'http://192.168.0.3:8000/api',
    }),
    { primary: 'http://192.168.0.2:8000/api', fallback: 'http://192.168.0.3:8000/api' },
  );
  assert.deepEqual(
    resolveBackendApiBaseUrls('localhost', {
      NODE_ENV: 'production',
      BACKEND_API_URL: 'http://127.0.0.1:8000/api',
      BACKEND_API_FALLBACK_URL: 'http://127.0.0.1:8000',
    }),
    LOCAL_ONLY,
  );
});

test('known-unhealthy legacy hosts are never used as upstreams', () => {
  assert.deepEqual(
    resolveBackendApiBaseUrls('localhost', {
      NODE_ENV: 'development',
      BACKEND_API_URL: 'https://crackcms-backend.onrender.com',
      BACKEND_API_FALLBACK_URL: 'https://crackcms-vsthc.ondigitalocean.app/api',
    }),
    LOCAL_ONLY,
  );
});

test('isLocalNetworkHost matches the private ranges only', () => {
  for (const host of ['10.1.2.3', '127.0.0.2', '172.20.0.1', '192.168.50.50', 'LOCALHOST', 'printer.local']) {
    assert.equal(isLocalNetworkHost(host), true, host);
  }
  for (const host of ['172.15.0.1', '172.32.0.1', '192.169.0.1', '11.0.0.1', '256.1.1.1', '10.0.0', 'cracklabs.app']) {
    assert.equal(isLocalNetworkHost(host), false, host);
  }
});
