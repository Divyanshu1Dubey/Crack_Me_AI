/**
 * Unit tests for the student citation rules (frontend/src/components/evidence/citationRules.ts):
 * at most three citations, snippets of at most 240 characters, nothing for a locked answer, only
 * signed evidence-figure URLs.
 *
 *   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/editorial-citations.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  MAX_CITATIONS,
  SNIPPET_MAX_CHARS,
  clipSnippet,
  normalizeCitations,
  pageText,
  safeFigureUrl,
  sourceLine,
  stanceText,
} from '../../src/components/evidence/citationRules.ts';

const LONG = 'Laryngomalacia is the most common congenital anomaly of the larynx and the most frequent cause of '
  + 'congenital stridor in infants; the stridor is inspiratory, worse when supine or feeding, and most cases resolve '
  + 'spontaneously by eighteen to twenty-four months without any intervention at all.';

function raw(id: number, overrides: Record<string, unknown> = {}) {
  return {
    id,
    citation: `Nelson Textbook of Pediatrics, 21st, 2020, p. ${1400 + id}`,
    source: { title: 'Nelson Textbook of Pediatrics', edition: '21st', year: 2020, kind: 'textbook' },
    chapter: 'Congenital anomalies of the larynx',
    page_label: String(1400 + id),
    page_note: '',
    snippet: 'Laryngomalacia is the most common cause of congenital stridor.',
    stance: 'supports',
    option_letter: 'A',
    figure_url: null,
    verified: true,
    ...overrides,
  };
}

test('snippets are cut to at most 240 characters at a word boundary', () => {
  assert.ok(LONG.length > SNIPPET_MAX_CHARS);
  const cut = clipSnippet(LONG);
  assert.ok(cut.length <= SNIPPET_MAX_CHARS, String(cut.length));
  assert.ok(cut.endsWith('…'));
  assert.ok(LONG.startsWith(cut.slice(0, -1)));
  assert.equal(clipSnippet('  short\n text '), 'short text');
  assert.equal(clipSnippet(42), '');
});

test('a locked or malformed answer shows nothing', () => {
  assert.deepEqual(normalizeCitations({ citations: [raw(1)], locked: true }), []);
  assert.deepEqual(normalizeCitations({ citations: 'nope' }), []);
  assert.deepEqual(normalizeCitations(null), []);
  assert.deepEqual(normalizeCitations({ question_id: 3, citations: [] }), []);
  assert.deepEqual(normalizeCitations({ citations: [{ id: 5, source: { title: '' }, citation: '' }] }), []);
});

test('at most three citations, deduplicated, each clipped and without extra fields', () => {
  const page = 'Full page text that must never reach a student. '.repeat(40);
  const views = normalizeCitations({
    locked: false,
    citations: [raw(1, { snippet: LONG, text: page, sha256: 'a'.repeat(64) }), raw(1), raw(2), raw(3), raw(4)],
  });
  assert.equal(views.length, MAX_CITATIONS);
  assert.deepEqual(views.map((v) => v.id), [1, 2, 3]);
  assert.ok(views[0].snippet.length <= SNIPPET_MAX_CHARS);
  assert.deepEqual(Object.keys(views[0]).sort(),
    ['chapter', 'edition', 'figureUrl', 'id', 'page', 'snippet', 'stance', 'title', 'year']);
  assert.ok(!JSON.stringify(views).includes('Full page text'));
});

test('page, stance and source lines', () => {
  assert.equal(pageText({ page_label: '312', page_note: '' }), 'p. 312');
  assert.equal(pageText({ page_label: '', page_note: 'PDF p. 340' }), 'PDF p. 340');
  assert.equal(pageText({ page_label: '', page_note: '' }), '');
  assert.equal(stanceText({ stance: 'supports', option_letter: 'b' }), 'Supports option B');
  assert.equal(stanceText({ stance: 'contradicts', option_letter: 'C' }), 'Argues against option C');
  assert.equal(stanceText({ stance: 'states_key', option_letter: '' }), 'States the answer');
  assert.equal(stanceText({ stance: 'candidate', option_letter: 'A' }), '');
  assert.equal(sourceLine({ title: 'Nelson Textbook of Pediatrics', edition: '21st', year: 2020 }), 'Nelson Textbook of Pediatrics, 21st ed. (2020)');
  assert.equal(sourceLine({ title: 'Harrison', edition: '21st edition', year: null }), 'Harrison, 21st edition');
  assert.equal(sourceLine({ title: 'WHO guideline 2023', edition: '', year: 2023 }), 'WHO guideline 2023');
});

test('only signed evidence-figure URLs are shown', () => {
  assert.equal(safeFigureUrl('https://api.cracklabs.app/api/evidence/figures/12/?t=abc'), 'https://api.cracklabs.app/api/evidence/figures/12/?t=abc');
  assert.equal(safeFigureUrl('/api/evidence/figures/12/?t=abc'), '/api/evidence/figures/12/?t=abc');
  assert.equal(safeFigureUrl('javascript:alert(1)'), null);
  assert.equal(safeFigureUrl('data:image/png;base64,AAAA'), null);
  assert.equal(safeFigureUrl('https://api.cracklabs.app/api/evidence/pages/abc/3/image.png'), null);
  assert.equal(safeFigureUrl(null), null);
  const views = normalizeCitations({ citations: [raw(1, { figure_url: 'https://evil.example/x.png' })] });
  assert.equal(views[0].figureUrl, null);
});
