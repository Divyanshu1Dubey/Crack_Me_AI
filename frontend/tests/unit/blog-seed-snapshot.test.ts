// The blog seed: backend/blog_engine/seed_data/static_posts.json is the static
// posts of src/lib/blog.ts (src/content/blog) as blog_engine records.
// `manage.py seed_blogs` imports it into the database, which is what the
// public /blog pages render; the static modules stay the build fallback.
//
// After editing a static post, regenerate the snapshot (from frontend/):
//   UPDATE_BLOG_SEED=1 node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/blog-seed-snapshot.test.ts
// The next deploy's seed_blogs then updates the posts nobody edited in the
// admin (an admin edit is never overwritten without --update).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { isDeepStrictEqual } from 'node:util';

import { getAllPosts, postFromRecord, postToRecord, type BlogPost } from '../../src/lib/blog.ts';

const SNAPSHOT = fileURLToPath(new URL('../../../backend/blog_engine/seed_data/static_posts.json', import.meta.url));

function buildSnapshot() {
    const posts = getAllPosts().map(postToRecord);
    return {
        source: 'frontend/src/content/blog via frontend/src/lib/blog.ts getAllPosts() (newest first)',
        regenerate: 'UPDATE_BLOG_SEED=1 node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/blog-seed-snapshot.test.ts',
        count: posts.length,
        posts,
    };
}

test('the backend seed snapshot holds every static post, field for field', () => {
    const expected = buildSnapshot();
    if (process.env.UPDATE_BLOG_SEED === '1') {
        writeFileSync(SNAPSHOT, `${JSON.stringify(expected, null, 1)}\n`, 'utf8');
    }
    const actual = JSON.parse(readFileSync(SNAPSHOT, 'utf8'));
    const hint = 'a static post changed: regenerate the seed snapshot (see the header of this test)';
    assert.equal(actual.count, expected.count, hint);
    assert.deepEqual(actual.posts.map((p: { slug: string }) => p.slug), expected.posts.map((p) => p.slug), hint);
    const differing = expected.posts
        .filter((post, i) => !isDeepStrictEqual(actual.posts[i], post))
        .map((post) => post.slug);
    assert.deepEqual(differing, [], hint);
});

/** A post as the public pages see it: unset flags are false, unset optionals absent. */
function comparable(post: BlogPost) {
    return JSON.parse(JSON.stringify({ ...post, pinned: post.pinned === true, trending: post.trending === true }));
}

test('a database record keeps every field a public page reads (record → post round trip)', () => {
    assert.equal(getAllPosts().length, 129);
    for (const post of getAllPosts()) {
        const back = postFromRecord({ ...postToRecord(post), is_published: true });
        assert.ok(back, post.slug);
        assert.deepEqual(comparable(back), comparable(post), post.slug);
    }
});

test('prelude / outro: no static post uses a React snippet; the database stores markdown text', () => {
    for (const post of getAllPosts()) {
        for (const snippet of [post.prelude, post.outro]) {
            assert.ok(snippet === undefined || typeof snippet === 'string', post.slug);
        }
    }
    const [post] = getAllPosts();
    assert.equal(postToRecord({ ...post, prelude: 'Read this first.' }).prelude, 'Read this first.');
    assert.throws(() => postToRecord({ ...post, outro: { type: 'div', props: {} } }), /outro is not text/);
});
