// The published blog article (src/components/blog/blogArticleCore.ts through
// src/lib/blogMarkdown.ts): headings and their table of contents, callouts,
// figures, tables, links, line breaks, the sanitizer on raw HTML, and the word
// count / reading time rule shared with backend/blog_engine/text_stats.py.
// Run (from frontend/):
//   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/blog-article.test.ts
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { BlogArticleBody } from '../../src/components/blog/blogArticleCore.ts';
import { blogToc, CALLOUT_KINDS } from '../../src/lib/blogMarkdown.ts';
import { countBlogWords, readingMinutes, readingTimeLabel, THIN_POST_WORDS } from '../../src/lib/blogText.ts';
import { postReadingStats } from '../../src/lib/blog.ts';

const SNAPSHOT = fileURLToPath(new URL('../../../backend/blog_engine/seed_data/static_posts.json', import.meta.url));
const POSTS: { slug: string; body: string; toc: { id: string; label: string }[]; word_count: number | null }[] =
    JSON.parse(readFileSync(SNAPSHOT, 'utf8')).posts;

const render = (markdown: string, options: Record<string, unknown> = {}) =>
    renderToStaticMarkup(createElement(BlogArticleBody, { markdown, ...options }));

// Shared with backend/blog_engine/tests_blog_editor_api.py COUNT_VECTORS.
const COUNT_VECTORS: [string, number][] = [
    ['', 0],
    ['## One two\n\nthree **four**', 4],
    ['1. First item\n2. Second\n- third', 4],
    ['See [the guide](/blog/x) and ![diagram](/a.png) now', 5],
    ['> [!NOTE]\n> Keep it short.', 3],
    ['| Drug | Dose |\n|---|---|\n| Atropine | 0.6 mg |', 5],
    ['Visit https://upsc.gov.in/ today <br> ok <!-- hidden note -->', 3],
    ['pH ~7.4 — normal; e.g. **Na⁺**', 5],
    ['Pédiatrie ça va', 3],
    ['snake_case and C++', 4],
    ['Line one\r\nLine two\\\nLine three', 6],
];

test('word count and reading time: the backend rule (shared vectors)', () => {
    for (const [markdown, words] of COUNT_VECTORS) assert.equal(countBlogWords(markdown), words, JSON.stringify(markdown));
    const minutes: Record<number, number> = { 0: 1, 99: 1, 299: 1, 300: 2, 500: 3, 1000: 5, 2731: 14 };
    for (const [words, expected] of Object.entries(minutes)) assert.equal(readingMinutes(Number(words)), expected, words);
    assert.equal(readingTimeLabel(99), '1 min');
    assert.equal(THIN_POST_WORDS, 400);
});

test('reading stats: the body when present, else the API count; never the seed metadata', () => {
    const post = POSTS.find((p) => p.slug === 'forensic-medicine-upsc-cms-essentials')!;
    const words = countBlogWords(post.body);
    assert.ok(words < 300 && (post.word_count ?? 0) > 1500, `${words} words, seed claims ${post.word_count}`);
    assert.deepEqual(postReadingStats({ body: post.body, wordCount: post.word_count ?? undefined }),
        { words, minutes: readingMinutes(words), label: readingTimeLabel(words) });
    assert.equal(postReadingStats({ body: '', wordCount: 905 }).label, '5 min'); // a catalog row: the API count
    assert.equal(postReadingStats({ body: '', wordCount: undefined }).label, '1 min');
});

test('headings: ids from their text, unique, kept from the stored TOC, never a page id', () => {
    const html = render('## What toppers do\n\n## What toppers do\n\n### Day-5: **audit**\n\n## start-reading\n\n## हिन्दी');
    assert.match(html, /<h2 id="what-toppers-do">What toppers do<a class="heading-anchor" href="#what-toppers-do" aria-label="Link to this section: What toppers do">#<\/a><\/h2>/);
    assert.match(html, /<h2 id="what-toppers-do-2">/);
    assert.match(html, /<h3 id="day-5-audit">Day-5: <strong>audit<\/strong>/);
    assert.match(html, /<h2 id="start-reading-2">/, 'the page uses #start-reading itself');
    assert.match(html, /<h2 id="section-5">/, 'a heading with no latin letters is numbered');
    // A stored TOC keeps its anchor ids (inbound #links keep working).
    const kept = render('## UPSC CMS Marking Scheme\n\n## Expected Value', { preferredIds: [{ id: 'marking', label: 'UPSC CMS Marking Scheme' }] });
    assert.match(kept, /<h2 id="marking">/);
    assert.match(kept, /<h2 id="expected-value">/);
    // # in a body is not a second page title.
    assert.match(render('# Big'), /^<div class="blog-article blog-prose"><h2 id="big">/);
});

test('every seeded post: the "On this page" entries are exactly its ## headings, with the ids they render with', () => {
    for (const post of POSTS) {
        const html = render(post.body, { preferredIds: post.toc });
        const rendered = [...html.matchAll(/<h2 id="([^"]+)">/g)].map((m) => m[1]);
        const toc = blogToc(post.body, post.toc);
        assert.deepEqual(toc.map((t) => t.id), rendered, post.slug);
        assert.ok(toc.every((t) => t.label.trim() && !t.label.includes('#')), post.slug);
        assert.equal(new Set(rendered).size, rendered.length, `${post.slug}: duplicate ids`);
        // Stored TOC ids that name a heading are the ids the headings get.
        for (const item of post.toc) {
            const heading = toc.find((t) => t.label.replace(/\s+/g, ' ').trim().toLowerCase() === item.label.replace(/[*_`]/g, '').trim().toLowerCase());
            if (heading) assert.equal(heading.id, item.id, `${post.slug}: ${item.label}`);
        }
    }
});

test('callouts: the five GitHub alert types, in any case, marker on its own line or not', () => {
    for (const kind of CALLOUT_KINDS) {
        const html = render(`> [!${kind.toUpperCase()}]\n> Revise the PYQs first.`);
        const label = kind[0].toUpperCase() + kind.slice(1);
        assert.match(html, new RegExp(`<div class="callout callout-${kind}" data-callout="${kind}" role="note">\\n<p class="callout-title"><span class="callout-icon" aria-hidden="true"></span>${label}</p>\\n<p>Revise the PYQs first.</p>\\n</div>`), kind);
    }
    const same = render('> [!TIP]\n> Revise the PYQs first.');
    assert.equal(render('> [!tip]\n>\n> Revise the PYQs first.'), same);
    assert.equal(render('> [!TIP] Revise the PYQs first.'), same);
    const list = render('> [!WARNING]\n> - one\n> - two');
    assert.match(list, /callout-warning[\s\S]*<ul>\n<li>one<\/li>\n<li>two<\/li>\n<\/ul>/);
    // Not callouts: a plain quote, an unknown type, a marker that is not first.
    assert.match(render('> Just a quote.'), /<blockquote>\n<p>Just a quote.<\/p>\n<\/blockquote>/);
    assert.match(render('> [!FOO]\n> text'), /<blockquote>/);
    assert.match(render('> text\n> [!NOTE]'), /<blockquote>/);
});

test('raw HTML is sanitized before the article structure is added', () => {
    const html = render('Hi <script>alert(1)</script><iframe src="https://evil.example"></iframe>'
        + '<img src="x.png" onerror="alert(2)"> <a href="javascript:alert(3)">bad</a> <a href="/ok" onclick="x()">ok</a>\n\n'
        + '<div class="callout callout-note" style="position:fixed">fake box</div>\n\n<h2 id="evil" class="x">Raw heading</h2>');
    for (const bad of ['<script', 'alert(', '<iframe', 'evil.example', 'onerror', 'onclick', 'javascript:', 'position:fixed']) {
        assert.ok(!html.includes(bad), `${bad} survived: ${html}`);
    }
    assert.match(html, /<div>fake box<\/div>/, 'classes in the post never reach the page (no fake callouts)');
    assert.match(html, /<h2 id="raw-heading">Raw heading<a class="heading-anchor"/, 'ids come from the renderer');
    assert.match(html, /<a href="\/ok">ok<\/a>/);
});

test('tables scroll in their own box and keep their alignment; figures, links, breaks and task items', () => {
    const table = render('| Drug | Dose |\n|:--|--:|\n| Atropine | 0.6 mg |');
    assert.match(table, /^<div class="blog-article blog-prose"><div class="blog-table-wrap" role="region" aria-label="Table \(scrolls sideways\)" tabindex="0"><table>/);
    assert.match(table, /<th style="text-align:left">Drug<\/th><th style="text-align:right">Dose<\/th>/);

    const figure = render('![ECG strip](/api/blog/images/2026/11/abc.png "Lead II rhythm strip")', { imageOrigin: 'https://api.cracklabs.app/' });
    assert.match(figure, /<figure class="blog-figure"><img src="https:\/\/api\.cracklabs\.app\/api\/blog\/images\/2026\/11\/abc\.png" alt="ECG strip" loading="lazy" decoding="async"\/><figcaption>Lead II rhythm strip<\/figcaption><\/figure>/);
    assert.doesNotMatch(render('Text ![x](/a.png) inline'), /<figure/, 'an image inside text is not a figure');
    assert.match(render('![No caption](https://cdn.example/a.png)'), /<figure class="blog-figure"><img src="https:\/\/cdn\.example\/a\.png" alt="No caption"[^>]*\/><\/figure>/);

    const links = render('[PYQs](/questions) and [UPSC](https://upsc.gov.in/)');
    assert.match(links, /<a href="\/questions">PYQs<\/a>/);
    assert.match(links, /<a href="https:\/\/upsc\.gov\.in\/" rel="nofollow noopener noreferrer" target="_blank">UPSC<\/a>/);

    assert.match(render('**CBR:** births\n**CDR:** deaths'), /<p><strong>CBR:<\/strong> births<br\/>\n<strong>CDR:<\/strong> deaths<\/p>/,
        'a newline inside a paragraph is a line break (38 seeded posts rely on it)');
    const tasks = render('- [ ] Admit card\n- [x] Pens');
    assert.match(tasks, /<li>☐ Admit card<\/li>\n<li>☑ Pens<\/li>/);
    assert.doesNotMatch(tasks, /<input/);
    assert.match(render('pH ~7.4 and ~~gone~~'), /pH ~7\.4 and <del>gone<\/del>/);
});
