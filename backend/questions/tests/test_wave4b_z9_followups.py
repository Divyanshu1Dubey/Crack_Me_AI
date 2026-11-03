"""Wave 4 Z9 follow-ups of the security / performance pass.

REVEAL    The per-question ai/* GETs (the practice reveal panel) never call an
          LLM in the request thread any more: they serve stored / cached text
          and, on a miss, queue ONE django-q task per question (single-flight
          lock, charged once to the caller's hourly budget) and answer 202
          ``{<field>: null, "pending": true}``. The task writes every missing
          section with one LLM call, into empty fields only.
PREMIUM   ``attempt`` responses report premium entitlement (Subscription rows),
          not the legacy ``CustomUser.is_subscribed`` flag.
DISPLAY   The loader's "Imported" subject is "Expert Curated" in every
          student-facing questions payload (stats by_subject, topics,
          flashcards, duplicates, study time, mistakes, topic notes).
HANDLE    Discussion authors (and the verifying admin / topic-note author)
          appear by a chosen username only, never one derived from their
          email address (crack_cms.public_names.public_handle).

No AI provider and no queue is reached: ``_ai_call`` and ``async_task`` are
patched wherever they could run.
"""
from __future__ import annotations

import json
import os
from datetime import timedelta
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Subscription
from accounts.models_freemium import FreeShowcaseQuestion
from questions import ai_per_question as ai
from questions.models import (
    Discussion, Flashcard, MistakeNotebook, Question, StudyTimeBreakdown, Subject, Topic, TopicNote,
)

User = get_user_model()

QUEUE = 'django_q.tasks.async_task'
SECTIONS = ('why_correct', 'clinical', 'mnemonic', 'concept')
FIELD = {'why_correct': 'why_correct', 'clinical': 'clinical_significance',
         'mnemonic': 'memory_trick', 'concept': 'concept'}
GENERATED = {
    'concept': 'Gamma physiology',
    'why_correct': 'Gamma is right because of the stem.',
    'clinical_significance': 'Gamma matters at the bedside.',
    'memory_trick': 'G for gamma',
}


def _question(subject, i, **kw):
    defaults = dict(
        question_text=f'Z9 follow-up stem {i}', option_a='alpha', option_b='beta',
        option_c='gamma', option_d='delta', correct_answer='C', year=2024, subject=subject,
        explanation=f'Gamma is right ({i}).',
    )
    defaults.update(kw)
    return Question.objects.create(**defaults)


def _premium(username, **kw):
    user = User.objects.create_user(username=username, email=f'{username}@example.com',
                                    password='unused-pw-1', **kw)
    Subscription.objects.create(user=user, plan='1_year', status='active',
                                expires_at=timezone.now() + timedelta(days=365))
    return user


def _client(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user)
    return client


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='Z9 Follow-up Medicine', code='Z9FMED')
        cls.premium = _premium('z9f-premium')
        cls.free = User.objects.create_user(username='z9f-free', email='z9f-free@example.com',
                                            password='unused-pw-2')
        cls.admin = User.objects.create_user(username='z9f-admin', email='z9f-admin@example.com',
                                             password='unused-pw-3', role='admin')

    def setUp(self):
        cache.clear()


# ── REVEAL: GETs never generate; one queued task per question ─────────────

class RevealGetsNeverCallAnLLMTests(_Base):
    def test_a_miss_queues_one_generation_and_the_request_never_calls_a_provider(self):
        q = _question(self.subject, 1)
        api = _client(self.premium)
        with mock.patch.object(ai, '_ai_call') as llm, \
                mock.patch('ai_engine.services.AIService._call_ai') as rotation, \
                mock.patch(QUEUE) as queue:
            responses = {path: api.get(f'/api/questions/{q.id}/ai/{path}/') for path in SECTIONS}
        llm.assert_not_called()
        rotation.assert_not_called()
        # concept is cache-only, so with the tests' process-local cache it is
        # not generated in the background (the worker could not hand it over).
        for path in ('why_correct', 'clinical', 'mnemonic'):
            self.assertEqual(responses[path].status_code, 202, path)
            self.assertEqual(responses[path].data, {FIELD[path]: None, 'pending': True}, path)
        self.assertEqual(responses['concept'].status_code, 200)
        self.assertEqual(responses['concept'].data, {'concept': None})
        # Single flight: four section GETs, one task.
        queue.assert_called_once_with(ai.GENERATION_TASK, q.id, timeout=ai.GENERATION_TASK_TIMEOUT)

    @override_settings(AI_PER_QUESTION_HOURLY_LIMIT=1)
    def test_the_budget_is_charged_once_per_queued_question(self):
        q1 = _question(self.subject, 2)
        q2 = _question(self.subject, 3)
        api = _client(self.premium)
        with mock.patch(QUEUE) as queue:
            for path in SECTIONS:
                res = api.get(f'/api/questions/{q1.id}/ai/{path}/')
                self.assertNotIn('rate_limited', res.data, path)
            res = api.get(f'/api/questions/{q2.id}/ai/why_correct/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data, {'why_correct': None, 'rate_limited': True})
        self.assertEqual(queue.call_count, 1)

    @override_settings(AI_PER_QUESTION_HOURLY_LIMIT=0)
    def test_staff_are_not_budgeted(self):
        q = _question(self.subject, 4)
        with mock.patch(QUEUE) as queue:
            res = _client(self.admin).get(f'/api/questions/{q.id}/ai/clinical/')
        self.assertEqual(res.status_code, 202)
        queue.assert_called_once()

    def test_anonymous_and_locked_callers_never_queue(self):
        showcase = _question(self.subject, 5)
        FreeShowcaseQuestion.objects.create(question=showcase, year=2024, position=1)
        locked = _question(self.subject, 6)
        with mock.patch(QUEUE) as queue:
            anon = _client().get(f'/api/questions/{showcase.id}/ai/why_correct/')
            free_locked = _client(self.free).get(f'/api/questions/{locked.id}/ai/why_correct/')
            free_showcase = _client(self.free).get(f'/api/questions/{showcase.id}/ai/mnemonic/')
        self.assertEqual((anon.status_code, anon.data), (200, {'why_correct': None}))
        self.assertEqual(free_locked.data, {'why_correct': None, 'locked': True})
        # An entitled free account (showcase question) may queue, as before.
        self.assertEqual(free_showcase.status_code, 202)
        queue.assert_called_once_with(ai.GENERATION_TASK, showcase.id, timeout=ai.GENERATION_TASK_TIMEOUT)

    def test_stored_content_is_served_without_queueing(self):
        q = _question(self.subject, 7, ai_answer='Stored why', ai_clinical_pearl='Stored pearl',
                      mnemonic='Stored trick')
        api = _client(self.premium)
        with mock.patch(QUEUE) as queue:
            why = api.get(f'/api/questions/{q.id}/ai/why_correct/')
            pearl = api.get(f'/api/questions/{q.id}/ai/clinical/')
            trick = api.get(f'/api/questions/{q.id}/ai/mnemonic/')
        self.assertEqual((why.status_code, why.data), (200, {'why_correct': 'Stored why'}))
        self.assertEqual(pearl.data, {'clinical_significance': 'Stored pearl'})
        self.assertEqual(trick.data, {'memory_trick': 'Stored trick'})
        queue.assert_not_called()

    def test_why_incorrect_is_never_generated(self):
        q = _question(self.subject, 8)
        with mock.patch(QUEUE) as queue:
            res = _client(self.premium).get(f'/api/questions/{q.id}/ai/why_incorrect/')
        self.assertEqual((res.status_code, res.data), (200, {'why_incorrect': None}))
        queue.assert_not_called()

    def test_offline_mode_queues_nothing(self):
        q = _question(self.subject, 9)
        with mock.patch.dict(os.environ, {'AI_OFFLINE_MODE': '1'}), mock.patch(QUEUE) as queue:
            res = _client(self.premium).get(f'/api/questions/{q.id}/ai/why_correct/')
        self.assertEqual((res.status_code, res.data), (200, {'why_correct': None}))
        queue.assert_not_called()

    def test_a_queue_failure_releases_the_lock(self):
        q = _question(self.subject, 10)
        api = _client(self.premium)
        with mock.patch(QUEUE, side_effect=RuntimeError('broker down')):
            res = api.get(f'/api/questions/{q.id}/ai/why_correct/')
        self.assertEqual((res.status_code, res.data), (200, {'why_correct': None}))
        with mock.patch(QUEUE) as queue:
            res = api.get(f'/api/questions/{q.id}/ai/why_correct/')
        self.assertEqual(res.status_code, 202)
        queue.assert_called_once()

    def test_the_real_queue_takes_the_task(self):
        """Without the patch the task lands in the django-q ORM broker (the
        worker's queue); nothing runs in the request."""
        from django_q.models import OrmQ

        q = _question(self.subject, 11)
        with mock.patch.object(ai, '_ai_call') as llm:
            res = _client(self.premium).get(f'/api/questions/{q.id}/ai/why_correct/')
        self.assertEqual(res.status_code, 202)
        llm.assert_not_called()
        self.assertEqual(OrmQ.objects.count(), 1)
        task = OrmQ.objects.get().task
        self.assertEqual((task['func'], task['args']), (ai.GENERATION_TASK, (q.id,)))


# ── REVEAL: the background task ─────────────────────────────────────────────

class BackgroundGenerationTests(_Base):
    def _run(self, q, reply):
        from questions.tasks import generate_reveal_sections_task

        with mock.patch.object(ai, '_ai_call', return_value=reply) as llm:
            written = generate_reveal_sections_task(q.id)
        return written, llm

    def test_one_llm_call_fills_every_missing_section(self):
        q = _question(self.subject, 20)
        with mock.patch.object(ai, '_cache_is_shared', return_value=True):
            written, llm = self._run(q, json.dumps(GENERATED))
            self.assertEqual(llm.call_count, 1)
            self.assertEqual(sorted(written), sorted(GENERATED))
            q.refresh_from_db()
            self.assertEqual(q.ai_answer, GENERATED['why_correct'])
            self.assertEqual(q.ai_clinical_pearl, GENERATED['clinical_significance'])
            self.assertEqual(q.ai_mnemonic, GENERATED['memory_trick'])
            # The panel now reads every section, with no new queueing.
            api = _client(self.premium)
            with mock.patch(QUEUE) as queue:
                for path in SECTIONS:
                    res = api.get(f'/api/questions/{q.id}/ai/{path}/')
                    self.assertEqual(res.status_code, 200, path)
                    self.assertEqual(res.data[FIELD[path]], GENERATED[FIELD[path]], path)
            queue.assert_not_called()

    def test_only_missing_sections_are_asked_for_and_curated_content_stays(self):
        q = _question(self.subject, 21, ai_clinical_pearl='Curated pearl', mnemonic='Curated trick')
        written, llm = self._run(q, json.dumps(GENERATED))
        self.assertEqual(written, ['why_correct'])
        prompt = llm.call_args.args[0]
        self.assertIn('"why_correct"', prompt)
        for absent in ('"clinical_significance"', '"memory_trick"', '"concept"'):
            self.assertNotIn(absent, prompt)
        q.refresh_from_db()
        self.assertEqual(q.ai_clinical_pearl, 'Curated pearl')
        self.assertEqual(q.ai_mnemonic, '')  # the curated mnemonic answers that section

    def test_a_failed_generation_writes_nothing_and_is_not_requeued_at_once(self):
        q = _question(self.subject, 22)
        for reply in ('', 'Sorry, here is some prose instead of JSON.'):
            cache.clear()
            written, llm = self._run(q, reply)
            self.assertEqual(written, [])
            self.assertEqual(llm.call_count, 1)
            q.refresh_from_db()
            self.assertEqual((q.ai_answer, q.ai_clinical_pearl, q.ai_mnemonic), ('', '', ''))
            with mock.patch(QUEUE) as queue:
                res = _client(self.premium).get(f'/api/questions/{q.id}/ai/why_correct/')
            self.assertEqual((res.status_code, res.data), (200, {'why_correct': None}))
            queue.assert_not_called()
            # ... and a second run in the failure window makes no LLM call.
            written, llm = self._run(q, json.dumps(GENERATED))
            self.assertEqual(written, [])
            llm.assert_not_called()

    def test_the_task_releases_the_single_flight_lock(self):
        q = _question(self.subject, 23)
        cache.set(ai._k(q.id, 'generation'), 1, ai.GENERATION_LOCK_TTL)
        self._run(q, json.dumps(GENERATED))
        self.assertIsNone(cache.get(ai._k(q.id, 'generation')))

    def test_inactive_questions_and_offline_mode_make_no_call(self):
        q = _question(self.subject, 24, is_active=False)
        written, llm = self._run(q, json.dumps(GENERATED))
        self.assertEqual(written, [])
        llm.assert_not_called()
        q2 = _question(self.subject, 25)
        with mock.patch.dict(os.environ, {'AI_OFFLINE_MODE': '1'}):
            written, llm = self._run(q2, json.dumps(GENERATED))
        self.assertEqual(written, [])
        llm.assert_not_called()

    def test_outage_text_in_a_section_is_never_stored(self):
        q = _question(self.subject, 26)
        reply = dict(GENERATED, why_correct='All AI services are temporarily unavailable. Please try again.')
        written, _ = self._run(q, json.dumps(reply))
        self.assertNotIn('why_correct', written)
        q.refresh_from_db()
        self.assertEqual(q.ai_answer, '')

    def test_concept_is_only_generated_with_a_shared_cache(self):
        q = _question(self.subject, 27, ai_answer='a', ai_clinical_pearl='b', mnemonic='c')
        self.assertEqual(ai.missing_sections(q), [])
        with mock.patch.object(ai, '_cache_is_shared', return_value=True):
            self.assertEqual(ai.missing_sections(q), ['concept'])

    def test_locmem_is_not_a_shared_cache(self):
        self.assertFalse(ai._cache_is_shared())
        with override_settings(CACHES={'default': {'BACKEND': 'django_redis.cache.RedisCache',
                                                   'LOCATION': 'redis://localhost:6379/0'}}):
            self.assertTrue(ai._cache_is_shared())


# ── PREMIUM: the attempt response's is_subscribed ─────────────────────────

class AttemptPremiumFlagTests(_Base):
    def test_attempt_reports_premium_not_the_legacy_flag(self):
        q = _question(self.subject, 30)
        FreeShowcaseQuestion.objects.create(question=q, year=2024, position=1)
        flagged = User.objects.create_user(username='z9f-flagged', email='z9f-flagged@example.com',
                                           password='unused-pw-4', is_subscribed=True)
        for user, expected in ((flagged, False), (self.free, False), (self.premium, True), (self.admin, True)):
            res = _client(user).post(f'/api/questions/{q.id}/attempt/', {'selected_answer': 'C'}, format='json')
            self.assertEqual(res.status_code, 200, (user.username, res.data))
            self.assertIs(res.data['is_subscribed'], expected, user.username)
        unkeyed = _question(self.subject, 31, correct_answer='')
        FreeShowcaseQuestion.objects.create(question=unkeyed, year=2024, position=2)
        res = _client(flagged).post(f'/api/questions/{unkeyed.id}/attempt/', {'selected_answer': 'C'}, format='json')
        self.assertIsNone(res.data['is_correct'])
        self.assertIs(res.data['is_subscribed'], False)


# ── DISPLAY: "Imported" is "Expert Curated" ───────────────────────────────

class ExpertCuratedLabelTests(_Base):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.imported = Subject.objects.create(name='Imported', code='IMPORTED', exam_type='neet_pg')
        cls.topic = Topic.objects.create(subject=cls.imported, name='Z9 loader topic')

    def test_public_subject_name(self):
        from questions.serializers import public_subject_name

        for name in ('Imported', 'imported', ' Imported '):
            self.assertEqual(public_subject_name(name), 'Expert Curated')
        for name in ('Medicine', 'Imported Drugs', '', None):
            self.assertEqual(public_subject_name(name), name)

    def test_stats_by_subject(self):
        _question(self.imported, 40, exam_source='NEET PG')
        res = _client().get('/api/questions/stats/', {'exam_source': 'NEET PG'})
        names = [row['name'] for row in res.data['by_subject']]
        self.assertIn('Expert Curated', names)
        self.assertNotIn('Imported', names)

    def test_topics_list(self):
        rows = _client().get('/api/questions/topics/', {'subject': self.imported.id}).data
        rows = rows['results'] if isinstance(rows, dict) else rows
        self.assertEqual({row['subject_name'] for row in rows}, {'Expert Curated'})

    def test_flashcards_and_duplicates(self):
        q = _question(self.imported, 41)
        Flashcard.objects.create(user=self.premium, question=q, subject=self.imported, front='f', back='b')
        rows = _client(self.premium).get('/api/questions/flashcards/').data
        rows = rows['results'] if isinstance(rows, dict) else rows
        self.assertEqual([row['subject_name'] for row in rows], ['Expert Curated'])
        twin = _question(self.imported, 41)  # same stem, year and source: a live duplicate
        res = _client(self.premium).get(f'/api/questions/{q.id}/duplicates/')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual({m['id'] for m in res.data['members']}, {q.id, twin.id})
        self.assertEqual({m['subject_name'] for m in res.data['members']}, {'Expert Curated'})
        self.assertNotIn('Imported', json.dumps(res.data))

    def test_student_serializers(self):
        from questions.serializers import (
            MistakeNotebookSerializer, StudyTimeBreakdownSerializer, TopicNoteListSerializer,
            TopicNoteSerializer,
        )

        q = _question(self.imported, 42)
        mistake = MistakeNotebook.objects.create(user=self.premium, question=q, selected_answer='A',
                                                 correct_answer='C', is_correct=False)
        study = StudyTimeBreakdown.objects.create(user=self.premium, subject=self.imported,
                                                  date=timezone.localdate(), seconds=60)
        note = TopicNote.objects.create(subject=self.imported, topic=self.topic, title='T', content='c')
        for serializer in (MistakeNotebookSerializer(mistake), StudyTimeBreakdownSerializer(study),
                           TopicNoteSerializer(note), TopicNoteListSerializer(note)):
            self.assertEqual(serializer.data['subject_name'], 'Expert Curated', type(serializer).__name__)

    def test_admin_extraction_items_keep_the_real_name(self):
        from questions.serializers import PublicSubjectNameField, QuestionExtractionItemSerializer

        self.assertNotIsInstance(QuestionExtractionItemSerializer().fields['subject_name'],
                                 PublicSubjectNameField)

    def test_topic_note_generation_prompts_carry_the_public_label(self):
        """Generated notes are published to students: the prompts name the
        subject "Expert Curated" and the topic by its name (str(topic) is
        "IMPORTED → <name>")."""
        _question(self.imported, 43, topic=self.topic, exam_type='neet_pg', explanation='Gamma explained.')
        note = TopicNote.objects.create(subject=self.imported, topic=self.topic, title='T', content='c',
                                        exam_type='neet_pg')
        admin = _client(self.admin)
        with mock.patch('ai_engine.services.AIService._call_ai', return_value='Generated topic note body.') as llm:
            first = admin.post(f'/api/questions/topic-notes/{note.id}/generate/', {}, format='json')
            second = admin.post(f'/api/questions/topic-notes/library/{note.id}/generate/', {}, format='json')
        self.assertEqual((first.status_code, second.status_code), (200, 200), (first.data, second.data))
        prompts = [call.args[0] for call in llm.call_args_list]
        self.assertEqual(len(prompts), 2)
        self.assertIn('(Subject: Expert Curated)', prompts[0])
        self.assertIn('"Z9 loader topic"', prompts[1])
        for prompt in prompts:
            self.assertNotIn('Imported', prompt)
            self.assertNotIn('IMPORTED', prompt)


# ── Dashboard v3 cache after a bank answer ─────────────────────────────────

class DashboardV3InvalidationTests(_Base):
    def test_a_bank_answer_refreshes_the_dashboard_v3_cache(self):
        q = _question(self.subject, 60)
        with mock.patch('analytics.dashboard_v3.invalidate_user_cache') as invalidate:
            res = _client(self.premium).post(f'/api/questions/{q.id}/attempt/', {'selected_answer': 'C'},
                                             format='json')
        self.assertEqual(res.status_code, 200, res.data)
        invalidate.assert_called_with(self.premium.id)

    def test_the_helper_drops_only_that_users_dashboard_v3_results(self):
        from analytics import dashboard_v3
        from questions.views import _invalidate_user_question_caches

        mine = [dashboard_v3._cache_key(self.premium.id, name) for name in dashboard_v3.CACHED_RESULTS]
        theirs = [dashboard_v3._cache_key(self.free.id, name) for name in dashboard_v3.CACHED_RESULTS]
        cache.set_many({key: {'stale': True} for key in mine + theirs}, 60)
        _invalidate_user_question_caches(self.premium.id)
        self.assertEqual(cache.get_many(mine), {})
        self.assertEqual(len(cache.get_many(theirs)), len(theirs))


# ── HANDLE: no email-derived names ─────────────────────────────────────────

class PublicHandleTests(SimpleTestCase):
    CASES = [
        ('rahul.k', 'Rahul.K@gmail.com'), ('RAHUL.K_2', 'rahul.k@gmail.com'),
        ('a' * 140, f'{"a" * 150}@example.com'), ('a' * 130 + '_3', f'{"a" * 150}@example.com'),
        ('someone@else.org', 'rahul@gmail.com'), ('cardio_queen', 'rahul@gmail.com'),
        ('rahul', ''), ('', 'x@y.z'), ('learner_1a2b3c4d', 'rahul@gmail.com'), ('rahul_x', 'rahul@gmail.com'),
    ]

    def test_rule(self):
        from crack_cms.public_names import public_handle

        self.assertIsNone(public_handle(SimpleNamespace(username='rahul.k', email='Rahul.K@gmail.com')))
        self.assertIsNone(public_handle(SimpleNamespace(username='x@y.z', email='')))
        self.assertIsNone(public_handle(None))
        self.assertEqual(public_handle(SimpleNamespace(username='cardio_queen', email='rahul@gmail.com')),
                         'cardio_queen')

    def test_same_rule_as_the_leaderboard_and_the_handle_module(self):
        from analytics.views import _public_name
        from crack_cms.public_names import public_handle

        try:
            from accounts.handles import exposes_email
        except ImportError:  # pragma: no cover - module of another group
            exposes_email = None
        for username, email in self.CASES:
            user = SimpleNamespace(username=username, email=email)
            with self.subTest(username=username, email=email):
                self.assertEqual(public_handle(user), _public_name(user))
                if exposes_email is not None and username.strip():
                    self.assertEqual(public_handle(user) is None, exposes_email(username, email))


class DiscussionAuthorNameTests(_Base):
    def test_email_derived_author_names_are_null(self):
        q = _question(self.subject, 50)
        derived = User.objects.create_user(username='rahul.k', email='Rahul.K@gmail.com', password='unused-pw-5')
        Subscription.objects.create(user=derived, plan='1_year', status='active',
                                    expires_at=timezone.now() + timedelta(days=365))
        chosen = User.objects.create_user(username='cardio_queen', email='priya.s@gmail.com', password='unused-pw-7')
        Discussion.objects.create(question=q, user=derived, text='C, because gamma.')
        Discussion.objects.create(question=q, user=chosen, text='Agreed.')
        rows = _client(self.premium).get('/api/questions/discussions/', {'question': q.id}).data
        rows = rows['results'] if isinstance(rows, dict) else rows
        names = {row['text']: row['username'] for row in rows}
        self.assertEqual(names, {'C, because gamma.': None, 'Agreed.': 'cardio_queen'})
        self.assertNotIn('rahul', json.dumps(rows).lower())
        # The author's own create response follows the same rule.
        res = _client(derived).post('/api/questions/discussions/', {'question': q.id, 'text': 'Me again'},
                                    format='json')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertIsNone(res.data['username'])

    def test_verifying_admin_and_note_author_names(self):
        from questions.serializers import QuestionListSerializer, TopicNoteSerializer

        admin = User.objects.create_user(username='divya.admin', email='divya.admin@gmail.com',
                                         password='unused-pw-6', role='admin')
        q = _question(self.subject, 51, is_verified_by_admin=True, verified_by=admin)
        self.assertEqual(QuestionListSerializer(q).data['verified_by_username'], '')
        self.assertEqual(QuestionListSerializer(_question(self.subject, 52)).data['verified_by_username'], '')
        q.verified_by = User.objects.create_user(username='qa_lead', email='divya.admin2@gmail.com',
                                                 password='unused-pw-8', role='admin')
        self.assertEqual(QuestionListSerializer(q).data['verified_by_username'], 'qa_lead')
        topic = Topic.objects.create(subject=self.subject, name='Z9 note topic')
        note = TopicNote.objects.create(subject=self.subject, topic=topic, title='T', content='c', created_by=admin)
        self.assertEqual(TopicNoteSerializer(note).data['created_by_username'], '')
