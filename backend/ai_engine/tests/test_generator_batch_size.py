"""AI question generator batch size: 20 MCQs per batch only where AI is unlimited.

GenerateQuestionsView (POST /api/ai/generate-questions/):
  * everyone may ask for 1-10 questions (10 tokens per batch, refunded on failure);
  * callers whose AI is unlimited -- the 1-year, legacy and admin-granted plans,
    admins and staff -- may ask for up to 20;
  * a larger batch from anyone else is a 402 ``upgrade_required`` answered before
    any token is consumed (and before the AI is called);
  * counts are clamped: below 1 -> 1, an unlimited caller's count above 20 -> 20.

No test reaches an AI provider: provider clients are never built and
AIService.generate_questions is patched.
"""
import os
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Subscription, TokenBalance, TokenTransaction
from ai_engine.services import AIOutputUnusable, AIService
from ai_engine.views import GenerateQuestionsView

User = get_user_model()

PATH = '/api/ai/generate-questions/'


def _mcqs(n):
    return [
        {
            'question_text': f'Question {i}?', 'option_a': 'a', 'option_b': 'b', 'option_c': 'c',
            'option_d': 'd', 'correct_answer': 'A', 'explanation': '**Harrison** ch. 1',
            'difficulty': 'medium', 'subject': 'Medicine', 'topic': 'General',
        }
        for i in range(n)
    ]


class GeneratorBatchSizeTests(TestCase):
    def setUp(self):
        cache.clear()
        for p in (
            patch.object(AIService, '_init_clients', lambda self: None),
            patch.dict(os.environ, {'AI_OFFLINE_MODE': ''}),
        ):
            p.start()
            self.addCleanup(p.stop)
        self.factory = APIRequestFactory()
        self.student = User.objects.create(username='batch-student', role='student')

    # -- helpers -----------------------------------------------------------

    def post(self, data, user=None):
        request = self.factory.post(PATH, {'subject': 'Medicine', **data}, format='json')
        force_authenticate(request, user=user or self.student)
        return GenerateQuestionsView.as_view()(request)

    def generate(self, data, user=None, side_effect=None):
        """POST with AIService.generate_questions patched; returns (response, mock)."""
        kwargs = {'side_effect': side_effect} if side_effect else {
            'side_effect': lambda subject, topic, difficulty, count: _mcqs(count),
        }
        with patch.object(AIService, 'generate_questions', **kwargs) as mock:
            resp = self.post(data, user=user)
        return resp, mock

    def subscribe(self, user, plan, days=365):
        expires = None if days is None else timezone.now() + timedelta(days=days)
        return Subscription.objects.create(user=user, plan=plan, status='active', expires_at=expires)

    def wallet(self, user=None):
        balance, _ = TokenBalance.objects.get_or_create(user=user or self.student)
        balance.refresh_from_db()
        return (balance.daily_tokens_used, balance.weekly_tokens_used,
                balance.purchased_tokens, balance.feedback_credits)

    def assert_upgrade_required(self, resp):
        self.assertEqual(resp.status_code, 402)
        self.assertEqual(resp.data['code'], 'upgrade_required')
        self.assertEqual(resp.data['feature'], 'Generate up to 20 MCQs at once')
        self.assertTrue(resp.data['message'])
        self.assertIs(resp.data['charged'], False)
        self.assertEqual(resp.data['max_count'], 10)
        self.assertNotIn('questions', resp.data)

    # -- the cap -----------------------------------------------------------

    def test_free_user_asking_for_20_is_refused_before_any_token_or_ai_call(self):
        before = self.wallet()
        transactions = TokenTransaction.objects.filter(user=self.student).count()
        resp, mock = self.generate({'count': 20})
        self.assert_upgrade_required(resp)
        mock.assert_not_called()
        self.assertEqual(self.wallet(), before)
        self.assertEqual(TokenTransaction.objects.filter(user=self.student).count(), transactions)

    def test_free_user_with_purchased_tokens_is_still_refused_above_10(self):
        balance, _ = TokenBalance.objects.get_or_create(user=self.student)
        balance.purchased_tokens = 500
        balance.save()
        for count in (11, 15, 21, 500):
            resp, mock = self.generate({'count': count})
            self.assert_upgrade_required(resp)
            mock.assert_not_called()
        balance.refresh_from_db()
        self.assertEqual(balance.purchased_tokens, 500)
        self.assertEqual(balance.daily_tokens_used, 0)

    def test_metered_subscription_plans_are_capped_at_10(self):
        for plan in ('1_month', '3_months', 'scholarship_1_month'):
            user = User.objects.create(username=f'batch-{plan}', role='student')
            self.subscribe(user, plan, days=30)
            before = self.wallet(user)
            resp, mock = self.generate({'count': 15}, user=user)
            self.assert_upgrade_required(resp)
            mock.assert_not_called()
            self.assertEqual(self.wallet(user), before, plan)

    def test_expired_one_year_plan_is_capped_at_10(self):
        self.subscribe(self.student, '1_year', days=-1)
        resp, mock = self.generate({'count': 20})
        self.assert_upgrade_required(resp)
        mock.assert_not_called()

    def test_upgrade_required_comes_before_offline_mode(self):
        with patch.dict(os.environ, {'AI_OFFLINE_MODE': '1'}):
            resp, mock = self.generate({'count': 20})
        self.assert_upgrade_required(resp)
        mock.assert_not_called()

    def test_free_user_may_generate_up_to_10_for_10_tokens(self):
        resp, mock = self.generate({'count': 10})
        self.assertEqual(resp.status_code, 200)
        mock.assert_called_once_with('Medicine', '', 'medium', 10)
        self.assertEqual(resp.data['count'], 10)
        self.assertEqual(resp.data['cost'], 10)
        self.assertEqual(self.wallet()[0], 10)

    # -- unlimited callers -------------------------------------------------

    def test_one_year_subscriber_may_generate_20_without_tokens(self):
        self.subscribe(self.student, '1_year')
        before = self.wallet()
        resp, mock = self.generate({'count': 20})
        self.assertEqual(resp.status_code, 200)
        mock.assert_called_once_with('Medicine', '', 'medium', 20)
        self.assertEqual(len(resp.data['questions']), 20)
        self.assertEqual(self.wallet(), before)  # unlimited AI is never metered

    def test_lifetime_and_admin_granted_plans_may_generate_20(self):
        for plan in ('legacy', 'admin_grant'):
            user = User.objects.create(username=f'batch-{plan}', role='student')
            self.subscribe(user, plan, days=None)
            resp, mock = self.generate({'count': 20}, user=user)
            self.assertEqual(resp.status_code, 200, plan)
            mock.assert_called_once_with('Medicine', '', 'medium', 20)

    def test_admin_and_staff_may_generate_20(self):
        admin = User.objects.create(username='batch-admin', role='admin')
        staff = User.objects.create(username='batch-staff', role='student', is_staff=True)
        for user in (admin, staff):
            resp, mock = self.generate({'count': 20}, user=user)
            self.assertEqual(resp.status_code, 200, user.username)
            mock.assert_called_once_with('Medicine', '', 'medium', 20)

    # -- clamping and validation -------------------------------------------

    def test_counts_are_clamped(self):
        self.subscribe(self.student, '1_year')
        for requested, sent in ((50, 20), (21, 20), (15, 15), (0, 1), (-3, 1)):
            resp, mock = self.generate({'count': requested})
            self.assertEqual(resp.status_code, 200, requested)
            mock.assert_called_once_with('Medicine', '', 'medium', sent)
        free = User.objects.create(username='batch-free', role='student')
        balance, _ = TokenBalance.objects.get_or_create(user=free)
        balance.purchased_tokens = 100  # four 10-token batches; the free daily quota is 10
        balance.save()
        for requested, sent in ((0, 1), (-5, 1), (3, 3), ('7', 7)):
            resp, mock = self.generate({'count': requested}, user=free)
            self.assertEqual(resp.status_code, 200, requested)
            mock.assert_called_once_with('Medicine', '', 'medium', sent)

    def test_non_integer_count_is_a_400(self):
        resp, mock = self.generate({'count': 'twenty'})
        self.assertEqual(resp.status_code, 400)
        mock.assert_not_called()

    # -- refunds -------------------------------------------------------------

    def test_failed_batch_is_refunded(self):
        resp, mock = self.generate({'count': 10}, side_effect=AIOutputUnusable('no json'))
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.data['code'], 'ai_unavailable')
        mock.assert_called_once()
        self.assertEqual(self.wallet()[0], 0)

    def test_failed_unlimited_batch_of_20_charges_nothing(self):
        self.subscribe(self.student, '1_year')
        before = self.wallet()
        resp, mock = self.generate({'count': 20}, side_effect=AIOutputUnusable('no json'))
        self.assertEqual(resp.status_code, 503)
        mock.assert_called_once_with('Medicine', '', 'medium', 20)
        self.assertEqual(self.wallet(), before)
