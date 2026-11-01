/**
 * safeInternalPath (src/lib/auth-redirect.ts): the guard on every post-sign-in
 * redirect (`?next=` on /login and /auth/callback, and the path auth.tsx
 * remembers across an OAuth / magic-link round trip).
 *
 * Each value is also resolved the way Next's router does it
 * (`new URL(href, location.href)`, see client/components/
 * sequential-router-queue.js), so a test fails if anything the guard lets
 * through would leave the site.
 *
 * Run (from frontend/):
 *   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/auth-redirect.test.ts
 * (AUTH_REDIRECT_UNDER_TEST=<file URL> runs the same checks against another
 * copy of the module, e.g. an older revision.)
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';

const { safeInternalPath } = (await import(
    process.env.AUTH_REDIRECT_UNDER_TEST || '../../src/lib/auth-redirect.ts'
)) as typeof import('../../src/lib/auth-redirect.ts');

const SITE = 'https://cracklabs.app';
const FALLBACK = '/dashboard-fallback';

/** Where router.push / router.replace would really go from the callback page. */
const routerTarget = (href: string) => new URL(href, `${SITE}/auth/callback?next=x`);

/** `?next=<raw>` as the browser hands it to useSearchParams().get('next'). */
const nextParamFrom = (rawQueryValue: string) =>
    new URL(`${SITE}/auth/callback?next=${rawQueryValue}`).searchParams.get('next');

test('tab / LF / CR between the slashes no longer leave the site (?next=/%09/evil.example)', () => {
    const attacks = [
        '/%09/evil.example/login',
        '/%0A/evil.example',
        '/%0D/evil.example',
        '/%09%5Cevil.example',
        '/%0D%0A/evil.example',
        '/%09%09//evil.example',
        '/%5C%09evil.example',
    ];
    for (const raw of attacks) {
        const next = nextParamFrom(raw);
        assert.ok(next, raw);
        // Precondition: the router itself would really send the user off-site.
        assert.notEqual(routerTarget(next).origin, SITE, `${raw} is not a real attack vector`);
        assert.equal(safeInternalPath(next, FALLBACK), FALLBACK, `${JSON.stringify(next)} was accepted`);
    }
});

test('control characters, whitespace and back-slashes are rejected anywhere', () => {
    for (const value of [
        '/\t/evil.example/login',
        '/\n/evil.example',
        '/\r/evil.example',
        '/\t\\evil.example',
        '/\\evil.example',
        '/a\\b',
        '/dash board',
        '/dashboard\u0000',
        '/dashboard\u007F',
        '/dashboard\u001B',
        '/dashboard ',
    ]) {
        assert.equal(safeInternalPath(value, FALLBACK), FALLBACK, JSON.stringify(value));
    }
});

test('values that only decode to something dangerous are rejected', () => {
    for (const value of [
        '/%2F%2Fevil.example',
        '/%5C%5Cevil.example',
        '/%5Cevil.example',
        '/%09/evil.example',
        '/%09%5Cevil.example',
        '/%0A%0D',
        '/./%2F/evil.example',
        '/%E0%A4%A', // malformed escape
    ]) {
        assert.equal(safeInternalPath(value, FALLBACK), FALLBACK, value);
    }
});

test('the older protections still hold', () => {
    for (const value of [
        '//evil.example',
        '//evil.example/login',
        '///evil.example',
        '/.//evil.example',
        '/a/..//evil.example',
        '\\\\evil.example',
        'https://evil.example',
        'HTTPS://evil.example',
        'javascript:alert(1)',
        '/javascript:alert(1)',
        'evil.example',
        ' /dashboard',
        '',
        null,
        undefined,
    ]) {
        assert.equal(safeInternalPath(value, FALLBACK), FALLBACK, JSON.stringify(value));
    }
});

test('a non-string value (tampered localStorage) falls back instead of throwing', () => {
    for (const value of [42, {}, ['/dashboard'], true]) {
        assert.equal(safeInternalPath(value as unknown as string, FALLBACK), FALLBACK);
    }
});

test('legitimate deep links come back unchanged', () => {
    for (const value of [
        '/',
        '/dashboard',
        '/admin',
        '/admin/import-center',
        '/reset-password',
        '/analytics/heatmap',
        '/questions/practice?year=2020&exam=cms',
        '/practice?id=12',
        '/questions?subject=General+Medicine',
        '/questions?topic=General%20Medicine&page=2',
        '/topic-notes#cardiology',
        '/dashboard/',
    ]) {
        assert.equal(safeInternalPath(value, FALLBACK), value, value);
    }
});

test('the next= values the app builds survive the round trip', () => {
    // middleware.ts: loginUrl.searchParams.set('next', pathname + search)
    const loginUrl = new URL('/login', SITE);
    loginUrl.searchParams.set('next', '/questions/practice?year=2020&exam=cms&q=General%20Medicine');
    assert.equal(
        safeInternalPath(new URL(loginUrl.href).searchParams.get('next'), FALLBACK),
        '/questions/practice?year=2020&exam=cms&q=General%20Medicine',
    );
    // useRequireAuth / ExamQuestionBank: `/login?next=${encodeURIComponent(next)}`
    const built = `/login?next=${encodeURIComponent('/questions?subject=General+Medicine&year=2019')}`;
    assert.equal(
        safeInternalPath(new URL(built, SITE).searchParams.get('next'), FALLBACK),
        '/questions?subject=General+Medicine&year=2019',
    );
    // auth.tsx stores the accepted path as JSON and checks it again on return.
    const stored = JSON.parse(JSON.stringify({ path: safeInternalPath('/practice?id=7#q2', '') })) as { path: string };
    assert.equal(safeInternalPath(stored.path, ''), '/practice?id=7#q2');
});

test('whatever is accepted stays on the site and is a canonical same-origin path', () => {
    const probes = [
        '/dashboard', '/a/../b', '/a/./b', '/%2e%2e/admin', '/q?x=é', '/x#y', '/x?', '/x#',
        '/%09/evil.example', '/\t/evil.example', '/.//evil.example', '/%2F/evil.example',
    ];
    for (const value of probes) {
        const out = safeInternalPath(value, '');
        if (!out) continue;
        assert.ok(out.startsWith('/') && !out.startsWith('//'), `${value} -> ${out}`);
        assert.equal(routerTarget(out).origin, SITE, `${value} -> ${out}`);
        // Idempotent: auth.tsx re-checks the stored value.
        assert.equal(safeInternalPath(out, ''), out, `${value} -> ${out}`);
    }
    // Dot segments are resolved, not passed through.
    assert.equal(safeInternalPath('/a/../b', ''), '/b');
    assert.equal(safeInternalPath('/%2e%2e/admin', ''), '/admin');
});
