/**
 * Unit tests for the answer-key review queue helpers (frontend/src/lib/keyAudit.ts).
 *
 *   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/key-audit.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  STATUS_LABELS,
  STATUS_ORDER,
  batchEligible,
  batchItems,
  cleanEvidence,
  describeError,
  evidenceError,
  expectedStatus,
  hasStrongEvidence,
  resolvePayload,
  signalLabel,
  sourceKeyEvidence,
  statusTone,
  type QueueRow,
} from '../../src/lib/keyAudit.ts';

function row(overrides: Partial<QueueRow> = {}): QueueRow {
  return {
    id: 1, question_id: 10, status: 'needs_review', status_reason: 'source_key_mismatch', stored_key: 'A',
    suggested_key: 'C', suggested_from: 'source_key_mismatch', priority: 95, open_signals: ['source_key_mismatch'],
    is_stale: false, audited_at: '', question_text: 'stem', exam_type: 'neet_pg', year: 2025, subject: 'Medicine',
    claimed_by: null, printed_key: { id: 7, letter: 'C', source_file: 'x.pdf', question_page: 3, question_number: 2 },
    ...overrides,
  };
}

test('every status has a label and the queue order starts with what needs a human', () => {
  assert.equal(STATUS_ORDER[0], 'needs_review');
  for (const status of STATUS_ORDER) assert.ok(STATUS_LABELS[status]);
  assert.equal(statusTone('needs_review'), 'destructive');
  assert.equal(statusTone('likely_correct'), 'success');
  assert.equal(statusTone('insufficient_evidence'), 'secondary');
});

test('signal labels fall back to readable text', () => {
  assert.equal(signalLabel('ai_review_disagrees'), 'AI review signal disagrees');
  assert.equal(signalLabel('some_new_code'), 'some new code');
  assert.equal(signalLabel(''), '');
});

test('evidence rules mirror the backend', () => {
  assert.match(evidenceError({ kind: 'passage', source_title: 'Book', page_label: '12' }) ?? '', /needs quote/);
  assert.match(evidenceError({ kind: 'passage', source_title: 'Book', page_label: '12', quote: 'short' }) ?? '', /10 characters/);
  assert.equal(evidenceError({ kind: 'passage', source_title: 'Book', page_label: '12', quote: 'Adrenaline is first line.' }), null);
  assert.match(evidenceError({ kind: 'guideline_url', source_title: 'WHO', url: 'javascript:alert(1)' }) ?? '', /http/);
  assert.equal(evidenceError({ kind: 'official_key', source_title: 'UPSC CMS 2024 key' }), null);
  assert.match(evidenceError({ kind: 'nonsense' as never }) ?? '', /kind/);
});

test('only official keys, errata, guidelines and passages are strong evidence', () => {
  assert.equal(hasStrongEvidence([{ kind: 'note', text: 'I am sure' }]), false);
  assert.equal(hasStrongEvidence([sourceKeyEvidence({ id: 3, source_file: 'x.pdf', question_page: 4 })]), false);
  assert.equal(hasStrongEvidence([{ kind: 'official_key', source_title: 'UPSC CMS 2024 key' }]), true);
  assert.equal(hasStrongEvidence([{ kind: 'official_key' }]), false);   // incomplete items do not count
  assert.equal(expectedStatus({ resolution: 'key_confirmed', evidence: [] }), 'likely_correct');
  assert.equal(expectedStatus({ resolution: 'key_changed', evidence: [{ kind: 'errata', source_title: 'UPSC errata 2023' }] }), 'verified');
  assert.equal(expectedStatus({ resolution: 'deferred', evidence: [] }), 'needs_review');
});

test('cleanEvidence keeps only filled fields', () => {
  assert.deepEqual(cleanEvidence({ kind: 'passage', source_title: ' Harrison 21e ', page_label: '', quote: 'A quote here.' }),
    { kind: 'passage', source_title: 'Harrison 21e', quote: 'A quote here.' });
});

test('resolvePayload validates the form before anything is sent', () => {
  assert.deepEqual(resolvePayload({ resolution: 'key_confirmed', reason: 'short', expectedKey: 'A', evidence: [] }),
    { error: 'Give a reason (at least 10 characters).' });
  assert.ok('error' in resolvePayload({ resolution: 'key_changed', reason: 'long enough reason', expectedKey: 'A', newKey: 'A', evidence: [] }));
  assert.ok('error' in resolvePayload({ resolution: 'key_changed', reason: 'long enough reason', expectedKey: 'A', newKey: 'E', evidence: [] }));
  const ok = resolvePayload({ resolution: 'key_changed', reason: ' long enough reason ', expectedKey: 'A', newKey: 'c', evidence: [] });
  assert.ok('body' in ok);
  if ('body' in ok) {
    assert.equal(ok.body.new_key, 'C');
    assert.equal(ok.body.expected_key, 'A');
    assert.equal(ok.body.reason, 'long enough reason');
  }
  assert.ok('error' in resolvePayload({ resolution: 'explanation_fixed', reason: 'long enough reason', expectedKey: 'A', evidence: [], explanation: ' ' }));
});

test('batch selection takes only confident printed-key rows the reviewer ticked', () => {
  const rows = [
    row(),
    row({ question_id: 11, printed_key: null }),
    row({ question_id: 12, claimed_by: 'someone' }),
    row({ question_id: 13, claimed_by: 'me' }),
    row({ question_id: 14, suggested_from: 'ai_review_disagrees' }),
    row({ question_id: 15, stored_key: '' }),
  ];
  assert.deepEqual(rows.map((r) => batchEligible(r, 'me')), [true, false, false, true, false, false]);
  const items = batchItems(rows, new Set([10, 11, 12, 13]), 'me');
  assert.deepEqual(items, [
    { question_id: 10, expected_key: 'A', source_key_id: 7 },
    { question_id: 13, expected_key: 'A', source_key_id: 7 },
  ]);
  const many = Array.from({ length: 30 }, (_, i) => row({ question_id: 100 + i }));
  assert.equal(batchItems(many, new Set(many.map((r) => r.question_id)), 'me').length, 25);
});

test('describeError explains conflicts and validation errors', () => {
  assert.match(describeError({ response: { status: 409, data: { code: 'claimed', claimed_by: 'admin2' } } }), /admin2/);
  assert.match(describeError({ response: { status: 409, data: { code: 'key_changed', current_key: 'B' } } }), /changed to B/);
  assert.equal(describeError({ response: { status: 400, data: { reason: ['At least 10 characters.'] } } }), 'reason: At least 10 characters.');
  assert.equal(describeError(new Error('Network Error')), 'Network Error');
});
