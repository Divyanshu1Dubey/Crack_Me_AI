/**
 * Unit tests for src/lib/authFragment.ts: the one-time values of the emailed
 * links of the Django-native sign-in are read from the URL FRAGMENT only and
 * removed from the address bar (/verify-email, /reset-password,
 * /connect-google).
 *
 * Run (from frontend/):
 *   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/auth-fragment.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseAuthFragment, stripAuthFragment, takeAuthFragment } from '../../src/lib/authFragment.ts';

/** location + history stand-in recording replaceState calls. */
function fakeWindow(url: string, { throwOnReplace = false } = {}) {
  const parsed = new URL(url);
  const calls: Array<[unknown, string, string]> = [];
  const win = {
    location: { pathname: parsed.pathname, search: parsed.search, hash: parsed.hash },
    history: {
      replaceState: (state: unknown, title: string, next?: string | URL | null) => {
        if (throwOnReplace) throw new Error('SecurityError');
        calls.push([state, title, String(next)]);
        const after = new URL(String(next), parsed.origin);
        win.location.pathname = after.pathname;
        win.location.search = after.search;
        win.location.hash = after.hash;
      },
    },
  };
  return { win, calls };
}

test('a sign-up link: #token=...', () => {
  assert.deepEqual(parseAuthFragment('#token=Zx9_kQ-3vT0aBcD1eF2gH3iJ4kL5mN6o'), {
    token: 'Zx9_kQ-3vT0aBcD1eF2gH3iJ4kL5mN6o',
    uid: null,
  });
});

test('reset / existing-account links: #uid=..&token=.. (order and "#" optional)', () => {
  const expected = { uid: 'MTI3', token: 'cbm4qa-0f1e2d3c4b5a69788796a5b4c3d2e1f0' };
  assert.deepEqual(parseAuthFragment('#uid=MTI3&token=cbm4qa-0f1e2d3c4b5a69788796a5b4c3d2e1f0'), expected);
  assert.deepEqual(parseAuthFragment('token=cbm4qa-0f1e2d3c4b5a69788796a5b4c3d2e1f0&uid=MTI3'), expected);
});

test('a connect-Google link keeps the signed token as sent (":" and "." of django.core.signing)', () => {
  const token = '.eJxVjEEOwiAQRe_CuiYwUJAuvYAncAEDY1MxbQTaxHh32-pCt-_mZ5QIlZUPqi.1uXyZ:1tYQbE:Hk3T_J8e';
  assert.equal(parseAuthFragment(`#token=${token}`).token, token);
  // Percent-encoded by a mail client: decoded once.
  assert.equal(parseAuthFragment(`#token=${encodeURIComponent(token)}`).token, token);
});

test('missing, empty or malformed values give null', () => {
  for (const hash of [undefined, null, '', '#', '#token=', '#uid=MTI', '#foo=bar', '#token=%E0%A4%A']) {
    const parsed = parseAuthFragment(hash as string | null | undefined);
    assert.equal(parsed.token, null, String(hash));
  }
  // Whitespace, quotes and angle brackets are never part of a backend token.
  for (const bad of ['a b', 'a"b', "a'b", 'a<b>', 'a\\b']) {
    assert.equal(parseAuthFragment(`#token=${encodeURIComponent(bad)}`).token, null, bad);
  }
  assert.equal(parseAuthFragment(`#token=${'a'.repeat(2049)}`).token, null);
  assert.equal(parseAuthFragment(`#token=${'a'.repeat(5000)}`).token, null);
  // Surrounding spaces are trimmed.
  assert.equal(parseAuthFragment('#token=%20abc123%20').token, 'abc123');
});

test('stripAuthFragment drops only the fragment (path and query stay) with history.replaceState', () => {
  const { win, calls } = fakeWindow('https://www.cracklabs.app/reset-password?utm_source=mail#uid=MTI&token=t-1');
  stripAuthFragment(win);
  assert.deepEqual(calls, [[null, '', '/reset-password?utm_source=mail']]);
  assert.equal(win.location.hash, '');

  // Nothing to strip: no history entry is touched.
  stripAuthFragment(win);
  assert.equal(calls.length, 1);

  // A browser that refuses history changes does not break the page.
  const refusing = fakeWindow('https://www.cracklabs.app/verify-email#token=abc', { throwOnReplace: true });
  assert.doesNotThrow(() => stripAuthFragment(refusing.win));
});

test('takeAuthFragment reads once and clears the address bar; the query string is never read', () => {
  const { win, calls } = fakeWindow('https://www.cracklabs.app/verify-email?token=from-query#uid=MTI&token=from-fragment');
  assert.deepEqual(takeAuthFragment(win), { uid: 'MTI', token: 'from-fragment' });
  assert.equal(calls.length, 1);
  assert.equal(win.location.hash, '');
  // A second read (React runs effects twice in development) finds nothing.
  assert.deepEqual(takeAuthFragment(win), { uid: null, token: null });

  const queryOnly = fakeWindow('https://www.cracklabs.app/reset-password?uid=MTI&token=abc');
  assert.deepEqual(takeAuthFragment(queryOnly.win), { uid: null, token: null });
  assert.equal(queryOnly.calls.length, 0);

  // Server-side rendering: no window, nothing read.
  assert.deepEqual(takeAuthFragment(undefined), { uid: null, token: null });
});
