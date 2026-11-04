// /admin/blog form helpers (src/app/admin/blog/blogForm.ts): API record ⇄
// form, client checks mirroring backend/blog_engine/serializers.py, list
// params and error messages.
// Run (from frontend/):
//   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/blog-admin-form.test.ts
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import {
    blogListParams,
    describeBlogError,
    emptyBlogForm,
    estimateReadingTime,
    formFromPost,
    formToPayload,
    formsDiffer,
    isIsoDate,
    isSafeLink,
    isStubBody,
    slugify,
    tocFromBody,
    todayIso,
    wordCountOf,
} from '../../src/app/admin/blog/blogForm.ts';

const PROFILE = { slug: 'crackcms-editorial', name: 'CrackCMS Editorial Team', role: 'Clinical Content Editors, CrackCMS' };

const RECORD = {
    id: 7,
    slug: 'renal-physiology-in-ten-minutes',
    title: 'Renal Physiology in Ten Minutes',
    description: 'GFR and tubular transport.',
    excerpt: 'The renal facts UPSC CMS asks.',
    cover_image: '',
    category: 'Subject Prep',
    subcategory: 'Physiology',
    tags: ['Physiology', 'Renal'],
    difficulty: 'advanced' as const,
    author_id: 'crackcms-editorial',
    reviewed_by: 'crackcms-editorial',
    author: 'CrackCMS Editorial Team',
    author_role: 'Clinical Content Editors, CrackCMS',
    date_published: '2026-11-04',
    date_modified: '2026-11-04',
    updated_at: '2026-11-04',
    reading_time: '10 min',
    word_count: 1200,
    primary_cta: { label: 'Practise renal PYQs', href: '/questions?exam=cms', event_name: 'blog_practice_intent', event_params: { source: 'renal' } },
    related_exam_paths: ['/cms', '/neet-pg'],
    faqs: [{ q: 'Normal GFR?', a: 'About 125 mL/min.' }],
    toc: [{ id: 'gfr', label: 'GFR' }],
    references: [{ label: 'Guyton & Hall' }, { label: 'UPSC', url: 'https://upsc.gov.in/' }],
    revision_log: [{ date: '2026-11-04', note: 'First published.' }],
    body: '## GFR\n\nAbout 125 mL/min.',
    prelude: '',
    outro: '',
    pinned: true,
    trending: false,
    is_published: true,
    created_at: '2026-11-04T10:00:00Z',
    updated: '2026-11-04T10:00:00Z',
};

test('an API record survives form → payload unchanged', () => {
    const form = formFromPost(RECORD);
    assert.equal(form.tags, 'Physiology, Renal');
    assert.equal(form.relatedExamPaths, '/cms\n/neet-pg');
    assert.equal(form.wordCount, '1200');
    const { payload, errors } = formToPayload(form);
    assert.deepEqual(errors, {});
    const { id: _id, created_at: _c, updated: _u, ...content } = RECORD;
    assert.deepEqual(payload, content);
});

test('the bundled static posts are valid forms too (a seeded post can be saved unchanged)', () => {
    const snapshot = JSON.parse(readFileSync(fileURLToPath(new URL('../../../backend/blog_engine/seed_data/static_posts.json', import.meta.url)), 'utf8'));
    for (const record of snapshot.posts) {
        const { errors } = formToPayload(formFromPost({ ...record, is_published: true }));
        assert.deepEqual(errors, {}, record.slug);
    }
});

test('a new post starts as a dated draft with the editorial byline', () => {
    const form = emptyBlogForm('2026-11-04', PROFILE);
    assert.equal(form.isPublished, false);
    assert.equal(form.datePublished, '2026-11-04');
    assert.equal(form.author, 'CrackCMS Editorial Team');
    assert.equal(form.authorId, 'crackcms-editorial');
    const { errors } = formToPayload(form);
    assert.ok(errors.slug && errors.title && errors.description && errors.excerpt && errors.category, JSON.stringify(errors));
    assert.equal(errors.isPublished, undefined, 'a draft may have no body');
});

test('the checks mirror the API: what would break a public page is reported per field', () => {
    const base = formFromPost(RECORD);
    const check = (changes: Partial<typeof base>) => formToPayload({ ...base, ...changes }).errors;
    assert.ok(check({ slug: 'Has Spaces' }).slug);
    assert.ok(check({ slug: 'category' }).slug);
    assert.ok(check({ datePublished: '04/11/2026' }).datePublished);
    assert.ok(check({ dateModified: '2026-02-30' }).dateModified);
    assert.ok(check({ ctaHref: 'javascript:alert(1)' }).cta);
    assert.ok(check({ ctaHref: '//evil.example' }).cta);
    assert.ok(check({ ctaHref: '' }).cta, 'label without a link');
    assert.ok(check({ ctaEventParams: '{not json' }).cta);
    assert.ok(check({ ctaEventParams: '[1, 2]' }).cta);
    assert.ok(check({ relatedExamPaths: 'https://example.com' }).relatedExamPaths);
    assert.ok(check({ faqs: [{ q: 'Only a question', a: '' }] }).faqs);
    assert.ok(check({ toc: [{ id: 'Has Space', label: 'L' }] }).toc);
    assert.ok(check({ references: [{ label: '', url: 'https://x.y/', published: '' }] }).references);
    assert.ok(check({ references: [{ label: 'L', url: 'javascript:alert(1)', published: '' }] }).references);
    assert.ok(check({ revisionLog: [{ date: 'yesterday', note: 'n' }] }).revisionLog);
    assert.ok(check({ wordCount: '12.5' }).wordCount);
    assert.ok(check({ coverImage: 'javascript:alert(1)' }).coverImage);
    assert.ok(check({ body: 'Full article content here.' }).isPublished);
    assert.equal(check({ body: '', isPublished: false }).isPublished, undefined);
});

test('inputs are normalised the way the API stores them', () => {
    const form = {
        ...formFromPost(RECORD),
        tags: ' Renal , renal,, UPSC CMS ',
        ctaLabel: '', ctaHref: '', ctaEventName: '', ctaEventParams: '',
        faqs: [{ q: ' Q? ', a: ' A. ' }, { q: '', a: '' }],
        toc: [{ id: '', label: '' }],
        references: [{ label: ' Ref ', url: '', published: '' }],
        wordCount: '',
    };
    const { payload, errors } = formToPayload(form);
    assert.deepEqual(errors, {});
    assert.deepEqual(payload.tags, ['Renal', 'UPSC CMS']);
    assert.deepEqual(payload.primary_cta, {}, 'no CTA: the site shows its default one');
    assert.deepEqual(payload.faqs, [{ q: 'Q?', a: 'A.' }], 'blank rows are dropped');
    assert.deepEqual(payload.toc, []);
    assert.deepEqual(payload.references, [{ label: 'Ref' }]);
    assert.equal(payload.word_count, null);
});

test('slugs, TOC, word counts and dates', () => {
    assert.equal(slugify('  UPSC CMS: Last 5 Days & Revision!! '), 'upsc-cms-last-5-days-and-revision');
    assert.equal(slugify('Pédiatrie — ça va'), 'pediatrie-ca-va');
    assert.equal(slugify('---'), '');
    assert.deepEqual(tocFromBody('## What toppers do\ntext\n```\n## not a heading\n```\n### Sub\n## **Day-5:** audit'), [
        { id: 'what-toppers-do', label: 'What toppers do' },
        { id: 'day-5-audit', label: 'Day-5: audit' },
    ]);
    assert.equal(wordCountOf('## One two\n\nthree **four**'), 4);
    assert.equal(estimateReadingTime('word '.repeat(1000)), '5 min');
    assert.equal(estimateReadingTime(''), '1 min');
    assert.equal(todayIso(new Date(2026, 0, 5)), '2026-01-05');
    assert.ok(isIsoDate('2026-02-28') && !isIsoDate('2026-02-30') && !isIsoDate('2026-2-3'));
    assert.ok(isStubBody('  Full article content here. ') && isStubBody('') && !isStubBody('A body'));
    assert.ok(isSafeLink('/questions?exam=cms') && isSafeLink('https://upsc.gov.in/x'));
    assert.ok(!isSafeLink('//evil') && !isSafeLink('javascript:alert(1)') && !isSafeLink('/a b'));
});

test('list params and error messages', () => {
    assert.deepEqual(blogListParams({ page: 2, pageSize: 25, search: ' renal ', status: 'draft', category: 'Career', ordering: '-updated' }),
        { page: 2, page_size: 25, search: 'renal', is_published: 'false', category: 'Career', ordering: '-updated' });
    assert.deepEqual(blogListParams({ page: 1, pageSize: 25, search: '', status: '', category: '', ordering: '' }), { page: 1, page_size: 25 });
    assert.equal(describeBlogError({ response: { status: 403, data: {} } }), 'Admin access is needed for this.');
    assert.equal(describeBlogError({ response: { status: 400, data: { slug: ['blog post with this slug already exists.'] } } }),
        'Slug: blog post with this slug already exists.');
    assert.equal(describeBlogError({ response: { status: 400, data: { detail: 'Add the article body before publishing this post.' } } }),
        'Add the article body before publishing this post.');
    assert.match(describeBlogError(new Error('Network Error'), 'saving the post'), /Could not reach the server for saving the post/);
    assert.match(describeBlogError({ response: { status: 502, data: '<html>' } }), /server could not complete/);
    const a = formFromPost(RECORD);
    assert.equal(formsDiffer(a, { ...a }), false);
    assert.equal(formsDiffer(a, { ...a, title: 'Changed' }), true);
});
