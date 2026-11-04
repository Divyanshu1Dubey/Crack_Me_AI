/**
 * Unit tests for the question editor's medical-accuracy rules
 * (frontend/src/app/admin/questions-editor/editorialRules.ts).
 *
 *   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/editorial-rules.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  acceptBlockedReason,
  acceptableFields,
  auditStatusLabel,
  canMarkReviewed,
  changedExplanationFields,
  citationWhere,
  describeEditorialError,
  draftFromForm,
  evidenceSummary,
  explanationTone,
  formatWhen,
  keyChangeLine,
  keyChangeOutcome,
  keyChangeOutcomeText,
  keyChangePayload,
  keyChangeProblems,
  normalizeKey,
  optionSupportRows,
  originLabel,
  reviewQueueLink,
  saveExplanationBody,
  suggestionMessage,
  suggestionTone,
} from '../../src/app/admin/questions-editor/editorialRules.ts';

const PASSAGE = {
  kind: 'passage' as const,
  source_title: "Harrison's Principles of Internal Medicine, 21st",
  page_label: '1450',
  quote: 'ST elevation with a rise in troponin defines an acute myocardial infarction.',
};

function suggestion(overrides: Record<string, unknown> = {}) {
  return {
    status: 'ok' as const,
    for_key: 'B',
    stored_key: 'B',
    retrieval_mode: 'bm25_fts5',
    conflict: null,
    image_context: { required: false, available: true },
    fields: { explanation: 'Option B: reference passages' },
    option_evidence: {},
    ...overrides,
  } as never;
}

test('keys are A-D or nothing', () => {
  assert.equal(normalizeKey(' b '), 'B');
  assert.equal(normalizeKey('E'), '');
  assert.equal(normalizeKey('AB'), '');
  assert.equal(normalizeKey(undefined), '');
});

test('a key change needs a new key, a reason and complete evidence', () => {
  const ready = { storedKey: 'A', newKey: 'B', reason: 'Troponin rise and ST elevation.', evidence: [PASSAGE] };
  assert.deepEqual(keyChangeProblems(ready), []);
  assert.match(keyChangeProblems({ ...ready, newKey: '' })[0], /Choose the new key/);
  assert.match(keyChangeProblems({ ...ready, newKey: 'A' })[0], /already the key/);
  assert.match(keyChangeProblems({ ...ready, reason: ' too short ' })[0], /at least 10/);
  assert.match(keyChangeProblems({ ...ready, evidence: [{ kind: 'passage', source_title: 'Book', page_label: '3' }] })[0], /quote/);
  // Setting a first key: any letter.
  assert.deepEqual(keyChangeProblems({ ...ready, storedKey: '' }), []);
});

test('the change-key body is cleaned and carries the key the editor loaded', () => {
  const built = keyChangePayload({
    storedKey: 'a', newKey: 'c', reason: '  Official key says C.  ',
    evidence: [{ kind: 'official_key', source_title: ' UPSC CMS 2024 key ', quote: '', url: '' }],
  });
  assert.ok('body' in built);
  assert.deepEqual(built.body, {
    new_key: 'C', reason: 'Official key says C.', expected_key: 'A',
    evidence: [{ kind: 'official_key', source_title: 'UPSC CMS 2024 key' }],
  });
  const refused = keyChangePayload({ storedKey: 'A', newKey: 'C', reason: 'short', evidence: [] });
  assert.ok('error' in refused);
});

test('the result is shown in advance: verified only with strong evidence', () => {
  assert.equal(keyChangeOutcome([]), 'likely_correct');
  assert.equal(keyChangeOutcome([{ kind: 'note', text: 'I am sure' }]), 'likely_correct');
  assert.equal(keyChangeOutcome([{ kind: 'source_key', source_key_id: 3 }]), 'likely_correct');
  assert.equal(keyChangeOutcome([{ kind: 'passage', source_title: 'Book', page_label: '3' }]), 'likely_correct');
  assert.equal(keyChangeOutcome([PASSAGE]), 'verified');
  assert.match(keyChangeOutcomeText([]), /never "verified"/);
  assert.match(keyChangeOutcomeText([PASSAGE]), /^Verified/);
});

test('suggestion outcomes are explained plainly', () => {
  assert.match(suggestionMessage(suggestion()), /support option B/);
  assert.match(suggestionMessage(suggestion({ stored_key: 'A' })), /stored key is A: change the key first/);
  assert.match(
    suggestionMessage(suggestion({ status: 'conflict', for_key: 'A', stored_key: 'A',
      conflict: { evidence_supports: 'C', selected: 'A', stored: 'A', margin: 1.2, summary: '' } })),
    /support option C, not A.*must not argue/,
  );
  assert.match(suggestionMessage(suggestion({ status: 'insufficient_evidence', retrieval_mode: 'none' })),
    /no reference store on this server/);
  assert.match(suggestionMessage(suggestion({ status: 'insufficient_evidence' })), /too weak to support option B/);
  assert.match(suggestionMessage(suggestion({ status: 'image_context_missing',
    image_context: { required: true, available: false, missing_reason: 'no_image_attached' } })), /no image is attached/);
  assert.match(suggestionMessage(suggestion({ status: 'failed' })), /failed/);
  assert.equal(suggestionTone('ok'), 'success');
  assert.equal(suggestionTone('conflict'), 'destructive');
  assert.equal(suggestionTone('insufficient_evidence'), 'secondary');
});

test('only an evidence-supported suggestion for the stored key goes into the editor', () => {
  assert.equal(acceptBlockedReason(suggestion(), 'B'), null);
  assert.match(acceptBlockedReason(suggestion(), 'A') ?? '', /explains option B; the key is A/);
  assert.match(acceptBlockedReason(suggestion(), '') ?? '', /Set the answer key first/);
  assert.match(acceptBlockedReason(suggestion({ status: 'conflict', fields: {} }), 'B') ?? '', /evidence supports/);
  assert.match(acceptBlockedReason(suggestion({ fields: { explanation: '  ' } }), 'B') ?? '', /no text/);
});

test('only the fields save-explanation writes are offered', () => {
  const offered = acceptableFields(suggestion({ fields: { explanation: 'Quote', why_correct: 'Not saved by this path', mnemonic: '' } }));
  assert.deepEqual(offered.map((f) => f.field), ['explanation']);
});

test('passages are labelled with their own metadata', () => {
  assert.equal(citationWhere({ source_title: 'Harrison', page: 1450, page_label: '', tier: 3 }), 'Harrison · PDF p. 1450 · tier 3');
  assert.equal(citationWhere({ source_title: 'Harrison', page: 1450, page_label: 'PDF p. 1450', tier: null }), 'Harrison · PDF p. 1450');
  assert.equal(citationWhere({ source_title: '', page: null, page_label: '', tier: null }), 'Reference');
});

test('option support rows mark the best supported option', () => {
  const rows = optionSupportRows(suggestion({
    for_key: 'A', stored_key: 'A',
    option_evidence: { A: { support: 0.2, citations: [{}] }, C: { support: 1.9, citations: [{}, {}] } },
  }));
  assert.deepEqual(rows.map((r) => [r.letter, r.support, r.passages, r.best, r.selected, r.stored]), [
    ['A', 0.2, 1, false, true, true], ['B', 0, 0, false, false, false], ['C', 1.9, 2, true, false, false], ['D', 0, 0, false, false, false],
  ]);
  assert.ok(optionSupportRows(suggestion({ option_evidence: {} })).every((r) => !r.best));
});

test('the draft carries the unsaved stem, options and explanation, never the key', () => {
  const draft = draftFromForm({
    question_text: 'Stem', option_a: 'a', option_b: 'b', option_c: 'c', option_d: 'd', explanation: 'x',
    correct_answer: 'D', needs_review: true, concept_keywords: 'k',
  });
  assert.deepEqual(Object.keys(draft).sort(), ['explanation', 'option_a', 'option_b', 'option_c', 'option_d', 'question_text']);
});

test('save-explanation body: for the key, accepted fields only with their suggestion', () => {
  assert.ok('error' in saveExplanationBody({ fields: { explanation: 'x' }, forKey: '' }));
  assert.ok('error' in saveExplanationBody({ fields: { why_correct: 'x' }, forKey: 'A' }));
  const plain = saveExplanationBody({ fields: { explanation: 'x', why_correct: 'y' }, forKey: 'a', acceptedFields: ['explanation'] });
  assert.ok('body' in plain);
  assert.deepEqual(plain.body, { fields: { explanation: 'x' }, for_key: 'A' });
  const mixed = saveExplanationBody({
    fields: { explanation: 'x', mnemonic: 'm' }, forKey: 'A', suggestionId: 'uuid-1',
    acceptedFields: ['explanation', 'concept_explanation'], aiFields: ['mnemonic', 'why_correct'],
  });
  assert.ok('body' in mixed);
  assert.deepEqual(mixed.body, {
    fields: { explanation: 'x', mnemonic: 'm' }, for_key: 'A', suggestion_id: 'uuid-1',
    accepted_fields: ['explanation'], ai_fields: ['mnemonic'],
  });
});

test('changed explanation fields are detected', () => {
  assert.deepEqual(changedExplanationFields({ explanation: 'new', mnemonic: 'm' }, { explanation: 'old', mnemonic: 'm' }), ['explanation']);
  assert.deepEqual(changedExplanationFields({ explanation: '' }, {}), []);
});

test('provenance labels', () => {
  assert.equal(explanationTone('stale'), 'destructive');
  assert.equal(explanationTone('pending_review'), 'warning');
  assert.equal(explanationTone('reviewed'), 'success');
  assert.equal(canMarkReviewed('stale'), false);
  assert.equal(canMarkReviewed('conflict'), false);
  assert.equal(canMarkReviewed('absent'), false);
  assert.equal(canMarkReviewed('pending_review'), true);
  assert.equal(originLabel('mixed'), 'Admin, from a suggestion or AI draft');
  assert.equal(originLabel(''), 'Not recorded');
  assert.equal(auditStatusLabel('unaudited'), 'Not audited yet');
  assert.equal(auditStatusLabel('likely_correct'), 'Likely correct');
  assert.equal(evidenceSummary([{ kind: 'passage' }, { kind: 'note' }]), 'Textbook passage (page + quote) (strong), Note (reasoning, not evidence)');
  assert.equal(keyChangeLine({ old_key: '', new_key: 'C', changed_by_username: '', source: 'review_queue' }), '– → C by unknown (review queue)');
  const link = reviewQueueLink(10290);
  assert.equal(link.href, '/admin/review-queue?q=10290');
  assert.match(link.hint, /10290/);
  assert.equal(formatWhen(null), '');
  assert.equal(formatWhen('not a date'), '');
  assert.ok(formatWhen('2026-11-04T10:00:00Z').length > 0);
});

test('editor errors read as sentences', () => {
  const err = (status: number, data: unknown) => ({ response: { status, data } });
  assert.match(describeEditorialError(err(409, { code: 'key_changed', current_key: 'C', detail: 'x' })), /now C/);
  assert.equal(describeEditorialError(err(400, { code: 'no_key', detail: 'Set the answer key first.' })), 'Set the answer key first.');
  assert.match(describeEditorialError(err(429, { detail: 'Request was throttled.' })), /Too many requests/);
  assert.match(describeEditorialError(err(400, { evidence: ['source_key_id 9 is not a source key of this question'] })), /evidence: source_key_id 9/);
  assert.match(describeEditorialError(err(403, {})), /Admin access/);
});
