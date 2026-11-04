// The sitemap and the RSS feed list the same posts as the blog pages: the
// published posts of the database catalog (GET /api/blog/posts/catalog/), or
// the static posts while a build cannot reach the API.
// Run (from frontend/):
//   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/blog-routes.test.ts
import { test } from 'node:test';
import assert from 'node:assert/strict';

import sitemap from '../../src/app/sitemap.ts';
import { GET as feed } from '../../src/app/blog/feed.xml/route.ts';
import { MIN_INDEXABLE_TAG_POSTS, getAllPosts } from '../../src/lib/blog.ts';

const SITE = 'https://www.cracklabs.app';

function record(slug: string, tags: string[], extra: Record<string, unknown> = {}) {
    return {
        slug, title: `Post ${slug} & <friends>`, description: `About ${slug}`, excerpt: 'e', category: 'Exam Strategy', tags,
        author_id: 'crackcms-editorial', reviewed_by: 'crackcms-editorial', author: 'CrackCMS Editorial Team',
        author_role: 'Clinical Content Editors, CrackCMS', date_published: '2026-11-01', date_modified: '2026-11-02',
        reading_time: '5 min', is_published: true, ...extra,
    };
}

const CATALOG = [
    record('admin-written-post', ['Renal', 'Strategy']),
    record('second-post', ['Renal']),
    record('third-post', ['Renal'], { date_published: 'not a date', date_modified: '' }),
    record('a-draft-somehow', ['Renal'], { is_published: false }),
];

async function withCatalog(fn: () => Promise<void>) {
    const saved = { fetch: globalThis.fetch, env: { ...process.env }, warn: console.warn };
    process.env.NODE_ENV = 'production';
    process.env.NEXT_PUBLIC_API_URL = 'https://api.example.test/api';
    delete process.env.NEXT_PHASE;
    delete process.env.BLOG_SOURCE;
    globalThis.fetch = (async (input: string | URL) => {
        assert.equal(String(input), 'https://api.example.test/api/blog/posts/catalog/');
        return new Response(JSON.stringify({ count: CATALOG.length, results: CATALOG }), { status: 200 });
    }) as unknown as typeof fetch;
    console.warn = () => {};
    try {
        await fn();
    } finally {
        globalThis.fetch = saved.fetch;
        process.env = saved.env;
        console.warn = saved.warn;
    }
}

test('the sitemap lists exactly the published catalog posts, their categories, indexable tags and authors', async () => {
    await withCatalog(async () => {
        const entries = await sitemap();
        const paths = entries.map((e) => new URL(e.url).pathname);
        assert.equal(new Set(paths).size, paths.length, 'no duplicate URLs');
        const posts = paths.filter((p) => /^\/blog\/[^/]+$/.test(p) && p !== '/blog/feed.xml');
        assert.deepEqual(posts.sort(), ['/blog/admin-written-post', '/blog/second-post', '/blog/third-post']);
        assert.ok(!paths.includes('/blog/upsc-cms-last-5-days-strategy'), 'a static post missing from the database is not listed');
        assert.ok(paths.includes('/blog/category/exam-strategy'));
        assert.deepEqual(paths.filter((p) => p.startsWith('/blog/tag/')), ['/blog/tag/renal'],
            `only tags with ${MIN_INDEXABLE_TAG_POSTS}+ posts`);
        assert.ok(paths.includes('/blog/author/crackcms-editorial'));
        for (const entry of entries) {
            const modified = entry.lastModified instanceof Date ? entry.lastModified : new Date(String(entry.lastModified));
            assert.ok(!isNaN(modified.getTime()), `${entry.url} has a valid lastModified`);
        }
        const first = entries.find((e) => e.url === `${SITE}/blog/admin-written-post`);
        assert.equal((first?.lastModified as Date).toISOString().slice(0, 10), '2026-11-02');
    });
});

test('the RSS feed lists the same posts, escaped, without an invalid pubDate', async () => {
    await withCatalog(async () => {
        const response = await feed();
        assert.match(response.headers.get('Content-Type') ?? '', /application\/rss\+xml/);
        const xml = await response.text();
        const links = [...xml.matchAll(/<item>[\s\S]*?<link>([^<]+)<\/link>/g)].map((m) => m[1]);
        assert.deepEqual(links, [`${SITE}/blog/admin-written-post`, `${SITE}/blog/second-post`, `${SITE}/blog/third-post`]);
        assert.match(xml, /<title>Post admin-written-post &amp; &lt;friends&gt;<\/title>/);
        assert.equal((xml.match(/<pubDate>/g) ?? []).length, 2, 'the post with an unparseable date has no pubDate');
        assert.doesNotMatch(xml, /Invalid Date/);
    });
});

test('during a build without the API, the sitemap lists the static posts instead of failing', async () => {
    const saved = { fetch: globalThis.fetch, env: { ...process.env }, warn: console.warn };
    process.env.NODE_ENV = 'production';
    process.env.NEXT_PHASE = 'phase-production-build';
    globalThis.fetch = (async () => { throw new TypeError('fetch failed'); }) as unknown as typeof fetch;
    console.warn = () => {};
    try {
        const paths = (await sitemap()).map((e) => new URL(e.url).pathname);
        for (const post of getAllPosts()) assert.ok(paths.includes(`/blog/${post.slug}`), post.slug);
    } finally {
        globalThis.fetch = saved.fetch;
        process.env = saved.env;
        console.warn = saved.warn;
    }
});
