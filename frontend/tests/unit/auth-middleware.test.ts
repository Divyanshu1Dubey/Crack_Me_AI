/**
 * Unit tests for src/utils/supabase/middleware.ts (route gating).
 *
 * Run (from frontend/):
 *   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/auth-middleware.test.ts
 *
 * No network: the Supabase URL points at a closed local port, and the test
 * cookies hold no parseable session, so supabase.auth.getUser() resolves
 * without a request. `tests/` is excluded from tsconfig.
 */
import { test, after, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import type { AddressInfo } from 'node:net';
import { register } from 'node:module';

// Plain Node ESM needs the file name for `next/server` (Next's bundler maps it).
register(
  'data:text/javascript,' +
    encodeURIComponent(
      "export async function resolve(specifier, context, next) {" +
        " return next(specifier === 'next/server' ? 'next/server.js' : specifier, context); }",
    ),
);

const CLOSED_PORT_URL = 'http://127.0.0.1:9';
process.env.NEXT_PUBLIC_SUPABASE_URL = CLOSED_PORT_URL;
process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = 'test-anon-key';

const { NextRequest } = await import('next/server.js');
const { updateSession } = await import(process.env.MIDDLEWARE_UNDER_TEST || '../../src/utils/supabase/middleware.ts');

// A Supabase auth cookie without a usable session ("{}"): signed in as far as
// the cookie check goes, but getUser() has no user (and makes no request).
const SUPABASE_COOKIE = 'sb-127-auth-token=base64-e30';

// A local stand-in for Supabase's GET /auth/v1/user (127.0.0.1 only), so
// getUser() returns the user a test chooses.
let currentUser: Record<string, unknown> = {};
let supabaseRequests = 0;
const fakeSupabase = createServer((req, res) => {
  supabaseRequests += 1;
  if ((req.url || '').startsWith('/auth/v1/user')) {
    res.writeHead(200, { 'content-type': 'application/json' });
    res.end(JSON.stringify(currentUser));
    return;
  }
  res.writeHead(404).end();
});
await new Promise<void>((resolve) => fakeSupabase.listen(0, '127.0.0.1', resolve));
const FAKE_SUPABASE_URL = `http://127.0.0.1:${(fakeSupabase.address() as AddressInfo).port}`;
after(() => fakeSupabase.close());

/** Signed-in request whose Supabase user is `user` (served by fakeSupabase). */
function signedInAs(path: string, user: Record<string, unknown>) {
  currentUser = { id: 'u-1', aud: 'authenticated', email: 'someone@example.com', app_metadata: {}, user_metadata: {}, ...user };
  const session = {
    access_token: 'test-access-token',
    token_type: 'bearer',
    expires_in: 3600,
    expires_at: Math.floor(Date.now() / 1000) + 3600,
    refresh_token: 'test-refresh-token',
    user: currentUser,
  };
  const value = `base64-${Buffer.from(JSON.stringify(session)).toString('base64url')}`;
  return request(path, `sb-127-auth-token=${value}`);
}

function request(path: string, cookie = '') {
  return new NextRequest(new URL(path, 'http://localhost:3000'), {
    headers: cookie ? { cookie } : {},
  });
}

function redirectTarget(response: Response): string | null {
  const location = response.headers.get('location');
  if (!location) return null;
  const url = new URL(location);
  return `${url.pathname}${url.search}`;
}

afterEach(() => {
  delete process.env.NEXT_PUBLIC_AUTH_MODE;
  process.env.NEXT_PUBLIC_SUPABASE_URL = CLOSED_PORT_URL;
});

test('AUTH-05: user_metadata (editable by the user) never counts as admin', async () => {
  process.env.NEXT_PUBLIC_SUPABASE_URL = FAKE_SUPABASE_URL;
  const response = await updateSession(
    signedInAs('/login', { user_metadata: { role: 'admin', is_admin: true } }),
  );
  assert.equal(redirectTarget(response), '/dashboard');
});

test('AUTH-05: an admin promoted in the app (no Supabase flag) is not bounced from /admin', async () => {
  process.env.NEXT_PUBLIC_SUPABASE_URL = FAKE_SUPABASE_URL;
  const response = await updateSession(signedInAs('/admin', {}));
  assert.equal(redirectTarget(response), null);
});

test('app_metadata admins still land on /admin from /login', async () => {
  process.env.NEXT_PUBLIC_SUPABASE_URL = FAKE_SUPABASE_URL;
  const response = await updateSession(signedInAs('/login', { app_metadata: { role: 'admin' } }));
  assert.equal(redirectTarget(response), '/admin');
});

test('signed-out visitors of a protected page keep the query string in next', async () => {
  const response = await updateSession(request('/questions/practice?year=2020&exam=cms'));
  assert.equal(
    redirectTarget(response),
    `/login?next=${encodeURIComponent('/questions/practice?year=2020&exam=cms')}`,
  );
});

test('signed-out visitors of /admin go to login', async () => {
  const response = await updateSession(request('/admin'));
  assert.equal(redirectTarget(response), `/login?next=${encodeURIComponent('/admin')}`);
});

test('/admin renders for a signed-in user; the page checks the backend profile', async () => {
  // Used to redirect anyone whose Supabase metadata lacked an admin flag,
  // including admins promoted in the app (Django role only).
  const response = await updateSession(request('/admin/questions-editor', SUPABASE_COOKIE));
  assert.equal(redirectTarget(response), null);
});

test('/reset-password stays reachable with a (recovery) session', async () => {
  const response = await updateSession(request('/reset-password', SUPABASE_COOKIE));
  assert.equal(redirectTarget(response), null);
});

test('signed-in users still skip /login and /register', async () => {
  for (const path of ['/login', '/register', '/forgot-password']) {
    const response = await updateSession(request(path, SUPABASE_COOKIE));
    assert.equal(redirectTarget(response), '/dashboard', path);
  }
});

test('local auth mode: cookie gate unchanged, deep links kept', async () => {
  process.env.NEXT_PUBLIC_AUTH_MODE = 'local';
  let response = await updateSession(request('/questions?year=2020'));
  assert.equal(redirectTarget(response), `/login?next=${encodeURIComponent('/questions?year=2020')}`);

  response = await updateSession(request('/dashboard'));
  assert.equal(redirectTarget(response), `/login?next=${encodeURIComponent('/dashboard')}`);

  response = await updateSession(request('/admin', 'crack_local_session=1'));
  assert.equal(redirectTarget(response), '/dashboard');

  response = await updateSession(request('/admin', 'crack_local_session=1; crack_local_admin=1'));
  assert.equal(redirectTarget(response), null);

  response = await updateSession(request('/dashboard', 'crack_local_session=1'));
  assert.equal(redirectTarget(response), null);
});

test('personal pages (study time, quests, mistake notebook, topic notes) redirect signed-out visitors', async () => {
  for (const path of ['/study-time', '/quests', '/mistake-notebook', '/mistake-notebook/12', '/topic-notes']) {
    const response = await updateSession(request(path));
    assert.equal(redirectTarget(response), `/login?next=${encodeURIComponent(path)}`, path);
  }
  // Signed in (Supabase auth cookie present): no redirect.
  for (const path of ['/quests', '/topic-notes']) {
    const response = await updateSession(request(path, SUPABASE_COOKIE));
    assert.equal(redirectTarget(response), null, path);
  }
  // Only the exact prefix: a look-alike path is not gated.
  const response = await updateSession(request('/topic-notes-guide'));
  assert.equal(redirectTarget(response), null);
});

test('local auth mode gates the personal pages on the presence cookie too', async () => {
  process.env.NEXT_PUBLIC_AUTH_MODE = 'local';
  for (const path of ['/study-time', '/topic-notes']) {
    let response = await updateSession(request(path));
    assert.equal(redirectTarget(response), `/login?next=${encodeURIComponent(path)}`, path);
    response = await updateSession(request(path, 'crack_local_session=1'));
    assert.equal(redirectTarget(response), null, path);
  }
});

test('django auth mode: presence-cookie gate, no Supabase request, no Supabase keys needed', async () => {
  process.env.NEXT_PUBLIC_AUTH_MODE = 'django';
  // A reachable Supabase stand-in and a signed-in Supabase cookie: neither is used.
  process.env.NEXT_PUBLIC_SUPABASE_URL = FAKE_SUPABASE_URL;
  const before = supabaseRequests;

  let response = await updateSession(signedInAs('/dashboard', { app_metadata: { role: 'admin' } }));
  assert.equal(redirectTarget(response), `/login?next=${encodeURIComponent('/dashboard')}`);

  response = await updateSession(request('/questions/practice?year=2020'));
  assert.equal(redirectTarget(response), `/login?next=${encodeURIComponent('/questions/practice?year=2020')}`);

  response = await updateSession(request('/dashboard', 'crack_local_session=1'));
  assert.equal(redirectTarget(response), null);

  response = await updateSession(request('/admin', 'crack_local_session=1'));
  assert.equal(redirectTarget(response), '/dashboard');
  response = await updateSession(request('/admin', 'crack_local_session=1; crack_local_admin=1'));
  assert.equal(redirectTarget(response), null);

  // The emailed-link pages and the sign-in pages are always reachable (the
  // login page itself moves a confirmed session on; a stale cookie must not loop).
  for (const path of ['/verify-email', '/connect-google', '/reset-password', '/login', '/register', '/forgot-password']) {
    response = await updateSession(request(path, 'crack_local_session=1'));
    assert.equal(redirectTarget(response), null, path);
  }

  // Production django builds have no Supabase keys at all.
  const savedUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const savedKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  delete process.env.NEXT_PUBLIC_SUPABASE_URL;
  delete process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  try {
    response = await updateSession(request('/dashboard'));
    assert.equal(redirectTarget(response), `/login?next=${encodeURIComponent('/dashboard')}`);
  } finally {
    process.env.NEXT_PUBLIC_SUPABASE_URL = savedUrl;
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = savedKey;
  }

  assert.equal(supabaseRequests, before, 'django mode made a Supabase request');
});

test('no Supabase keys never crashes the middleware (MIDDLEWARE_INVOCATION_FAILED regression)', async () => {
  const savedUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const savedKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  delete process.env.NEXT_PUBLIC_SUPABASE_URL;
  delete process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  const before = supabaseRequests;
  try {
    // NEXT_PUBLIC_AUTH_MODE unset: without keys the build signs in natively (presence-cookie gate).
    delete process.env.NEXT_PUBLIC_AUTH_MODE;
    let response = await updateSession(request('/'));
    assert.equal(redirectTarget(response), null);
    response = await updateSession(request('/dashboard'));
    assert.equal(redirectTarget(response), `/login?next=${encodeURIComponent('/dashboard')}`);
    response = await updateSession(request('/dashboard', 'crack_local_session=1'));
    assert.equal(redirectTarget(response), null);
    // Explicit supabase mode without keys used to throw on every request: now it lets requests through.
    process.env.NEXT_PUBLIC_AUTH_MODE = 'supabase';
    for (const path of ['/', '/login', '/dashboard']) {
      response = await updateSession(request(path));
      assert.equal(response.status, 200, path);
      assert.equal(redirectTarget(response), null, path);
    }
  } finally {
    process.env.NEXT_PUBLIC_SUPABASE_URL = savedUrl;
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = savedKey;
  }
  assert.equal(supabaseRequests, before, 'made a Supabase request without Supabase keys');
});

test('router prefetches are never redirected (a cached redirect sent signed-in users back to /login)', async () => {
  process.env.NEXT_PUBLIC_AUTH_MODE = 'django';
  const prefetch = (path: string, headers: Record<string, string>, cookie = '') =>
    new NextRequest(new URL(path, 'http://localhost:3000'), { headers: { ...headers, ...(cookie ? { cookie } : {}) } });
  for (const headers of [
    { rsc: '1', 'next-router-prefetch': '1' },
    { rsc: '1', 'next-router-segment-prefetch': '/_tree' },
    { purpose: 'prefetch' },
    { 'sec-purpose': 'prefetch;prerender' },
  ]) {
    const label = JSON.stringify(headers);
    let response = await updateSession(prefetch('/questions', headers));
    assert.equal(redirectTarget(response), null, `signed-out prefetch ${label}`);
    response = await updateSession(prefetch('/admin', headers, 'crack_local_session=1'));
    assert.equal(redirectTarget(response), null, `non-admin prefetch of /admin ${label}`);
  }
  // Real navigations (including the RSC fetch of a click) are still gated.
  let response = await updateSession(prefetch('/questions', { rsc: '1' }));
  assert.equal(redirectTarget(response), `/login?next=${encodeURIComponent('/questions')}`);
  response = await updateSession(request('/questions'));
  assert.equal(redirectTarget(response), `/login?next=${encodeURIComponent('/questions')}`);
  response = await updateSession(request('/admin', 'crack_local_session=1'));
  assert.equal(redirectTarget(response), '/dashboard');
});
