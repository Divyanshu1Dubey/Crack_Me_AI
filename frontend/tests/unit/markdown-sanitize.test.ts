/**
 * rehypeAllowlist (src/lib/markdownSanitize.ts): the sanitizer FormattedText
 * runs after rehype-raw. Renders real markdown + raw HTML through
 * react-markdown exactly as the component does and checks the markup.
 *
 * Run (from frontend/):
 *   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/markdown-sanitize.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import ReactMarkdown from 'react-markdown';
import rehypeRaw from 'rehype-raw';
import remarkBreaks from 'remark-breaks';
import { rehypeAllowlist, safeStyle, safeUrl } from '../../src/lib/markdownSanitize.ts';

const render = (md: string) =>
    renderToStaticMarkup(createElement(ReactMarkdown, { remarkPlugins: [remarkBreaks], rehypePlugins: [rehypeRaw, rehypeAllowlist] }, md));

test('scripts, styles, iframes, forms and svg are removed with their content', () => {
    const html = render('Before <script>alert(1)</script><style>body{display:none}</style>'
        + '<iframe src="https://evil.example"></iframe><form action="https://evil.example"><input name="p"><button>Go</button></form>'
        + '<svg><a href="javascript:alert(1)"><text>x</text></a></svg> After');
    for (const bad of ['<script', 'alert(1)', '<style', 'display:none', '<iframe', '<form', '<input', '<button', '<svg', 'evil.example']) {
        assert.ok(!html.includes(bad), `${bad} survived: ${html}`);
    }
    assert.match(html, /Before/);
    assert.match(html, /After/);
});

test('event handlers and dangerous URLs are stripped', () => {
    const html = render('<img src="https://cdn.example/a.png" onerror="alert(1)" alt="ok"> '
        + '<a href="javascript:alert(2)" onclick="alert(3)">one</a> <a href="java&#x09;script:alert(4)">two</a> '
        + '<a href=" data:text/html;base64,PHNjcmlwdD4=">three</a> <img src="data:image/svg+xml;base64,PHN2Zz4=">');
    assert.ok(!/onerror|onclick|alert|javascript|data:text|svg\+xml/i.test(html), html);
    assert.match(html, /<img src="https:\/\/cdn\.example\/a\.png" alt="ok"\/>/);
    assert.match(html, /<a>one<\/a>/);
    assert.match(html, /<a>two<\/a>/);
});

test('admin colour and underline spans keep only safe declarations', () => {
    const html = render('<span style="color:#dc2626">red</span> <span style="text-decoration:underline">u</span> '
        + '<span style="position:fixed;top:0;left:0;width:100vw;height:100vh;color:blue">overlay</span> '
        + '<span style="background-image:url(https://t.example/x)">bg</span> <div style="color:red">div</div>');
    assert.match(html, /<span style="color:#dc2626">red<\/span>/);
    assert.match(html, /<span style="text-decoration:underline">u<\/span>/);
    assert.match(html, /<span style="color:blue">overlay<\/span>/);
    assert.ok(!/position|100vw|url\(|t\.example/.test(html), html);
    assert.match(html, /<div>div<\/div>/);
});

test('ordinary markdown, tables, images and links still render', () => {
    const html = render('**Bold** and *italic*\n\n- one\n- two\n\n![Fig 1](https://cdn.example/fig.png "Figure")\n\n'
        + '[Harrison](https://example.org/h) and [local](/questions?q=5)\n\n'
        + '<table><tr><td colspan="2">cell</td></tr></table>\n\n<sub>2</sub>O and x<sup>2</sup>');
    assert.match(html, /<strong>Bold<\/strong>/);
    assert.match(html, /<em>italic<\/em>/);
    assert.match(html, /<li>one<\/li>/);
    assert.match(html, /<img src="https:\/\/cdn\.example\/fig\.png" alt="Fig 1" title="Figure"\/>/);
    assert.match(html, /<a href="https:\/\/example\.org\/h" rel="nofollow noopener noreferrer">Harrison<\/a>/);
    assert.match(html, /<a href="\/questions\?q=5">local<\/a>/);
    assert.match(html, /<td colSpan="2">cell<\/td>/i);
    assert.match(html, /<sub>2<\/sub>/);
    assert.match(html, /<sup>2<\/sup>/);
});

test('unknown tags are unwrapped, comments dropped', () => {
    const html = render('<custom-box data-x="1" id="a">kept text</custom-box><!-- secret note -->');
    assert.match(html, /kept text/);
    assert.ok(!/custom-box|data-x|id="a"|secret note/.test(html), html);
});

test('helpers: safeUrl and safeStyle', () => {
    assert.equal(safeUrl('JaVaScRiPt:alert(1)', 'link'), null);
    assert.equal(safeUrl('\u0001javascript:alert(1)', 'link'), null);
    assert.equal(safeUrl('vbscript:x', 'link'), null);
    assert.equal(safeUrl('mailto:help@example.org', 'link'), 'mailto:help@example.org');
    assert.equal(safeUrl('media/q/1.png', 'image'), 'media/q/1.png');
    assert.equal(safeUrl('data:image/png;base64,iVBORw0KGgo=', 'image'), 'data:image/png;base64,iVBORw0KGgo=');
    assert.equal(safeUrl('ftp://x/y.png', 'image'), null);
    assert.equal(safeStyle('color: red; expression(alert(1))'), 'color:red');
    assert.equal(safeStyle('color: var(--x)'), null);
    assert.equal(safeStyle(42), null);
});
