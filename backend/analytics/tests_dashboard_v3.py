"""dashboard_v3 / heatmap / revision / coverage / average-time endpoints.

They used to query TestAttempt for fields it does not have (created_at,
is_correct, question, time_spent_seconds) and SQLite-only SQL, so every
endpoint returned HTTP 500.
"""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from questions.models import Question, QuestionAttempt, Subject, Topic

User = get_user_model()


class DashboardV3Tests(TestCase):
    def setUp(self):
        from tests_engine.models import QuestionResponse, Test, TestAttempt

        cache.clear()  # every endpoint here is cached per user (dashboard_v3.CACHE_TTL)
        self.subject = Subject.objects.create(name='Dash Subject', code='DSUB')
        self.topic = Topic.objects.create(name='Dash Topic', subject=self.subject)
        qs = [Question.objects.create(
            question_text=f'Dash Q{i}', option_a='A', option_b='B', option_c='C', option_d='D',
            correct_answer='A', year=2023, subject=self.subject, topic=self.topic) for i in range(4)]
        self.user = User.objects.create_user(username='dash-u', password='x')
        test = Test.objects.create(title='Dash test', test_type='mixed')
        attempt = TestAttempt.objects.create(user=self.user, test=test, is_completed=True,
                                             completed_at=timezone.now(), time_taken_seconds=300)
        QuestionResponse.objects.create(attempt=attempt, question=qs[0], selected_answer='A',
                                        is_correct=True, time_taken_seconds=40)
        QuestionResponse.objects.create(attempt=attempt, question=qs[1], selected_answer='B',
                                        is_correct=False, time_taken_seconds=20)
        QuestionResponse.objects.create(attempt=attempt, question=qs[2], selected_answer=None,
                                        is_correct=None, time_taken_seconds=5)  # skipped
        QuestionAttempt.objects.create(user=self.user, question=qs[3], selected_answer='C', is_correct=False)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_dashboard_v3_aggregates_test_and_bank_answers(self):
        r = self.client.get('/api/analytics/dashboard_v3/?nocache=1')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['accuracy'], {'total': 3, 'correct': 1, 'accuracy_pct': 33.3})
        self.assertEqual(r.data['average_time']['average_seconds'], 30)
        weak = r.data['weak_subjects'][0]
        self.assertEqual((weak['subject'], weak['attempts'], weak['mistakes']), ('Dash Subject', 3, 2))
        self.assertEqual(r.data['weak_topics'][0]['topic'], 'Dash Topic')
        self.assertEqual(sum(d['attempts'] for d in r.data['performance_trend']), 3)
        self.assertEqual(r.data['revision_progress']['topics'][0]['total'], 3)
        self.assertEqual(r.data['pyq_coverage']['cms']['attempted'], 3)

    def test_heatmap_uses_sunday_zero_day_keys(self):
        r = self.client.get('/api/analytics/heatmap/subject/')
        self.assertEqual(r.status_code, 200, r.data)
        cells = r.data[str(self.subject.id)]
        self.assertEqual(sum(c['n'] for c in cells.values()), 3)
        today = str((timezone.localtime().weekday() + 1) % 7)
        self.assertIn(today, cells)

    def test_other_v3_endpoints_respond(self):
        for path in ('/api/analytics/revision_progress/', '/api/analytics/pyq_coverage/',
                     '/api/analytics/average_time/', '/api/analytics/search_analytics/'):
            self.assertEqual(self.client.get(path).status_code, 200, path)
