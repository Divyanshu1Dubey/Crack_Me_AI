"""Regression tests: AI failure is a typed signal, never a billed sentence.

Covers (audit 2026-11, group G5):
  * AIService._call_ai raises AIUnavailable when every provider fails, skips
    provider-error / outage payloads, honours AI_OFFLINE_MODE and its call
    budget (AI-01, AI-11).
  * Views refund tokens AND release the freemium slot on failure, persist and
    cache nothing, and answer with a grounded offline answer or a 503
    ``{code: 'ai_unavailable'}`` (AI-01, AI-07, FE-STU-15).
  * Explain endpoints build prompts from DB fields, never trust a client key
    for dispute flags, never overwrite curated fields (AI-02, AI-03,
    FE-STU-07, FE-STU-36, AI-15).
  * Subscribers of every plan skip the free tutor cap (FE-STU-02).
  * High-yield predictions are cached and metered (AI-10, FE-STU-22).
  * Question generation refunds on unparseable output (AI-12).
  * rag-search / knowledge stats are admin-only (AI-13).
  * Chat turns are saved server-side; the list is a plain array without
    N+1 queries (AI-09, FE-STU-14).

No test reaches a real AI provider: provider clients are never built and the
provider methods / _call_ai are patched.
"""
import json
import os
from datetime import timedelta
from unittest.mock import PropertyMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Subscription, TokenBalance
from ai_engine import offline
from ai_engine.models import ChatMessage, ChatSession
from ai_engine.models_usage import consume_ai_tutor_message, get_today_usage
from ai_engine.services import AIOutputUnusable, AIService, AIUnavailable

User = get_user_model()

PROVIDER_METHODS = (
    '_call_omniroute', '_call_groq', '_call_cerebras', '_call_gemini', '_call_cohere',
    '_call_openrouter', '_call_github_models', '_call_huggingface', '_call_mistral',
    '_call_openrouter2',
)

GROUNDED = offline.OfflineAnswer(
    grounded=True,
    answer='> Offline answer\n\n- Nephrotic syndrome causes edema by hypoalbuminaemia. *[Ghai p.12]*',
    citations=[{'book': 'Ghai', 'page': 12, 'excerpt': 'Nephrotic syndrome causes edema', 'relevance': 0.8}],
    reason=offline.REASON_PROVIDERS_DOWN,
    body='- Nephrotic syndrome causes edema by hypoalbuminaemia. *[Ghai p.12]*',
    sentences=[{'text': 'Nephrotic syndrome causes edema by hypoalbuminaemia.', 'label': 'Ghai p.12'}],
)
NOT_GROUNDED = offline.OfflineAnswer(grounded=False, answer=offline.NO_GROUNDED_ANSWER)

RICH = {
    'ai_verified_answer': 'B', 'answer_mismatch': False, 'confidence_note': '',
    'why_correct': 'Because hypoalbuminaemia lowers oncotic pressure and fluid leaks out.',
    'why_wrong': {'A': 'Not related', 'C': 'Wrong organ', 'D': 'Wrong mechanism'},
    'textbook_reference': {'book': 'Ghai', 'chapter': 'Kidney', 'page': '12', 'section': ''},
    'mnemonic': 'PALE: proteinuria, albumin low, lipids, edema',
    'core_concept': 'Oncotic pressure', 'clinical_pearl': 'Check urine protein',
    'exam_tip': 'Look for frothy urine', 'around_concepts': ['nephritic syndrome'],
    'high_yield_points': ['>3.5 g/day proteinuria'],
}


class _Base(TestCase):
    """No provider clients, no offline mode unless a test turns it on."""

    def setUp(self):
        cache.clear()
        for p in (
            patch.object(AIService, '_init_clients', lambda self: None),
            patch.dict(os.environ, {'AI_OFFLINE_MODE': ''}),
        ):
            p.start()
            self.addCleanup(p.stop)
        self.factory = APIRequestFactory()
        self.student = User.objects.create(username='g5-student', role='student')

    def post(self, view, path, data, user=None, **kwargs):
        request = self.factory.post(path, data, format='json')
        force_authenticate(request, user=user or self.student)
        return view.as_view()(request, **kwargs)

    def get(self, view, path, user=None, **params):
        request = self.factory.get(path, params)
        force_authenticate(request, user=user or self.student)
        return view.as_view()(request)

    def balance(self, user=None):
        return TokenBalance.objects.get(user=user or self.student)

    def all_providers_fail(self):
        """Patch every provider method to return nothing (no network)."""
        mocks = []
        for name in PROVIDER_METHODS:
            p = patch.object(AIService, name, return_value=None)
            mocks.append(p.start())
            self.addCleanup(p.stop)
        return mocks


# ─── Service layer ──────────────────────────────────────────────────────

class CallAIFailureContractTests(_Base):

    def test_all_providers_failing_raises_ai_unavailable(self):
        mocks = self.all_providers_fail()
        with self.assertRaises(AIUnavailable) as ctx:
            AIService()._call_ai('What is nephrotic syndrome?')
        self.assertFalse(ctx.exception.offline)
        self.assertEqual(ctx.exception.code, 'ai_unavailable')
        self.assertTrue(all(m.called for m in mocks), 'every provider is tried once')

    def test_outage_and_provider_error_payloads_are_not_answers(self):
        self.all_providers_fail()
        with patch.object(AIService, '_call_groq', return_value='Service Unavailable'), \
                patch.object(AIService, '_call_mistral',
                             return_value='All AI services are temporarily unavailable. Please try again in a moment.'):
            with self.assertRaises(AIUnavailable):
                AIService()._call_ai('q')

    def test_first_usable_answer_is_returned_and_provider_recorded(self):
        self.all_providers_fail()
        with patch.object(AIService, '_call_cohere', return_value='Real answer'):
            service = AIService()
            self.assertEqual(service._call_ai('q'), 'Real answer')
            self.assertEqual(service.last_provider, 'cohere')

    def test_offline_mode_calls_no_provider_and_builds_no_client(self):
        mocks = self.all_providers_fail()
        with patch.dict(os.environ, {'AI_OFFLINE_MODE': 'true'}), \
                patch.object(AIService, '_init_clients') as init_clients:
            service = AIService()
            with self.assertRaises(AIUnavailable) as ctx:
                service._call_ai('q')
        self.assertTrue(ctx.exception.offline)
        init_clients.assert_not_called()
        self.assertFalse(any(m.called for m in mocks))

    def test_attempt_cap_bounds_the_whole_call(self):
        attempts = []

        def fake_provider(self, prompt, system, temperature, max_tokens):
            attempts.append(self._attempt_timeout(15.0))
            return None

        for name in PROVIDER_METHODS:
            p = patch.object(AIService, name, fake_provider)
            p.start()
            self.addCleanup(p.stop)
        with patch('ai_engine.services.AI_CALL_MAX_ATTEMPTS', 3):
            with self.assertRaises(AIUnavailable):
                AIService()._call_ai('q')
        self.assertEqual(len(attempts), 3, 'stops after the attempt cap instead of trying all 10')

    def test_attempt_timeout_never_exceeds_remaining_deadline(self):
        seen = []

        def fake_provider(self, prompt, system, temperature, max_tokens):
            seen.append(self._attempt_timeout(20.0))
            return 'ok'

        self.all_providers_fail()
        with patch('ai_engine.services.AI_CALL_DEADLINE_SECONDS', 5.0):
            for name in PROVIDER_METHODS:
                p = patch.object(AIService, name, fake_provider)
                p.start()
                self.addCleanup(p.stop)
            AIService()._call_ai('q')
        self.assertLessEqual(seen[0], 5.0)

    def test_ask_tutor_failure_keeps_passages_and_adds_no_references(self):
        passages = [{'text': 'Edema in nephrotic syndrome.', 'book': 'Ghai', 'page': 3, 'score': 2.0}]

        class FakeRag:
            def search(self, q, n_results=3):
                return passages

        with patch.object(AIService, 'rag', new_callable=PropertyMock, return_value=FakeRag()), \
                patch.object(AIService, '_call_ai', side_effect=AIUnavailable('down')):
            with self.assertRaises(AIUnavailable) as ctx:
                AIService().ask_tutor('edema in nephrotic syndrome')
        self.assertEqual(ctx.exception.passages, passages)

    def test_generate_admin_explanation_reports_failure_instead_of_crashing(self):
        with patch.object(AIService, '_call_ai', side_effect=AIUnavailable('down')):
            result = AIService().generate_admin_explanation('Q?', {'A': 'a', 'B': 'b', 'C': 'c', 'D': 'd'}, 'A')
        self.assertTrue(result.get('_failed'))


class ExplainAfterAnswerServiceTests(_Base):
    OPTS = {'A': 'one', 'B': 'two', 'C': 'three', 'D': 'four'}

    def setUp(self):
        super().setUp()
        p = patch.object(AIService, 'rag', new_callable=PropertyMock, return_value=None)
        p.start()
        self.addCleanup(p.stop)

    def test_unparseable_output_is_a_failure_and_is_not_cached(self):
        with patch.object(AIService, '_call_ai', return_value='Sorry, here is some prose instead of JSON.'):
            with self.assertRaises(AIOutputUnusable):
                AIService().explain_after_answer('Stem?', self.OPTS, 'B', 'A')
        self.assertIsNone(AIService.get_cached_explanation('Stem?', self.OPTS, 'B'))

    def test_outage_never_becomes_why_correct(self):
        self.all_providers_fail()
        with self.assertRaises(AIUnavailable):
            AIService().explain_after_answer('Stem?', self.OPTS, 'B', 'A')

    def test_valid_json_is_cached_per_question_and_options(self):
        with patch.object(AIService, '_call_ai', return_value=json.dumps(RICH)):
            result = AIService().explain_after_answer('Stem?', self.OPTS, 'B', 'A')
        self.assertEqual(result['why_correct'], RICH['why_correct'])
        self.assertIsNotNone(AIService.get_cached_explanation('Stem?', self.OPTS, 'B'))
        shuffled = {'A': 'two', 'B': 'one', 'C': 'three', 'D': 'four'}
        self.assertIsNone(AIService.get_cached_explanation('Stem?', shuffled, 'B'),
                          'duplicates with shuffled options must not share an explanation')
        self.assertNotEqual(AIService.explanation_cache_key('Stem?', self.OPTS, 'B', 1),
                            AIService.explanation_cache_key('Stem?', self.OPTS, 'B', 2))

    def test_json_wrapped_in_prose_still_parses(self):
        with patch.object(AIService, '_call_ai', return_value='Here you go:\n' + json.dumps(RICH) + '\nThanks'):
            result = AIService().explain_after_answer('Stem?', self.OPTS, 'B', 'B')
        self.assertTrue(result['is_correct'])


class GenerateQuestionsServiceTests(_Base):
    def setUp(self):
        super().setUp()
        p = patch.object(AIService, 'rag', new_callable=PropertyMock, return_value=None)
        p.start()
        self.addCleanup(p.stop)

    def test_prose_output_raises_and_never_exposes_raw(self):
        with patch.object(AIService, '_call_ai', return_value='I cannot produce JSON today.'):
            with self.assertRaises(AIOutputUnusable):
                AIService().generate_questions('Medicine', count=2)

    def test_invalid_rows_are_dropped(self):
        rows = [
            {'question_text': 'Q1', 'option_a': 'a', 'option_b': 'b', 'option_c': 'c', 'option_d': 'd',
             'correct_answer': 'b', 'explanation': 'x'},
            {'question_text': 'Q2 missing options', 'correct_answer': 'A'},
        ]
        with patch.object(AIService, '_call_ai', return_value=json.dumps(rows)):
            out = AIService().generate_questions('Medicine', count=5)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['correct_answer'], 'B')
        self.assertNotIn('raw', out[0])


# ─── Tutor endpoints: refunds, slot release, offline answers ───────────

class TutorFailureRefundTests(_Base):

    def setUp(self):
        super().setUp()
        from ai_engine.views import AskTutorView, GenerateMnemonicView
        self.AskTutorView = AskTutorView
        self.GenerateMnemonicView = GenerateMnemonicView

    def _assert_nothing_charged(self):
        bal = self.balance()
        self.assertEqual(bal.daily_tokens_used, 0)
        self.assertEqual(bal.total_tokens_used, 0)
        self.assertEqual(get_today_usage(self.student), 0, 'freemium slot must be released')

    def test_total_failure_refunds_token_and_slot_and_serves_offline_answer(self):
        with patch.object(AIService, 'ask_tutor', side_effect=AIUnavailable('down')), \
                patch('ai_engine.views.compose_offline_answer', return_value=GROUNDED):
            resp = self.post(self.AskTutorView, '/api/ai/tutor/', {'question': 'edema in nephrotic syndrome?'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['offline'])
        self.assertFalse(resp.data['charged'])
        self.assertIn('Nephrotic syndrome', resp.data['response'])
        self.assertNotIn('temporarily unavailable', resp.data['response'].lower())
        self._assert_nothing_charged()

    def test_total_failure_without_grounded_answer_is_503_ai_unavailable(self):
        with patch.object(AIService, 'ask_tutor', side_effect=AIUnavailable('down')), \
                patch('ai_engine.views.compose_offline_answer', return_value=NOT_GROUNDED):
            resp = self.post(self.AskTutorView, '/api/ai/tutor/', {'question': 'zzz'})
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.data['code'], 'ai_unavailable')
        self.assertNotIn('response', resp.data)
        self._assert_nothing_charged()

    def test_failure_through_the_real_rotation_refunds_10_tokens(self):
        """End-to-end through _call_ai with every provider patched to fail."""
        self.all_providers_fail()
        with patch.object(AIService, 'rag', new_callable=PropertyMock, return_value=None), \
                patch('ai_engine.views.compose_offline_answer', return_value=NOT_GROUNDED):
            resp = self.post(self.GenerateMnemonicView, '/api/ai/mnemonic/', {'topic': 'pancreatitis causes'})
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.data['code'], 'ai_unavailable')
        self._assert_nothing_charged()

    def test_insufficient_tokens_gives_the_freemium_slot_back(self):
        TokenBalance.objects.create(user=self.student, daily_tokens_used=10, weekly_tokens_used=10,
                                    purchased_tokens=0)
        resp = self.post(self.GenerateMnemonicView, '/api/ai/mnemonic/', {'topic': 'x'})
        self.assertEqual(resp.status_code, 429)
        self.assertEqual(get_today_usage(self.student), 0)

    def test_offline_mode_answers_free_without_any_ai_call(self):
        with patch.dict(os.environ, {'AI_OFFLINE_MODE': '1'}), \
                patch.object(AIService, '_call_ai') as call_ai, \
                patch('ai_engine.views.compose_offline_answer', return_value=GROUNDED):
            resp = self.post(self.AskTutorView, '/api/ai/tutor/', {'question': 'edema?'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['offline'])
        self.assertEqual(resp.data['offline_reason'], 'offline_mode')
        call_ai.assert_not_called()
        self.assertFalse(TokenBalance.objects.filter(user=self.student, total_tokens_used__gt=0).exists())
        self.assertEqual(get_today_usage(self.student), 0)

    def test_success_is_charged_once(self):
        with patch.object(AIService, 'ask_tutor', return_value='A real answer'):
            resp = self.post(self.AskTutorView, '/api/ai/tutor/', {'question': 'q?'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['response'], 'A real answer')
        self.assertEqual(self.balance().daily_tokens_used, 1)
        self.assertEqual(get_today_usage(self.student), 1)

    def test_oversized_question_is_rejected(self):
        resp = self.post(self.AskTutorView, '/api/ai/tutor/', {'question': 'x' * 4001})
        self.assertEqual(resp.status_code, 400)


class SubscriberTutorCapTests(_Base):
    """FE-STU-02: every active plan skips the free 2/day tutor cap."""

    def test_one_month_subscriber_is_not_capped(self):
        from ai_engine.views import AskTutorView
        Subscription.objects.create(user=self.student, plan='1_month', status='active',
                                    expires_at=timezone.now() + timedelta(days=30))
        consume_ai_tutor_message(self.student)
        consume_ai_tutor_message(self.student)
        with patch.object(AIService, 'ask_tutor', return_value='ok'):
            resp = self.post(AskTutorView, '/api/ai/tutor/', {'question': 'third message'})
        self.assertEqual(resp.status_code, 200)

    def test_expired_subscriber_is_capped(self):
        from ai_engine.views import AskTutorView
        Subscription.objects.create(user=self.student, plan='1_month', status='active',
                                    expires_at=timezone.now() - timedelta(days=1))
        consume_ai_tutor_message(self.student)
        consume_ai_tutor_message(self.student)
        with patch.object(AIService, 'ask_tutor', return_value='ok'):
            resp = self.post(AskTutorView, '/api/ai/tutor/', {'question': 'third message'})
        self.assertEqual(resp.status_code, 402)


class RAGAnswerMeteringTests(_Base):
    def setUp(self):
        super().setUp()
        from ai_engine.views import RAGAnswerView
        self.view = RAGAnswerView

    def test_no_textbook_match_is_free(self):
        with patch.object(AIService, 'rag_answer', return_value={
            'answer': 'No matching textbook content was found for this query.', 'citations': [],
            'confidence': 'low', 'no_match': True,
        }):
            resp = self.post(self.view, '/api/ai/rag-answer/', {'question': 'q'})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['charged'])
        self.assertEqual(self.balance().daily_tokens_used, 0)
        self.assertEqual(get_today_usage(self.student), 0)

    def test_rag_unavailable_releases_slot_for_the_tutor_fallback(self):
        with patch.object(AIService, 'rag_answer', return_value=dict(AIService.TEXTBOOK_UNAVAILABLE)):
            resp = self.post(self.view, '/api/ai/rag-answer/', {'question': 'q'})
        self.assertEqual(resp.data['error'], 'textbook_search_unavailable')
        self.assertEqual(get_today_usage(self.student), 0, 'the client tutor fallback costs one slot, not two')
        self.assertEqual(self.balance().daily_tokens_used, 0)

    def test_generation_failure_answers_from_retrieved_passages(self):
        passages = [{'text': 'x', 'book': 'B', 'page': 1, 'score': 1.0}]
        with patch.object(AIService, 'rag_answer', side_effect=AIUnavailable('down', passages=passages)), \
                patch('ai_engine.views.compose_offline_answer', return_value=GROUNDED) as composer:
            resp = self.post(self.view, '/api/ai/rag-answer/', {'question': 'q'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['offline'])
        self.assertEqual(composer.call_args.kwargs['passages'], passages)
        self.assertEqual(get_today_usage(self.student), 0)


# ─── Explain endpoints: DB-built prompts, no shared overwrites ─────────

class ExplainPersistenceTests(_Base):

    def setUp(self):
        super().setUp()
        from questions.models import Question, Subject
        from ai_engine.views import ExplainAfterAnswerView, ExplainQuestionView
        self.ExplainAfter = ExplainAfterAnswerView
        self.ExplainQuestion = ExplainQuestionView
        subject = Subject.objects.create(name='Pediatrics G5', code='PEDG5')
        self.q = Question.objects.create(
            question_text='Edema in nephrotic syndrome is due to?', option_a='Hypertension',
            option_b='Hypoalbuminaemia', option_c='Heart failure', option_d='Liver failure',
            correct_answer='B', year=2020, subject=subject,
            learning_technique='Curated study tip',
        )
        p = patch.object(AIService, 'rag', new_callable=PropertyMock, return_value=None)
        p.start()
        self.addCleanup(p.stop)

    def test_prompt_uses_db_fields_not_client_key(self):
        with patch.object(AIService, 'explain_after_answer', return_value=dict(RICH)) as explain:
            resp = self.post(self.ExplainAfter, '/api/ai/explain-answer/', {
                'question_id': self.q.id, 'question_text': 'tampered', 'correct_answer': 'D',
                'options': {'A': 'x', 'B': 'y', 'C': 'z', 'D': 'w'}, 'selected_answer': 'B',
            })
        self.assertEqual(resp.status_code, 200)
        args = explain.call_args
        self.assertEqual(args.args[0], self.q.question_text)
        self.assertEqual(args.args[1]['B'], 'Hypoalbuminaemia')
        self.assertEqual(args.args[2], 'B', 'answer key comes from the DB')
        self.q.refresh_from_db()
        self.assertEqual(json.loads(self.q.ai_explanation)['why_correct'], RICH['why_correct'])
        self.assertEqual(self.q.learning_technique, 'Curated study tip', 'curated field not overwritten')
        self.assertEqual(self.q.ai_mnemonic, RICH['mnemonic'], 'empty AI field filled')
        self.assertFalse(self.q.is_disputed)

    def test_dispute_flag_only_against_the_stored_key(self):
        mismatch = dict(RICH, ai_verified_answer='C', answer_mismatch=True)
        with patch.object(AIService, 'explain_after_answer', return_value=mismatch):
            self.post(self.ExplainAfter, '/api/ai/explain-answer/', {'question_id': self.q.id})
        self.q.refresh_from_db()
        self.assertTrue(self.q.is_disputed)

        # Ad-hoc question with a client key: nothing stored, nothing flagged.
        with patch.object(AIService, 'explain_after_answer', return_value=mismatch):
            resp = self.post(self.ExplainAfter, '/api/ai/explain-answer/', {
                'question_text': 'A generated question?', 'correct_answer': 'A',
                'options': {'A': 'p', 'B': 'q', 'C': 'r', 'D': 's'},
            })
        self.assertEqual(resp.status_code, 200)

    def test_existing_explanation_is_never_overwritten_and_is_free(self):
        self.q.ai_explanation = json.dumps(RICH)
        self.q.ai_generated_at = timezone.now()
        self.q.save()
        with patch.object(AIService, 'explain_after_answer') as explain:
            resp = self.post(self.ExplainAfter, '/api/ai/explain-answer/',
                             {'question_id': self.q.id, 'selected_answer': 'A'})
        explain.assert_not_called()
        self.assertEqual(resp.data['why_correct'], RICH['why_correct'])
        self.assertFalse(resp.data['is_correct'])
        self.assertFalse(TokenBalance.objects.filter(user=self.student, total_tokens_used__gt=0).exists())

    def test_stored_outage_sentence_is_not_served(self):
        self.q.ai_explanation = json.dumps({'why_correct': 'All AI services are temporarily unavailable. Please try again in a moment.'})
        self.q.ai_generated_at = timezone.now()
        self.q.save()
        with patch.object(AIService, 'explain_after_answer', return_value=dict(RICH)):
            resp = self.post(self.ExplainAfter, '/api/ai/explain-answer/', {'question_id': self.q.id})
        self.assertEqual(resp.data['why_correct'], RICH['why_correct'])
        self.q.refresh_from_db()
        self.assertEqual(json.loads(self.q.ai_explanation)['why_correct'], RICH['why_correct'])

    def test_failure_refunds_10_and_persists_nothing(self):
        with patch.object(AIService, 'explain_after_answer', side_effect=AIOutputUnusable('bad json')), \
                patch('ai_engine.views.compose_offline_answer', return_value=NOT_GROUNDED):
            resp = self.post(self.ExplainAfter, '/api/ai/explain-answer/', {'question_id': self.q.id})
        # The question has no curated explanation and nothing grounded: 503.
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.data['code'], 'ai_unavailable')
        self.q.refresh_from_db()
        self.assertEqual(self.q.ai_explanation, '')
        self.assertIsNone(self.q.ai_generated_at)
        self.assertEqual(self.balance().daily_tokens_used, 0)

    def test_failure_with_curated_explanation_serves_it_offline(self):
        self.q.explanation = 'Low albumin lowers plasma oncotic pressure.'
        self.q.save()
        with patch.object(AIService, 'explain_after_answer', side_effect=AIUnavailable('down')), \
                patch('ai_engine.views.compose_offline_answer', return_value=NOT_GROUNDED):
            resp = self.post(self.ExplainAfter, '/api/ai/explain-answer/',
                             {'question_id': self.q.id, 'selected_answer': 'B'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['offline'])
        self.assertEqual(resp.data['why_correct'], self.q.explanation)
        self.assertTrue(resp.data['is_correct'])

    def test_service_cache_hit_is_served_before_charging(self):
        options = {'A': 'Hypertension', 'B': 'Hypoalbuminaemia', 'C': 'Heart failure', 'D': 'Liver failure'}
        key = AIService.explanation_cache_key(self.q.question_text, options, 'B', self.q.id)
        cache.set(key, dict(RICH), 60)
        self.q.lock_explanation = True  # stored copy not used / not written
        self.q.save()
        with patch.object(AIService, 'explain_after_answer') as explain:
            resp = self.post(self.ExplainAfter, '/api/ai/explain-answer/', {'question_id': self.q.id})
        explain.assert_not_called()
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(TokenBalance.objects.filter(user=self.student, total_tokens_used__gt=0).exists())

    def test_custom_prompt_result_is_not_persisted(self):
        with patch.object(AIService, 'analyze_question', return_value='Mnemonic: PALE'):
            resp = self.post(self.ExplainQuestion, f'/api/ai/explain-question/{self.q.id}/',
                             {'prompt': 'Give me a mnemonic'}, question_id=self.q.id)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['persisted'])
        self.q.refresh_from_db()
        self.assertEqual(self.q.ai_explanation, '')

    def test_student_regenerate_does_not_replace_shared_explanation(self):
        self.q.ai_explanation = json.dumps({'analysis': 'Original shared analysis', 'context': {}})
        self.q.save()
        with patch.object(AIService, 'analyze_question', return_value='New analysis'):
            resp = self.post(self.ExplainQuestion, f'/api/ai/explain-question/{self.q.id}/',
                             {'force_regenerate': True}, question_id=self.q.id)
        self.assertEqual(resp.data['explanation'], 'New analysis')
        self.q.refresh_from_db()
        self.assertIn('Original shared analysis', self.q.ai_explanation)

        admin = User.objects.create(username='g5-admin', role='admin')
        with patch.object(AIService, 'analyze_question', return_value='Admin regenerated'):
            self.post(self.ExplainQuestion, f'/api/ai/explain-question/{self.q.id}/',
                      {'force_regenerate': True}, user=admin, question_id=self.q.id)
        self.q.refresh_from_db()
        self.assertIn('Admin regenerated', self.q.ai_explanation)

    def test_explain_question_failure_refunds_and_persists_nothing(self):
        with patch.object(AIService, 'analyze_question', side_effect=AIUnavailable('down')), \
                patch('ai_engine.views.compose_offline_answer', return_value=NOT_GROUNDED):
            resp = self.post(self.ExplainQuestion, f'/api/ai/explain-question/{self.q.id}/', {},
                             question_id=self.q.id)
        self.assertEqual(resp.status_code, 503)
        self.q.refresh_from_db()
        self.assertEqual(self.q.ai_explanation, '')
        self.assertEqual(self.balance().daily_tokens_used, 0)

    def test_stitched_markdown_has_no_python_reprs(self):
        from ai_engine.views import _stitch_explanation_markdown
        md = _stitch_explanation_markdown(dict(RICH), self.q)
        self.assertNotIn("{'", md)
        self.assertIn('- **A:** Not related', md)
        self.assertIn('Ghai, Chapter: Kidney, p. 12', md)


# ─── High-yield, generation, admin-only endpoints ──────────────────────

class HighYieldTests(_Base):
    def test_second_request_is_served_from_cache_without_ai_or_charge(self):
        from ai_engine.views import HighYieldTopicsView
        with patch.object(AIService, 'predict_high_yield_topics', return_value='## Medicine\n1. **HTN** (★★★)') as predict:
            first = self.get(HighYieldTopicsView, '/api/ai/high-yield/')
            second = self.get(HighYieldTopicsView, '/api/ai/high-yield/')
        self.assertEqual(predict.call_count, 1)
        self.assertFalse(first.data['cached'])
        self.assertTrue(second.data['cached'])
        self.assertEqual(self.balance().daily_tokens_used, 1, 'only the fresh generation is metered')

    def test_failure_refunds_and_falls_back_to_question_bank(self):
        from questions.models import Question, Subject, Topic
        from ai_engine.views import HighYieldTopicsView
        subject = Subject.objects.create(name='Medicine G5', code='MEDG5')
        topic = Topic.objects.create(subject=subject, name='Hypertension')
        for year in (2019, 2020, 2021, 2022):
            Question.objects.create(question_text=f'HTN {year}', option_a='a', option_b='b', option_c='c',
                                    option_d='d', correct_answer='A', year=year, subject=subject, topic=topic)
        with patch.object(AIService, 'predict_high_yield_topics', side_effect=AIUnavailable('down')):
            resp = self.get(HighYieldTopicsView, '/api/ai/high-yield/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['offline'])
        self.assertIn('**Hypertension** (4 PYQs in 4 years) (★★★)', resp.data['predictions'])
        self.assertEqual(self.balance().daily_tokens_used, 0)


class GenerateQuestionsViewTests(_Base):
    def test_unparseable_generation_refunds_and_returns_503(self):
        from ai_engine.views import GenerateQuestionsView
        with patch.object(AIService, 'generate_questions', side_effect=AIOutputUnusable('no json')):
            resp = self.post(GenerateQuestionsView, '/api/ai/generate-questions/', {'subject': 'Medicine'})
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.data['code'], 'ai_unavailable')
        self.assertNotIn('questions', resp.data)
        self.assertEqual(self.balance().daily_tokens_used, 0)


class AdminOnlyRetrievalTests(_Base):
    def test_students_cannot_bulk_read_textbook_passages_or_book_list(self):
        from ai_engine.views import KnowledgeStatsView, RAGSearchView
        self.assertEqual(self.post(RAGSearchView, '/api/ai/rag-search/', {'query': 'x'}).status_code, 403)
        self.assertEqual(self.get(KnowledgeStatsView, '/api/ai/knowledge/stats/').status_code, 403)

    def test_admin_rag_search_excerpts_are_capped(self):
        from ai_engine.views import RAGSearchView
        admin = User.objects.create(username='g5-admin-rag', role='admin')
        with patch.object(AIService, 'rag_search', return_value={'results': [{'text': 'y' * 5000, 'book': 'B'}]}):
            resp = self.post(RAGSearchView, '/api/ai/rag-search/', {'query': 'x', 'n_results': 50}, user=admin)
        self.assertEqual(resp.status_code, 200)
        self.assertLessEqual(len(resp.data['results'][0]['text']), RAGSearchView.RAG_SEARCH_EXCERPT_CHARS)


# ─── Chat history ───────────────────────────────────────────────────────

class ChatHistoryTests(_Base):
    def test_turns_are_saved_when_requested_and_appended_to_the_session(self):
        from ai_engine.views import AskTutorView
        with patch.object(AIService, 'ask_tutor', return_value='Answer one'):
            first = self.post(AskTutorView, '/api/ai/tutor/', {'question': 'Q one', 'save_history': True})
        session_id = first.data['chat_session_id']
        with patch.object(AIService, 'ask_tutor', return_value='Answer two'):
            self.post(AskTutorView, '/api/ai/tutor/', {'question': 'Q two', 'chat_session_id': session_id})
        session = ChatSession.objects.get(id=session_id, user=self.student)
        self.assertEqual(session.title, 'Q one')
        self.assertEqual(list(session.messages.values_list('role', 'content')),
                         [('user', 'Q one'), ('ai', 'Answer one'), ('user', 'Q two'), ('ai', 'Answer two')])

    def test_not_saved_without_opt_in_or_on_failure(self):
        from ai_engine.views import AskTutorView
        with patch.object(AIService, 'ask_tutor', return_value='Answer'):
            self.post(AskTutorView, '/api/ai/tutor/', {'question': 'Q'})
        with patch.object(AIService, 'ask_tutor', side_effect=AIUnavailable('down')), \
                patch('ai_engine.views.compose_offline_answer', return_value=NOT_GROUNDED):
            self.post(AskTutorView, '/api/ai/tutor/', {'question': 'Q', 'save_history': True})
        self.assertFalse(ChatSession.objects.filter(user=self.student).exists())

    def test_session_list_is_a_plain_array_without_n_plus_one(self):
        from ai_engine.views import ChatSessionListCreateView
        for i in range(5):
            s = ChatSession.objects.create(user=self.student, title=f'S{i}')
            ChatMessage.objects.create(session=s, role='user', content=f'hello {i}')
            ChatMessage.objects.create(session=s, role='ai', content=f'answer {i}')
        request = self.factory.get('/api/ai/chat/sessions/')
        force_authenticate(request, user=self.student)
        with self.assertNumQueries(1):
            resp = ChatSessionListCreateView.as_view()(request)
            resp.render()
        self.assertIsInstance(resp.data, list)
        self.assertEqual(len(resp.data), 5)
        self.assertEqual(resp.data[0]['message_count'], 2)
        self.assertTrue(resp.data[0]['last_message_preview'].startswith('answer'))

    def test_message_create_rejects_unknown_role(self):
        from ai_engine.views import ChatMessageCreateView
        session = ChatSession.objects.create(user=self.student)
        resp = self.post(ChatMessageCreateView, f'/api/ai/chat/sessions/{session.id}/messages/add/',
                         {'role': 'system', 'content': 'x'}, session_id=session.id)
        self.assertEqual(resp.status_code, 400)
