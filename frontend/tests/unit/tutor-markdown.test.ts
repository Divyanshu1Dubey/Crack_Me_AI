/**
 * AI Tutor answer rendering (frontend/src/lib/tutorMarkdown.ts): tables, <br> in cells, tags, safety.
 *
 *   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/tutor-markdown.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import ReactMarkdown from 'react-markdown';
import {
  normalizeTutorMarkdown,
  tutorRehypePlugins,
  tutorRemarkPlugins,
} from '../../src/lib/tutorMarkdown.ts';

const render = (markdown: string) => renderToStaticMarkup(createElement(
  ReactMarkdown,
  { remarkPlugins: tutorRemarkPlugins, rehypePlugins: tutorRehypePlugins },
  normalizeTutorMarkdown(markdown),
));

// The shape of the answer in the owner's screenshot: a table right after a sentence, bold first cells,
// bullet lists inside cells written with <br>.
const MI_ANSWER = [
  'The cascade can be divided into four inter-related phases:',
  '| Phase | Time frame | Key events | Clinical correlate |',
  '|-------|-----------|------------|--------------------|',
  '| **1. Plaque rupture & thrombus formation** | Seconds-minutes | • Fissuring of a thin-cap fibro-atheroma<br>• Platelet adhesion via GP IIb/IIIa | Sudden chest pain |',
  '| **2. Acute coronary occlusion** | 0-30 min | • Occlusion > 90 % of lumen<br>• Shift to anaerobic glycolysis | ST elevation |',
  '**Key pathogenic concepts**',
  '- **Platelet-mediated thrombosis** – aspirin and clopidogrel are cornerstone agents.',
].join('\n');

test('a table glued to the sentence before it renders as a table', () => {
  const html = render(MI_ANSWER);
  assert.match(html, /<table>/);
  assert.match(html, /<th>Phase<\/th>/);
  assert.equal((html.match(/<tr>/g) || []).length, 3);
  assert.match(html, /<td><strong>1\. Plaque rupture &amp; thrombus formation<\/strong><\/td>/);
  assert.doesNotMatch(html, /\| Phase \|/);                 // no raw pipes left
  assert.doesNotMatch(html, /&lt;br&gt;/);                  // no literal <br>
  assert.match(html, /Fissuring of a thin-cap fibro-atheroma<br\/>• Platelet adhesion/);
  assert.match(html, /<li><strong>Platelet-mediated thrombosis<\/strong>/);
});

test('a table squashed onto one line is rebuilt row by row', () => {
  const md = 'Phases of MI: | Phase | Time | |---|---| | Rupture | Seconds | | Necrosis | 30 min-4 h |';
  const normalized = normalizeTutorMarkdown(md);
  assert.equal(normalized, [
    'Phases of MI:', '', '| Phase | Time |', '|---|---|', '| Rupture | Seconds |', '| Necrosis | 30 min-4 h |',
  ].join('\n'));
  const html = render(md);
  assert.match(html, /<td>Necrosis<\/td><td>30 min-4 h<\/td>/);
});

test('well-formed markdown is left alone', () => {
  const md = 'Intro\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\nAfter';
  assert.equal(normalizeTutorMarkdown(md), md);
  assert.equal(normalizeTutorMarkdown('Plain text, no table | just a pipe'), 'Plain text, no table | just a pipe');
});

test('tags become badges without flattening the sentence', () => {
  const html = render('[High Yield] MI = *ischemic necrosis* of myocardium [PYQ 2019]\n\n**Textbook Reference: Robbins 10e, ch. 12**');
  assert.match(html, /<span class="ai-tag ai-tag-amber">🔥 HIGH YIELD<\/span>/);
  assert.match(html, /<em>ischemic necrosis<\/em>/);
  assert.match(html, /<span class="ai-tag ai-tag-pink">📋 PYQ 2019<\/span>/);
  assert.match(html, /<strong class="ai-tag ai-tag-green">📚 Textbook Reference: Robbins 10e, ch\. 12<\/strong>/);
});

test('the AI Tutor page and the dock render the repaired text, not the raw reply', () => {
  const page = readFileSync('src/app/ai-tutor/page.tsx', 'utf8');
  assert.match(page, /const markdown = normalizeTutorMarkdown\(safeText\);[\s\S]*?\{markdown\}\s*<\/ReactMarkdown>/);
  assert.doesNotMatch(page, /\{safeText\}\s*<\/ReactMarkdown>/);
  const dock = readFileSync('src/components/FloatingDockReply.tsx', 'utf8');
  assert.match(dock, /\{normalizeTutorMarkdown\(text\)\}/);
});

test('unsafe HTML from a model is removed and one tilde stays text', () => {
  const html = render('pH ~7.4 to ~7.5 <script>alert(1)</script><iframe src="https://x.test"></iframe><img src="x" onerror="alert(1)"> done');
  assert.doesNotMatch(html, /<script|<iframe|onerror|alert\(1\)/);
  assert.doesNotMatch(html, /<del>/);
  assert.match(html, /pH ~7\.4 to ~7\.5/);
});
