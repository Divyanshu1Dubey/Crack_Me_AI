"""Tests for the AI Tutor 2/day freemium quota.

The plan in `docs/superpowers/plans/2026-08-02-freemium-conversion-layer.md`
(Task 5) calls for the AI tutor endpoints — AskTutorView, GenerateMnemonicView,
ExplainConceptView, AnalyzeQuestionView, RAGAnswerView — to refuse the third
free-user message per day with a 402 carrying `code: 'upgrade_required'`.

Premium/admin users bypass the cap entirely.

These tests pin the behaviour of `_check_ai_tutor_quota` directly (unit-style)
and one end-to-end behaviour through `AskTutorView` to make sure the gate
fires in a real view flow.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from ai_engine.models_usage import (
    consume_ai_tutor_message,
    get_today_usage,
)


User = get_user_model()


class AITutorQuotaHelperTests(TestCase):
    """Unit tests for the `_check_ai_tutor_quota` helper."""

    _seq = 0

    def _user(self, *, is_admin=False, is_superuser=False, is_premium=False):
        cls = AITutorQuotaHelperTests
        cls._seq += 1
        user = User.objects.create(
            username=f'freemium-{int(is_admin)}-{int(is_premium)}-{cls._seq}',
            role='admin' if is_admin else 'student',
            is_superuser=is_superuser,
        )
        if is_premium:
            from accounts.models import Subscription
            from django.utils import timezone
            from datetime import timedelta
            Subscription.objects.create(
                user=user,
                plan='1_year',
                status='active',
                expires_at=timezone.now() + timedelta(days=365),
            )
        return user

    def test_check_returns_none_for_admin(self):
        """Admin users never see the upgrade modal — bypass entirely."""
        from ai_engine.views import _check_ai_tutor_quota
        admin = self._user(is_admin=True)
        # Even with 100 messages used, admin still bypasses
        for _ in range(5):
            consume_ai_tutor_message(admin)
        self.assertIsNone(_check_ai_tutor_quota(admin))

    def test_check_returns_none_for_premium_user(self):
        """Premium (active subscription) bypasses the 2/day cap."""
        from ai_engine.views import _check_ai_tutor_quota
        premium = self._user(is_premium=True)
        for _ in range(5):
            consume_ai_tutor_message(premium)
        self.assertIsNone(_check_ai_tutor_quota(premium))

    def test_check_allows_first_two_messages_for_free_user(self):
        """Free user with 0 or 1 messages used → still allowed."""
        from ai_engine.views import _check_ai_tutor_quota
        free = self._user()
        # 0 messages
        self.assertIsNone(_check_ai_tutor_quota(free))
        # After the helper above, used = 1. Second call should still pass.
        self.assertIsNone(_check_ai_tutor_quota(free))
        # After the helper above, used = 2 (cap reached, but check still passes)
        # The THIRD call would be blocked (covered by test_check_blocks_third_message_for_free_user).

    def test_check_blocks_third_message_for_free_user(self):
        """Free user's 3rd message → 402 Response with upgrade_required code."""
        from ai_engine.views import _check_ai_tutor_quota
        from rest_framework.response import Response

        free = self._user()
        # Two messages succeed
        consume_ai_tutor_message(free)
        consume_ai_tutor_message(free)
        # Third message: helper returns a Response object (not None)
        result = _check_ai_tutor_quota(free)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, Response)
        self.assertEqual(result.status_code, 402)
        self.assertEqual(result.data.get('code'), 'upgrade_required')
        self.assertEqual(result.data.get('feature'), 'AI Tutor')
        # Counter should NOT have incremented (cap blocks BEFORE consume)
        self.assertEqual(get_today_usage(free), 2)

    def test_counter_persists_per_day(self):
        """`get_today_usage` reflects the in-memory AITutorDailyUsage row."""
        free = self._user()
        self.assertEqual(get_today_usage(free), 0)
        consume_ai_tutor_message(free)
        consume_ai_tutor_message(free)
        self.assertEqual(get_today_usage(free), 2)


class AskTutorViewFreemiumGateTests(TestCase):
    """End-to-end smoke test: AskTutorView returns 402 for free user on 3rd msg."""

    def setUp(self):
        self.user = User.objects.create(username='freemium-asktutor')

    def _post(self, user, payload):
        factory = APIRequestFactory()
        request = factory.post('/api/ai/tutor/', payload, format='json')
        force_authenticate(request, user=user)
        return request

    def test_third_message_returns_402(self):
        """After two `consume_ai_token` returns (1, 2), the third call returns 402."""
        from ai_engine.views import AskTutorView

        # Pre-charge two messages for today
        consume_ai_tutor_message(self.user)
        consume_ai_tutor_message(self.user)

        request = self._post(self.user, {'question': 'What is X?'})

        # Mock out the token consume (so we only test the quota layer)
        # and the AI call (so we don't hit the round-robin). Patch the
        # symbol the view looks up at call time, not the source module.
        from unittest.mock import patch
        with patch('ai_engine.views.consume_ai_token') as mock_consume, \
             patch('ai_engine.views.AIService.ask_tutor') as mock_ai:
            mock_consume.return_value = (True, None)
            mock_ai.return_value = 'mocked answer'
            response = AskTutorView.as_view()(request)

        self.assertEqual(response.status_code, 402)
        self.assertEqual(response.data.get('code'), 'upgrade_required')

    def test_first_message_passes_through(self):
        """First message (0 used) should NOT be blocked by the quota gate."""
        from ai_engine.views import AskTutorView

        request = self._post(self.user, {'question': 'Hello?'})

        from unittest.mock import patch
        with patch('ai_engine.views.consume_ai_token') as mock_consume, \
             patch('ai_engine.views.AIService.ask_tutor') as mock_ai:
            mock_consume.return_value = (True, None)
            mock_ai.return_value = 'mocked answer'
            response = AskTutorView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.get('response'), 'mocked answer')


class PremiumUserBypassIntegrationTests(TestCase):
    """A premium user (with active subscription) is never blocked."""

    def test_premium_user_passes_through_after_two_messages(self):
        from django.utils import timezone
        from datetime import timedelta
        from accounts.models import Subscription
        from ai_engine.views import AskTutorView

        user = User.objects.create(username='premium-bypass-test')
        Subscription.objects.create(
            user=user,
            plan='1_year',
            status='active',
            expires_at=timezone.now() + timedelta(days=365),
        )
        # Pre-charge two messages
        consume_ai_tutor_message(user)
        consume_ai_tutor_message(user)

        factory = APIRequestFactory()
        request = factory.post('/api/ai/tutor/', {'question': 'q'}, format='json')
        force_authenticate(request, user=user)

        from unittest.mock import patch
        with patch('ai_engine.views.consume_ai_token') as mock_consume, \
             patch('ai_engine.views.AIService.ask_tutor') as mock_ai:
            mock_consume.return_value = (True, None)
            mock_ai.return_value = 'unlocked answer'
            response = AskTutorView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.get('response'), 'unlocked answer')
