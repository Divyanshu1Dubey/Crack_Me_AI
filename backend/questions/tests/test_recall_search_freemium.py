"""Regression tests for the freemium gate on /api/questions/recall_search/.

Fix #6 — recall_search was wired as an ``AllowAny`` ``@action`` and was
previously exempt from the showcase filter that the ``list`` and
``retrieve`` endpoints enforce. A free authenticated user could
``GET /api/questions/recall_search/?q=…`` and see every question in
the bank — including correct answers / explanations via the list
serializer — bypassing the freemium gate.

These tests verify:
  1. Free authenticated users only see FreeShowcaseQuestion rows
     (admin-curated 10 / year) in recall_search.
  2. Premium users see the full set.
  3. Admins bypass the gate.
  4. Anonymous requests still see the full set (intentional — public
     SEO/showroom value).
  5. Cache is bucketed per user — a free user's restricted result
     cannot leak to a premium user via cache poisoning.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models_freemium import FreeShowcaseQuestion
from accounts.utils import is_premium
from questions.models import Question, Subject


User = get_user_model()


def _make_question(text, year, subject):
    return Question.objects.create(
        question_text=text,
        option_a='A', option_b='B', option_c='C', option_d='D',
        correct_answer='A',
        year=year,
        subject=subject,
    )


class RecallSearchFreemiumGateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='Medicine-Recall', code='MEDR')

        cls.admin = User.objects.create_user(
            username="admin_recall",
            email="admin_recall@cracklabs.test",
            password="pw_admin_recall_123",
            role="admin",
            is_staff=True,
            is_superuser=True,
        )
        cls.free = User.objects.create_user(
            username="free_recall",
            email="free_recall@cracklabs.test",
            password="pw_free_recall_123",
        )
        # Premium user with an active subscription.
        from accounts.models import Subscription
        from django.utils import timezone
        from datetime import timedelta
        cls.premium = User.objects.create_user(
            username="premium_recall",
            email="premium_recall@cracklabs.test",
            password="pw_premium_recall_123",
        )
        Subscription.objects.create(
            user=cls.premium,
            plan='1_year',
            status='active',
            expires_at=timezone.now() + timedelta(days=365),
        )

        # Create 12 questions across two years. The first 5 in 2024 are
        # showcase, the first 5 in 2025 are showcase, the rest are not.
        cls.questions = []
        for year, qid in [(2024, 1), (2024, 2), (2024, 3), (2024, 4), (2024, 5),
                           (2024, 6), (2024, 7),
                           (2025, 1), (2025, 2), (2025, 3), (2025, 4), (2025, 5),
                           (2025, 6), (2025, 7)]:
            q = _make_question(
                f"recall_search test q{qid} year {year}",
                year,
                cls.subject,
            )
            cls.questions.append(q)

        # Showcase: 5 per year.
        for i, q in enumerate(cls.questions[:5]):
            FreeShowcaseQuestion.objects.create(question=q, year=2024, position=i)
        for i, q in enumerate(cls.questions[7:12]):
            FreeShowcaseQuestion.objects.create(question=q, year=2025, position=i)

    def _search(self, user, year=None):
        client = APIClient()
        if user is not None:
            client.force_authenticate(user=user)
        params = {}
        if year is not None:
            params["year"] = year
        return client.get("/api/questions/recall_search/", params)

    def test_anonymous_sees_full_set_by_design(self):
        """Anonymous users get the full bank — intentional SEO behaviour."""
        res = self._search(None, year=2024)
        self.assertEqual(res.status_code, 200)
        # 7 active questions for 2024 — anonymous gets them all.
        self.assertEqual(res.json()["count"], 7)

    def test_free_user_sees_only_showcase_for_year(self):
        """Free user with year=2024 → only 5 showcase rows."""
        self.assertFalse(is_premium(self.free))
        res = self._search(self.free, year=2024)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["count"], 5)

    def test_free_user_sees_only_showcase_without_year(self):
        """Free user without year filter → 10 showcase (5+5) rows."""
        res = self._search(self.free)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["count"], 10)

    def test_premium_user_sees_full_set(self):
        """Premium user with year=2024 → all 7 active rows."""
        self.assertTrue(is_premium(self.premium))
        res = self._search(self.premium, year=2024)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["count"], 7)

    def test_admin_bypasses_gate(self):
        """Admin → all rows regardless of showcase."""
        res = self._search(self.admin, year=2024)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["count"], 7)

    def test_cache_is_per_user_bucketed(self):
        """A free user's restricted query must not leak to a premium user.

        This exercises the cache_key bucket in recall_search — without the
        per-user bucket, a free user could prime the cache and a premium
        user would see the (smaller) restricted result set.
        """
        # Prime cache with a free user.
        free_res = self._search(self.free, year=2024)
        self.assertEqual(free_res.json()["count"], 5)

        # Now hit the same URL with a premium user — must see 7, not 5.
        premium_res = self._search(self.premium, year=2024)
        self.assertEqual(premium_res.json()["count"], 7)
