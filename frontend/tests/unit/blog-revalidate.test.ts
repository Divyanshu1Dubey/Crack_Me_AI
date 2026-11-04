// POST /api/blog-revalidate (src/app/api/blog-revalidate/route.ts): only an admin,
// by the backend's own answer for the caller's token, may refresh the public blog
// (src/lib/blogRevalidate.ts). Also: the "Edit post" button's admin rule.
// Run (from frontend/):
//   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/blog-revalidate.test.ts
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { confirmBlogAdmin, revalidationSlugs } from '../../src/lib/blogRevalidate.ts';

const API = 'https://api.example/api';

function backend(status: number, body: unknown) {
    const calls: { url: string; init: RequestInit }[] = [];
    const fetchImpl = async (url: string, init: RequestInit) => {
        calls.push({ url, init });
        return { ok: status >= 200 && status < 300, status, json: async () => body };
    };
    return { calls, fetchImpl };
}

test('no bearer token: refused without asking the backend', async () => {
    const { calls, fetchImpl } = backend(200, { role: 'admin' });
    for (const header of ['', 'Basic abc', 'Bearer ', 'token']) {
        assert.deepEqual(await confirmBlogAdmin(header, null, API, fetchImpl), {
            ok: false, status: 401, detail: 'Sign in as an admin to refresh the blog.',
        });
    }
    assert.equal(calls.length, 0);
});

test('the backend decides: admins pass, students and failures do not', async () => {
    const cases: [number, unknown, number | true][] = [
        [200, { role: 'admin', is_admin: true }, true],
        [200, { role: 'student', is_admin: true }, true],
        [200, { role: 'student', is_admin: false }, 403],
        [200, { role: 'Admin' }, 403],
        [200, null, 403],
        [401, { code: 'token_not_valid' }, 401],
        [403, {}, 403],
        [500, {}, 502],
    ];
    for (const [status, body, expected] of cases) {
        const { calls, fetchImpl } = backend(status, body);
        const result = await confirmBlogAdmin('Bearer tok-123', 'device-1', API, fetchImpl);
        assert.equal(result.ok ? true : result.status, expected, `${status} ${JSON.stringify(body)}`);
        assert.equal(calls[0].url, `${API}/auth/profile/`);
        const headers = calls[0].init.headers as Record<string, string>;
        assert.equal(headers.Authorization, 'Bearer tok-123', 'the caller\'s own token is checked');
        assert.equal(headers['X-Session-ID'], 'device-1');
    }
    const unreachable = await confirmBlogAdmin('Bearer x', null, API, async () => { throw new Error('ECONNREFUSED'); });
    assert.deepEqual(unreachable, { ok: false, status: 502, detail: 'Could not reach the API to confirm your admin access.' });
});

test('slugs: well-formed, unique, at most ten', () => {
    assert.deepEqual(revalidationSlugs({ slugs: ['a-post', 'a-post', '../etc', 'Bad Slug', 7, 'b'] }), ['a-post', 'b']);
    assert.deepEqual(revalidationSlugs({ slugs: Array.from({ length: 15 }, (_, i) => `p-${i}`) }).length, 10);
    assert.deepEqual(revalidationSlugs(null), []);
    assert.deepEqual(revalidationSlugs({ slugs: 'one' }), []);
});

test('the route expires the blog data and re-renders /blog and the posts, after the admin check', () => {
    const route = readFileSync(fileURLToPath(new URL('../../src/app/api/blog-revalidate/route.ts', import.meta.url)), 'utf8');
    const check = route.indexOf('confirmBlogAdmin(');
    assert.ok(check > 0 && check < route.indexOf("revalidateTag('blog', { expire: 0 })"), 'checked before revalidating');
    assert.match(route, /revalidatePath\('\/blog'\)/);
    assert.match(route, /revalidatePath\(`\/blog\/\$\{slug\}`\)/);
    // lib/blog.ts tags every blog API read 'blog' (what revalidateTag expires).
    assert.match(readFileSync(fileURLToPath(new URL('../../src/lib/blog.ts', import.meta.url)), 'utf8'), /tags: \['blog'\]/);
});
