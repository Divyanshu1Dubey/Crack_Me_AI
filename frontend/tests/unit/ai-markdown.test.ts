/**
 * AI-written markdown outside the AI Tutor (frontend/src/lib/aiMarkdown.ts, components/ai/AiMarkdown.tsx):
 * the /roadmap study plan used to split the AI text line by line, so table rows, "**", "|---|" and
 * "<br>" showed as plain text, one checklist item per line.
 *
 *   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/ai-markdown.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import ReactMarkdown from 'react-markdown';
import rehypeRaw from 'rehype-raw';
import remarkBreaks from 'remark-breaks';
import remarkGfm from 'remark-gfm';
import { rehypeAllowlist } from '../../src/lib/markdownSanitize.ts';
import {
  plainInline,
  prepareAiMarkdown,
  splitMarkdownSections,
  unwrapMarkdownFence,
} from '../../src/lib/aiMarkdown.ts';

const FRONTEND = fileURLToPath(new URL('../../', import.meta.url));
const read = (rel: string) => readFileSync(path.join(FRONTEND, rel), 'utf8');

// What AiMarkdown renders: FormattedText (components/FormattedText.tsx) given prepareAiMarkdown(text).
// FormattedText collapses horizontal whitespace, then GFM + breaks, raw HTML reduced by the allow-list.
const render = (markdown: string) => renderToStaticMarkup(createElement(
  ReactMarkdown,
  {
    remarkPlugins: [[remarkGfm, { singleTilde: false }], remarkBreaks],
    rehypePlugins: [rehypeRaw, rehypeAllowlist],
  },
  prepareAiMarkdown(markdown).replace(/[ \t\f\v]+/g, ' '),
));

// The shape of the plan in the owner's screenshot: a title, a schedule table with bold, italics and
// <br> inside cells, a "---" separator, lists.
const PLAN = [
  '# 60-Day UPSC CMS Study Plan',
  '',
  'Here is your plan, built around your weak areas.',
  '',
  '## Phase 1 (Foundation): Days 1-20',
  '**Goal:** cover every core subject once.',
  '',
  '| Day | Morning (3h) | Afternoon (3h) | Evening (2h) |',
  '|-----|---|---|---|',
  '| 1-5 | **Medicine**: Cardiology<br>*Harrison Ch. 1-5* | Paediatrics | PYQs (50) |',
  '| 6-10 | **Surgery**: GI tract | OBG | Revision |',
  '',
  '---',
  '',
  '## Phase 2 (Deep Dive): Days 21-40',
  '- **Weak topics first**: Nephrology, *Endocrinology*',
  '- Solve 100 PYQs a day',
  '',
  '## Daily Schedule',
  'Wake up at 6 am<br>Study in 90-minute blocks',
].join('\n');

test('the plan splits into a title, an intro and one section per ## heading', () => {
  const plan = splitMarkdownSections(PLAN);
  assert.equal(plan.title, '60-Day UPSC CMS Study Plan');
  assert.equal(plan.intro, 'Here is your plan, built around your weak areas.');
  assert.deepEqual(plan.sections.map((s) => s.title), [
    'Phase 1 (Foundation): Days 1-20',
    'Phase 2 (Deep Dive): Days 21-40',
    'Daily Schedule',
  ]);
  // The separator after the table is not part of the card.
  assert.ok(plan.sections[0].body.endsWith('| 6-10 | **Surgery**: GI tract | OBG | Revision |'));
  assert.ok(plan.sections[0].body.startsWith('**Goal:**'));
});

test('a section body renders as a table with bold, italics and line breaks, nothing raw', () => {
  const html = render(splitMarkdownSections(PLAN).sections[0].body);
  assert.match(html, /<table>/);
  assert.match(html, /<th>Morning \(3h\)<\/th>/);
  assert.equal((html.match(/<tr>/g) || []).length, 3);
  assert.match(html, /<td><strong>Medicine<\/strong>: Cardiology<br\/><em>Harrison Ch\. 1-5<\/em><\/td>/);
  assert.doesNotMatch(html, /\*\*/);
  assert.doesNotMatch(html, /\|-{3,}/);
  assert.doesNotMatch(html, /&lt;br/);
  assert.doesNotMatch(html, /\| Day \|/);
});

test('the whole plan renders without raw markdown', () => {
  const html = render(PLAN);
  assert.doesNotMatch(html, /\*\*|&lt;br|\|---/);
  assert.match(html, /<li><strong>Weak topics first<\/strong>: Nephrology, <em>Endocrinology<\/em><\/li>/);
  assert.match(html, /Wake up at 6 am<br\/>Study in 90-minute blocks/);
});

test('a table glued to a sentence or squashed onto one line is repaired', () => {
  const glued = render('Weekly targets:\n| Week | Target |\n|---|---|\n| 1 | Medicine |\n**Note:** revise daily');
  assert.match(glued, /<td>Medicine<\/td>/);
  assert.match(glued, /<p><strong>Note:<\/strong> revise daily<\/p>/);
  const squashed = render('Targets: | Week | Target | |---|---| | 1 | Medicine | | 2 | Surgery |');
  assert.match(squashed, /<td>2<\/td><td>Surgery<\/td>/);
});

test('without # headings, bold-only lines split the answer', () => {
  const plan = splitMarkdownSections('Intro line\n\n**Phase 1: Foundation**\n- Harrison\n\n**Daily Schedule:**\nMorning: Medicine');
  assert.equal(plan.title, null);
  assert.equal(plan.intro, 'Intro line');
  assert.deepEqual(plan.sections, [
    { title: 'Phase 1: Foundation', body: '- Harrison' },
    { title: 'Daily Schedule', body: 'Morning: Medicine' },
  ]);
  // A single bold line is emphasis, not a section.
  assert.equal(splitMarkdownSections('**Tip:** read daily\n\n**Only bold line**').sections.length, 0);
});

test('an answer without headings is one block; fenced headings are not sections', () => {
  assert.deepEqual(splitMarkdownSections('Just a paragraph.\n- one\n- two'), {
    title: null, intro: 'Just a paragraph.\n- one\n- two', sections: [],
  });
  const fenced = splitMarkdownSections('## Real\ntext\n```\n## not a heading\n```\n## Second\nmore');
  assert.deepEqual(fenced.sections.map((s) => s.title), ['Real', 'Second']);
  assert.match(fenced.sections[0].body, /## not a heading/);
  assert.deepEqual(splitMarkdownSections(''), { title: null, intro: '', sections: [] });
});

test('several top-level headings split at that level; deeper headings stay in the body', () => {
  const plan = splitMarkdownSections('## Medicine\n### Week 1\nCardiology\n## Surgery\nGI');
  assert.equal(plan.title, null);
  assert.deepEqual(plan.sections, [
    { title: 'Medicine', body: '### Week 1\nCardiology' },
    { title: 'Surgery', body: 'GI' },
  ]);
  assert.deepEqual(splitMarkdownSections('### **Week 1** ###\nA\n### Week 2:\nB').sections.map((s) => s.title),
    ['Week 1', 'Week 2']);
});

test('an answer wrapped in a ```markdown fence is markdown, not a code block', () => {
  const fenced = '```markdown\n# Plan\n## Week 1\n| a | b |\n|---|---|\n| 1 | 2 |\n```';
  assert.equal(unwrapMarkdownFence(fenced), '# Plan\n## Week 1\n| a | b |\n|---|---|\n| 1 | 2 |');
  assert.equal(splitMarkdownSections(fenced).title, 'Plan');
  assert.match(render(fenced), /<table>/);
  assert.doesNotMatch(render(fenced), /<pre>|<code>/);
  // A fence labelled markdown inside prose is unwrapped too; real code blocks stay.
  assert.equal(unwrapMarkdownFence('Plan:\n```md\n**Bold**\n```\nBye'), 'Plan:\n**Bold**\nBye');
  const twoBlocks = '```\ncode one\n```\ntext\n```\ncode two\n```';
  assert.equal(unwrapMarkdownFence(twoBlocks), twoBlocks);
  assert.equal(unwrapMarkdownFence('```json\n{"a": 1}\n```'), '```json\n{"a": 1}\n```');
});

test('model-written images keep only their description; unsafe HTML is removed', () => {
  const html = render('ECG: ![ST elevation](https://example.com/x.png) <script>alert(1)</script><iframe src="x"></iframe>');
  assert.doesNotMatch(html, /<img|<script|<iframe|alert/);
  assert.match(html, /<em>\[ST elevation\]<\/em>/);
});

test('plainInline turns a short markdown label into plain text', () => {
  assert.equal(plainInline('**Phase 1 (Foundation):**'), 'Phase 1 (Foundation)');
  assert.equal(plainInline('** Harrison 21e Ch 277'), 'Harrison 21e Ch 277');
  assert.equal(plainInline('*Hypertension*'), 'Hypertension');
  assert.equal(plainInline('_Staphylococcus aureus_ and snake_case'), 'Staphylococcus aureus and snake_case');
  assert.equal(plainInline('Morning<br>Evening <b>Night</b>'), 'Morning Evening Night');
  assert.equal(plainInline('`code` and [Park](https://example.com) &amp; more'), 'code and Park & more');
  assert.equal(plainInline('  spaced\n out  '), 'spaced out');
  assert.equal(plainInline(277), '277');
  assert.equal(plainInline(null), '');
  assert.equal(plainInline(undefined), '');
});

test('AiMarkdown renders through the shared FormattedText pipeline the test mirrors', () => {
  const component = read('src/components/ai/AiMarkdown.tsx');
  assert.match(component, /<FormattedText text=\{prepareAiMarkdown\(source\)\}/);
  const formatted = read('src/components/FormattedText.tsx');
  assert.match(formatted, /remarkPlugins=\{\[\[remarkGfm, \{ singleTilde: false \}\], remarkBreaks\]\}/);
  assert.match(formatted, /rehypePlugins=\{\[rehypeRaw, rehypeAllowlist\]\}/);
  assert.match(formatted, /text\.replace\(\/\[ \\t\\f\\v\]\+\/g, ' '\)/);
});

test('the roadmap renders the plan and high-yield answers as markdown, never as raw text', () => {
  const page = read('src/app/roadmap/page.tsx');
  assert.match(page, /splitMarkdownSections\(studyPlan\)/);
  assert.match(page, /<AiMarkdown text=\{section\.body\}/);
  assert.match(page, /<AiMarkdown text=\{highYield\}/);
  assert.doesNotMatch(page, /<pre\b/);
  assert.doesNotMatch(page, /studyPlan\.split\('\\n'\)/);
  assert.doesNotMatch(page, /section\.items\.map/);
});

test('generated questions and AI analyses go through AiMarkdown', () => {
  const card = read('src/components/QuestionComposer/QuestionCard.tsx');
  assert.match(card, /<AiMarkdown text=\{question\.question_text\}/);
  assert.match(card, /<AiMarkdown\s+text=\{question\.explanation\}/);
  const panel = read('src/components/QuestionComposer/ExplanationPanel.tsx');
  for (const field of ['why_correct', 'mnemonic', 'clinical_pearl', 'exam_tip']) {
    assert.match(panel, new RegExp(`<AiMarkdown text=\\{explanation\\.${field}\\}`), field);
  }
  const review = read('src/app/tests/[id]/page.tsx');
  for (const field of ['mnemonic', 'topic_deep_dive', 'clinical_pearl', 'exam_tip', 'quick_revision']) {
    assert.match(review, new RegExp(`<AiMarkdown text=\\{aiExp\\.${field}\\} />`), field);
  }
  assert.match(review, /<AiMarkdown text=\{whyCorrectMarkdown\(aiExp\.why_correct\)\} \/>/);
});
