"""PYQ-first topic notes, end to end (2026-11, notes group).

Covers questions.key_status, questions.notes_builder, the admin routes (build, sources, library,
the old generate endpoints delegating to the builder), the student read paths (published list,
detail, facets) and their entitlement: a note restates answers, so a free account reads only the
points whose PYQs are all free showcase questions, and never a scholarship question's answer.
No test calls an AI provider (AIService._call_ai is patched where a path could reach it).
"""
import os
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models_freemium import FreeShowcaseQuestion
from questions import key_status as ks
from questions import notes_builder as nb
from questions.models import (
    DuplicateCluster, DuplicateMember, Question, QuestionFeedback, QuestionImage, Subject, Topic, TopicNote,
    TopicNoteSource,
)

User = get_user_model()

BUILD = '/api/questions/topic-notes/build/'
PUBLISHED = '/api/questions/topic-notes/published/'
FACETS = '/api/questions/topic-notes/published/facets/'
LIBRARY = '/api/questions/topic-notes/library/'
CALL_AI = 'ai_engine.services.AIService._call_ai'


def _user(name, *, premium=False, **extra):
    user = User.objects.create_user(username=name, email=f'{name}@cracklabs.test', password='unused-pw-1', **extra)
    if premium:
        from accounts.models import Subscription
        Subscription.objects.create(user=user, plan='1_year', status='active',
                                    expires_at=timezone.now() + timedelta(days=365))
    return user


def _client(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user)
    return client


def _q(subject, topic, stem, answer, *, year=2020, exam_type='cms', paper=1, **kw):
    data = dict(question_text=stem, option_a=answer, option_b='Placebo tablet', option_c='Sugar pill',
                option_d='Saline drip', correct_answer='A', subject=subject, topic=topic, exam_type=exam_type,
                year=year, paper=paper if exam_type == 'cms' else 0)
    data.update(kw)
    return Question.objects.create(**data)


class _NotesBase(TestCase):
    """A topic with four usable CMS PYQs (one admin-verified, one repeated pair, one provisional),
    four excluded ones, and one NEET PG PYQ."""

    def setUp(self):
        self.subject = Subject.objects.create(name='Pharmacology', code='PHARM')
        self.topic = Topic.objects.create(name='Antidotes and emergencies', subject=self.subject)
        t = (self.subject, self.topic)
        self.verified = _q(*t, 'Drug of choice for anaphylactic shock is', 'Adrenaline', year=2021,
                           is_verified_by_admin=True, verified_at=timezone.now())
        self.repeat_old = _q(*t, 'Antidote used for organophosphate poisoning', 'Atropine', year=2018)
        self.repeat_new = _q(*t, 'Antidote for organophosphate poisoning is', 'Atropine', year=2022, paper=2)
        self.provisional = _q(*t, 'Drug used to reverse heparin overdose is', 'Protamine sulphate', year=2019)
        self.scholarship = _q(*t, 'Specific antidote for digoxin toxicity is', 'Digoxin immune fab',
                              is_scholarship_eligible=True)
        self.disputed = _q(*t, 'Drug of choice for malignant hyperthermia is', 'Dantrolene', is_disputed=True)
        self.reported = _q(*t, 'Antidote for methanol poisoning is', 'Fomepizole')
        QuestionFeedback.objects.create(question=self.reported, category='wrong_answer', comment='key wrong')
        self.no_key = _q(*t, 'Antidote for iron poisoning is', 'Desferrioxamine', correct_answer='')
        self.neet = _q(*t, 'Drug of choice for absence seizures is', 'Ethosuximide', exam_type='neet_pg', year=2023)
        self.usable = (self.verified, self.repeat_old, self.repeat_new, self.provisional)
        self.excluded = (self.scholarship, self.disputed, self.reported, self.no_key)
        self.admin = _user('notes-admin', role='admin')
        self.free = _user('notes-free')
        self.premium = _user('notes-premium', premium=True)

    def build_note(self, **kw):
        note = TopicNote(title='Antidotes: PYQ notes', content='', subject=self.subject, topic=self.topic,
                         exam_type=kw.pop('exam_type', 'cms'), is_combined=kw.pop('is_combined', False))
        result = nb.build_topic_note(note, evidence=False, **kw)
        self.assertTrue(result.built, result.error)
        return note, result

    def publish(self, note):
        TopicNote.objects.filter(pk=note.pk).update(is_published=True)
        note.refresh_from_db()
        return note

    def point_for(self, structured, question):
        return next(p for p in structured['points'] if question.pk in p['question_ids'])


# ─── key status rules ───────────────────────────────────────────────────────

class KeyStatusTests(_NotesBase):
    def test_reasons(self):
        statuses = ks.key_statuses([*self.usable, *self.excluded])
        got = {q.pk: (statuses[q.pk].status, statuses[q.pk].reason) for q in [*self.usable, *self.excluded]}
        self.assertEqual(got[self.verified.pk], ('verified', 'admin_verified'))
        self.assertEqual(got[self.provisional.pk], ('provisional', 'unverified'))
        self.assertEqual(got[self.scholarship.pk], ('excluded', 'scholarship'))
        self.assertEqual(got[self.disputed.pk], ('excluded', 'disputed'))
        self.assertEqual(got[self.reported.pk], ('excluded', 'open_wrong_answer_report'))
        self.assertEqual(got[self.no_key.pk], ('excluded', 'no_key'))

    def test_provisional_reasons_and_image_rule(self):
        t = (self.subject, self.topic)
        recall = _q(*t, 'Recall stem about nerve agents', 'Pralidoxime', recall_status='recall')
        ai_key = _q(*t, 'Imported stem about opioid overdose', 'Naloxone', source='PYQ_2019_Paper1.txt')
        image = _q(*t, 'Identify the instrument shown', 'Ambu bag', is_image_based=True)
        statuses = ks.key_statuses([recall, ai_key, image])
        self.assertEqual(statuses[recall.pk].reason, 'recall_key')
        self.assertEqual(statuses[ai_key.pk].reason, 'ai_solved_import')
        self.assertEqual((statuses[image.pk].status, statuses[image.pk].reason), ('excluded', 'image_context_missing'))
        QuestionImage.objects.create(question=image, page_number=1, role='primary', url='https://example.test/i.png')
        self.assertTrue(ks.key_statuses([image])[image.pk].usable)

    def test_duplicate_with_another_answer_is_excluded(self):
        twin = _q(self.subject, self.topic, 'Antidote for organophosphate poisoning', 'Pralidoxime',
                  is_active=False)
        cluster = DuplicateCluster.objects.create(canonical_question=self.repeat_new)
        DuplicateMember.objects.create(cluster=cluster, question=twin)
        status = ks.key_statuses([self.repeat_new])[self.repeat_new.pk]
        self.assertEqual((status.status, status.reason), ('excluded', 'duplicate_key_conflict'))

    def test_audit_statuses(self):
        from key_audit.models import QuestionAudit

        def audit(question, status, **kw):
            defaults = dict(status=status, stored_key=question.correct_answer, method_version='test',
                            audited_at=timezone.now())
            defaults.update(kw)
            QuestionAudit.objects.update_or_create(question=question, defaults=defaults)
        audit(self.provisional, 'verified')
        audit(self.repeat_old, 'verified', is_stale=True)
        audit(self.repeat_new, 'needs_review')
        statuses = ks.key_statuses([self.provisional, self.repeat_old, self.repeat_new])
        self.assertEqual(statuses[self.provisional.pk].reason, 'audit_verified')
        self.assertEqual(statuses[self.repeat_old.pk].reason, 'audit_stale')
        self.assertEqual(statuses[self.repeat_new.pk].reason, 'audit_needs_review')
        # An audit made for another key never verifies the current one.
        audit(self.provisional, 'verified', stored_key='B')
        self.assertEqual(ks.key_statuses([self.provisional])[self.provisional.pk].status, 'provisional')


# ─── builder ────────────────────────────────────────────────────────────────

class BuilderTests(_NotesBase):
    def test_points_marks_sources_and_exclusions(self):
        note, result = self.build_note()
        self.assertFalse(note.is_published)
        structured = note.structured
        self.assertEqual(structured['builder_version'], nb.BUILDER_VERSION)
        self.assertEqual(result.counts['cited'], 4)
        self.assertEqual((result.counts['verified'], result.counts['provisional']), (1, 3))

        verified = self.point_for(structured, self.verified)
        self.assertEqual((verified['key_status'], verified['answer']), ('verified', 'Adrenaline'))
        provisional = self.point_for(structured, self.provisional)
        self.assertEqual(provisional['key_status'], 'provisional')
        lines = note.content.splitlines()
        self.assertTrue(any(line.startswith('- Drug of choice for anaphylactic') for line in lines))
        self.assertTrue(any(line.startswith(f'- {nb.MARK} Drug used to reverse heparin') for line in lines))
        self.assertIn(f'{nb.MARK} = answer key not yet verified', note.content)

        repeated = self.point_for(structured, self.repeat_old)
        self.assertEqual(sorted(repeated['question_ids']), sorted([self.repeat_old.pk, self.repeat_new.pk]))
        self.assertEqual(repeated['frequency'], 2)
        self.assertEqual([(s['id'], s['label'], s['key_status']) for s in repeated['sources']],
                         [(self.repeat_new.pk, 'CMS 2022 P2', 'provisional'),
                          (self.repeat_old.pk, 'CMS 2018 P1', 'provisional')])
        self.assertEqual(structured['sections'][0]['title'], 'Most repeated')
        self.assertIn(f'[Q{self.repeat_new.pk}](/practice?id={self.repeat_new.pk})', note.content)

        for question in self.excluded:
            self.assertNotIn(question.option_a, note.content)
            row = TopicNoteSource.objects.get(note=note, question=question)
            self.assertEqual((row.cited, row.key_status), (False, 'excluded'))
        self.assertEqual(TopicNoteSource.objects.get(note=note, question=self.scholarship).reason, 'scholarship')
        self.assertNotIn('Ethosuximide', note.content)   # another exam
        self.assertEqual(set(note.source_question_ids), {q.pk for q in self.usable})

    def test_rebuild_is_a_no_op_until_a_source_changes(self):
        note, _ = self.build_note()
        again = nb.build_topic_note(note, evidence=False)
        self.assertTrue(again.built)
        self.assertFalse(again.changed)
        Question.objects.filter(pk=self.provisional.pk).update(correct_answer='B')
        changed = nb.build_topic_note(note, evidence=False)
        self.assertTrue(changed.changed)
        self.assertIn('Placebo tablet', note.content)

    def test_verified_only_and_provisional_hidden(self):
        note, result = self.build_note(verified_only=True, min_questions=1)
        self.assertEqual(result.counts['cited'], 1)
        self.assertNotIn(nb.MARK + ' Drug', note.content)
        note2 = TopicNote(title='x', content='', subject=self.subject, topic=self.topic, exam_type='cms')
        hidden = nb.build_topic_note(note2, include_provisional=False, evidence=False, dry_run=True)
        self.assertEqual(self.point_for(hidden.structured, self.provisional)['kind'], 'practice')
        self.assertNotIn('Protamine', hidden.markdown)
        self.assertIsNone(note2.pk)   # dry run: nothing saved

    def test_combined_note_covers_every_exam(self):
        note, _ = self.build_note(exam_type='all', is_combined=True)
        self.assertIn('Ethosuximide', note.content)
        self.assertIn('NEET PG 2023', note.content)
        self.assertEqual(note.structured['exam_label'], 'all exams')

    def test_not_enough_usable_pyqs(self):
        note = TopicNote(title='x', content='', subject=self.subject, topic=self.topic, exam_type='neet_pg')
        result = nb.build_topic_note(note, evidence=False)
        self.assertEqual((result.built, result.error), (False, 'not_enough_pyqs'))
        self.assertIsNone(note.pk)

    def test_offline_mode_never_calls_a_model(self):
        with mock.patch.dict(os.environ, {'AI_OFFLINE_MODE': '1'}), mock.patch(CALL_AI) as llm:
            note, result = self.build_note(mode='auto')
        llm.assert_not_called()
        self.assertEqual(result.method, 'extractive')
        self.assertIn('llm_skipped_offline_mode', result.warnings)

    def test_llm_rewrite_is_checked_against_the_facts(self):
        good = ('## Antidotes\n- Atropine treats organophosphate poisoning [F1]\n'
                '- Adrenaline for anaphylactic shock [F2]\n- Protamine reverses heparin [F3]\n')
        with mock.patch.dict(os.environ, {'AI_OFFLINE_MODE': ''}), mock.patch(CALL_AI, return_value=good):
            note, result = self.build_note(mode='llm')
        self.assertEqual(result.method, 'llm')
        self.assertTrue(note.ai_generated)
        for line in note.content.splitlines():
            if 'Protamine' in line or 'Atropine' in line:
                self.assertTrue(line.startswith(f'- {nb.MARK} '), line)   # provisional facts keep the mark
        bad = '- Atropine 2 mg every 5 minutes [F1]\n- An uncited claim\n- Adrenaline [F9]\n'
        with mock.patch.dict(os.environ, {'AI_OFFLINE_MODE': ''}), mock.patch(CALL_AI, return_value=bad):
            note2 = TopicNote(title='y', content='', subject=self.subject, topic=self.topic, exam_type='cms')
            fallback = nb.build_topic_note(note2, mode='llm', evidence=False, dry_run=True)
        self.assertEqual(fallback.method, 'extractive')
        self.assertIn('llm_fallback_extractive', fallback.warnings)

    def test_text_repair_and_answers_that_need_the_statements(self):
        # cp437 readings of UTF-8 punctuation found in imported rows (local copy, 2026-11-04).
        self.assertEqual(nb.repair_cp437_triplets('4 Γ\xe5\xc6 3'), '4 → 3')
        self.assertEqual(nb.repair_cp437_triplets('CHAΓ\xe9\xe9DS'), 'CHA₂DS')
        self.assertEqual(nb.repair_cp437_triplets('Γάμμα'), 'Γάμμα')
        self.assertEqual(nb.clean_answer('4 Γ\xe5\xc6 3 Γ\xe5\xc6 1 Γ\xe5\xc6 2'), '4 → 3 → 1 → 2')
        for answer in ('4 → 3 → 1 → 2', 'B-D-A-C', 'ii > i > iii', '2 -> 1 -> 3'):
            self.assertTrue(nb.is_generic_answer(answer), answer)
        for answer in ('Atropine', 'Beta-blockers', 'T3 > T4 in potency'):
            self.assertFalse(nb.is_generic_answer(answer), answer)
        t = (self.subject, self.topic)
        order = _q(*t, 'Arrange the stages of the family life cycle in order', '4 Γ\xe5\xc6 3 Γ\xe5\xc6 1 Γ\xe5\xc6 2')
        note, _ = self.build_note()
        point = self.point_for(note.structured, order)
        self.assertEqual((point['kind'], point['practice_reason'], point['answer']), ('practice', 'needs_options', ''))

    def test_validate_llm_markdown_rules(self):
        facts = {
            'F1': {'stem': 'Antidote for organophosphate poisoning', 'answer': 'Atropine', 'asked_in': ['CMS 2018 P1'],
                   'key_status': 'provisional', 'question_ids': [11], 'evidence': []},
            'F2': {'stem': 'Drug of choice for anaphylaxis', 'answer': 'Adrenaline', 'asked_in': ['CMS 2021 P1'],
                   'key_status': 'verified', 'question_ids': [12], 'evidence': []},
        }
        text = ('- Atropine for organophosphates [F1]\n- Adrenaline first [F2]\n'
                '- Adrenaline 0.5 mg IM [F2]\n- No citation here\n')
        markdown, stats = nb.validate_llm_markdown(text, facts)
        self.assertIsNone(markdown)   # 2 of 4 bullets survive (< 70 %)
        self.assertEqual(stats, {'bullets': 4, 'kept': 2})
        markdown, _ = nb.validate_llm_markdown('- Atropine for organophosphates [F1]\n- Adrenaline first [F2]\n', facts)
        self.assertEqual(markdown.splitlines(), [f'- {nb.MARK} Atropine for organophosphates [Q11](/practice?id=11)',
                                                 '- Adrenaline first [Q12](/practice?id=12)'])

    def test_textbook_evidence_must_be_a_verbatim_sentence_on_the_page(self):
        page = ('Organophosphate poisoning inhibits acetylcholinesterase. Atropine is the antidote of choice '
                'for organophosphate poisoning and is titrated to drying of secretions.')

        class FakeApi:
            def store_available(self):
                return True

            def search(self, query, **kw):
                return [{'source': {'sha256': 'abc', 'title': 'Pharmacology Textbook', 'edition': '8th', 'tier': 3},
                         'page_start': 41, 'page_end': 41, 'page_label': '37', 'text': page, 'chunk_key': 'c1'}]

            def page_text(self, sha256, page_no):
                return {'text': page}

        note = TopicNote(title='z', content='', subject=self.subject, topic=self.topic, exam_type='cms')
        result = nb.build_topic_note(note, api=FakeApi(), dry_run=True)
        evidence = self.point_for(result.structured, self.repeat_old)['evidence']
        self.assertEqual(len(evidence), 1)
        self.assertTrue(evidence[0]['excerpt'].startswith('Atropine is the antidote of choice'))
        self.assertEqual(evidence[0]['label'], 'Pharmacology Textbook, 8th, p. 37')
        self.assertLessEqual(len(evidence[0]['excerpt']), 240)
        self.assertEqual(result.structured['evidence_state'], 'on')

    def test_a_key_change_hides_the_point_and_marks_the_note_stale(self):
        note, _ = self.build_note()
        nb.on_question_changed(self.provisional)
        note.refresh_from_db()
        self.assertTrue(note.is_stale)
        # A change made outside the API (no hook) is caught when the note is read.
        TopicNote.objects.filter(pk=note.pk).update(is_stale=False)
        Question.objects.filter(pk=self.verified.pk).update(correct_answer='C')
        state = nb.source_state([note.pk])[note.pk]
        self.assertEqual(state['hidden'], {self.verified.pk})
        view = nb.viewer_view(note, full_access=True, free_ids=set(), state=state)
        self.assertEqual(view['hidden_points'], 1)
        self.assertNotIn('Adrenaline', view['content'])

    def test_a_verified_source_that_loses_its_verification_reads_as_provisional(self):
        note, _ = self.build_note()
        Question.objects.filter(pk=self.verified.pk).update(is_verified_by_admin=False)
        state = nb.source_state([note.pk])[note.pk]
        self.assertEqual(state['provisional'], {self.verified.pk})
        view = nb.viewer_view(note, full_access=True, free_ids=set(), state=state)
        point = next(p for p in view['points'] if self.verified.pk in p['question_ids'])
        self.assertEqual(point['key_status'], 'provisional')
        self.assertEqual(point['sources'][0]['key_status'], 'provisional')
        self.assertIn(f'- {nb.MARK} Drug of choice for anaphylactic', view['content'])

    def test_stored_verified_status_without_an_audit_row_stays_verified(self):
        Question.objects.filter(pk=self.provisional.pk).update(answer_key_status='verified')
        self.provisional.refresh_from_db()
        note, result = self.build_note()
        self.assertEqual(self.point_for(note.structured, self.provisional)['key_status'], 'verified')
        self.assertEqual(nb.source_state([note.pk])[note.pk]['provisional'], set())


# ─── admin routes ───────────────────────────────────────────────────────────

@override_settings(TOPIC_NOTES_BUILDER=True)
class BuildRouteTests(_NotesBase):
    BODY = {'exam_type': 'cms', 'level': 'topic'}

    def body(self, **kw):
        return {**self.BODY, 'topic': self.topic.pk, **kw}

    def test_permissions(self):
        self.assertIn(_client().post(BUILD, self.body(), format='json').status_code, (401, 403))
        for user in (self.free, self.premium, _user('notes-staff-only', is_staff=True)):
            self.assertEqual(_client(user).post(BUILD, self.body(), format='json').status_code, 403, user.username)

    @override_settings(TOPIC_NOTES_BUILDER=False)
    def test_switched_off(self):
        res = _client(self.admin).post(BUILD, self.body(), format='json')
        self.assertEqual((res.status_code, res.data['code']), (404, 'feature_disabled'))
        self.assertFalse(TopicNote.objects.exists())
        self.assertFalse(_client(self.admin).get(BUILD).data['enabled'])

    def test_status(self):
        self.assertEqual(_client(self.premium).get(BUILD).status_code, 403)
        with mock.patch.dict(os.environ, {'AI_OFFLINE_MODE': '1'}):
            res = _client(self.admin).get(BUILD)
        self.assertEqual(res.status_code, 200)
        self.assertEqual((res.data['enabled'], res.data['ai_offline'], res.data['builder_version']),
                         (True, True, nb.BUILDER_VERSION))
        self.assertIn(res.data['evidence_state'], ('no_store', 'unavailable', 'on', 'error'))

    def test_build_creates_an_unpublished_draft_then_reports_unchanged(self):
        with mock.patch(CALL_AI) as llm:
            res = _client(self.admin).post(BUILD, self.body(), format='json')
        llm.assert_not_called()
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['totals'], {'create': 1})
        note = TopicNote.objects.get()
        self.assertEqual((note.is_published, note.created_by, note.generation_method), (False, self.admin, 'extractive'))
        self.assertEqual(res.data['notes'][0]['note_id'], note.pk)
        again = _client(self.admin).post(BUILD, self.body(), format='json')
        self.assertEqual(again.data['totals'], {'unchanged': 1})
        forced = _client(self.admin).post(BUILD, self.body(force=True), format='json')
        self.assertEqual(forced.data['totals'], {'update': 1})

    def test_dry_run_of_one_note_previews_and_writes_nothing(self):
        res = _client(self.admin).post(BUILD, self.body(dry_run=True), format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertIn('Adrenaline', res.data['notes'][0]['preview']['markdown'])
        self.assertFalse(TopicNote.objects.exists())

    def test_combined_builds_only_the_cross_exam_note(self):
        res = _client(self.admin).post(BUILD, {'combined': True, 'level': 'topic', 'topic': self.topic.pk},
                                       format='json')
        self.assertEqual(res.status_code, 200, res.data)
        notes = list(TopicNote.objects.values_list('exam_type', 'is_combined'))
        self.assertEqual(notes, [('all', True)])

    def test_bad_requests(self):
        admin = _client(self.admin)
        self.assertEqual(admin.post(BUILD, self.body(exam_type='usmle'), format='json').status_code, 400)
        self.assertEqual(admin.post(BUILD, self.body(level='chapter'), format='json').status_code, 400)
        self.assertEqual(admin.post(BUILD, self.body(mode='poem'), format='json').status_code, 400)
        self.assertEqual(admin.post(BUILD, self.body(min_questions=50), format='json').status_code, 400)

    def test_large_builds_go_to_the_worker(self):
        with mock.patch('questions.views_notes.ASYNC_THRESHOLD', 0), \
                mock.patch('django_q.tasks.async_task', return_value='task-1') as queue:
            res = _client(self.admin).post(BUILD, self.body(), format='json')
        self.assertEqual((res.status_code, res.data['task_id'], res.data['notes']), (202, 'task-1', 1))
        self.assertEqual(queue.call_args.args[0], 'questions.tasks_notes.build_topic_notes_task')
        self.assertEqual(queue.call_args.args[2], self.admin.pk)
        self.assertFalse(TopicNote.objects.exists())

    def test_the_worker_task_builds_the_notes(self):
        from questions.tasks_notes import build_topic_notes_task
        result = build_topic_notes_task({'exams': ('cms',), 'levels': ('topic',), 'topic_id': self.topic.pk},
                                        self.admin.pk)
        self.assertEqual(result['totals'], {'create': 1})
        note = TopicNote.objects.get()
        self.assertEqual((note.created_by, note.is_published), (self.admin, False))
        self.assertEqual(result['notes'][0]['note_id'], note.pk)


@override_settings(TOPIC_NOTES_BUILDER=True)
class SourcesAndLibraryTests(_NotesBase):
    def test_sources_lists_cited_and_excluded_questions(self):
        note, _ = self.build_note()
        url = f'{LIBRARY}{note.pk}/sources/'
        self.assertEqual(_client(self.premium).get(url).status_code, 403)
        res = _client(self.admin).get(url)
        self.assertEqual(res.status_code, 200, res.data)
        rows = {row['question']: row for row in res.data['results']}
        self.assertEqual(res.data['counts'], {'cited': 4, 'not_cited': 4, 'changed_since_build': 0})
        self.assertEqual((rows[self.verified.pk]['key_status'], rows[self.verified.pk]['cited']), ('verified', True))
        self.assertEqual(rows[self.reported.pk]['reason'], 'open_wrong_answer_report')
        self.assertEqual(rows[self.repeat_new.pk]['asked_in'], 'CMS 2022 P2')
        Question.objects.filter(pk=self.verified.pk).update(correct_answer='D')
        res = _client(self.admin).get(url, {'cited': 'true'})
        self.assertTrue(res.data['is_stale'])
        self.assertEqual(len(res.data['results']), 4)
        changed = {row['question']: row['changed_since_build'] for row in res.data['results']}
        self.assertTrue(changed[self.verified.pk])
        self.assertEqual(sum(changed.values()), 1)

    @override_settings(TOPIC_NOTES_BUILDER=False)
    def test_sources_switched_off(self):
        note, _ = self.build_note()
        self.assertEqual(_client(self.admin).get(f'{LIBRARY}{note.pk}/sources/').status_code, 404)

    def test_library_rows_carry_the_build_state(self):
        note, _ = self.build_note()
        res = _client(self.admin).get(f'{LIBRARY}{note.pk}/')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['is_built'])
        self.assertEqual(res.data['generation_method'], 'extractive')
        self.assertEqual(res.data['build_counts']['cited'], 4)
        self.assertEqual(res.data['excluded_reasons']['scholarship'], 1)
        listed = _client(self.admin).get(LIBRARY, {'is_stale': 'false', 'generation_method': 'extractive'})
        self.assertEqual([row['id'] for row in listed.data['results']], [note.pk])

    def test_a_hand_edit_turns_a_built_note_into_a_manual_note(self):
        note, _ = self.build_note()
        self.publish(note)
        res = _client(self.admin).patch(f'{LIBRARY}{note.pk}/', {'title': 'Renamed'}, format='json')
        self.assertTrue(res.data['is_built'])   # a title edit keeps the build
        res = _client(self.admin).patch(f'{LIBRARY}{note.pk}/', {'content': f'- {nb.MARK} Edited text'},
                                        format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual((res.data['is_built'], res.data['generation_method']), (False, 'manual'))
        body = _client(self.premium).get(PUBLISHED).data['results'][0]
        self.assertEqual(body['content'], f'- {nb.MARK} Edited text')
        # The free plan does not get a manual note citing premium PYQs.
        free = _client(self.free).get(PUBLISHED).data['results'][0]
        self.assertEqual((free['content'], free['answers_locked']), ('', True))

    def test_old_generate_endpoints_build_from_pyqs(self):
        note = TopicNote.objects.create(title='Antidotes', content='', subject=self.subject, topic=self.topic,
                                        exam_type='cms')
        admin = _client(self.admin)
        with mock.patch(CALL_AI) as llm:
            first = admin.post(f'/api/questions/topic-notes/{note.pk}/generate/', {}, format='json')
            second = admin.post(f'{LIBRARY}{note.pk}/generate/', {'force': True}, format='json')
        llm.assert_not_called()
        self.assertEqual((first.status_code, second.status_code), (200, 200), (first.data, second.data))
        self.assertEqual(first.data['build']['method'], 'extractive')
        self.assertIn('Adrenaline', first.data['content'])
        self.assertEqual(second.data['note']['id'], note.pk)
        self.assertTrue(second.data['build']['changed'])

    def test_body_lookup_saves_a_new_note_only_when_the_build_succeeds(self):
        empty = Topic.objects.create(name='Empty topic', subject=self.subject)
        admin = _client(self.admin)
        res = admin.post('/api/questions/topic-notes/0/generate/',
                         {'subject': self.subject.pk, 'topic': empty.pk, 'exam_type': 'cms'}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertFalse(TopicNote.objects.exists())
        res = admin.post('/api/questions/topic-notes/0/generate/',
                         {'subject': self.subject.pk, 'topic': self.topic.pk, 'exam_type': 'cms'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(TopicNote.objects.get().created_by, self.admin)
        for exam_type in ('mars', 'all', ['cms']):
            res = admin.post('/api/questions/topic-notes/0/generate/',
                             {'subject': self.subject.pk, 'topic': self.topic.pk, 'exam_type': exam_type}, format='json')
            self.assertEqual(res.status_code, 400, exam_type)


# ─── student read paths ─────────────────────────────────────────────────────

@override_settings(TOPIC_NOTES_BUILDER=True)
class PublishedNoteTests(_NotesBase):
    def setUp(self):
        super().setUp()
        self.note, _ = self.build_note()
        self.publish(self.note)
        # The free showcase: the verified question only.
        FreeShowcaseQuestion.objects.create(question=self.verified, year=2021, position=0)
        self.detail_url = f'{PUBLISHED}{self.note.pk}/'

    def test_anonymous_cannot_read(self):
        for url in (PUBLISHED, self.detail_url, FACETS):
            self.assertIn(_client().get(url).status_code, (401, 403), url)

    def test_premium_reads_every_point_with_its_sources(self):
        res = _client(self.premium).get(self.detail_url)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual((res.data['locked_points'], res.data['hidden_points']), (0, 0))
        self.assertEqual(len(res.data['points']), 3)
        repeated = next(p for p in res.data['points'] if self.repeat_old.pk in p['question_ids'])
        self.assertEqual([s['label'] for s in repeated['sources']], ['CMS 2022 P2', 'CMS 2018 P1'])
        self.assertEqual(repeated['key_status'], 'provisional')
        self.assertEqual(res.data['counts']['points'], 3)
        self.assertNotIn('created_by', res.data)

    def test_free_reads_only_the_points_of_free_questions(self):
        res = _client(self.free).get(self.detail_url)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['locked_points'], 2)
        self.assertTrue(res.data['answers_locked'])
        self.assertEqual([p['question_ids'] for p in res.data['points']], [[self.verified.pk]])
        payload = str(res.data)
        for secret in ('Atropine', 'Protamine', 'organophosphate', 'heparin'):
            self.assertNotIn(secret, payload)
        self.assertIn('2 more points with Premium', res.data['content'])
        self.assertEqual(res.data['source_question_ids'], [self.verified.pk])

    def test_a_scholarship_showcase_question_is_never_free(self):
        FreeShowcaseQuestion.objects.create(question=self.provisional, year=2019, position=1)
        Question.objects.filter(pk=self.provisional.pk).update(is_scholarship_eligible=True)
        res = _client(self.free).get(self.detail_url)
        self.assertNotIn('Protamine', str(res.data))

    def test_the_list_is_filtered_per_viewer(self):
        free = _client(self.free).get(PUBLISHED).data['results'][0]
        self.assertNotIn('Protamine', free['content'])
        self.assertIn('Adrenaline', free['content'])
        self.assertEqual(free['locked_points'], 2)
        premium = _client(self.premium).get(PUBLISHED).data['results'][0]
        self.assertIn('Protamine', premium['content'])
        self.assertNotIn('points', premium)   # the list has no structure, only the rendered note

    def test_unpublished_notes(self):
        TopicNote.objects.filter(pk=self.note.pk).update(is_published=False)
        self.assertEqual(_client(self.premium).get(self.detail_url).status_code, 404)
        self.assertEqual(_client(self.premium).get(PUBLISHED).data['count'], 0)
        self.assertEqual(_client(self.admin).get(self.detail_url).status_code, 200)   # admin preview

    def test_hidden_points_after_a_key_change(self):
        Question.objects.filter(pk=self.provisional.pk).update(correct_answer='C')
        res = _client(self.premium).get(self.detail_url)
        self.assertEqual(res.data['hidden_points'], 1)
        self.assertTrue(res.data['is_stale'])
        self.assertNotIn('Protamine', str(res.data))
        self.assertTrue(TopicNote.objects.get(pk=self.note.pk).is_stale)

    def test_manual_notes(self):
        free_manual = TopicNote.objects.create(title='Free manual', content='Open note', subject=self.subject,
                                               exam_type='cms', is_published=True)
        locked_manual = TopicNote.objects.create(title='Premium manual', content='Atropine secrets',
                                                 subject=self.subject, exam_type='cms', is_published=True,
                                                 source_question_ids=[self.repeat_old.pk])
        rows = {row['id']: row for row in _client(self.free).get(PUBLISHED).data['results']}
        self.assertEqual(rows[free_manual.pk]['content'], 'Open note')
        self.assertEqual((rows[locked_manual.pk]['content'], rows[locked_manual.pk]['content_preview']), ('', ''))
        self.assertTrue(rows[locked_manual.pk]['answers_locked'])
        detail = _client(self.free).get(f'{PUBLISHED}{locked_manual.pk}/')
        self.assertEqual((detail.data['content'], detail.data['points']), ('', None))

    def test_list_filters(self):
        combined, _ = self.build_note(exam_type='all', is_combined=True)
        self.publish(combined)
        neet_only = TopicNote.objects.create(title='NEET manual', content='n', exam_type='neet_pg', is_published=True)
        client = _client(self.premium)

        def ids(**params):
            return {row['id'] for row in client.get(PUBLISHED, params).data['results']}
        self.assertEqual(ids(exam_type='cms'), {self.note.pk, combined.pk})
        self.assertEqual(ids(exam_type='neet_pg'), {neet_only.pk, combined.pk})
        self.assertEqual(ids(exam_type='all'), {combined.pk})
        self.assertEqual(ids(id=self.note.pk), {self.note.pk})
        self.assertEqual(ids(topic=self.topic.pk, exam_type='cms'), {self.note.pk, combined.pk})
        self.assertEqual(ids(q='NEET manual'), {neet_only.pk})
        self.assertEqual(ids(q='Atropine'), set())   # never a search over the content
        self.assertEqual(ids(subject='junk'), set())

    def test_facets(self):
        combined, _ = self.build_note(exam_type='all', is_combined=True)
        self.publish(combined)
        TopicNote.objects.create(title='Draft', content='d', exam_type='neet_pg', subject=self.subject)
        res = _client(self.free).get(FACETS)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['exams'], [{'value': 'cms', 'count': 1}, {'value': 'all', 'count': 1}])
        self.assertEqual(res.data['total'], 2)
        subject = res.data['subjects'][0]
        self.assertEqual((subject['id'], subject['count']), (self.subject.pk, 2))
        self.assertEqual(subject['topics'], [{'id': self.topic.pk, 'name': self.topic.name, 'count': 2}])
        self.assertEqual(_client(self.free).get(FACETS, {'exam_type': 'neet_pg'}).data['total'], 1)
        self.assertNotIn('Adrenaline', str(res.data))

    @override_settings(TOPIC_NOTES_BUILDER=False)
    def test_switched_off_the_list_still_serves_the_filtered_note(self):
        self.assertEqual(_client(self.premium).get(self.detail_url).data['code'], 'feature_disabled')
        rows = _client(self.free).get(PUBLISHED, {'id': self.note.pk}).data['results']
        self.assertEqual(len(rows), 1)
        self.assertNotIn('Protamine', rows[0]['content'])
        self.assertEqual(_client(self.free).get(FACETS).status_code, 200)
