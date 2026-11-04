// The public blog reads the blog_engine database (src/lib/blog.ts):
// records → posts (drafts never, unsafe links never), the API base URL,
// the failure policy (static fallback while building / in dev, throw on a
// production server so ISR keeps the last good page) and the list helpers.
// Run (from frontend/):
//   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/blog-source.test.ts
import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
    DEFAULT_PRIMARY_CTA,
    authorSlugsOf,
    blogApiBaseUrl,
    blogFailurePolicy,
    categoriesOf,
    getAllPosts,
    getPostBySlug,
    getRelatedPosts,
    linkRelatedPosts,
    loadBlogCatalog,
    loadBlogPost,
    postFromRecord,
    postLastModified,
    postsInCategory,
    postsWithTag,
    relatedPostsFrom,
    safeLinkTarget,
    tagOf,
    tagsOf,
    type BlogPost,
} from '../../src/lib/blog.ts';

const RECORD = {
    slug: 'db-post',
    title: 'A database post',
    description: 'd',
    excerpt: 'e',
    category: 'UPSC CMS',
    tags: ['UPSC CMS', 'Renal'],
    author_id: 'crackcms-editorial',
    author: 'CrackCMS Editorial Team',
    author_role: 'Clinical Content Editors, CrackCMS',
    date_published: '2026-11-01',
    reading_time: '6 min',
    body: '## Hello\n\nBody.',
    is_published: true,
};

type Env = Record<string, string | undefined>;
const ENV_KEYS = ['NODE_ENV', 'NEXT_PHASE', 'BLOG_SOURCE', 'BLOG_API_URL', 'NEXT_PUBLIC_API_URL', 'VERCEL'];

/** Run `fn` with these env values and a fetch stub; restore both afterwards. */
async function withEnv(env: Env, fetchStub: typeof fetch, fn: () => Promise<void>) {
    const saved: Env = Object.fromEntries(ENV_KEYS.map((k) => [k, process.env[k]]));
    const savedFetch = globalThis.fetch;
    const savedWarn = console.warn;
    for (const k of ENV_KEYS) delete process.env[k];
    Object.assign(process.env, Object.fromEntries(Object.entries(env).filter(([, v]) => v !== undefined)));
    globalThis.fetch = fetchStub;
    console.warn = () => {};
    try {
        await fn();
    } finally {
        for (const k of ENV_KEYS) {
            if (saved[k] === undefined) delete process.env[k];
            else process.env[k] = saved[k];
        }
        globalThis.fetch = savedFetch;
        console.warn = savedWarn;
    }
}

function json(body: unknown, status = 200): Response {
    return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

const unreachable = (async () => { throw new TypeError('fetch failed'); }) as unknown as typeof fetch;

test('records become posts; drafts and unusable records never do', () => {
    const post = postFromRecord(RECORD);
    assert.ok(post);
    assert.equal(post.slug, 'db-post');
    assert.equal(post.dateModified, '2026-11-01', 'falls back to the publish date');
    assert.equal(post.updatedAt, '2026-11-01');
    assert.deepEqual(post.primaryCta, DEFAULT_PRIMARY_CTA, 'a post without a CTA gets the default one');
    assert.equal(postFromRecord({ ...RECORD, is_published: false }), null);
    assert.equal(postFromRecord({ ...RECORD, slug: '' }), null);
    assert.equal(postFromRecord({ ...RECORD, title: '   ' }), null);
    assert.equal(postFromRecord(null), null);
    assert.equal(postFromRecord('nope'), null);
    // Partial and malformed fields are tolerated.
    const odd = postFromRecord({ ...RECORD, tags: 'UPSC CMS', difficulty: 'expert', word_count: '12', faqs: [{ q: 'Q' }, 'x', { q: 'Q', a: 'A' }] });
    assert.ok(odd);
    assert.deepEqual(odd.tags, []);
    assert.equal(odd.difficulty, 'intermediate');
    assert.equal(odd.wordCount, undefined);
    assert.deepEqual(odd.faqs, [{ q: 'Q', a: 'A' }]);
    assert.equal(odd.body, '## Hello\n\nBody.');
    assert.equal(postFromRecord({ ...RECORD, body: undefined })?.body, '', 'catalog rows have no body');
});

test('links in a record are internal paths or http(s) URLs only', () => {
    for (const href of ['javascript:alert(1)', '//evil.example/x', 'data:text/html,hi', ' ', 'mailto:a@b.c']) {
        assert.deepEqual(postFromRecord({ ...RECORD, primary_cta: { label: 'Go', href } })?.primaryCta, DEFAULT_PRIMARY_CTA, href);
    }
    const post = postFromRecord({
        ...RECORD,
        primary_cta: { label: 'Practise', href: '/questions?exam=cms', eventName: 'blog_practice_intent', eventParams: { source: 'x' } },
        references: [{ label: 'Evil', url: 'javascript:alert(1)' }, { label: 'UPSC', url: 'https://upsc.gov.in/' }, { url: 'https://x.y/' }],
        related_exam_paths: ['/cms', 'https://example.com', '//evil', 'javascript:x'],
        cover_image: 'javascript:alert(1)',
    });
    assert.ok(post);
    assert.deepEqual(post.primaryCta, { label: 'Practise', href: '/questions?exam=cms', eventName: 'blog_practice_intent', eventParams: { source: 'x' } });
    assert.deepEqual(post.references, [{ label: 'Evil' }, { label: 'UPSC', url: 'https://upsc.gov.in/' }]);
    assert.deepEqual(post.relatedExamPaths, ['/cms']);
    assert.equal(post.coverImage, undefined);
    assert.equal(safeLinkTarget('  /blog/x '), '/blog/x');
    assert.equal(safeLinkTarget('https://cracklabs.app/a b'), '');
});

test('the API base: BLOG_API_URL, else NEXT_PUBLIC_API_URL, never a relative, retired or Vercel-localhost URL', () => {
    assert.equal(blogApiBaseUrl({ BLOG_API_URL: 'https://internal.example/', NEXT_PUBLIC_API_URL: 'https://api.cracklabs.app/api' }), 'https://internal.example/api');
    assert.equal(blogApiBaseUrl({ NEXT_PUBLIC_API_URL: 'https://api.cracklabs.app/api/' }), 'https://api.cracklabs.app/api');
    assert.equal(blogApiBaseUrl({ NEXT_PUBLIC_API_URL: '/api/proxy', NODE_ENV: 'development' }), 'http://localhost:8000/api');
    assert.equal(blogApiBaseUrl({ NEXT_PUBLIC_API_URL: 'https://crackcms-backend.onrender.com/api', NODE_ENV: 'production' }), 'https://api.cracklabs.app/api');
    assert.equal(blogApiBaseUrl({ NEXT_PUBLIC_API_URL: 'http://localhost:8000/api', VERCEL: '1', NODE_ENV: 'production' }), 'https://api.cracklabs.app/api');
    assert.equal(blogApiBaseUrl({ NEXT_PUBLIC_API_URL: 'http://localhost:8000/api', NODE_ENV: 'production' }), 'http://localhost:8000/api', 'a local production build keeps its local backend');
    assert.equal(blogApiBaseUrl({ NODE_ENV: 'production' }), 'https://api.cracklabs.app/api');
    assert.equal(blogApiBaseUrl({}), 'http://localhost:8000/api');
});

test('failure policy: static fallback while building and outside production; a production server throws', () => {
    assert.equal(blogFailurePolicy({ NODE_ENV: 'production', NEXT_PHASE: 'phase-production-build' }), 'fallback');
    assert.equal(blogFailurePolicy({ NODE_ENV: 'production' }), 'throw');
    assert.equal(blogFailurePolicy({ NODE_ENV: 'development' }), 'fallback');
    assert.equal(blogFailurePolicy({}), 'fallback');
});

test('the catalog and a post come from the API: drafts dropped, a 404 is "no such post" (no static resurrection)', async () => {
    const urls: string[] = [];
    const stub = (async (input: string | URL) => {
        const url = String(input);
        urls.push(url);
        if (url.endsWith('/blog/posts/catalog/')) {
            return json({ count: 3, results: [RECORD, { ...RECORD, slug: 'a-draft', is_published: false }, { title: 'no slug' }] });
        }
        if (url.endsWith('/blog/posts/by-slug/db-post/')) return json(RECORD);
        return json({ detail: 'Not found' }, 404);
    }) as unknown as typeof fetch;
    await withEnv({ NODE_ENV: 'production', NEXT_PUBLIC_API_URL: 'https://api.example.test/api' }, stub, async () => {
        assert.deepEqual((await loadBlogCatalog()).map((p) => p.slug), ['db-post']);
        assert.equal((await loadBlogPost('db-post'))?.title, 'A database post');
        assert.equal(await loadBlogPost('upsc-cms-last-5-days-strategy'), null, 'deleted in the admin: not served from the static copy');
        assert.equal(await loadBlogPost('../../etc/passwd'), null, 'odd slugs never reach the API');
    });
    assert.deepEqual(urls, [
        'https://api.example.test/api/blog/posts/catalog/',
        'https://api.example.test/api/blog/posts/by-slug/db-post/',
        'https://api.example.test/api/blog/posts/by-slug/upsc-cms-last-5-days-strategy/',
    ]);
});

test('a production server throws when the API fails (ISR keeps the last generated page)', async () => {
    await withEnv({ NODE_ENV: 'production' }, unreachable, async () => {
        await assert.rejects(loadBlogCatalog(), /fetch failed/);
        await assert.rejects(loadBlogPost('upsc-cms-last-5-days-strategy'), /fetch failed/);
    });
    const failing = (async () => json({ detail: 'boom' }, 503)) as unknown as typeof fetch;
    await withEnv({ NODE_ENV: 'production' }, failing, async () => {
        await assert.rejects(loadBlogCatalog(), /503/);
    });
    const missingEndpoint = (async () => json({ detail: 'Not found' }, 404)) as unknown as typeof fetch;
    await withEnv({ NODE_ENV: 'production' }, missingEndpoint, async () => {
        await assert.rejects(loadBlogCatalog(), /catalog is missing/, 'an older backend without the catalog endpoint');
    });
});

test('in development an unreachable API falls back to the static posts; BLOG_SOURCE=static never calls it', async () => {
    await withEnv({ NODE_ENV: 'development' }, unreachable, async () => {
        assert.equal((await loadBlogCatalog()).length, getAllPosts().length);
        assert.equal((await loadBlogPost('upsc-cms-last-5-days-strategy'))?.slug, 'upsc-cms-last-5-days-strategy');
    });
    const forbidden = (async () => { throw new Error('the API must not be called'); }) as unknown as typeof fetch;
    await withEnv({ NODE_ENV: 'production', BLOG_SOURCE: 'static' }, forbidden, async () => {
        assert.equal((await loadBlogCatalog()).length, getAllPosts().length);
        assert.equal((await loadBlogPost('no-such-post')), null);
    });
});

test('against an older backend (no catalog endpoint) a fallback render never mixes in its database rows', async () => {
    const slug = 'upsc-cms-last-5-days-strategy';
    const urls: string[] = [];
    const olderBackend = (async (input: string | URL) => {
        urls.push(String(input));
        if (String(input).endsWith('/blog/posts/catalog/')) return json({ detail: 'Not found' }, 404);
        return json({ ...RECORD, slug, body: 'Full article content here.' }); // an old seed's stub row
    }) as unknown as typeof fetch;
    await withEnv({ NODE_ENV: 'development' }, olderBackend, async () => {
        assert.equal((await loadBlogPost(slug))?.body, getPostBySlug(slug)?.body);
    });
    assert.ok(urls.every((u) => u.endsWith('/blog/posts/catalog/')), 'by-slug is not even asked');
});

// Last: trips the per-process "API down during the build" switch.
test('next build falls back to the static posts, retries once, then stops calling the API', async () => {
    let calls = 0;
    const counting = (async () => { calls += 1; throw new TypeError('fetch failed'); }) as unknown as typeof fetch;
    await withEnv({ NODE_ENV: 'production', NEXT_PHASE: 'phase-production-build' }, counting, async () => {
        assert.equal((await loadBlogCatalog()).length, getAllPosts().length);
        assert.equal(calls, 2, 'one retry');
        assert.equal((await loadBlogPost('upsc-cms-last-5-days-strategy'))?.slug, 'upsc-cms-last-5-days-strategy');
        assert.equal(calls, 2, 'the rest of the build skips the API');
    });
});

function post(slug: string, category: string, tags: string[], extra: Partial<BlogPost> = {}): BlogPost {
    return { ...(postFromRecord({ ...RECORD, slug, category, tags }) as BlogPost), ...extra };
}

test('list helpers work on any list of posts (the live catalog)', () => {
    const list = [
        post('a', 'UPSC CMS', ['High-Yield', 'Renal']),
        post('b', 'UPSC CMS', ['high yield'], { reviewedBy: 'crackcms-editorial' }),
        post('c', 'NEET PG', ['Renal'], { authorId: 'guest-writer' }),
    ];
    assert.deepEqual(categoriesOf(list), [{ name: 'UPSC CMS', slug: 'upsc-cms', count: 2 }, { name: 'NEET PG', slug: 'neet-pg', count: 1 }]);
    assert.deepEqual(postsInCategory(list, 'neet-pg').map((p) => p.slug), ['c']);
    assert.deepEqual(tagsOf(list), [{ name: 'High-Yield', slug: 'high-yield', count: 2 }, { name: 'Renal', slug: 'renal', count: 2 }]);
    assert.equal(tagOf(list, 'High Yield')?.count, 2);
    assert.deepEqual(postsWithTag(list, 'high-yield').map((p) => p.slug), ['a', 'b']);
    assert.deepEqual(relatedPostsFrom(list, list[0], 2).map((p) => p.slug), ['c'], 'shares "Renal" exactly');
    assert.deepEqual(authorSlugsOf(list), ['crackcms-editorial', 'guest-writer']);
    const fallback = new Date('2026-01-01T00:00:00Z');
    assert.equal(postLastModified({ dateModified: '', datePublished: 'not a date' }, fallback), fallback);
    assert.equal(postLastModified({ dateModified: '2026-11-02', datePublished: '2026-11-01' }, fallback).toISOString().slice(0, 10), '2026-11-02');
});

test('related reading comes from the catalog the post page links, else from the static posts', () => {
    const live = postFromRecord(RECORD) as BlogPost;
    const sibling = post('db-sibling', 'UPSC CMS', ['Renal']);
    assert.deepEqual(getRelatedPosts(linkRelatedPosts(live, [live, sibling]), 2).map((p) => p.slug), ['db-sibling']);
    const unlinked = postFromRecord(RECORD) as BlogPost;
    assert.ok(getRelatedPosts(unlinked, 2).every((p) => getAllPosts().includes(p)));
});
