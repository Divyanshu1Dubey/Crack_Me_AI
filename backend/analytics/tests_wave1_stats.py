"""Analytics numbers (AN-13 / AN-19 / AN-20 / AN-22 / AN-30 / FE-STU-17 and
the earlier StudyStreak / admin-funnel fix concerns)."""
import importlib
from datetime import timedelta
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from analytics.models import AnalyticsEvent, StudyStreak, UserTopicPerformance
from questions.models import Question, QuestionFeedback, Subject, Topic
from tests_engine.models import QuestionResponse, Test, TestAttempt

User = get_user_model()


class SubjectLevelPerformanceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='stats-u', password='x')
        self.subject = Subject.objects.create(name='General Medicine', code='MED')
        self.topic = Topic.objects.create(name='Cardiology', subject=self.subject)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_subject_level_rows_are_unique(self):
        UserTopicPerformance.objects.create(user=self.user, subject=self.subject, topic=None)
        with self.assertRaises(IntegrityError), transaction.atomic():
            UserTopicPerformance.objects.create(user=self.user, subject=self.subject, topic=None)
        # get_or_create keeps working (it used to raise MultipleObjectsReturned forever).
        row, created = UserTopicPerformance.objects.get_or_create(user=self.user, subject=self.subject, topic=None)
        self.assertFalse(created)

    def test_dashboard_does_not_double_count_topic_rows(self):
        UserTopicPerformance.objects.create(user=self.user, subject=self.subject, topic=None,
                                            total_attempts=10, correct_answers=6)
        UserTopicPerformance.objects.create(user=self.user, subject=self.subject, topic=self.topic,
                                            total_attempts=10, correct_answers=6)
        perf = self.client.get('/api/analytics/dashboard/').data['subject_performance']
        self.assertEqual([(p['subject'], p['total_attempts'], p['accuracy']) for p in perf],
                         [('General Medicine', 10, 60.0)])
        bundle = self.client.get('/api/analytics/dashboard/bundle/').data['dashboard']['subject_performance']
        self.assertEqual(bundle[0]['total_attempts'], 10)

    def test_topic_rows_are_used_when_no_subject_row_exists(self):
        UserTopicPerformance.objects.create(user=self.user, subject=self.subject, topic=self.topic,
                                            total_attempts=4, correct_answers=1)
        perf = self.client.get('/api/analytics/dashboard/').data['subject_performance']
        self.assertEqual(perf[0]['total_attempts'], 4)

    def test_merge_migration_helper_sums_duplicates(self):
        migration = importlib.import_module('analytics.migrations.0008_merge_duplicate_subject_performance')
        now = timezone.now()
        rows = [
            SimpleNamespace(total_attempts=3, correct_answers=2, incorrect_answers=1, total_time_seconds=30,
                            avg_confidence=4.0, last_attempted=now - timedelta(days=1)),
            SimpleNamespace(total_attempts=1, correct_answers=0, incorrect_answers=1, total_time_seconds=10,
                            avg_confidence=0.0, last_attempted=now),
        ]
        merged = migration.merged_values(rows)
        self.assertEqual((merged['total_attempts'], merged['correct_answers'], merged['incorrect_answers'],
                          merged['total_time_seconds'], merged['last_attempted']), (4, 2, 2, 40, now))
        self.assertAlmostEqual(merged['avg_confidence'], 3.0)

    def test_weak_topics_ranked_by_accuracy_with_minimum_attempts(self):
        def topic(name, total, correct):
            t = Topic.objects.create(name=name, subject=self.subject)
            UserTopicPerformance.objects.create(user=self.user, subject=self.subject, topic=t,
                                                total_attempts=total, correct_answers=correct)
        topic('Many attempts 40%', 50, 20)   # 20 correct: was ranked after the 1-attempt topic
        topic('Few attempts 0%', 1, 0)       # below the minimum: not judged
        topic('Medium 50%', 10, 5)
        topic('Strong 90%', 10, 9)
        data = self.client.get('/api/analytics/weak-topics/').data
        self.assertEqual([t['topic_name'] for t in data['weak_topics']], ['Many attempts 40%', 'Medium 50%'])
        self.assertEqual([t['topic_name'] for t in data['strong_topics']], ['Strong 90%'])


class TestHistoryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='trend-u', password='x')
        self.test = Test.objects.create(title='Trend test', test_type='mixed')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _attempt(self, days_ago, correct, incorrect, unanswered=0):
        attempt = TestAttempt.objects.create(user=self.user, test=self.test, is_completed=True,
                                             completed_at=timezone.now(), correct_count=correct,
                                             incorrect_count=incorrect, unanswered_count=unanswered)
        TestAttempt.objects.filter(pk=attempt.pk).update(started_at=timezone.now() - timedelta(days=days_ago))
        return attempt

    def test_trend_returns_latest_20_oldest_first(self):
        for day in range(25, 0, -1):  # 25 tests, one per day
            self._attempt(day, correct=day, incorrect=1)
        trend = self.client.get('/api/analytics/performance-trend/').data['trend']
        self.assertEqual(len(trend), 20)
        self.assertEqual([t['correct'] for t in trend], list(range(20, 0, -1)))  # day 20 ... day 1
        self.assertLess(trend[0]['date'], trend[-1]['date'])

    def test_score_prediction_uses_two_250_mark_papers(self):
        # 70% accuracy, 80% of questions answered.
        for day in (3, 2, 1):
            self._attempt(day, correct=56, incorrect=24, unanswered=20)
        data = self.client.get('/api/analytics/score-prediction/').data
        self.assertEqual((data['max_score'], data['max_score_per_paper']), (500, 250))
        answered = 120 * 0.8
        per_paper = round(answered * 0.7 * (250 / 120) - answered * 0.3 * (250 / 360), 1)
        self.assertEqual(data['predicted_score_paper1'], per_paper)  # 120.0
        self.assertEqual(data['predicted_score_paper2'], per_paper)
        self.assertEqual(data['predicted_score'], round(per_paper * 2, 1))
        self.assertEqual(data['attempt_rate'], 80.0)

    def test_score_prediction_uses_subject_accuracy_and_real_question_counts(self):
        for day in (3, 2, 1):
            self._attempt(day, correct=60, incorrect=60)
        ped = Subject.objects.create(name='Paediatrics', code='PED')
        UserTopicPerformance.objects.create(user=self.user, subject=ped, topic=None,
                                            total_attempts=20, correct_answers=20)
        data = self.client.get('/api/analytics/score-prediction/').data
        row = next(s for s in data['subject_predictions'] if s['code'] == 'PED')
        self.assertEqual((row['out_of'], row['predicted_correct']), (24, 24))
        # Paper I: 96 MED at the overall 50% + 24 PED at 100% beats Paper II (all at 50%).
        self.assertGreater(data['predicted_score_paper1'], data['predicted_score_paper2'])


class AdminWeakAreaTests(TestCase):
    def test_reports_are_not_multiplied_by_responses(self):
        admin = User.objects.create_user(username='wa-admin', password='x', role='admin')
        student = User.objects.create_user(username='wa-student', password='x')
        subject = Subject.objects.create(name='Surgery', code='SUR')
        q = Question.objects.create(question_text='Q', option_a='A', option_b='B', option_c='C', option_d='D',
                                    correct_answer='A', year=2024, subject=subject)
        for i in range(2):
            QuestionFeedback.objects.create(question=q, user=student, category='wrong_answer',
                                            comment=f'c{i}', is_resolved=False)
        test = Test.objects.create(title='WA', test_type='mixed')
        for i in range(5):
            attempt = TestAttempt.objects.create(user=student, test=test, is_completed=True)
            QuestionResponse.objects.create(attempt=attempt, question=q, selected_answer='A', is_correct=True)
        UserTopicPerformance.objects.create(user=student, subject=subject, topic=None, total_attempts=5)

        client = APIClient()
        client.force_authenticate(admin)
        data = client.get('/api/analytics/admin/weak-area-control/', {'user_id': student.id}).data
        row = next(r for r in data['impact_priorities'] if r['id'] == q.id)
        self.assertEqual((row['reports'], row['attempts']), (2, 5))
        for key in ('most_difficult_topics', 'cohort_weak_areas', 'student_weak_areas'):
            self.assertTrue(all(r['topic_id'] is not None for r in data[key]), key)


class StudyStreakXpTests(TestCase):
    def test_record_activity_keeps_concurrent_xp(self):
        user = User.objects.create_user(username='xp-u', password='x')
        streak = StudyStreak.objects.create(user=user, last_activity_date=timezone.localdate() - timedelta(days=1))
        # Another request awards XP after this instance was loaded.
        StudyStreak.objects.get(pk=streak.pk).add_xp(15)
        streak.record_activity()
        streak.refresh_from_db()
        self.assertEqual((streak.xp_points, streak.current_streak), (15, 1))


class PYQTrendsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.client.force_authenticate(User.objects.create_user(username='trends-u', password='x'))
        med = Subject.objects.create(name='General Medicine', code='MED')
        sur = Subject.objects.create(name='General Surgery', code='SUR')

        def q(subject, year, n, **kw):
            for i in range(n):
                Question.objects.create(question_text=f'{subject.code}{year}{i}', option_a='A', option_b='B',
                                        option_c='C', option_d='D', correct_answer='A', year=year,
                                        subject=subject, exam_source=kw.get('exam_source', 'UPSC CMS'),
                                        is_active=kw.get('is_active', True))
        q(med, 2024, 3)
        q(med, 2023, 2)
        q(sur, 2024, 1)
        q(sur, 0, 4)                       # unknown year: total only
        q(med, 2022, 5, is_active=False)   # inactive: ignored
        q(med, 2024, 7, exam_source='NEET PG')

    def test_year_by_subject_matrix(self):
        data = self.client.get('/api/analytics/pyq-trends/').data
        self.assertEqual(data['total'], 10)
        self.assertEqual(data['years'], [2024, 2023])
        self.assertEqual([(s['code'], s['count']) for s in data['subjects']], [('MED', 5), ('SUR', 1)])
        cells = {(t['year'], t['subject__code']): t['count'] for t in data['trends']}
        self.assertEqual(cells, {(2024, 'MED'): 3, (2023, 'MED'): 2, (2024, 'SUR'): 1})

    def test_exam_source_is_validated(self):
        self.assertEqual(self.client.get('/api/analytics/pyq-trends/', {'exam_source': 'NEET PG'}).data['total'], 7)
        self.assertEqual(self.client.get('/api/analytics/pyq-trends/', {'exam_source': 'x'}).status_code, 400)


class AdminFunnelTests(TestCase):
    def test_forged_signup_and_payment_events_do_not_move_the_funnel(self):
        admin = User.objects.create_superuser(username='funnel-admin', email='f@example.com', password='x')
        for name in ('sign_up', 'checkout_start', 'payment_success'):
            for i in range(5):
                AnalyticsEvent.objects.create(event_name=name, visitor_id=f'forged-{name}-{i}')
        AnalyticsEvent.objects.create(event_name='quest_streak_freeze_used', user_id=admin.id)
        client = APIClient()
        client.force_authenticate(admin)
        data = client.get('/api/analytics/admin/dashboard-data/').data
        funnel = {row['stage']: row['users'] for row in data['funnel']}
        self.assertEqual(funnel['sign_up'], User.objects.filter(date_joined__gte=timezone.now() - timedelta(days=31)).count())
        self.assertEqual((funnel['checkout_start'], funnel['payment_success']), (0, 0))
        # Server-written ledger rows are not visitors.
        self.assertEqual(data['today']['users'], 15)
