"""Tests for the PYQ list freemium filter (Task 6).

For free (non-premium) users, the QuestionViewSet.list endpoint must
restrict the queryset to questions Curated into accounts.FreeShowcaseQuestion
for the requested year. Premium users and admins see everything.

The annotation `is_showcase: bool` is added to every row so the frontend
can render a "Premium" badge on non-showcase rows even when the user
deep-links to one.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models_freemium import FreeShowcaseQuestion
from questions.models import Question, Subject
from questions.views import QuestionViewSet


User = get_user_model()


class FreemiunQuestionListFilterTests(TestCase):
    """Verify the queryset filter for free users is `FreeShowcaseQuestion` only."""

    @classmethod
    def setUpTestData(cls):
        cls.track = Subject  # placeholder; real fixture is in `_make_user` etc.
        cls.subject = Subject.objects.create(name='Medicine', code='MED')
        # 15 questions in 2024 and 15 in 2023
        cls.questions_2024 = [
            Question.objects.create(
                question_text=f'2024 Q{i}',
                option_a='A', option_b='B', option_c='C', option_d='D',
                correct_answer='A', year=2024, subject=cls.subject,
            )
            for i in range(15)
        ]
        cls.questions_2023 = [
            Question.objects.create(
                question_text=f'2023 Q{i}',
                option_a='A', option_b='B', option_c='C', option_d='D',
                correct_answer='A', year=2023, subject=cls.subject,
            )
            for i in range(15)
        ]
        # Curate 10 in 2024 + 5 in 2023 (admin-curated counts)
        for i in range(10):
            FreeShowcaseQuestion.objects.create(
                question=cls.questions_2024[i], year=2024, position=i + 1,
            )
        for i in range(5):
            FreeShowcaseQuestion.objects.create(
                question=cls.questions_2023[i], year=2023, position=i + 1,
            )

    def _user(self, *, is_admin=False, is_premium=False):
        # Unique username per test instance so the test is hermetic
        suffix = f'{int(is_admin)}-{int(is_premium)}-{self._seq()}'
        user = User.objects.create(
            username=f'freemium-q-{suffix}',
            role='admin' if is_admin else 'student',
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

    _seq = TestCase._seq if hasattr(TestCase, '_seq') else None
    @classmethod
    def _seq(cls):
        cls._counter = getattr(cls, '_counter', 0) + 1
        return cls._counter

    def _list(self, user, year=None):
        factory = APIRequestFactory()
        url = '/api/questions/'
        if year is not None:
            url += f'?year={year}'
        request = factory.get(url)
        force_authenticate(request, user=user)
        view = QuestionViewSet.as_view({'get': 'list'})
        # Set the kwargs the view expects
        view.kwargs = {}
        response = view(request)
        return response

    def _ids(self, response):
        data = response.data if hasattr(response, 'data') else response
        # Handle paginated and non-paginated responses
        if isinstance(data, dict) and 'results' in data:
            return {row['id'] for row in data['results']}
        return {row['id'] for row in data}

    def test_free_user_sees_only_showcase_for_year_2024(self):
        """Free user + year=2024 → only the 10 curated questions."""
        free = self._user()
        response = self._list(free, year=2024)
        self.assertEqual(response.status_code, 200)
        ids = self._ids(response)
        expected = {q.id for q in self.questions_2024[:10]}
        self.assertEqual(ids, expected)

    def test_free_user_sees_only_showcase_for_year_2023(self):
        """Free user + year=2023 → only the 5 curated questions."""
        free = self._user()
        response = self._list(free, year=2023)
        self.assertEqual(response.status_code, 200)
        ids = self._ids(response)
        expected = {q.id for q in self.questions_2023[:5]}
        self.assertEqual(ids, expected)

    def test_free_user_sees_all_showcase_across_years(self):
        """Free user + no year filter → all curated (10 + 5 = 15)."""
        free = self._user()
        response = self._list(free)
        self.assertEqual(response.status_code, 200)
        ids = self._ids(response)
        expected = {q.id for q in self.questions_2024[:10] + self.questions_2023[:5]}
        self.assertEqual(ids, expected)

    def test_premium_user_sees_all_questions(self):
        """Premium user sees the full list."""
        premium = self._user(is_premium=True)
        response = self._list(premium, year=2024)
        self.assertEqual(response.status_code, 200)
        ids = self._ids(response)
        self.assertEqual(len(ids), 15)

    def test_admin_user_sees_all_questions(self):
        """Admin bypasses the showcase filter."""
        admin = self._user(is_admin=True)
        response = self._list(admin, year=2024)
        self.assertEqual(response.status_code, 200)
        ids = self._ids(response)
        self.assertEqual(len(ids), 15)

    def test_each_showcase_row_has_is_showcase_true(self):
        """Rows that are in FreeShowcaseQuestion get `is_showcase=True`."""
        free = self._user()
        response = self._list(free, year=2024)
        data = response.data if hasattr(response, 'data') else response
        rows = data['results'] if isinstance(data, dict) and 'results' in data else data
        self.assertTrue(all(row.get('is_showcase') is True for row in rows))

    def test_non_showcase_row_has_is_showcase_false(self):
        """Premium user sees non-showcase rows marked `is_showcase=False`."""
        premium = self._user(is_premium=True)
        response = self._list(premium, year=2024)
        data = response.data if hasattr(response, 'data') else response
        rows = data['results'] if isinstance(data, dict) and 'results' in data else data
        showcases = [r for r in rows if r.get('is_showcase')]
        nonshowcase = [r for r in rows if not r.get('is_showcase')]
        self.assertEqual(len(showcases), 10)
        self.assertEqual(len(nonshowcase), 5)
