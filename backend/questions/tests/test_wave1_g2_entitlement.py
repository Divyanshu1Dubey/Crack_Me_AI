"""Wave-1 G2: one entitlement rule for every answer-revealing endpoint.

Entitled = admin / staff, premium subscriber, or (anyone) a showcase
question. Before the fix the answer and explanation of every question
leaked through anonymous retrieve, ``attempt``, ``practice/attempt``,
``ai/*``, ``sources``, ``images`` and the FloatingDock chat context.

Issues: QB-02, QB-03, FE-STU-01, ENT-01, QB-14, FD-01, QB-23, QB-33.
No AI provider is called: every AI entry point is patched.
"""
from __future__ import annotations

from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Subscription
from accounts.models_freemium import FreeShowcaseQuestion
from questions.models import (
    DuplicateCluster, DuplicateMember, MistakeNotebook, Question, QuestionAttempt,
    QuestionImage, QuestionSource, RecallSource, Subject,
)

User = get_user_model()

OUTAGE = 'All AI services are temporarily unavailable. Please try again in a moment.'


def _question(subject, i, **kw):
    defaults = dict(
        question_text=f'G2 entitlement stem {i}', option_a='alpha', option_b='beta',
        option_c='gamma', option_d='delta', correct_answer='C', year=2024, subject=subject,
        explanation=f'Gamma is right ({i}).', mnemonic='G for gamma',
    )
    defaults.update(kw)
    return Question.objects.create(**defaults)


def _premium(username):
    user = User.objects.create_user(username=username, email=f'{username}@example.com', password='unused-pw-1')
    Subscription.objects.create(
        user=user, plan='1_year', status='active', expires_at=timezone.now() + timedelta(days=365),
    )
    return user


def _client(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user)
    return client


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='G2 Medicine', code='G2MED')
        cls.locked = _question(
            cls.subject, 1, ai_answer='Gamma because of the stem.', ai_explanation='AI says gamma.',
            ai_mnemonic='Gamma mnemonic', ai_clinical_pearl='Gamma pearl',
            video_url='https://example.com/v/locked.mp4', video_status='completed',
            why_wrong_a='Alpha is a distractor.', why_wrong_b='Beta is a distractor.',
        )
        cls.showcase = _question(cls.subject, 2)
        FreeShowcaseQuestion.objects.create(question=cls.showcase, year=2024, position=0)
        cls.free = User.objects.create_user(username='g2-free', email='g2-free@example.com', password='unused-pw-2')
        cls.premium = _premium('g2-premium')
        cls.admin = User.objects.create_user(username='g2-admin', password='unused-pw-3', role='admin')

    def setUp(self):
        cache.clear()


class RetrieveEntitlementTests(_Base):
    def test_anonymous_retrieve_of_locked_question_redacts_answer(self):
        res = _client().get(f'/api/questions/{self.locked.id}/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['question_text'], self.locked.question_text)
        self.assertTrue(res.data['answer_locked'])
        for field in ('correct_answer', 'explanation', 'mnemonic', 'ai_answer', 'ai_explanation',
                      'ai_mnemonic', 'effective_answer', 'effective_explanation', 'effective_mnemonic',
                      'video_url'):
            self.assertIsNone(res.data[field], field)
        self.assertNotIn('Gamma', str(res.data))

    def test_anonymous_retrieve_drops_explanation_images(self):
        QuestionImage.objects.create(question=self.locked, page_number=1, role='explanation',
                                     url='https://example.com/expl.png')
        QuestionImage.objects.create(question=self.locked, page_number=1, role='primary',
                                     url='https://example.com/stem.png')
        res = _client().get(f'/api/questions/{self.locked.id}/')
        self.assertEqual([img['role'] for img in res.data['images']], ['primary'])

    def test_anonymous_retrieve_of_showcase_question_is_complete(self):
        res = _client().get(f'/api/questions/{self.showcase.id}/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['correct_answer'], 'C')
        self.assertEqual(res.data['explanation'], self.showcase.explanation)
        self.assertNotIn('answer_locked', res.data)

    def test_free_user_cannot_open_a_locked_question(self):
        self.assertEqual(_client(self.free).get(f'/api/questions/{self.locked.id}/').status_code, 404)
        self.assertEqual(_client(self.free).get(f'/api/questions/{self.showcase.id}/').status_code, 200)

    def test_premium_and_admin_get_the_full_detail(self):
        for user in (self.premium, self.admin):
            res = _client(user).get(f'/api/questions/{self.locked.id}/')
            self.assertEqual(res.status_code, 200, user.username)
            self.assertEqual(res.data['correct_answer'], 'C')
            self.assertEqual(res.data['video_url'], self.locked.video_url)


class AnswerSubmissionEntitlementTests(_Base):
    def test_free_attempt_on_locked_question_is_paywalled_and_records_nothing(self):
        res = _client(self.free).post(f'/api/questions/{self.locked.id}/attempt/',
                                      {'selected_answer': 'A'}, format='json')
        self.assertEqual(res.status_code, 402)
        self.assertEqual(res.data['code'], 'upgrade_required')
        self.assertNotIn('correct_answer', res.data)
        self.assertNotIn('is_correct', res.data)
        self.assertFalse(QuestionAttempt.objects.filter(user=self.free).exists())
        self.assertFalse(MistakeNotebook.objects.filter(user=self.free).exists())

    def test_invalid_letter_is_still_a_400(self):
        res = _client(self.free).post(f'/api/questions/{self.locked.id}/attempt/',
                                      {'selected_answer': 'Z'}, format='json')
        self.assertEqual(res.status_code, 400)

    def test_free_attempt_on_showcase_question_reveals_answer_and_explanation(self):
        res = _client(self.free).post(f'/api/questions/{self.showcase.id}/attempt/',
                                      {'selected_answer': 'a', 'time_spent_seconds': 30}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertIs(res.data['is_correct'], False)
        self.assertEqual(res.data['correct_answer'], 'C')
        self.assertEqual(res.data['explanation'], self.showcase.explanation)
        self.assertTrue(res.data['effective_explanation'])
        # mistake + study-time hooks still run
        self.assertTrue(MistakeNotebook.objects.filter(user=self.free, question=self.showcase).exists())

    def test_premium_attempt_on_any_question(self):
        res = _client(self.premium).post(f'/api/questions/{self.locked.id}/attempt/',
                                         {'selected_answer': 'C'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertIs(res.data['is_correct'], True)
        self.assertEqual(res.data['explanation'], self.locked.explanation)

    def test_anonymous_attempt_is_rejected(self):
        res = _client().post(f'/api/questions/{self.showcase.id}/attempt/', {'selected_answer': 'C'}, format='json')
        self.assertIn(res.status_code, (401, 403))

    def test_practice_attempt_free_on_locked_question_is_paywalled(self):
        res = _client(self.free).post(f'/api/questions/{self.locked.id}/practice/attempt/',
                                      {'answer': 'B'}, format='json')
        self.assertEqual(res.status_code, 402)
        self.assertEqual(res.data['code'], 'upgrade_required')
        self.assertNotIn('correct', res.data)
        self.assertFalse(QuestionAttempt.objects.filter(user=self.free).exists())

    def test_practice_attempt_response_contract_for_entitled_users(self):
        res = _client(self.premium).post(f'/api/questions/{self.locked.id}/practice/attempt/',
                                         {'answer': 'b', 'time_spent': 20}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertIs(res.data['correct'], False)
        self.assertIs(res.data['is_correct'], False)
        self.assertEqual(res.data['correct_answer'], 'C')
        self.assertEqual(res.data['explanation'], self.locked.explanation)
        self.assertTrue(MistakeNotebook.objects.filter(user=self.premium, question=self.locked).exists())


class AIPerQuestionEntitlementTests(_Base):
    def test_locked_question_ai_text_is_withheld_from_anonymous_and_free(self):
        from questions import ai_per_question as ai
        with mock.patch.object(ai, '_ai_call', return_value='generated') as call:
            for user in (None, self.free):
                for path, key in (('why_correct', 'why_correct'), ('why_incorrect', 'why_incorrect'),
                                  ('clinical', 'clinical_significance'), ('mnemonic', 'memory_trick'),
                                  ('concept', 'concept')):
                    res = _client(user).get(f'/api/questions/{self.locked.id}/ai/{path}/')
                    self.assertEqual(res.status_code, 200)
                    self.assertIsNone(res.data[key], (user, path))
                    self.assertTrue(res.data['locked'])
        call.assert_not_called()

    def test_entitled_users_get_stored_content(self):
        res = _client(self.premium).get(f'/api/questions/{self.locked.id}/ai/why_correct/')
        self.assertEqual(res.data['why_correct'], 'Gamma because of the stem.')
        res = _client(self.premium).get(f'/api/questions/{self.locked.id}/ai/why_incorrect/')
        self.assertIn('Alpha is a distractor.', res.data['why_incorrect'])
        self.assertIn('Beta is a distractor.', res.data['why_incorrect'])
        self.assertNotIn('not the canonical answer', res.data['why_incorrect'])
        # showcase questions are open to everyone (stored content only)
        res = _client().get(f'/api/questions/{self.showcase.id}/ai/mnemonic/')
        self.assertEqual(res.data['memory_trick'], 'G for gamma')

    def test_no_template_boilerplate_when_there_is_no_genuine_content(self):
        from questions import ai_per_question as ai
        with mock.patch.object(ai, '_ai_call', return_value=''):
            res = _client(self.premium).get(f'/api/questions/{self.showcase.id}/ai/clinical/')
            self.assertIsNone(res.data['clinical_significance'])
            res = _client(self.premium).get(f'/api/questions/{self.showcase.id}/ai/why_incorrect/')
            self.assertIsNone(res.data['why_incorrect'])
            res = _client(self.premium).get(f'/api/questions/{self.showcase.id}/ai/concept/')
            self.assertIsNone(res.data['concept'])
        res = _client().get(f'/api/questions/{self.showcase.id}/ai/exam_importance/')
        self.assertIsNone(res.data['exam_importance'])

    def test_stored_outage_sentence_is_never_served(self):
        q = _question(self.subject, 3, ai_answer=OUTAGE, ai_explanation=OUTAGE)
        from questions import ai_per_question as ai
        with mock.patch.object(ai, '_ai_call', return_value=''):
            res = _client(self.premium).get(f'/api/questions/{q.id}/ai/why_correct/')
        self.assertIsNone(res.data['why_correct'])
        detail = _client(self.premium).get(f'/api/questions/{q.id}/').data
        self.assertNotIn('temporarily unavailable', str(detail['effective_explanation']))
        self.assertNotIn('temporarily unavailable', str(detail['effective_answer']))

    @override_settings(AI_PER_QUESTION_HOURLY_LIMIT=1)
    def test_llm_generation_is_rate_capped_per_user(self):
        # The GET queues the (background) generation instead of calling the
        # LLM in the request (wave 4b); the hourly cap applies to queueing.
        q1 = _question(self.subject, 4, explanation='')
        q2 = _question(self.subject, 5, explanation='')
        from questions import ai_per_question as ai
        with mock.patch.object(ai, '_ai_call', return_value='Shock physiology') as call, \
                mock.patch('django_q.tasks.async_task') as queue:
            first = _client(self.premium).get(f'/api/questions/{q1.id}/ai/why_correct/')
            second = _client(self.premium).get(f'/api/questions/{q2.id}/ai/why_correct/')
        self.assertEqual(first.status_code, 202)
        self.assertEqual(first.data, {'why_correct': None, 'pending': True})
        self.assertIsNone(second.data['why_correct'])
        self.assertTrue(second.data['rate_limited'])
        self.assertEqual(queue.call_count, 1)
        call.assert_not_called()


class SourcesAndImagesTests(_Base):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        source = RecallSource.objects.create(
            pdf_filename='recall.pdf', pdf_path='/srv/private/recall.pdf',
            pdf_sha256='a' * 64, pdf_sha256_short='a' * 16,
        )
        QuestionSource.objects.create(
            question=cls.locked, recall_source=source, page_number=3,
            original_text='Q1 ... Ans: C. Explanation: gamma', extracted_text='Ans: C',
        )
        cls.stem_img = QuestionImage.objects.create(
            question=cls.locked, page_number=1, role='primary', caption='Chest X-ray: pneumothorax',
        )
        cls.expl_img = QuestionImage.objects.create(question=cls.locked, page_number=1, role='primary')
        Question.objects.filter(pk=cls.locked.pk).update(
            explanation=f'See [[img:{cls.expl_img.id}]] for the answer.',
        )

    def test_sources_never_expose_raw_text_to_non_admins(self):
        for user in (None, self.free, self.premium):
            res = _client(user).get(f'/api/questions/{self.locked.id}/sources/')
            self.assertEqual(res.status_code, 200)
            self.assertEqual(len(res.data), 1)
            self.assertNotIn('original_text', res.data[0])
            self.assertNotIn('extracted_text', res.data[0])
            self.assertEqual(res.data[0]['recall_source_filename'], 'recall.pdf')
        admin = _client(self.admin).get(f'/api/questions/{self.locked.id}/sources/')
        self.assertEqual(admin.data[0]['original_text'], 'Q1 ... Ans: C. Explanation: gamma')

    def test_sources_of_archived_question_404_for_students(self):
        Question.objects.filter(pk=self.locked.pk).update(is_active=False)
        self.assertEqual(_client().get(f'/api/questions/{self.locked.id}/sources/').status_code, 404)

    def test_images_for_non_entitled_callers_hide_explanation_figures_and_captions(self):
        res = _client(self.free).get(f'/api/questions/{self.locked.id}/images/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual([row['id'] for row in res.data], [self.stem_img.id])
        self.assertEqual(res.data[0]['caption'], '')

    def test_images_for_entitled_callers_carry_runtime_roles(self):
        res = _client(self.premium).get(f'/api/questions/{self.locked.id}/images/')
        roles = {row['id']: row['role'] for row in res.data}
        self.assertEqual(roles, {self.stem_img.id: 'primary', self.expl_img.id: 'explanation'})
        self.assertEqual(
            next(r for r in res.data if r['id'] == self.stem_img.id)['caption'], 'Chest X-ray: pneumothorax',
        )


class ListVideoRedactionTests(_Base):
    def test_free_list_hides_explanation_video_of_locked_rows(self):
        Question.objects.filter(pk=self.showcase.pk).update(video_url='https://example.com/v/free.mp4')
        rows = {r['id']: r for r in _client(self.free).get('/api/questions/', {'year': 2024}).data['results']}
        self.assertIsNone(rows[self.locked.id]['video_url'])
        self.assertEqual(rows[self.showcase.id]['video_url'], 'https://example.com/v/free.mp4')
        rows = {r['id']: r for r in _client(self.premium).get('/api/questions/', {'year': 2024}).data['results']}
        self.assertEqual(rows[self.locked.id]['video_url'], self.locked.video_url)


class RecallAdminEndpointsTests(_Base):
    def test_recall_sources_and_duplicate_clusters_are_admin_only(self):
        cluster = DuplicateCluster.objects.create(canonical_question=self.locked)
        DuplicateMember.objects.create(cluster=cluster, question=self.locked, similarity_score=1.0)
        DuplicateMember.objects.create(cluster=cluster, question=self.showcase, similarity_score=0.95)
        for path in ('recall_sources', 'duplicate_clusters'):
            self.assertIn(_client().get(f'/api/questions/{path}/').status_code, (401, 403), path)
            self.assertEqual(_client(self.free).get(f'/api/questions/{path}/').status_code, 403, path)
            self.assertEqual(_client(self.admin).get(f'/api/questions/{path}/').status_code, 200, path)
        rows = _client(self.admin).get('/api/questions/duplicate_clusters/').data
        self.assertEqual(rows[0]['member_count'], 2)

    def test_recall_search_rejects_malformed_params_instead_of_500(self):
        for params in ({'year': 'abc'}, {'subject': 'x'}, {'topic': '1.5'}, {'page_size': 'ten'},
                       {'min_confidence': 'nan'}, {'min_confidence': 'high'}):
            res = _client().get('/api/questions/recall_search/', params)
            self.assertEqual(res.status_code, 400, params)
        res = _client().get('/api/questions/recall_search/', {'page_size': -5, 'page': 0})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['page_size'], 1)
        self.assertEqual(res.data['page'], 1)


class ChatAssistantTests(_Base):
    def _chat(self, user, **data):
        return _client(user).post('/api/questions/chat/', {'message': 'Explain this', **data}, format='json')

    def _patched_service(self, reply='A real tutor answer'):
        patcher = mock.patch('ai_engine.services.AIService')
        service_cls = patcher.start()
        self.addCleanup(patcher.stop)
        service_cls.return_value.ask_tutor.return_value = reply
        return service_cls.return_value.ask_tutor

    def test_answer_of_a_locked_context_question_is_never_injected(self):
        ask = self._patched_service()
        self.assertEqual(self._chat(self.free, context_question_id=self.locked.id).status_code, 200)
        self.assertEqual(ask.call_args[0][1], '')
        self._chat(self.premium, context_question_id=self.locked.id)
        self.assertIn('Correct Answer: C', ask.call_args[0][1])

    def test_showcase_context_is_injected_for_free_users(self):
        ask = self._patched_service()
        self._chat(self.free, context_question_id=self.showcase.id)
        self.assertIn('Correct Answer: C', ask.call_args[0][1])

    def test_bad_or_inactive_context_ids_do_not_500(self):
        ask = self._patched_service()
        inactive = _question(self.subject, 9, is_active=False)
        for value in ('abc', '', None, 99999999, inactive.id):
            res = self._chat(self.premium, context_question_id=value)
            self.assertEqual(res.status_code, 200, value)
            self.assertEqual(ask.call_args[0][1], '', value)

    def test_free_tier_daily_cap_applies(self):
        self._patched_service()
        self.assertEqual(self._chat(self.free).status_code, 200)
        self.assertEqual(self._chat(self.free).status_code, 200)
        capped = self._chat(self.free)
        self.assertEqual(capped.status_code, 402)
        self.assertEqual(capped.data['code'], 'upgrade_required')

    def test_outage_sentence_refunds_the_token(self):
        # Same failure contract as the AI Tutor (wave 2, AI-01): never a 200
        # whose "reply" is an outage notice -- a 503 ai_unavailable when no
        # grounded offline answer exists (the composer is pinned to "none").
        from accounts.models import TokenBalance
        balance, _ = TokenBalance.objects.get_or_create(user=self.free)
        before = balance.available_tokens
        self._patched_service(reply=OUTAGE + '\n\n📚 **References**: Harrison p.1')
        with mock.patch('ai_engine.views.compose_offline_answer', return_value=None):
            res = self._chat(self.free)
        self.assertEqual(res.status_code, 503)
        self.assertEqual(res.data['code'], 'ai_unavailable')
        self.assertNotIn('reply', res.data)
        balance.refresh_from_db()
        self.assertEqual(balance.available_tokens, before)
