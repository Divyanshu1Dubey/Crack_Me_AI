"""Wave-4 Z9 (questions app): bounded free-text input -- the floating-dock
chat message, recall_search's ``q`` tokens / keyword filters / cache key,
and the question bank's ``?search=`` terms.

No AI provider, Supabase or network call is made: every AI entry point is
patched.
"""
from __future__ import annotations

import re
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Subscription, TokenBalance
from questions import recall_search
from questions.models import Question, Subject

User = get_user_model()


def _client(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user)
    return client


def _like_count(captured, table='questions_question'):
    """LIKE predicates in the widest captured query on ``table``."""
    counts = [len(re.findall(r'\bLIKE\b', q['sql'])) for q in captured.captured_queries if table in q['sql']]
    return max(counts) if counts else 0


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='Z9 Wave4 Bounds', code='Z9B4')
        for i in range(3):
            Question.objects.create(
                question_text=f'Gamma deficiency causes delta syndrome {i}', option_a='alpha', option_b='beta',
                option_c='gamma', option_d='delta', correct_answer='C', year=2024, subject=cls.subject,
            )
        cls.premium = User.objects.create_user(username='z9b4-premium', email='z9b4-premium@example.com',
                                               password='unused-pw-1')
        Subscription.objects.create(user=cls.premium, plan='1_year', status='active',
                                    expires_at=timezone.now() + timedelta(days=365))

    def setUp(self):
        cache.clear()


class ChatMessageLengthTests(_Base):
    def _post(self, message):
        return _client(self.premium).post('/api/questions/chat/', {'message': message}, format='json')

    def test_an_over_long_message_is_rejected_before_any_charge(self):
        balance, _ = TokenBalance.objects.get_or_create(user=self.premium)
        before = balance.available_tokens
        with mock.patch('ai_engine.services.AIService') as service:
            res = self._post('word ' * 801)   # 4005 characters once stripped
        self.assertEqual(res.status_code, 400)
        self.assertIn('too long', res.data['error'])
        service.return_value.ask_tutor.assert_not_called()
        balance.refresh_from_db()
        self.assertEqual(balance.available_tokens, before)

    def test_offline_mode_rejects_it_without_running_the_composer(self):
        with mock.patch('ai_engine.views.ai_offline_mode', return_value=True), \
                mock.patch('ai_engine.views.compose_offline_answer') as compose:
            res = self._post('x' * 4001)
        self.assertEqual(res.status_code, 400)
        compose.assert_not_called()

    def test_a_message_at_the_limit_still_reaches_the_tutor(self):
        with mock.patch('ai_engine.services.AIService') as service:
            service.return_value.ask_tutor.return_value = 'A real tutor answer'
            res = self._post('y' * 4000)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['reply'], 'A real tutor answer')
        self.assertEqual(len(service.return_value.ask_tutor.call_args[0][0]), 4000)


class RecallSearchBoundsTests(_Base):
    def _get(self, params, user=None):
        return _client(user).get('/api/questions/recall_search/', params)

    def test_q_tokens_are_capped_deduplicated_and_trimmed(self):
        tokens = recall_search._q_tokens('Gamma gamma GAMMA a ' + ' '.join(f't{i:03d}' for i in range(50)))
        self.assertEqual(len(tokens), recall_search.MAX_Q_TOKENS)
        self.assertEqual(tokens[0], 'Gamma')
        self.assertNotIn('a', tokens)
        self.assertEqual(recall_search._q_tokens('z' * 500), ['z' * recall_search.MAX_Q_TOKEN_CHARS])

    def test_a_huge_anonymous_q_runs_a_bounded_query(self):
        q = ' '.join(f'q{i:04d}' for i in range(1300))
        with CaptureQueriesContext(connection) as captured:
            res = self._get({'q': q})
        self.assertEqual(res.status_code, 200)
        # 8 tokens x 5 text fields, plus the whole-phrase filter and the
        # image-role checks of the modality facet; it was 1,300 x 5.
        bound = recall_search.MAX_Q_TOKENS * 5 + 10
        self.assertLessEqual(_like_count(captured), bound)
        with CaptureQueriesContext(connection) as captured:
            res = self._get({'q': q}, user=self.premium)
        self.assertEqual(res.status_code, 200)
        self.assertLessEqual(_like_count(captured), bound)

    def test_normal_queries_still_match(self):
        res = self._get({'q': 'gamma deficiency'})
        self.assertEqual(res.data['count'], 3)
        res = self._get({'drug': 'delta syndrome'})
        self.assertEqual(res.data['count'], 3)

    def test_keyword_filters_are_cut(self):
        with CaptureQueriesContext(connection) as captured:
            res = self._get({'drug': 'delta ' + 'x' * 5000, 'image_ocr': 'y' * 5000})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['count'], 0)
        longest = max((p for q in captured.captured_queries for p in re.findall(r"'%[^']*%'", q['sql'])),
                      key=len, default='')
        self.assertLessEqual(len(longest), recall_search.MAX_KEYWORD_CHARS + 4)

    def test_a_throwaway_param_no_longer_misses_the_cache(self):
        self.assertEqual(self._get({'q': 'gamma', 'junk': '1'}).status_code, 200)
        with CaptureQueriesContext(connection) as captured:
            res = self._get({'junk': '2', 'q': 'gamma'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['count'], 3)
        self.assertFalse([q for q in captured.captured_queries if 'questions_question' in q['sql']])
        # A different search is a different entry.
        self.assertEqual(self._get({'q': 'nothing-matches-this'}).data['count'], 0)


class BankSearchTermBoundsTests(_Base):
    def test_search_terms_are_capped(self):
        from crack_cms.filters import MAX_SEARCH_TERMS

        terms = ','.join(['e'] * 2000)
        with CaptureQueriesContext(connection) as captured:
            res = _client().get('/api/questions/', {'search': terms})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['count'], 3)
        self.assertLessEqual(_like_count(captured), MAX_SEARCH_TERMS)
        many = ' '.join(f'w{i}' for i in range(40))
        with CaptureQueriesContext(connection) as captured:
            _client().get('/api/questions/', {'search': many})
        self.assertLessEqual(_like_count(captured), MAX_SEARCH_TERMS)

    def test_normal_search_is_unchanged(self):
        res = _client().get('/api/questions/', {'search': 'gamma syndrome'})
        self.assertEqual(res.data['count'], 3)
        res = _client().get('/api/questions/', {'search': 'gamma "syndrome 1"'})
        self.assertEqual(res.data['count'], 1)
