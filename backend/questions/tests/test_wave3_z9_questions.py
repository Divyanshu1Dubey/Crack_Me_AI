"""Wave-3 Z9 (questions app): the entitlement rule on every list / detail
field and in recall search, ungradable answers, answer time in topic
performance, the explanation_overridden flag, AI generation retries and
cache keys, generate-explanation / force-regenerate verification and undo,
stats rows (INI-CET labels), ordering and the fixture loader on a fresh
database.

No AI provider, Supabase or network call is made: every AI entry point is
patched.
"""
from __future__ import annotations

import json
import tempfile
from datetime import timedelta
from io import StringIO
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.request import Request
from rest_framework.test import APIClient, APIRequestFactory

from accounts.models import Subscription
from accounts.models_freemium import FreeShowcaseQuestion
from questions.models import (
    AdminAIPromptVersion, MistakeNotebook, Question, QuestionAIOperationLog, QuestionAttempt,
    QuestionImage, QuestionRevisionSnapshot, StudyTimeBreakdown, Subject, Topic,
)

User = get_user_model()


def _question(subject, i, **kw):
    defaults = dict(
        question_text=f'Z9 wave3 stem {i}', option_a='alpha', option_b='beta', option_c='gamma',
        option_d='delta', correct_answer='C', year=2024, subject=subject,
        explanation=f'Gamma is right ({i}).',
    )
    defaults.update(kw)
    return Question.objects.create(**defaults)


def _premium(username):
    user = User.objects.create_user(username=username, email=f'{username}@example.com', password='unused-pw-1')
    Subscription.objects.create(user=user, plan='1_year', status='active',
                                expires_at=timezone.now() + timedelta(days=365))
    return user


def _client(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user)
    return client


REFERENCE = dict(
    reference_text='Gamma deficiency is the textbook cause.',
    textbook_references=[{'book': 'Harrison', 'chapter': 'Gamma disease', 'excerpt': 'gamma ...'}],
    book_name='Harrison', chapter='Gamma disease', page_number='42',
    concept_tags=['high_yield', 'ventricular aneurysm'],
)


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='Z9 Wave3 Subject', code='Z9W3')
        cls.topic = Topic.objects.create(name='Z9 topic', subject=cls.subject)
        cls.free = User.objects.create_user(username='z9w3-free', email='z9w3-free@example.com', password='unused-pw-2')
        cls.premium = _premium('z9w3-premium')
        cls.admin = User.objects.create_user(username='z9w3-admin', password='unused-pw-3', role='admin')

    def setUp(self):
        cache.clear()


# ── Entitlement: list / detail fields ──────────────────────────────────────

class LockedRowFieldTests(_Base):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.locked = _question(cls.subject, 1, **REFERENCE)
        cls.showcase = _question(cls.subject, 2, **REFERENCE)
        FreeShowcaseQuestion.objects.create(question=cls.showcase, year=2024, position=0)
        for q in (cls.locked, cls.showcase):
            QuestionImage.objects.create(question=q, page_number=0, role='explanation',
                                         url=f'/media/expl-{q.pk}.png')
            QuestionImage.objects.create(question=q, page_number=0, role='stem', url=f'/media/stem-{q.pk}.png')

    def _row(self, user, question, **params):
        res = _client(user).get('/api/questions/', {'question_id': question.id, **params})
        self.assertEqual(res.status_code, 200, res.data)
        rows = res.data['results']
        return rows[0] if rows else None

    def test_locked_row_hides_references_tags_and_explanation_images(self):
        row = self._row(self.free, self.locked)
        self.assertEqual((row['reference_text'], row['book_name'], row['chapter'], row['page_number']),
                         ('', '', '', ''))
        self.assertEqual(row['textbook_references'], [])
        self.assertEqual(row['concept_tags'], ['high_yield'])   # the badge marker survives
        self.assertEqual({img['role'] for img in row['images']}, {'stem'})
        anon = self._row(None, self.locked)
        self.assertEqual(anon['reference_text'], '')
        self.assertEqual(anon['concept_tags'], ['high_yield'])

    def test_showcase_premium_and_admin_rows_are_unchanged(self):
        for user, question in ((self.free, self.showcase), (self.premium, self.locked), (self.admin, self.locked)):
            row = self._row(user, question)
            self.assertEqual(row['reference_text'], REFERENCE['reference_text'], user)
            self.assertEqual(row['chapter'], 'Gamma disease', user)
            self.assertEqual(row['textbook_references'], REFERENCE['textbook_references'], user)
            self.assertEqual(row['concept_tags'], REFERENCE['concept_tags'], user)
            self.assertEqual({img['role'] for img in row['images']}, {'stem', 'explanation'}, user)

    def test_own_verdict_on_a_locked_row_is_hidden_and_not_filterable(self):
        QuestionAttempt.objects.create(user=self.free, question=self.locked, selected_answer='C', is_correct=True)
        QuestionAttempt.objects.create(user=self.free, question=self.showcase, selected_answer='C', is_correct=True)
        row = self._row(self.free, self.locked)
        # No verdict, and no bare pick either (cards render a pick without a
        # verdict as "Incorrect").
        self.assertIsNone(row['user_selected_answer'])
        self.assertIsNone(row['user_is_correct'])
        self.assertIsNone(self._row(self.free, self.locked, incorrect='false'))
        self.assertIsNotNone(self._row(self.free, self.locked, attempted='true'))
        self.assertIs(self._row(self.free, self.showcase)['user_is_correct'], True)
        self.assertEqual(self._row(self.free, self.showcase)['user_selected_answer'], 'C')
        self.assertIsNotNone(self._row(self.free, self.showcase, incorrect='false'))
        # A subscriber keeps the verdict and the filter.
        QuestionAttempt.objects.create(user=self.premium, question=self.locked, selected_answer='C', is_correct=True)
        self.assertIs(self._row(self.premium, self.locked, incorrect='false')['user_is_correct'], True)

    def test_concept_tags_are_not_a_search_oracle_for_locked_rows(self):
        ids = lambda user: {r['id'] for r in _client(user).get('/api/questions/', {'search': 'ventricular'}).data['results']}  # noqa: E731
        self.assertNotIn(self.locked.id, ids(self.free))
        self.assertNotIn(self.locked.id, ids(None))
        self.assertIn(self.locked.id, ids(self.premium))

    def test_anonymous_detail_redacts_reference_fields(self):
        data = _client().get(f'/api/questions/{self.locked.id}/').data
        self.assertTrue(data['answer_locked'])
        for key in ('reference_text', 'textbook_references', 'book_name', 'chapter', 'page_number'):
            self.assertIsNone(data[key], key)
        self.assertEqual(data['concept_tags'], ['high_yield'])
        shown = _client().get(f'/api/questions/{self.showcase.id}/').data
        self.assertEqual(shown['reference_text'], REFERENCE['reference_text'])
        self.assertNotIn('answer_locked', shown)


class ScholarshipQuestionTests(_Base):
    """is_scholarship_eligible questions are never free content, even when an
    admin also put them in the showcase."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.challenge = _question(cls.subject, 10, is_scholarship_eligible=True, ai_answer='Gamma, because.',
                                  **REFERENCE)
        FreeShowcaseQuestion.objects.create(question=cls.challenge, year=2024, position=5)

    def test_helpers_lock_it_for_free_and_anonymous_callers(self):
        from questions.views import free_showcase_rows, user_can_view_answer

        self.assertFalse(free_showcase_rows().filter(question=self.challenge).exists())
        for user in (self.free, None):
            self.assertFalse(user_can_view_answer(user, self.challenge))
            self.assertFalse(user_can_view_answer(user, self.challenge.pk))
        self.assertTrue(user_can_view_answer(self.premium, self.challenge))
        self.assertTrue(user_can_view_answer(self.admin, self.challenge.pk))

    def test_no_endpoint_reveals_its_answer_to_a_free_user(self):
        api = _client(self.free)
        q = self.challenge
        self.assertEqual(api.post(f'/api/questions/{q.id}/attempt/', {'selected_answer': 'C'}, format='json').status_code, 402)
        self.assertEqual(api.post(f'/api/questions/{q.id}/practice/attempt/', {'answer': 'C'}, format='json').status_code, 402)
        self.assertEqual(api.get(f'/api/questions/{q.id}/ai/why_correct/').data, {'why_correct': None, 'locked': True})
        self.assertEqual(api.get(f'/api/questions/{q.id}/').status_code, 404)
        row = api.get('/api/questions/', {'question_id': q.id}).data['results'][0]
        self.assertFalse(row['is_showcase'])
        self.assertEqual(row['reference_text'], '')
        anon = _client().get(f'/api/questions/{q.id}/').data
        self.assertIsNone(anon['correct_answer'])
        self.assertIsNone(anon['reference_text'])
        self.assertFalse(MistakeNotebook.objects.filter(question=q).exists())

    def test_premium_keeps_full_access(self):
        res = _client(self.premium).post(f'/api/questions/{self.challenge.id}/attempt/', {'selected_answer': 'C'},
                                         format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['correct_answer'], 'C')

    def test_recall_search_matches_its_explanation_for_entitled_callers_only(self):
        def ids(user):
            # 'is right' appears only in the explanation ('Gamma is right (10).').
            res = _client(user).get('/api/questions/recall_search/', {'drug': 'is right', 'year': 2024})
            self.assertEqual(res.status_code, 200, res.data)
            return {row['id'] for row in res.data['results']}

        self.assertNotIn(self.challenge.id, ids(None))
        self.assertNotIn(self.challenge.id, ids(self.free))
        self.assertIn(self.challenge.id, ids(self.premium))
        self.assertIn(self.challenge.id, ids(self.admin))


class DiscussionEntitlementTests(_Base):
    """Threads discuss the answer: same rule as the answer itself."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from questions.models import Discussion

        cls.locked = _question(cls.subject, 15)
        cls.showcase = _question(cls.subject, 16)
        FreeShowcaseQuestion.objects.create(question=cls.showcase, year=2024, position=1)
        cls.locked_thread = Discussion.objects.create(question=cls.locked, user=cls.premium, text='It is C: gamma.')
        Discussion.objects.create(question=cls.locked, user=cls.premium, parent=cls.locked_thread, text='Agree, C.')
        cls.own_post = Discussion.objects.create(question=cls.locked, user=cls.free, text='Why not B?')
        cls.showcase_thread = Discussion.objects.create(question=cls.showcase, user=cls.premium, text='Gamma.')

    def _texts(self, user, question):
        res = _client(user).get('/api/questions/discussions/', {'question': question.id})
        self.assertEqual(res.status_code, 200)
        return {row['text'] for row in res.data['results']}

    def test_free_users_read_only_their_own_posts_on_a_locked_question(self):
        self.assertEqual(self._texts(self.free, self.locked), {'Why not B?'})
        self.assertEqual(self._texts(self.free, self.showcase), {'Gamma.'})
        replies = _client(self.free).get(f'/api/questions/discussions/{self.locked_thread.id}/replies/').data
        rows = replies['results'] if isinstance(replies, dict) else replies
        self.assertEqual(rows, [])
        self.assertEqual(_client(self.free).get(f'/api/questions/discussions/{self.locked_thread.id}/').status_code,
                         404)
        # Their own post stays editable.
        res = _client(self.free).patch(f'/api/questions/discussions/{self.own_post.id}/', {'text': 'Why not B, really?'},
                                       format='json')
        self.assertEqual(res.status_code, 200, res.data)

    def test_premium_and_admin_read_every_thread(self):
        for user in (self.premium, self.admin):
            self.assertEqual(self._texts(user, self.locked), {'It is C: gamma.', 'Why not B?'})


class RecallSearchAnswerOracleTests(_Base):
    """Recall search matched clinical keywords (and image OCR / modality)
    against the explanation of questions the caller may not read: an
    anonymous ``?drug=<option>`` returned a locked question for its correct
    option only."""

    OPTIONS = ('Ethosuximide', 'Phenytoin', 'Carbamazepine', 'Gabapentin')
    DIMENSIONS = ('diagnosis', 'drug', 'disease', 'investigation', 'clinical_system', 'subtopic')

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        options = dict(zip(('option_a', 'option_b', 'option_c', 'option_d'), cls.OPTIONS))
        answer_text = dict(explanation='Ethosuximide blocks T-type calcium channels.',
                           ai_clinical_pearl='Zarontin pearl.', **options)
        cls.locked = _question(cls.subject, 100, question_text='Z9 recall: drug of choice for absences?',
                               correct_answer='A', year=2031, **answer_text)
        cls.showcase = _question(cls.subject, 101, question_text='Z9 recall: first-line drug for absences?',
                                 correct_answer='A', year=2031, **answer_text)
        FreeShowcaseQuestion.objects.create(question=cls.showcase, year=2031, position=0)

        # A locked question with a stem figure, an explanation figure, a figure
        # referenced only from the explanation (runtime role 'explanation')
        # and one referenced from the stem and the explanation.
        cls.figures = _question(cls.subject, 102, year=2032)

        def image(role, ocr, modality, **kw):
            return QuestionImage.objects.create(question=cls.figures, page_number=0, role=role, ocr_text=ocr,
                                                modality=modality, url=f'/media/z9-{modality}.png', **kw)

        image('primary', 'EEG 3 Hz spike-wave', 'chart')
        image('explanation', 'Zarontin label', 'ct', has_diagram=True)
        hidden = image('illustration', 'T-type channel figure', 'mri')
        shared = image('illustration', 'shared plot', 'x_ray')
        Question.objects.filter(pk=cls.figures.pk).update(
            question_text=f'Z9 recall figures stem [[img:{shared.id}]]',
            explanation=f'See [[img:{hidden.id}]] and [[img:{shared.id}]].',
        )

    def _search(self, user, **params):
        res = _client(user).get('/api/questions/recall_search/', params)
        self.assertEqual(res.status_code, 200, res.data)
        return res.data

    def _ids(self, user, **params):
        return {row['id'] for row in self._search(user, **params)['results']}

    def test_explanation_only_keywords_hit_only_entitled_callers(self):
        for dim in self.DIMENSIONS:
            for token in ('T-type calcium', 'Zarontin'):   # explanation / AI pearl only
                params = {'year': 2031, dim: token}
                # The showcase question's explanation is free content.
                self.assertEqual(self._ids(None, **params), {self.showcase.id}, params)
                self.assertEqual(self._ids(self.free, **params), {self.showcase.id}, params)
                for user in (self.premium, self.admin):
                    self.assertEqual(self._ids(user, **params), {self.locked.id, self.showcase.id}, params)

    def test_free_text_q_is_not_an_answer_oracle(self):
        # ``q`` must occur in the stem for every caller (_PARAM_FILTERS); the
        # tokenised match on answer-linked text is limited to the questions
        # the caller may read on top of that, so it can only narrow.
        for token in ('T-type', 'Zarontin'):   # explanation / AI clinical pearl only
            for user in (None, self.free):
                self.assertNotIn(self.locked.id, self._ids(user, year=2031, q=token), (user, token))
        # The stem is public: it finds the locked question for everyone who
        # may list it (a free account lists the showcase only).
        for user in (None, self.premium, self.admin):
            self.assertEqual(self._ids(user, year=2031, q='absences'), {self.locked.id, self.showcase.id}, user)
        self.assertEqual(self._ids(self.free, year=2031, q='absences'), {self.showcase.id})

    def test_every_option_of_a_locked_question_is_an_equal_hit(self):
        # Options are public: each one finds the question, so a hit no longer
        # singles out the correct option.
        for option in self.OPTIONS:
            self.assertIn(self.locked.id, self._ids(None, year=2031, drug=option), option)

    def test_image_filters_skip_explanation_figures_of_locked_questions(self):
        def hits(user, **params):
            return self._ids(user, year=2032, **params) == {self.figures.id}

        for params in ({'image_ocr': '3 Hz'}, {'image_ocr': 'shared plot'}, {'modality': 'chart'},
                       {'has_image': 'true'}):
            self.assertTrue(hits(None, **params), params)
        for params in ({'image_ocr': 'Zarontin'}, {'image_ocr': 'channel figure'}, {'modality': 'ct'},
                       {'modality': 'mri'}, {'has_diagram': 'true'}):
            self.assertFalse(hits(None, **params), params)
            self.assertTrue(hits(self.premium, **params), params)
            self.assertTrue(hits(self.admin, **params), params)
        self.assertEqual(self._search(None, year=2032)['facets']['modality'], {'chart': 1, 'x_ray': 1})
        self.assertEqual(self._search(self.premium, year=2032)['facets']['modality'],
                         {'chart': 1, 'ct': 1, 'mri': 1, 'x_ray': 1})


# ── Answer submission ──────────────────────────────────────────────────────

class UngradableAnswerTests(_Base):
    def test_blank_answer_key_records_no_attempt_and_no_mistake(self):
        q = _question(self.subject, 20, correct_answer='')
        api = _client(self.premium)
        res = api.post(f'/api/questions/{q.id}/attempt/', {'selected_answer': 'B', 'time_spent_seconds': 30},
                       format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['correct_answer'], '')
        self.assertIsNone(res.data['is_correct'])
        self.assertTrue(res.data['effective_explanation'])
        res = api.post(f'/api/questions/{q.id}/practice/attempt/', {'answer': 'B', 'time_spent': 20}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['correct_answer'], '')
        self.assertIsNone(res.data['is_correct'])
        self.assertFalse(QuestionAttempt.objects.filter(question=q).exists())
        self.assertFalse(MistakeNotebook.objects.filter(question=q).exists())
        # The time still counts as study time, but no answered question.
        row = StudyTimeBreakdown.objects.get(user=self.premium, subject=self.subject)
        self.assertEqual((row.seconds, row.question_count), (50, 0))

    def test_a_keyed_wrong_answer_is_still_a_mistake(self):
        q = _question(self.subject, 21)
        _client(self.premium).post(f'/api/questions/{q.id}/attempt/', {'selected_answer': 'b'}, format='json')
        self.assertTrue(MistakeNotebook.objects.filter(user=self.premium, question=q).exists())


class AnswerTimeTopicPerformanceTests(_Base):
    """AN-30: question-bank answers feed UserTopicPerformance.total_time_seconds."""

    def _rows(self, user):
        from analytics.models import UserTopicPerformance

        return {
            row.topic_id: (row.total_attempts, row.total_time_seconds)
            for row in UserTopicPerformance.objects.filter(user=user, subject=self.subject)
        }

    def test_first_answer_adds_its_clamped_time_once(self):
        q = _question(self.subject, 30, topic=self.topic)
        api = _client(self.premium)
        api.post(f'/api/questions/{q.id}/attempt/', {'selected_answer': 'C', 'time_spent_seconds': 95}, format='json')
        self.assertEqual(self._rows(self.premium), {None: (1, 95), self.topic.pk: (1, 95)})
        # Re-answering is not a new counted attempt: no time either.
        api.post(f'/api/questions/{q.id}/attempt/', {'selected_answer': 'A', 'time_spent_seconds': 50}, format='json')
        self.assertEqual(self._rows(self.premium), {None: (1, 95), self.topic.pk: (1, 95)})
        # An idle tab is clamped like study time (30 min per question).
        other = _question(self.subject, 31, topic=self.topic)
        api.post(f'/api/questions/{other.id}/attempt/', {'selected_answer': 'C', 'time_spent_seconds': 10 ** 7},
                 format='json')
        self.assertEqual(self._rows(self.premium), {None: (2, 95 + 1800), self.topic.pk: (2, 95 + 1800)})

    def test_practice_mode_answers_count_too(self):
        q = _question(self.subject, 32)
        _client(self.premium).post(f'/api/questions/{q.id}/practice/attempt/', {'answer': 'C', 'time_spent': 40},
                                   format='json')
        self.assertEqual(self._rows(self.premium), {None: (1, 40)})


class ExplanationOverrideTests(_Base):
    def test_admin_override_is_the_explanation_of_the_answer_response(self):
        q = _question(self.subject, 40, explanation='Old curated text.', admin_explanation_override='Admin fix.')
        locked = _question(self.subject, 41, explanation='Curated only.', lock_explanation=True)
        api = _client(self.premium)
        res = api.post(f'/api/questions/{q.id}/attempt/', {'selected_answer': 'C'}, format='json')
        self.assertEqual((res.data['explanation'], res.data['effective_explanation']), ('Admin fix.', 'Admin fix.'))
        res = api.post(f'/api/questions/{locked.id}/practice/attempt/', {'answer': 'C'}, format='json')
        self.assertEqual(res.data['explanation'], 'Curated only.')

    def test_explanation_overridden_flag_in_the_detail_and_the_answer_responses(self):
        # An admin override or lock decides the explanation; AI text alone
        # (or a blank override) does not.
        cases = (
            (_question(self.subject, 42, explanation='Curated.', admin_explanation_override='Admin fix.'), True),
            (_question(self.subject, 43, explanation='Curated.', lock_explanation=True), True),
            (_question(self.subject, 44, explanation='Curated.', ai_explanation='AI explanation text.'), False),
            (_question(self.subject, 45, explanation='Curated.', admin_explanation_override='   '), False),
        )
        api = _client(self.premium)
        for q, expected in cases:
            detail = api.get(f'/api/questions/{q.id}/')
            self.assertEqual(detail.status_code, 200, detail.data)
            self.assertIs(detail.data['explanation_overridden'], expected, q.id)
            res = api.post(f'/api/questions/{q.id}/attempt/', {'selected_answer': 'C'}, format='json')
            self.assertEqual(res.status_code, 200, res.data)
            self.assertIs(res.data['explanation_overridden'], expected, q.id)
            res = api.post(f'/api/questions/{q.id}/practice/attempt/', {'answer': 'C'}, format='json')
            self.assertEqual(res.status_code, 200, res.data)
            self.assertIs(res.data['explanation_overridden'], expected, q.id)
        # A question without an answer key carries it with its explanation too.
        keyless = _question(self.subject, 47, correct_answer='', admin_explanation_override='Admin fix.')
        res = api.post(f'/api/questions/{keyless.id}/attempt/', {'selected_answer': 'C'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertIs(res.data['explanation_overridden'], True)

    def test_a_redacted_detail_hides_the_flag(self):
        locked = _question(self.subject, 46, explanation='Curated.', lock_explanation=True,
                           admin_explanation_override='Admin fix.')
        data = _client().get(f'/api/questions/{locked.id}/').data
        self.assertTrue(data['answer_locked'])
        self.assertIsNone(data['explanation_overridden'])
        self.assertIsNone(data['effective_explanation'])
        # A free account gets neither the detail nor an answer payload.
        self.assertEqual(_client(self.free).get(f'/api/questions/{locked.id}/').status_code, 404)
        res = _client(self.free).post(f'/api/questions/{locked.id}/attempt/', {'selected_answer': 'C'}, format='json')
        self.assertEqual(res.status_code, 402)
        self.assertNotIn('explanation_overridden', res.data)


class LateTestQuestTests(_Base):
    def test_late_submission_does_not_finish_the_test_quest(self):
        from questions.quest_service import _progress_for
        from tests_engine.models import Test, TestAttempt

        test = Test.objects.create(title='Z9 quest test', test_type='mixed')
        now = timezone.now()
        TestAttempt.objects.create(user=self.free, test=test, is_completed=True, completed_at=now,
                                   correct_count=3, is_late=True)
        self.assertEqual(_progress_for(self.free, 'complete_tests', timezone.localdate()), 0)
        TestAttempt.objects.create(user=self.free, test=test, is_completed=True, completed_at=now, correct_count=1)
        self.assertEqual(_progress_for(self.free, 'complete_tests', timezone.localdate()), 1)


# ── AI ─────────────────────────────────────────────────────────────────────

class FailedGenerationRetryTests(_Base):
    def test_a_failed_generation_is_not_retried_on_the_next_request(self):
        # Wave 4b: the GET queues the generation; the background task runs
        # the rotation once for every missing section, and after a failure no
        # request queues it again within the failure window.
        from questions.tasks import generate_reveal_sections_task

        q = _question(self.subject, 50)
        api = _client(self.premium)
        with mock.patch('questions.ai_per_question._ai_call', return_value='') as ai_call, \
                mock.patch('django_q.tasks.async_task') as queue:
            res = api.get(f'/api/questions/{q.id}/ai/clinical/')
            self.assertEqual(res.status_code, 202)
            self.assertEqual(queue.call_count, 1)
            self.assertEqual(generate_reveal_sections_task(q.id), [])
            for _ in range(3):
                res = api.get(f'/api/questions/{q.id}/ai/clinical/')
                self.assertEqual(res.status_code, 200)
                self.assertIsNone(res.data['clinical_significance'])
                self.assertNotIn('rate_limited', res.data)
            other = api.get(f'/api/questions/{q.id}/ai/why_correct/')
            self.assertIsNone(other.data['why_correct'])
            self.assertEqual(generate_reveal_sections_task(q.id), [])
        # One rotation for the question, not one per request or per section.
        self.assertEqual(ai_call.call_count, 1)
        self.assertEqual(queue.call_count, 1)

    def test_success_after_the_failure_window_is_cached(self):
        from questions import ai_per_question

        q = _question(self.subject, 51)
        with mock.patch('questions.ai_per_question._ai_call', return_value=''):
            ai_per_question.memory_trick(q, allow_ai=True, fallback=False)
        cache.delete(ai_per_question._k(q.id, 'memory_trick:failed'))   # the window expired
        with mock.patch('questions.ai_per_question._ai_call', return_value='G for gamma') as ai_call:
            self.assertEqual(ai_per_question.memory_trick(q, allow_ai=True, fallback=False), 'G for gamma')
            self.assertEqual(ai_per_question.memory_trick(q, allow_ai=True, fallback=False), 'G for gamma')
        self.assertEqual(ai_call.call_count, 1)


class BankExplanationCacheKeyTests(_Base):
    """The cache task and the bulk commands cache a bank explanation under the
    question's own id (AIService.explanation_cache_key), the key that
    explain-answer reads for that question."""

    GOOD = {'why_correct': 'Gamma is right because...', 'mnemonic': 'G for gamma', 'core_concept': 'Concept'}

    def test_generate_ai_task_passes_the_question_id(self):
        from questions.tasks import generate_ai_task

        q = _question(self.subject, 55)
        with mock.patch('questions.tasks.AIService') as service:
            service.return_value.explain_after_answer.return_value = dict(self.GOOD)
            self.assertTrue(generate_ai_task(q.id))
        self.assertEqual(service.return_value.explain_after_answer.call_args.kwargs['question_id'], q.id)

    def test_backfill_and_generate_missing_ai_pass_the_question_id(self):
        from questions.management.commands.backfill_empty_ai import Command as Backfill

        q = _question(self.subject, 56)
        service = mock.Mock()
        service.explain_after_answer.return_value = dict(self.GOOD)
        self.assertTrue(Backfill(stdout=StringIO())._process_one(q, service, max_retries=0))
        self.assertEqual(service.explain_after_answer.call_args.kwargs['question_id'], q.id)

        other = _question(self.subject, 57)
        with mock.patch('questions.management.commands.generate_missing_ai.AIService') as missing:
            missing.return_value.explain_after_answer.return_value = dict(self.GOOD)
            call_command('generate_missing_ai', stdout=StringIO())
        ids = {call.kwargs['question_id'] for call in missing.return_value.explain_after_answer.call_args_list}
        self.assertIn(other.id, ids)


class GenerateExplanationVerificationTests(_Base):
    RESULT = {'explanation': 'New AI explanation', 'why_correct': 'Because gamma'}

    def _post(self, q, body, result=None):
        with mock.patch('ai_engine.services.AIService') as service:
            service.return_value.generate_admin_explanation.return_value = dict(result or self.RESULT)
            return _client(self.admin).post(f'/api/questions/{q.id}/generate-explanation/', body, format='json')

    def _verified(self, i, **kw):
        return _question(self.subject, i, is_verified_by_admin=True, verified_by=self.admin,
                         verified_at=timezone.now(), **kw)

    def test_regenerated_content_clears_the_verified_mark(self):
        q = self._verified(60, explanation='Reviewed explanation')
        res = self._post(q, {'correct_answer': 'C', 'regenerate_if_exists': True})
        self.assertEqual(res.status_code, 200, res.data)
        self.assertTrue(res.data['verification_cleared'])
        q.refresh_from_db()
        self.assertEqual(q.explanation, 'New AI explanation')
        self.assertEqual((q.is_verified_by_admin, q.verified_by, q.verified_at), (False, None, None))
        # The revision snapshot keeps the verified state (undo restores it).
        snapshot = QuestionRevisionSnapshot.objects.get(question=q)
        self.assertIs(snapshot.snapshot['is_verified_by_admin'], True)

    def test_identical_output_keeps_the_mark(self):
        q = self._verified(61, explanation='New AI explanation', why_correct='Because gamma')
        res = self._post(q, {'correct_answer': 'C', 'regenerate_if_exists': True})
        self.assertEqual(res.status_code, 200, res.data)
        self.assertFalse(res.data['verification_cleared'])
        q.refresh_from_db()
        self.assertTrue(q.is_verified_by_admin)

    def test_the_detail_says_what_happened_to_the_verified_mark(self):
        body = {'correct_answer': 'C', 'regenerate_if_exists': True}
        cleared = self._post(self._verified(63, explanation='Reviewed explanation'), body)
        self.assertTrue(cleared.data['verification_cleared'])
        self.assertIn('"Verified by Admin" mark was removed', cleared.data['detail'])
        # Identical output keeps the mark, and the message no longer says
        # "not marked verified" for it.
        kept = self._post(self._verified(64, explanation='New AI explanation', why_correct='Because gamma'), body)
        self.assertFalse(kept.data['verification_cleared'])
        self.assertTrue(kept.data['question']['is_verified_by_admin'])
        self.assertIn('keeps its "Verified by Admin" mark', kept.data['detail'])
        self.assertNotIn('not marked verified', kept.data['detail'])
        plain = self._post(_question(self.subject, 65, explanation=''), {'correct_answer': 'C'})
        self.assertEqual(plain.data['detail'], 'Explanation generated and saved (not marked verified).')

    def test_the_active_prompt_version_is_recorded_for_saves_and_dry_runs(self):
        prompt = AdminAIPromptVersion.objects.create(name='z9', prompt_text='Lead with the mechanism.',
                                                     is_active=True, created_by=self.admin)
        q = _question(self.subject, 62, explanation='')
        self.assertEqual(self._post(q, {'correct_answer': 'C', 'dry_run': True}).status_code, 200)
        self.assertEqual(self._post(q, {'correct_answer': 'C'}).status_code, 200)
        logs = list(QuestionAIOperationLog.objects.filter(question=q).order_by('id'))
        self.assertEqual(len(logs), 2)
        self.assertTrue(all(log.prompt_version_id == prompt.id for log in logs))
        self.assertEqual([log.provider for log in logs],
                         ['aiservice:generate-explanation:dry-run', 'aiservice:generate-explanation'])
        self.assertTrue(all(log.created_by_id == self.admin.id for log in logs))
        self.assertEqual(logs[1].response_excerpt, 'New AI explanation')


class ForceRegenerateVerificationTests(_Base):
    """QE-03 for the admin "Regenerate AI" action: students read ai_answer /
    ai_explanation unless the admin locked or overrode them."""

    def _post(self, q, analysis='## New AI analysis'):
        with mock.patch('ai_engine.services.AIService') as service:
            service.return_value.analyze_question.return_value = analysis
            return _client(self.admin).post(f'/api/questions/{q.id}/force-regenerate/')

    def _verified(self, i, **kw):
        return _question(self.subject, i, is_verified_by_admin=True, verified_by=self.admin,
                         verified_at=timezone.now(), **kw)

    def test_regenerated_text_clears_the_verified_mark_and_undo_restores_both(self):
        q = self._verified(110, ai_answer='Reviewed answer', ai_explanation='Reviewed explanation')
        res = self._post(q)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertTrue(res.data['verification_cleared'])
        self.assertEqual(res.data['updated_fields'], ['ai_answer', 'ai_explanation', 'ai_references'])
        q.refresh_from_db()
        self.assertEqual((q.ai_answer, q.ai_explanation), ('## New AI analysis', '## New AI analysis'))
        self.assertEqual((q.is_verified_by_admin, q.verified_by, q.verified_at), (False, None, None))
        # Students read the new text, without the badge.
        detail = _client(self.premium).get(f'/api/questions/{q.id}/').data
        self.assertIn('New AI analysis', detail['effective_explanation'])
        self.assertFalse(detail['is_verified_by_admin'])
        # Undo restores the reviewed AI text together with the verified flag.
        snapshot = QuestionRevisionSnapshot.objects.get(question=q)
        self.assertEqual(snapshot.reason, 'Before AI force-regenerate')
        self.assertEqual(snapshot.snapshot['ai_explanation'], 'Reviewed explanation')
        res = _client(self.admin).post(f'/api/questions/{q.id}/undo-last-revision/', {}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        q.refresh_from_db()
        self.assertEqual((q.ai_answer, q.ai_explanation, q.is_verified_by_admin),
                         ('Reviewed answer', 'Reviewed explanation', True))

    def test_identical_output_keeps_the_mark(self):
        q = self._verified(111, ai_answer='## Same analysis', ai_explanation='## Same analysis')
        res = self._post(q, analysis='## Same analysis')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertFalse(res.data['verification_cleared'])
        q.refresh_from_db()
        self.assertEqual((q.is_verified_by_admin, q.verified_by_id), (True, self.admin.id))
        self.assertIsNotNone(q.verified_at)

    def test_a_locked_explanation_keeps_its_text_but_a_new_ai_answer_clears_the_mark(self):
        q = self._verified(112, ai_answer='Reviewed answer', ai_explanation='Reviewed explanation',
                           lock_explanation=True)
        res = self._post(q)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['updated_fields'], ['ai_answer'])
        self.assertTrue(res.data['verification_cleared'])
        q.refresh_from_db()
        self.assertEqual((q.ai_answer, q.ai_explanation), ('## New AI analysis', 'Reviewed explanation'))
        self.assertFalse(q.is_verified_by_admin)


class RevisionDiffLegacySnapshotTests(_Base):
    def test_fields_an_older_snapshot_never_recorded_are_not_changes(self):
        from questions.views import QuestionViewSet

        q = _question(self.subject, 120, ai_answer='Some AI answer', ai_explanation='Some AI text')
        state = QuestionViewSet()._serialize_revision_state(q)
        legacy = {key: value for key, value in state.items() if not key.startswith('ai_')}
        legacy['explanation'] = 'Earlier text'
        QuestionRevisionSnapshot.objects.create(question=q, snapshot=legacy, reason='legacy')
        res = _client(self.admin).get(f'/api/questions/{q.id}/revisions-diff/')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual([row['field'] for row in res.data['changed_fields']], ['explanation'])


# ── Stats, ordering, admin rows, practice queue ────────────────────────────

class QuestionStatsRowsTests(_Base):
    def test_empty_subjects_and_unknown_years_are_not_rows(self):
        empty = Subject.objects.create(name='Z9 Empty Subject', code='Z9EMPTY')
        _question(self.subject, 70, exam_type='cms', exam_source='UPSC CMS', year=2023)
        _question(self.subject, 71, exam_type='cms', exam_source='UPSC CMS', year=0)
        data = _client().get('/api/questions/stats/', {'exam_type': 'cms'}).data
        self.assertNotIn(empty.id, [row['id'] for row in data['by_subject']])
        self.assertIn(self.subject.id, [row['id'] for row in data['by_subject']])
        self.assertEqual([row['year'] for row in data['by_year']], [2023])
        self.assertEqual(data['total'], 2)   # the total still counts every active question


class IniCetBankLabelTests(_Base):
    """The INI-CET bank is stored as 'INI-CET (recall)' and, by older imports,
    'INICET'; the stats strip matched the exact label 'INI-CET' and was empty."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.ini_subject = Subject.objects.create(name='Z9 INI-CET Subject', code='Z9INI', exam_type='ini_cet')
        cls.recall = _question(cls.ini_subject, 130, exam_type='ini_cet', exam_source='INI-CET (recall)', year=2034)
        cls.legacy = _question(cls.ini_subject, 131, exam_type='ini_cet', exam_source='INICET', year=2035)
        _question(cls.ini_subject, 132, exam_type='neet_pg', exam_source='NEET PG (recall)', year=2034)

    def test_stats_count_every_ini_cet_label(self):
        for params in ({'exam_source': 'INI-CET'}, {'exam_source': 'INICET'}, {'exam_type': 'ini_cet'},
                       {'exam': 'ini-cet'}):
            data = _client().get('/api/questions/stats/', params).data
            self.assertEqual(data['total'], 2, params)
            self.assertEqual([row['year'] for row in data['by_year']], [2035, 2034], params)
            self.assertEqual([(row['id'], row['count']) for row in data['by_subject']],
                             [(self.ini_subject.id, 2)], params)

    def test_solved_counts_cover_both_labels(self):
        QuestionAttempt.objects.create(user=self.premium, question=self.recall, selected_answer='C', is_correct=True)
        QuestionAttempt.objects.create(user=self.premium, question=self.legacy, selected_answer='A', is_correct=False)
        data = _client(self.premium).get('/api/questions/stats/', {'exam_source': 'INI-CET'}).data
        self.assertEqual(data['total_solved'], 2)
        self.assertEqual({row['year']: row['solved'] for row in data['by_year']}, {2034: 1, 2035: 1})
        self.assertEqual([row['solved'] for row in data['by_subject']], [2])

    def test_list_and_years_match_both_labels(self):
        rows = _client(self.premium).get('/api/questions/', {'exam_source': 'INI-CET'}).data['results']
        self.assertEqual({row['id'] for row in rows}, {self.recall.id, self.legacy.id})
        self.assertEqual(_client().get('/api/questions/years/', {'exam_source': 'INI-CET'}).data, [2035, 2034])
        self.assertEqual(_client().get('/api/questions/years/', {'exam_source': 'INICET'}).data, [2035, 2034])


class OrderingAndAdminRowTests(_Base):
    def test_ordering_gets_an_id_tiebreak(self):
        from questions.views import IdTiebreakOrderingFilter, QuestionViewSet

        def ordering(params):
            request = Request(APIRequestFactory().get('/api/questions/', params))
            view = QuestionViewSet()
            view.request, view.action, view.format_kwarg = request, 'list', None
            return IdTiebreakOrderingFilter().get_ordering(request, Question.objects.all(), view)

        self.assertEqual(ordering({'ordering': 'paper,display_number'}), ['paper', 'display_number', 'id'])
        self.assertEqual(ordering({'ordering': '-year'}), ['-year', 'id'])
        self.assertEqual(ordering({'ordering': 'paper,-id'}), ['paper', '-id'])
        self.assertIsNone(ordering({}))

    def test_admin_rows_are_ordered_and_carry_is_active(self):
        rows = [_question(self.subject, 80 + i, paper=1, display_number=n, year=2033) for i, n in enumerate((2, 1, 1))]
        res = _client(self.admin).get('/api/questions/', {'year': 2033, 'ordering': 'paper,display_number'})
        results = res.data['results']
        self.assertEqual([r['id'] for r in results], [rows[1].id, rows[2].id, rows[0].id])
        self.assertTrue(all(r['is_active'] is True for r in results))


class PracticeQueueStaffTests(_Base):
    def test_staff_get_the_full_queue(self):
        staff = User.objects.create_user(username='z9w3-staff', password='unused-pw-4', is_staff=True)
        _question(self.subject, 90)
        res = _client(staff).get('/api/questions/practice_queue/', {'mode': 'random'})
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data['freemium'])
        self.assertTrue(_client(self.free).get('/api/questions/practice_queue/', {'mode': 'random'}).data['freemium'])


# ── Fixture loader on a fresh database ─────────────────────────────────────

STEM_NEW = 'Z9 fixture stem: drug of choice for absence seizures?'
STEM_TAKEN = 'Z9 fixture stem: most common site of berry aneurysm?'


def _fixture_rows():
    fields = {
        'option_a': 'Ethosuximide', 'option_b': 'Phenytoin', 'option_c': 'Carbamazepine', 'option_d': 'Gabapentin',
        'correct_answer': 'A', 'year': 2024, 'subject': 'Z9SDM', 'topic': 'Z9 Seed Topic', 'difficulty': 'medium',
        'explanation': 'Fixture explanation.', 'paper': 1, 'exam_source': 'UPSC CMS', 'exam_type': 'cms',
        'is_active': True,
    }
    return [
        {'model': 'questions.subject', 'pk': 1, 'fields': {'name': 'Z9 Seed Medicine', 'code': 'Z9SDM', 'paper': 1}},
        {'model': 'questions.topic', 'pk': 1, 'fields': {'subject': 'Z9SDM', 'name': 'Z9 Seed Topic'}},
        {'model': 'questions.question', 'pk': 910001, 'fields': {**fields, 'question_text': STEM_NEW}},
        {'model': 'questions.question', 'pk': 910002, 'fields': {**fields, 'question_text': STEM_TAKEN}},
    ]


class FixtureSeedFreshDatabaseTests(TestCase):
    def setUp(self):
        from questions.management.commands import load_exam_fixture as loader
        from questions.management.commands import seed_question_bank as seed

        tmp = Path(tempfile.mkdtemp())
        (tmp / 'cms_fixture.json').write_text(json.dumps(_fixture_rows()), encoding='utf-8')
        (tmp / 'images' / 'cms').mkdir(parents=True)
        for module in (loader, seed):
            patcher = mock.patch.object(module, 'FIXTURES_DIR', tmp)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _seed(self):
        call_command('seed_question_bank', stdout=StringIO(), stderr=StringIO())

    def test_id_sequences_are_reset_after_explicit_pk_inserts(self):
        with mock.patch.object(connection.ops, 'sequence_reset_sql',
                               return_value=['SELECT 910003 AS z9_sequence_reset']) as reset:
            with CaptureQueriesContext(connection) as queries:
                self._seed()
        models = reset.call_args[0][1]
        self.assertIn(Question, models)
        self.assertTrue(any('z9_sequence_reset' in q['sql'] for q in queries.captured_queries))
        self.assertEqual(Question.objects.get(pk=910001).question_text, STEM_NEW)

    def test_a_legacy_row_of_another_exam_at_a_fixture_pk_is_left_alone(self):
        legacy_subject = Subject.objects.create(name='Legacy NEET', code='Z9LGC')
        legacy = Question.objects.create(
            pk=910002, question_text='Legacy NEET PG stem', option_a='a', option_b='b', option_c='c', option_d='d',
            correct_answer='D', year=2020, subject=legacy_subject, exam_type='cms', exam_source='NEET PG',
        )
        self._seed()   # the CMS bank is empty: only the legacy NEET PG row exists
        legacy.refresh_from_db()
        self.assertEqual((legacy.question_text, legacy.exam_source, legacy.correct_answer, legacy.subject_id),
                         ('Legacy NEET PG stem', 'NEET PG', 'D', legacy_subject.id))
        self.assertEqual(Question.objects.get(pk=910001).exam_source, 'UPSC CMS')
