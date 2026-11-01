/**
 * Unit tests for src/lib/sessionRefreshGate.ts: the bounded Supabase
 * refresh-after-401 used by src/lib/api.ts.
 *
 * Run (from frontend/):  node --test tests/unit/session-refresh-gate.test.ts
 *
 * `tests/` is excluded from tsconfig, so the explicit `.ts` import below does
 * not affect `tsc --noEmit -p .`.
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRefreshGate } from '../../src/lib/sessionRefreshGate.ts';

function fakeClock(start = 1_000_000) {
  let t = start;
  return { now: () => t, advance: (ms: number) => { t += ms; } };
}

/** A Supabase stand-in whose every refresh returns a new access token. */
function rotatingRefresh() {
  const state = { calls: 0, current: 't0' };
  const refresh = async () => {
    state.calls += 1;
    state.current = `t${state.calls}`;
    return state.current;
  };
  return { state, refresh };
}

test('concurrent 401s share one refresh', async () => {
  const clock = fakeClock();
  let calls = 0;
  let release: (token: string) => void = () => {};
  const gate = createRefreshGate(
    () => {
      calls += 1;
      return new Promise<string>((resolve) => { release = resolve; });
    },
    { now: clock.now },
  );
  const pending = [gate('t0'), gate('t0'), gate('t0')];
  release('t1');
  assert.deepEqual(await Promise.all(pending), ['t1', 't1', 't1']);
  assert.equal(calls, 1);
});

test('a backend that rejects every session cannot drive a refresh loop', async () => {
  // The old loop: refresh -> TOKEN_REFRESHED -> profile re-fetch -> 401 ->
  // refresh ... Model the worst case (something re-fetches after every
  // refresh, the backend 401s everything) and count Supabase refreshes.
  const clock = fakeClock();
  const { state, refresh } = rotatingRefresh();
  const gate = createRefreshGate(refresh, { now: clock.now });

  for (let i = 0; i < 100; i++) {
    const retryWith = await gate(state.current); // request with the current token: 401
    if (retryWith) await gate(retryWith); // the single retry 401s too (no second refresh for it)
    clock.advance(50);
  }
  assert.equal(state.calls, 1);

  // One request every 10 s for an hour: at most one refresh per 10 minutes.
  for (let second = 0; second < 3600; second += 10) {
    await gate(state.current);
    clock.advance(10_000);
  }
  assert.ok(state.calls <= 7, `expected <= 7 refreshes in an hour, got ${state.calls}`);
});

test('a request sent with an older token during the cooldown retries with the latest one', async () => {
  const clock = fakeClock();
  const { state, refresh } = rotatingRefresh();
  const gate = createRefreshGate(refresh, { now: clock.now });
  assert.equal(await gate('t0'), 't1');
  clock.advance(5_000);
  assert.equal(await gate('t0'), 't1'); // in flight before the refresh finished
  assert.equal(state.calls, 1);
});

test('an expired token refreshes again once the cooldown has passed', async () => {
  const clock = fakeClock();
  const { state, refresh } = rotatingRefresh();
  const gate = createRefreshGate(refresh, { now: clock.now });
  assert.equal(await gate('t0'), 't1');
  clock.advance(31_000);
  // A token the gate did not produce (e.g. from supabase-js auto refresh).
  assert.equal(await gate('auto-refreshed'), 't2');
  assert.equal(state.calls, 2);
});

test('a failed refresh gives no token and does not wedge the gate', async () => {
  const clock = fakeClock();
  let calls = 0;
  const outcomes: Array<() => Promise<string | null>> = [
    async () => null, // e.g. network error
    () => { throw new Error('synchronous failure'); },
    async () => 'fresh',
  ];
  const gate = createRefreshGate(() => outcomes[calls++](), { now: clock.now });
  assert.equal(await gate('t0'), null);
  clock.advance(5_000);
  assert.equal(await gate('t0'), null); // cooldown: no second call yet
  assert.equal(calls, 1);
  clock.advance(31_000);
  assert.equal(await gate('t0'), null); // threw synchronously
  clock.advance(31_000);
  assert.equal(await gate('t0'), 'fresh');
  assert.equal(calls, 3);
});
