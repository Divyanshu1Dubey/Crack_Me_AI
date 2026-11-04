// The visual editor keeps a post as it is: markdown -> editor document (the
// TipTap schema of src/app/admin/blog/editor/schema.ts, checked by
// ProseMirror) -> markdown (src/app/admin/blog/editor/markdownDoc.ts) renders
// the same article HTML (src/components/blog/blogArticleCore.ts) for every
// seeded post and for the constructs the editor offers.
// Run (from frontend/):
//   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/blog-editor-roundtrip.test.ts
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { getSchema } from '@tiptap/core';
import { BlogArticleBody } from '../../src/components/blog/blogArticleCore.ts';
import { blogSchemaExtensions } from '../../src/app/admin/blog/editor/schema.ts';
import { docToMarkdown, markdownToDoc, type PMNode } from '../../src/app/admin/blog/editor/markdownDoc.ts';

const SNAPSHOT = fileURLToPath(new URL('../../../backend/blog_engine/seed_data/static_posts.json', import.meta.url));
const POSTS: { slug: string; body: string }[] = JSON.parse(readFileSync(SNAPSHOT, 'utf8')).posts;
const schema = getSchema(blogSchemaExtensions());

const html = (markdown: string) => renderToStaticMarkup(createElement(BlogArticleBody, { markdown }));

/** markdown -> the editor's document (validated by the schema, as the editor would hold it) -> markdown. */
function roundTrip(markdown: string) {
    const { doc, unsupported } = markdownToDoc(markdown);
    const node = schema.nodeFromJSON(doc);
    node.check();
    return { markdown: docToMarkdown(node.toJSON() as PMNode), unsupported };
}

test('every seeded post survives the visual editor: the same article HTML', () => {
    assert.equal(POSTS.length, 129);
    const differing: string[] = [];
    for (const post of POSTS) {
        const { markdown, unsupported } = roundTrip(post.body);
        assert.deepEqual(unsupported, [], `${post.slug} has constructs the editor cannot hold`);
        if (html(markdown) !== html(post.body)) differing.push(post.slug);
    }
    assert.deepEqual(differing, []);
});

test('a second pass changes nothing (the written markdown is stable)', () => {
    for (const post of POSTS) {
        const once = roundTrip(post.body).markdown;
        assert.equal(roundTrip(once).markdown, once, post.slug);
    }
});

const CASES = [
    '> [!NOTE]\n> One line.\n> Two lines.',
    '> [!tip]\n>\n> - a\n> - b',
    '> [!WARNING] Same-line text',
    '> [!CAUTION]\n> | a | b |\n> |---|---|\n> | 1 | 2 |',
    '> plain quote\n>\n> > nested quote',
    '![Alt *text*](/api/blog/images/2026/11/0123456789abcdef0123456789abcdef.png "A caption")',
    'Inline ![x](https://cdn.example/a.png) image and [![linked](/b.png)](/target)',
    '| Left | Center | Right |\n|:---|:---:|---:|\n| a | **b** | `c\\|d` |\n| [l](/x) | e<br>f | |',
    '| short | row |\n|---|---|\n| only one |',
    'Text with \\* star, \\_under\\_score\\_, snake_case, a \\| pipe, <b>bold</b> raw, &amp; entity, 2 < 3, 1 <x> 2',
    'Not links: http\\://x.com and www\\.x.com and me\\@x.com',
    'Links: https://upsc.gov.in, www.example.com and someone@example.com',
    '1. one\n2. two\n\n- a\n- b\n\n* c',
    '3. starts at three\n4. four',
    '- [ ] open\n- [x] done',
    '- loose\n\n- items',
    '- a\n  - nested\n  - nested 2\n- b',
    '1. a\n   1. inner\n2. b',
    '```js\nconst fence = "```";\n```',
    '``code with ` backtick``',
    '**bold** *it* ~~strike~~ <u>under</u> `code` [link](/x "Title") <sup>2</sup>',
    '**[bold link](/x)** and *[`code link`](/y)*',
    '***bold italic*** and *a **b** c*',
    'Line one\nLine two\\\nLine three',
    '# H1 becomes h2\n\n## Heading with # in it #\n\n### Sub *em*',
    '<div class="x">raw block</div>\n\nafter',
    '---\n\n***\n\nText',
    'A line\n# that looks like a heading\n- and a list\n1. and ordered\n> and a quote\n=== and setext',
    '[ref link][r] and ![ref img][r]\n\n[r]: /target "T"',
    '[missing][nope] stays text',
    'Tilde ~ alone, double \\~\\~not strike\\~\\~, pH ~7.4',
    '<em>raw em</em> and <strong>raw strong</strong> and <a href="/x" title="t">raw link</a>',
];

test('the constructs the editor offers survive the round trip', () => {
    for (const markdown of CASES) {
        const { markdown: back, unsupported } = roundTrip(markdown);
        assert.deepEqual(unsupported, [], markdown);
        assert.equal(html(back), html(markdown), `${JSON.stringify(markdown)} -> ${JSON.stringify(back)}`);
        assert.equal(roundTrip(back).markdown, back, `unstable: ${JSON.stringify(back)}`);
    }
});

test('formatting markdown cannot hold falls back to HTML tags, never to stray asterisks', () => {
    // **"quoted"**s is not bold in markdown (the closing ** sits between a quote and a letter).
    const doc: PMNode = {
        type: 'doc',
        content: [{
            type: 'paragraph',
            content: [
                { type: 'text', text: 'a' },
                { type: 'text', text: '"quoted"', marks: [{ type: 'bold' }] },
                { type: 'text', text: 's and ' },
                { type: 'text', text: ' spaced ', marks: [{ type: 'italic' }] },
                { type: 'text', text: 'end' },
            ],
        }],
    };
    schema.nodeFromJSON(doc).check();
    const markdown = docToMarkdown(doc);
    const rendered = html(markdown);
    assert.match(rendered, /a<strong>&quot;quoted&quot;<\/strong>s and/);
    assert.match(rendered, /<em>(?: spaced |spaced)<\/em>/);
    assert.doesNotMatch(rendered, /\*/);
});

test('not lossless (documented): marks over exactly the same text are written emphasis-outside', () => {
    // [**x**](/y) and **[x](/y)** are the same document; both are written **[x](/y)**.
    const { markdown } = roundTrip('[**x**](/y)');
    assert.equal(markdown, '**[x](/y)**');
    assert.notEqual(html(markdown), html('[**x**](/y)'));
    assert.equal(html(markdown).replace(/<\/?(strong|a)[^>]*>/g, ''), html('[**x**](/y)').replace(/<\/?(strong|a)[^>]*>/g, ''));
});

test('what the visual editor cannot hold is reported (the post stays in the Markdown tab)', () => {
    assert.deepEqual(markdownToDoc('Text[^1]\n\n[^1]: A footnote.').unsupported, ['footnotes']);
    assert.deepEqual(markdownToDoc('## Fine\n\nAll *normal* content.').unsupported, []);
});
