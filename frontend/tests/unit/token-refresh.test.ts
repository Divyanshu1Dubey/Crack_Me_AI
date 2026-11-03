/**
 * Unit tests for src/lib/tokenRefresh.ts: one refresh at a time in the token
 * auth modes. The Django-native backend revokes a whole session when a
 * rotated refresh token is presented again (outside a 20 s window), so the
 * client must share one refresh across concurrent requests AND tabs.
 *
 * Run (from frontend/):
 *   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/token-refresh.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  browserRefreshLock,
  createTokenRefresher,
  type RefreshResponse,
  type StoredTokens,
} from '../../src/lib/tokenRefresh.ts';

/** Tokens shared by every "tab" (localStorage), with write / clear counters. */
function sharedStore(initial: StoredTokens = { access: 'A1', refresh: 'R1' }) {
  const state = { ...initial, writes: 0, clears: 0 };
  return {
    state,
    readTokens: () => ({ access: state.access, refresh: state.refresh }),
    writeTokens: (access: string, refresh: string | null) => {
      state.writes += 1;
      state.access = access;
      if (refresh) state.refresh = refresh;
    },
    clearTokens: () => {
      state.clears += 1;
      state.access = null;
      state.refresh = null;
    },
  };
}

/** The server's rotate(): the current refresh token rotates; anything else answers `otherwise`. */
function rotatingServer(otherwise: RefreshResponse = { status: 401, data: { code: 'session_revoked' } }) {
  const server = { current: 'R1', posts: [] as string[], n: 1 };
  const postRefresh = async (refresh: string): Promise<RefreshResponse> => {
    server.posts.push(refresh);
    await new Promise((resolve) => setTimeout(resolve, 5));
    if (refresh !== server.current) return otherwise;
    server.n += 1;
    server.current = `R${server.n}`;
    return { status: 200, data: { access: `A${server.n}`, refresh: server.current, session_id: 'sid' } };
  };
  return { server, postRefresh };
}

/** An exclusive lock shared by the refreshers of several "tabs" (Web Locks stand-in). */
function sharedLock() {
  let tail: Promise<unknown> = Promise.resolve();
  return <T,>(task: () => Promise<T>): Promise<T> => {
    const run = tail.then(task, task);
    tail = run.catch(() => undefined);
    return run;
  };
}

test('concurrent 401s in one tab share one refresh', async () => {
  const store = sharedStore();
  const { server, postRefresh } = rotatingServer();
  const refresh = createTokenRefresher({ ...store, postRefresh });
  const outcomes = await Promise.all([refresh('A1'), refresh('A1'), refresh('A1'), refresh('A1')]);
  assert.equal(server.posts.length, 1);
  for (const outcome of outcomes) assert.deepEqual(outcome, { ok: true, access: 'A2', refreshed: true });
  assert.deepEqual(store.readTokens(), { access: 'A2', refresh: 'R2' });
});

test('two tabs: the second waits for the lock, finds the new token and POSTs nothing', async () => {
  const store = sharedStore();
  const { server, postRefresh } = rotatingServer();
  const withLock = sharedLock();
  const tabA = createTokenRefresher({ ...store, postRefresh, withLock });
  const tabB = createTokenRefresher({ ...store, postRefresh, withLock });
  const [a, b] = await Promise.all([tabA('A1'), tabB('A1')]);
  assert.deepEqual(server.posts, ['R1']); // the old token is never presented twice
  assert.deepEqual(a, { ok: true, access: 'A2', refreshed: true });
  assert.deepEqual(b, { ok: true, access: 'A2', refreshed: false });
});

test('without the shared lock both tabs POST the same token (what the lock prevents)', async () => {
  const store = sharedStore();
  const { server, postRefresh } = rotatingServer();
  const tabA = createTokenRefresher({ ...store, postRefresh });
  const tabB = createTokenRefresher({ ...store, postRefresh });
  await Promise.all([tabA('A1'), tabB('A1')]);
  assert.deepEqual(server.posts, ['R1', 'R1']);
});

test('a request that failed with an older token is retried with the stored one, no POST', async () => {
  const store = sharedStore({ access: 'A7', refresh: 'R7' });
  let posts = 0;
  const refresh = createTokenRefresher({
    ...store,
    postRefresh: async () => {
      posts += 1;
      return { status: 200, data: { access: 'never' } };
    },
  });
  assert.deepEqual(await refresh('A6'), { ok: true, access: 'A7', refreshed: false });
  assert.equal(posts, 0);
});

test('the reuse-window answer (access only) keeps the stored refresh token', async () => {
  const store = sharedStore();
  const refresh = createTokenRefresher({
    ...store,
    postRefresh: async () => ({ status: 200, data: { access: 'A1b', session_id: 'sid' } }),
  });
  assert.deepEqual(await refresh('A1'), { ok: true, access: 'A1b', refreshed: true });
  assert.deepEqual(store.readTokens(), { access: 'A1b', refresh: 'R1' });
});

test('definitive refusals (400 / 401 / 403) clear the session and report the code', async () => {
  for (const [status, code] of [[401, 'session_revoked'], [401, 'token_not_valid'], [403, 'account_blocked'], [400, 'bad']] as const) {
    const store = sharedStore();
    const refresh = createTokenRefresher({ ...store, postRefresh: async () => ({ status, data: { code } }) });
    assert.deepEqual(await refresh('A1'), { ok: false, definitive: true, status, code }, `${status} ${code}`);
    assert.deepEqual(store.readTokens(), { access: null, refresh: null });
    assert.equal(store.state.clears, 1);
  }
});

test('a network error, 429 or 5xx keeps the session (django mode): a blip signs nobody out', async () => {
  const answers: Array<() => Promise<RefreshResponse>> = [
    async () => { throw new TypeError('Failed to fetch'); },
    async () => ({ status: 503, data: null }),
    async () => ({ status: 500, data: {} }),
    async () => ({ status: 429, data: { code: 'too_many_attempts' } }),
    async () => ({ status: 200, data: {} }), // no access token in the answer
  ];
  for (const answer of answers) {
    const store = sharedStore();
    const refresh = createTokenRefresher({ ...store, postRefresh: answer });
    const outcome = await refresh('A1');
    assert.equal(outcome.ok, false);
    assert.equal(outcome.ok === false && outcome.definitive, false);
    assert.deepEqual(store.readTokens(), { access: 'A1', refresh: 'R1' });
    assert.equal(store.state.clears, 0);
  }
});

test('local mode keeps its old rule: any failed refresh clears the session', async () => {
  const store = sharedStore();
  const refresh = createTokenRefresher({
    ...store,
    postRefresh: async () => ({ status: 503, data: null }),
    clearOnTransientFailure: true,
  });
  const outcome = await refresh('A1');
  assert.equal(outcome.ok, false);
  assert.deepEqual(store.readTokens(), { access: null, refresh: null });
});

test('a sign-in in another tab during the refresh wins: its tokens are not overwritten', async () => {
  const store = sharedStore();
  const refresh = createTokenRefresher({
    ...store,
    postRefresh: async () => {
      store.state.access = 'NEW-A';
      store.state.refresh = 'NEW-R'; // another tab signed in meanwhile
      return { status: 200, data: { access: 'A2', refresh: 'R2' } };
    },
  });
  assert.deepEqual(await refresh('A1'), { ok: true, access: 'NEW-A', refreshed: false });
  assert.deepEqual(store.readTokens(), { access: 'NEW-A', refresh: 'NEW-R' });
  assert.equal(store.state.writes, 0);
});

test('a sign-out in another tab during the refresh stays signed out', async () => {
  const store = sharedStore();
  const refresh = createTokenRefresher({
    ...store,
    postRefresh: async () => {
      store.state.access = null;
      store.state.refresh = null;
      return { status: 200, data: { access: 'A2', refresh: 'R2' } };
    },
  });
  assert.deepEqual(await refresh('A1'), { ok: false, definitive: true, status: 200, code: 'signed_out' });
  assert.deepEqual(store.readTokens(), { access: null, refresh: null });
});

test('no refresh token: nothing is POSTed', async () => {
  const store = sharedStore({ access: null, refresh: null });
  let posts = 0;
  const refresh = createTokenRefresher({ ...store, postRefresh: async () => { posts += 1; return { status: 200, data: {} }; } });
  assert.deepEqual(await refresh(null), { ok: false, definitive: true, status: 0, code: 'no_refresh_token' });
  assert.equal(posts, 0);
  assert.equal(store.state.clears, 0);
});

test('after a refresh settles, the next 401 with the new token refreshes again', async () => {
  const store = sharedStore();
  const { server, postRefresh } = rotatingServer();
  const refresh = createTokenRefresher({ ...store, postRefresh });
  assert.equal((await refresh('A1')).ok, true);
  assert.deepEqual(await refresh('A2'), { ok: true, access: 'A3', refreshed: true });
  assert.deepEqual(server.posts, ['R1', 'R2']);
});

test('browserRefreshLock uses the Web Locks API, and runs the task without it when missing', async () => {
  const names: string[] = [];
  const locks = {
    request: async (name: string, _options: { signal?: AbortSignal }, callback: () => Promise<unknown>) => {
      names.push(name);
      return callback();
    },
  };
  assert.equal(await browserRefreshLock('crack_auth_refresh', 1000, locks)(async () => 'ran'), 'ran');
  assert.deepEqual(names, ['crack_auth_refresh']);
  assert.equal(await browserRefreshLock('x', 1000, undefined)(async () => 'no-locks'), 'no-locks');
});

test('browserRefreshLock: a lock never granted (stuck tab) times out and the task still runs, once', async () => {
  const neverGranted = {
    request: (_name: string, options: { signal?: AbortSignal }) =>
      new Promise((_resolve, reject) => {
        options.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')));
      }),
  };
  let runs = 0;
  const result = await browserRefreshLock('crack_auth_refresh', 20, neverGranted)(async () => {
    runs += 1;
    return 'fallback';
  });
  assert.equal(result, 'fallback');
  assert.equal(runs, 1);

  // An error from the task itself is not retried without the lock.
  const granted = { request: async (_n: string, _o: { signal?: AbortSignal }, cb: () => Promise<unknown>) => cb() };
  let attempts = 0;
  await assert.rejects(
    browserRefreshLock('crack_auth_refresh', 1000, granted)(async () => {
      attempts += 1;
      throw new Error('task failed');
    }),
    /task failed/,
  );
  assert.equal(attempts, 1);
});
