"""Infrastructure/config regressions, wave 4 (group Z9): the bounded DRF
search filter (default backend) and the opt-in PostgreSQL statement
timeout.
"""
from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

BACKEND_DIR = Path(settings.BASE_DIR)


class BoundedSearchFilterTests(SimpleTestCase):
    def _terms(self, value):
        from crack_cms.filters import BoundedSearchFilter

        request = Request(APIRequestFactory().get('/x/', {'search': value}))
        return BoundedSearchFilter().get_search_terms(request)

    def test_terms_are_deduplicated_capped_and_trimmed(self):
        from crack_cms.filters import MAX_SEARCH_TERM_CHARS, MAX_SEARCH_TERMS

        self.assertEqual(self._terms(','.join(['e'] * 2000)), ['e'])
        self.assertEqual(self._terms('Gamma gamma GAMMA delta'), ['Gamma', 'delta'])
        many = self._terms(' '.join(f'w{i}' for i in range(50)))
        self.assertEqual(many, [f'w{i}' for i in range(MAX_SEARCH_TERMS)])
        self.assertEqual(self._terms('z' * 500), ['z' * MAX_SEARCH_TERM_CHARS])
        # Quoted phrases still work.
        self.assertEqual(self._terms('gamma "delta syndrome"'), ['gamma', 'delta syndrome'])

    def test_it_is_the_default_search_backend(self):
        backends = settings.REST_FRAMEWORK['DEFAULT_FILTER_BACKENDS']
        self.assertIn('crack_cms.filters.BoundedSearchFilter', backends)
        self.assertNotIn('rest_framework.filters.SearchFilter', backends)
        from crack_cms.filters import BoundedSearchFilter
        from questions.views import QuestionViewSet

        self.assertIn(BoundedSearchFilter, QuestionViewSet.filter_backends)


class StatementTimeoutTests(SimpleTestCase):
    def test_the_option_is_opt_in(self):
        from crack_cms.db_config import statement_timeout_option as option

        for value in (None, '', '0', '-5', 'abc', ' '):
            self.assertEqual(option(value), '', value)
        self.assertEqual(option('15000'), '-c statement_timeout=15000')
        self.assertEqual(option(' 2500 '), '-c statement_timeout=2500')

    def test_settings_apply_it_to_postgresql_only(self):
        text = (BACKEND_DIR / 'crack_cms' / 'settings.py').read_text(encoding='utf-8')
        self.assertIn("statement_timeout_option(os.getenv('DB_STATEMENT_TIMEOUT_MS'))", text)
        # The test database is SQLite: no libpq options there.
        if not settings.DATABASES['default']['ENGINE'].endswith('postgresql'):
            self.assertNotIn('options', settings.DATABASES['default'].get('OPTIONS', {}))
