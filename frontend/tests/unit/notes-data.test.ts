/**
 * Unit tests for the topic-notes helpers (frontend/src/components/notes/notesData.ts).
 *
 *   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/notes-data.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  DEFAULT_BUILD_FORM,
  PROVISIONAL_LABEL,
  askedLine,
  buildActionLabel,
  buildPayload,
  contentEditWarning,
  countMarks,
  describeNotesError,
  examLabel,
  facetTopics,
  hasProvisionalPoints,
  hiddenNotice,
  isBuiltNote,
  isFeatureDisabled,
  keyStatusLabel,
  keyStatusTone,
  lockedTeaser,
  noteListParams,
  noteSummary,
  pointSources,
  practiceHref,
  reasonLabel,
  sectionsWithPoints,
  spokenSittingLabel,
  summarizeBuild,
  warningLabel,
  type NoteFacets,
  type NotePoint,
  type PublishedNote,
} from '../../src/components/notes/notesData.ts';

function point(overrides: Partial<NotePoint> = {}): NotePoint {
  return {
    id: 'p1', kind: 'fact', stem: 'Antidote for organophosphate poisoning', answer: 'Atropine', key_status: 'provisional',
    question_ids: [11, 12], asked_in: ['CMS 2022 P2', 'CMS 2018 P1'], frequency: 2, ...overrides,
  };
}

function note(overrides: Partial<PublishedNote> = {}): PublishedNote {
  return {
    id: 1, title: 'Antidotes', subject: 3, subject_name: 'Pharmacology', topic: 4, topic_name: 'Antidotes', exam_type: 'cms',
    is_combined: false, content: '', content_preview: '', source_question_ids: [], source_question_count: 4,
    ai_generated: false, is_published: true, generation_method: 'extractive', builder_version: 'pyq-notes/2',
    built_at: null, is_stale: false, verified_source_count: 1, provisional_source_count: 3, answers_locked: false,
    locked_points: 0, hidden_points: 0, counts: { cited: 4 }, ...overrides,
  };
}

test('unverified keys are always labelled provisional, never as verified', () => {
  assert.equal(keyStatusLabel('provisional'), PROVISIONAL_LABEL);
  assert.equal(keyStatusLabel(''), PROVISIONAL_LABEL);
  assert.equal(keyStatusLabel(undefined), PROVISIONAL_LABEL);
  assert.equal(keyStatusLabel('verified'), 'Verified key');
  assert.equal(keyStatusTone('provisional'), 'warning');
  assert.equal(keyStatusTone('verified'), 'success');
  assert.match(PROVISIONAL_LABEL, /answer key not yet verified/);
});

test('exam labels and the cross-exam note', () => {
  assert.equal(examLabel('neet_pg'), 'NEET PG');
  assert.equal(examLabel('cms', true), 'All exams');
  assert.equal(examLabel('all'), 'All exams');
  assert.equal(examLabel('zz'), 'ZZ');
});

test('sources: per question when the build recorded them, else ids only', () => {
  const withSources = point({ sources: [{ id: 12, label: 'CMS 2022 P2', year: 2022, exam_type: 'cms', key_status: 'verified' }] });
  assert.deepEqual(pointSources(withSources).map((s) => s.id), [12]);
  assert.deepEqual(pointSources(point()).map((s) => [s.id, s.label, s.key_status]), [[11, '', 'provisional'], [12, '', 'provisional']]);
  assert.equal(practiceHref(42), '/practice?id=42');
  assert.equal(spokenSittingLabel('CMS 2019 P1'), 'CMS 2019 Paper 1');
  assert.equal(spokenSittingLabel('NEET PG 2021 (recall)'), 'NEET PG 2021 (recall)');
});

test('asked line', () => {
  assert.equal(askedLine(point()), 'Asked 2× · CMS 2022 P2, CMS 2018 P1');
  assert.equal(askedLine(point({ frequency: 1, asked_in: ['INI-CET 2023 May'] })), 'Asked in INI-CET 2023 May');
  assert.equal(askedLine(point({ asked_in: ['a', 'b', 'c'] }), 2), 'Asked 2× · a, b …');
  assert.equal(askedLine(point({ asked_in: [] })), '');
});

test('sections keep their order and drop points the viewer may not read', () => {
  const n = note({
    points: [point({ id: 'p1' }), point({ id: 'p3', key_status: 'verified' })],
    sections: [
      { id: 's1', title: 'Most repeated', points: ['p1', 'p2'] },
      { id: 's2', title: 'Locked only', points: ['p2'] },
      { id: 's3', title: 'Other PYQs', points: ['p3'] },
    ],
  });
  assert.deepEqual(sectionsWithPoints(n).map(({ section, points }) => [section.title, points.map((p) => p.id)]),
    [['Most repeated', ['p1']], ['Other PYQs', ['p3']]]);
  assert.equal(hasProvisionalPoints(n), true);
  assert.equal(hasProvisionalPoints(note({ points: [point({ key_status: 'verified' })] })), false);
  // A practice point states no answer: it does not need the legend.
  assert.equal(hasProvisionalPoints(note({ points: [point({ kind: 'practice' })] })), false);
  assert.equal(hasProvisionalPoints(note({ points: null, provisional_source_count: 2 })), true);
});

test('summaries, locked and hidden notices', () => {
  assert.equal(noteSummary(note()), '4 PYQs · 1 verified, 3 provisional');
  assert.equal(noteSummary(note({ builder_version: '', source_question_count: 2 })), '2 source PYQs');
  assert.equal(noteSummary(note({ builder_version: '', source_question_count: 0 })), '');
  assert.equal(isBuiltNote(note()), true);
  assert.equal(isBuiltNote(note({ builder_version: ' ' })), false);
  assert.equal(lockedTeaser(3), '3 more points with Premium');
  assert.equal(lockedTeaser(1), '1 more point with Premium');
  assert.equal(lockedTeaser(null), '');
  assert.match(hiddenNotice(1), /^1 point is hidden/);
  assert.match(hiddenNotice(2), /^2 points are hidden/);
  assert.equal(hiddenNotice(0), '');
});

test('list parameters', () => {
  assert.deepEqual(noteListParams({}), { page: 1 });
  assert.deepEqual(noteListParams({ exam: 'cms', subject: '3', topic: 'x', q: '  heart   failure ', page: 2 }),
    { page: 2, exam_type: 'cms', subject: 3, q: 'heart failure' });
  const facets: NoteFacets = { total: 1, exams: [], subjects: [{ id: 3, name: 'Pharma', count: 1, topics: [{ id: 4, name: 'T', count: 1 }] }] };
  assert.deepEqual(facetTopics(facets, '3').map((t) => t.id), [4]);
  assert.deepEqual(facetTopics(facets, ''), []);
  assert.deepEqual(facetTopics(null, 3), []);
});

test('errors: the switched-off builder and readable messages', () => {
  const off = { response: { status: 404, data: { code: 'feature_disabled', detail: 'off' } } };
  assert.equal(isFeatureDisabled(off), true);
  assert.equal(isFeatureDisabled({ response: { status: 404, data: { error: 'Note not found' } } }), false);
  assert.match(describeNotesError(off), /switched off/);
  assert.equal(describeNotesError({ response: { status: 400, data: { error: 'Fewer than 3 usable PYQs.' } } }), 'Fewer than 3 usable PYQs.');
  assert.equal(describeNotesError({ response: { status: 400, data: { content: ['A published note needs content.'] } } }),
    'content: A published note needs content.');
  assert.equal(describeNotesError({ response: { status: 403 } }), 'Admin access is needed.');
  assert.equal(describeNotesError({ message: 'Network Error' }), 'Network Error');
});

test('build payload', () => {
  assert.deepEqual(buildPayload(DEFAULT_BUILD_FORM, true), { error: 'Choose a subject.' });
  assert.deepEqual(buildPayload({ ...DEFAULT_BUILD_FORM, subjectId: '3' }, true),
    { error: 'Choose a topic, or build the whole subject.' });
  const topic = buildPayload({ ...DEFAULT_BUILD_FORM, subjectId: '3', topicId: '4' }, true);
  assert.ok('body' in topic);
  assert.deepEqual(topic.body, {
    exam_type: 'cms', combined: false, level: 'topic', subject: 3, topic: 4, mode: 'extractive',
    include_provisional: true, verified_only: false, min_questions: 3, force: false, dry_run: true,
  });
  const combinedSubject = buildPayload({ ...DEFAULT_BUILD_FORM, exam: 'combined', scope: 'subject', subjectId: '3' }, false);
  assert.ok('body' in combinedSubject);
  assert.equal(combinedSubject.body.combined, true);
  assert.equal(combinedSubject.body.exam_type, 'all');
  assert.equal(combinedSubject.body.level, 'subject');
  assert.equal('topic' in combinedSubject.body, false);
  const everyTopic = buildPayload({ ...DEFAULT_BUILD_FORM, exam: 'each', scope: 'subject_topics', subjectId: '3' }, false);
  assert.ok('body' in everyTopic);
  assert.deepEqual([everyTopic.body.exam_type, everyTopic.body.combined, everyTopic.body.level], ['all', false, 'topic']);
  assert.deepEqual(buildPayload({ ...DEFAULT_BUILD_FORM, subjectId: '3', topicId: '4', minQuestions: 0 }, true),
    { error: 'Minimum PYQs must be between 1 and 50.' });
});

test('build report labels', () => {
  assert.equal(buildActionLabel('create', true), 'created');
  assert.equal(buildActionLabel('create', false), 'would be created');
  assert.equal(summarizeBuild({ apply: true, totals: { create: 2, unchanged: 1 } }), '2 notes created, 1 note unchanged');
  assert.equal(summarizeBuild({ apply: false, totals: {} }), 'Nothing to build.');
  assert.equal(reasonLabel('open_wrong_answer_report'), 'Open wrong-answer report');
  assert.equal(reasonLabel('something_new'), 'something new');
  assert.equal(warningLabel('llm_skipped_offline_mode'), 'AI rewrite skipped: offline mode');
  assert.equal(warningLabel('llm_validation_failed (1/4 bullets usable)'), 'AI rewrite rejected (1/4 bullets usable)');
});

test('a hand edit of a built note warns, and dropped provisional marks are counted', () => {
  assert.equal(countMarks('- ⚠ a\n- ⚠ b\n- c'), 2);
  const built = { is_built: true, content: '- ⚠ a\n- ⚠ b' };
  assert.equal(contentEditWarning(built, built.content), null);
  const warning = contentEditWarning(built, '- a\n- ⚠ b') ?? '';
  assert.match(warning, /manual note/);
  assert.match(warning, /1 ⚠ mark removed/);
  assert.equal(contentEditWarning({ is_built: false, content: 'x' }, 'y'), null);
  assert.match(contentEditWarning({ builder_version: '', content: '- ⚠ x' }, 'x') ?? '', /mark removed/);
});
