"""The performance trend shows stored test titles the way students see them:
a subject test generated on the loader's "Imported" bucket reads
"Expert Curated — 20 Questions"."""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from tests_engine.models import Test, TestAttempt

User = get_user_model()


class PerformanceTrendTitleTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='trend-title-u', password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _attempt(self, title):
        test = Test.objects.create(title=title, test_type='subject')
        return TestAttempt.objects.create(user=self.user, test=test, is_completed=True, completed_at=timezone.now(),
                                          correct_count=3, incorrect_count=1, unanswered_count=0)

    def test_loader_subject_title_is_shown_as_expert_curated(self):
        self._attempt('Imported — 20 Questions')
        self._attempt('Imported Diseases — 20 Questions')
        titles = [row['test_title'] for row in self.client.get('/api/analytics/performance-trend/').data['trend']]
        self.assertIn('Expert Curated — 20 Questions', titles)
        self.assertIn('Imported Diseases — 20 Questions', titles)
        self.assertNotIn('Imported — 20 Questions', titles)
