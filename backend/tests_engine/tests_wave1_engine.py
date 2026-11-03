"""Regression tests for the tests-engine fixes of the 2026-11 audit (group G3).

Covers: server-side free-test gate and test_type validation (TE-02), input
validation (TE-28), exam scoping and real paper timing (TE-07, FE-STU-13),
resumable timer / stable order / capped duration (TE-06, FE-STU-10), the
start race, idempotent-ish submit and transactional analytics (TE-05), XP
farming, private generated tests and unpublish-safe submit/review (TE-26),
separate library / own-test listing (TE-14) and the list / start N+1 fixes
(TE-04, TE-29, FE-STU-29).
"""
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models_freemium import FreeShowcaseQuestion
from analytics.models import DailyActivity, StudyStreak, UserTopicPerformance
from questions.models import DuplicateCluster, DuplicateMember, Question, QuestionImage, Subject, Topic
from tests_engine import views as te_views
from tests_engine.models import Test, TestAttempt

User = get_user_model()


def _q(subject, i, **kw):
    defaults = dict(
        question_text=f'Wave1 question {i}', option_a='A', option_b='B', option_c='C',
        option_d='D', correct_answer='A', year=2024, subject=subject,
    )
    defaults.update(kw)
    return Question.objects.create(**defaults)


def _user(name, *, role='student', premium=False):
    user = User.objects.create_user(username=name, password='x', role=role)
    if premium:
        from accounts.models import Subscription
        Subscription.objects.create(
            user=user, plan='1_year', status='active',
            expires_at=timezone.now() + timedelta(days=365),
        )
    return user


class _ApiCase(TestCase):
    def setUp(self):
        self.client = APIClient()

    def login(self, user):
        self.client.force_authenticate(user)

    def start(self, test, expect=200):
        r = self.client.post(f'/api/tests/{test.id}/start/')
        self.assertEqual(r.status_code, expect, getattr(r, 'data', None))
        return r

    def submit(self, test, attempt_id, answers):
        return self.client.post(
            f'/api/tests/{test.id}/submit/',
            {'attempt_id': attempt_id, 'answers': answers}, format='json',
        )

    def generate(self, body):
        return self.client.post('/api/tests/generate/', body, format='json')


class FreeGateAndTestTypeTests(_ApiCase):
    """TE-02: the free decision depends only on the server-side count (and,
    since wave 3, on every question being a free showcase question)."""

    def setUp(self):
        super().setUp()
        self.subject = Subject.objects.create(name='Wave1 Gate')
        for i in range(30):
            FreeShowcaseQuestion.objects.create(question=_q(self.subject, i), year=2024, position=i)
        self.login(_user('w1-gate-free'))

    def test_unknown_test_type_is_rejected(self):
        for bad in ('bogus', 'x' * 40, 123, ['daily']):
            r = self.generate({'test_type': bad, 'num_questions': 5})
            self.assertEqual(r.status_code, 400, bad)
        self.assertFalse(Test.objects.exists())

    def test_daily_is_always_twenty_questions(self):
        r = self.generate({'test_type': 'daily', 'num_questions': 500})
        self.assertEqual(r.status_code, 201, r.data)
        test = Test.objects.get(pk=r.data['id'])
        self.assertEqual(test.questions.count(), 20)
        self.assertEqual(test.num_questions, 20)
        self.assertTrue(r.data['is_free_for_current_user'])
        self.start(test)

    def test_daily_type_no_longer_bypasses_the_limit(self):
        test = Test.objects.create(title='Big daily', test_type='daily')
        test.questions.set(list(Question.objects.all()[:21]))
        r = self.client.post(f'/api/tests/{test.id}/start/')
        self.assertEqual(r.status_code, 402)
        self.assertFalse(TestAttempt.objects.filter(test=test).exists())
        rows = self.client.get('/api/tests/', {'scope': 'library'}).data['results']
        self.assertFalse(next(t for t in rows if t['id'] == test.id)['is_free_for_current_user'])


class InputValidationTests(_ApiCase):
    """TE-28: junk ids / years are a 400, never a 500 or a stored raw value."""

    def setUp(self):
        super().setUp()
        self.subject = Subject.objects.create(name='Wave1 Validation')
        self.topic = Topic.objects.create(subject=self.subject, name='Wave1 Topic')
        for i in range(5):
            _q(self.subject, i, topic=self.topic)
        self.login(_user('w1-validation', premium=True))

    def test_bad_generate_payloads(self):
        cases = [
            {'test_type': 'mixed', 'subject_id': 'abc'},
            {'test_type': 'mixed', 'topic_id': '1.5'},
            {'test_type': 'subject'},
            {'test_type': 'subject', 'subject_id': 999999},
            {'test_type': 'topic', 'topic_id': 999999},
            {'test_type': 'pyq_year', 'year': '20x9'},
            {'test_type': 'pyq_year'},
            {'test_type': 'mixed', 'exam_type': 'mars'},
        ]
        for body in cases:
            r = self.generate(body)
            self.assertEqual(r.status_code, 400, (body, getattr(r, 'data', None)))
        self.assertFalse(Test.objects.exists())

    def test_bad_pyq_simulation_payloads(self):
        for body in ({}, {'year': '20x9'}, {'year': 0}, {'year': 2024, 'paper': 3},
                     {'year': 2024, 'paper': 'one'}, {'year': 2024, 'exam_type': 'mars'}):
            r = self.client.post('/api/tests/pyq-simulation/', body, format='json')
            self.assertEqual(r.status_code, 400, (body, getattr(r, 'data', None)))
        self.assertFalse(Test.objects.exists())

    def test_subject_and_topic_tests_store_validated_relations(self):
        r = self.generate({'test_type': 'subject', 'subject_id': str(self.subject.id)})
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Test.objects.get(pk=r.data['id']).subject_id, self.subject.id)
        r = self.generate({'test_type': 'topic', 'topic_id': self.topic.id})
        self.assertEqual(r.status_code, 201, r.data)
        test = Test.objects.get(pk=r.data['id'])
        self.assertEqual((test.topic_id, test.subject_id), (self.topic.id, self.subject.id))


class ExamScopeTests(_ApiCase):
    """TE-07 / FE-STU-13: one exam per generated test, real marking."""

    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='Wave1 Exam')  # Subject.paper defaults to 1
        cls.cms_p1 = [_q(cls.subject, i, year=2020, paper=1) for i in range(3)]
        cls.cms_p2 = [_q(cls.subject, 10 + i, year=2020, paper=2) for i in range(2)]
        cls.neet = [_q(cls.subject, 20 + i, year=2020, exam_type='neet_pg', exam_source='NEET PG') for i in range(2)]
        # Legacy import: exam_type left at the 'cms' default.
        cls.neet_legacy = [_q(cls.subject, 30 + i, year=2020, exam_source='NEET PG (recall)') for i in range(2)]
        cls.ini_legacy = [_q(cls.subject, 40, year=2020, exam_source='INI-CET (recall)')]

    def setUp(self):
        super().setUp()
        self.login(_user('w1-exam', premium=True))

    @staticmethod
    def _ids(test_id):
        return set(Test.objects.get(pk=test_id).questions.values_list('id', flat=True))

    def test_pyq_simulation_defaults_to_cms_only(self):
        r = self.client.post('/api/tests/pyq-simulation/', {'year': 2020}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self._ids(r.data['id']), {q.id for q in self.cms_p1 + self.cms_p2})
        test = Test.objects.get(pk=r.data['id'])
        self.assertEqual(test.exam_type, 'cms')
        self.assertTrue(test.title.startswith('UPSC CMS 2020'), test.title)
        self.assertEqual(test.negative_mark_value, 0.33)

    def test_pyq_simulation_other_exams_include_legacy_rows(self):
        r = self.client.post('/api/tests/pyq-simulation/', {'year': 2020, 'exam_type': 'neet_pg'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self._ids(r.data['id']), {q.id for q in self.neet + self.neet_legacy})
        test = Test.objects.get(pk=r.data['id'])
        self.assertTrue(test.title.startswith('NEET PG 2020'), test.title)
        self.assertEqual((test.exam_type, test.negative_mark_value), ('neet_pg', 0.25))

        r = self.client.post('/api/tests/pyq-simulation/', {'year': 2020, 'exam_type': 'ini_cet'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self._ids(r.data['id']), {self.ini_legacy[0].id})

        r = self.client.post('/api/tests/pyq-simulation/', {'year': 2020, 'exam_type': 'usmle'}, format='json')
        self.assertEqual(r.status_code, 404)

    def test_paper_mock_is_cms_and_respects_the_question_paper(self):
        r = self.generate({'test_type': 'paper1', 'num_questions': 5})
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self._ids(r.data['id']), {q.id for q in self.cms_p1})
        r = self.generate({'test_type': 'paper2', 'num_questions': 5})
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self._ids(r.data['id']), {q.id for q in self.cms_p2})

    def test_generated_test_carries_its_exam(self):
        r = self.generate({'test_type': 'mixed', 'exam_type': 'neet_pg', 'num_questions': 50})
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self._ids(r.data['id']), {q.id for q in self.neet + self.neet_legacy})
        self.assertEqual(r.data['exam_type'], 'neet_pg')


class PaperTimingTests(_ApiCase):
    """FE-STU-13 / TE-07: 120 minutes per CMS paper (not 180, not 120 for two)."""

    @classmethod
    def setUpTestData(cls):
        subject = Subject.objects.create(name='Wave1 Timing')
        Question.objects.bulk_create([
            Question(
                question_text=f'Timing question {i}', option_a='A', option_b='B', option_c='C',
                option_d='D', correct_answer='A', year=2021, subject=subject, paper=1 if i < 125 else 2,
            )
            for i in range(250)
        ])

    def setUp(self):
        super().setUp()
        self.login(_user('w1-timing'))

    def test_cms_paper_timing(self):
        combined = self.client.post('/api/tests/pyq-simulation/', {'year': 2021}, format='json')
        self.assertEqual(combined.status_code, 201, combined.data)
        self.assertEqual(combined.data['time_limit_minutes'], 240)
        one_paper = self.client.post('/api/tests/pyq-simulation/', {'year': 2021, 'paper': 1}, format='json')
        self.assertEqual(one_paper.data['time_limit_minutes'], 120)
        mock_paper = self.generate({'test_type': 'paper1', 'num_questions': 3})
        self.assertEqual((mock_paper.data['num_questions'], mock_paper.data['time_limit_minutes']), (120, 120))


class ResumeAndTimerTests(_ApiCase):
    """TE-06 / FE-STU-10: a reload resumes the clock and the order."""

    def setUp(self):
        super().setUp()
        subject = Subject.objects.create(name='Wave1 Timer')
        self.questions = [_q(subject, i) for i in range(6)]
        self.test = Test.objects.create(title='Timed', test_type='mixed', time_limit_minutes=30,
                                        negative_marking=False)
        self.test.questions.set(self.questions)
        self.user = _user('w1-timer', premium=True)
        self.login(self.user)

    def test_resume_keeps_the_clock_and_the_order(self):
        first = self.start(self.test).data
        self.assertFalse(first['resumed'])
        self.assertEqual(first['time_limit_seconds'], 1800)
        self.assertAlmostEqual(first['remaining_seconds'], 1800, delta=5)
        self.assertEqual(sorted(q['id'] for q in first['questions']), sorted(q.id for q in self.questions))

        TestAttempt.objects.filter(pk=first['attempt_id']).update(
            started_at=timezone.now() - timedelta(minutes=10))
        second = self.start(self.test).data
        self.assertTrue(second['resumed'])
        self.assertEqual(second['attempt_id'], first['attempt_id'])
        self.assertAlmostEqual(second['remaining_seconds'], 1200, delta=5)
        self.assertEqual([q['id'] for q in second['questions']], [q['id'] for q in first['questions']])

    def test_expired_attempt_reports_zero_and_duration_is_capped(self):
        attempt_id = self.start(self.test).data['attempt_id']
        TestAttempt.objects.filter(pk=attempt_id).update(started_at=timezone.now() - timedelta(days=3))
        again = self.start(self.test).data
        self.assertEqual((again['attempt_id'], again['remaining_seconds']), (attempt_id, 0))

        r = self.submit(self.test, attempt_id, [{'question_id': self.questions[0].id, 'selected_answer': 'A'}])
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(TestAttempt.objects.get(pk=attempt_id).time_taken_seconds, 1800)
        self.assertEqual(DailyActivity.objects.get(user=self.user).time_spent_minutes, 30)

    def test_racing_start_resumes_the_winning_attempt(self):
        winner = TestAttempt.objects.create(user=self.user, test=self.test)
        real_lookup = te_views._active_attempt
        calls = {'n': 0}

        def stale_then_real(user, test):
            # First lookup runs "before" the concurrent insert committed.
            calls['n'] += 1
            return None if calls['n'] == 1 else real_lookup(user, test)

        with mock.patch('tests_engine.views._active_attempt', side_effect=stale_then_real):
            r = self.client.post(f'/api/tests/{self.test.id}/start/')
        self.assertEqual(r.status_code, 200, getattr(r, 'data', None))
        self.assertTrue(r.data['resumed'])
        self.assertEqual(r.data['attempt_id'], winner.id)
        self.assertEqual(
            TestAttempt.objects.filter(user=self.user, test=self.test, is_completed=False).count(), 1)


class SubmitRobustnessTests(_ApiCase):
    """TE-05 / TE-26: results are never lost behind a dead retry."""

    def setUp(self):
        super().setUp()
        self.subject = Subject.objects.create(name='Wave1 Submit')
        self.questions = [_q(self.subject, i) for i in range(4)]
        self.test = Test.objects.create(title='Submit test', test_type='mixed', negative_marking=False)
        self.test.questions.set(self.questions)
        self.user = _user('w1-submit', premium=True)
        self.login(self.user)

    def _answers(self, *letters):
        return [{'question_id': q.id, 'selected_answer': letter}
                for q, letter in zip(self.questions, letters)]

    def test_repeat_submit_returns_the_stored_result(self):
        attempt_id = self.start(self.test).data['attempt_id']
        first = self.submit(self.test, attempt_id, self._answers('A', 'B'))
        self.assertEqual(first.status_code, 200, first.data)
        self.assertNotIn('responses', first.data)  # slim payload (TE-04)
        self.assertEqual((first.data['correct_count'], first.data['incorrect_count']), (1, 1))

        again = self.submit(self.test, attempt_id, self._answers('A', 'A', 'A'))
        self.assertEqual(again.status_code, 400)
        self.assertEqual(again.data['code'], 'already_submitted')
        self.assertEqual(again.data['result']['id'], attempt_id)
        self.assertEqual(again.data['result']['correct_count'], 1)

    def test_analytics_failure_does_not_lose_the_attempt(self):
        attempt_id = self.start(self.test).data['attempt_id']
        with mock.patch('tests_engine.views._record_submission_analytics', side_effect=RuntimeError('boom')):
            r = self.submit(self.test, attempt_id, self._answers('A'))
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(TestAttempt.objects.get(pk=attempt_id).is_completed)
        review = self.client.get(f'/api/tests/{self.test.id}/review/', {'attempt_id': attempt_id})
        self.assertEqual(review.status_code, 200)
        self.assertEqual(review.data['total_marks'], 4)

    def test_analytics_are_increments(self):
        DailyActivity.objects.create(user=self.user, date=timezone.localdate(),
                                     questions_attempted=5, correct_answers=2, tests_completed=2)
        attempt_id = self.start(self.test).data['attempt_id']
        r = self.submit(self.test, attempt_id, self._answers('A', 'B'))
        self.assertEqual(r.status_code, 200, r.data)
        daily = DailyActivity.objects.get(user=self.user)
        self.assertEqual((daily.questions_attempted, daily.correct_answers, daily.tests_completed), (7, 3, 3))
        perf = UserTopicPerformance.objects.get(user=self.user, subject=self.subject, topic=None)
        self.assertEqual((perf.total_attempts, perf.correct_answers, perf.incorrect_answers), (2, 1, 1))

    def test_unpublishing_does_not_break_submit_or_review(self):
        attempt_id = self.start(self.test).data['attempt_id']
        Test.objects.filter(pk=self.test.pk).update(is_published=False)
        r = self.submit(self.test, attempt_id, self._answers('A'))
        self.assertEqual(r.status_code, 200, r.data)
        review = self.client.get(f'/api/tests/{self.test.id}/review/', {'attempt_id': attempt_id})
        self.assertEqual(review.status_code, 200)
        # Visibility is still enforced where it belongs: starting again.
        self.assertEqual(self.client.post(f'/api/tests/{self.test.id}/start/').status_code, 404)

    def test_attempt_of_another_test_is_rejected(self):
        other = Test.objects.create(title='Other', test_type='mixed')
        other.questions.set(self.questions[:1])
        attempt_id = self.start(other).data['attempt_id']
        r = self.submit(self.test, attempt_id, self._answers('A'))
        self.assertEqual(r.status_code, 400)
        self.assertFalse(TestAttempt.objects.get(pk=attempt_id).is_completed)


class XpRulesTests(_ApiCase):
    """Test XP is earned once per question and once per test; empty submits
    earn nothing (previous-fix concern: XP / leaderboard farming)."""

    def setUp(self):
        super().setUp()
        self.subject = Subject.objects.create(name='Wave1 XP')
        self.questions = [_q(self.subject, i) for i in range(4)]
        self.test = Test.objects.create(title='XP test', test_type='mixed', negative_marking=False)
        self.test.questions.set(self.questions)
        self.user = _user('w1-xp', premium=True)
        self.login(self.user)

    def _xp(self):
        return StudyStreak.objects.filter(user=self.user).values_list('xp_points', flat=True).first() or 0

    def _run(self, test, letters):
        attempt_id = self.start(test).data['attempt_id']
        qs = list(test.questions.order_by('id'))
        r = self.submit(test, attempt_id, [
            {'question_id': q.id, 'selected_answer': letter} for q, letter in zip(qs, letters)
        ])
        self.assertEqual(r.status_code, 200, r.data)
        return r.data['xp_earned']

    def test_empty_submit_earns_nothing(self):
        self.assertEqual(self._run(self.test, ['', '', '', '']), 0)
        self.assertEqual(self._xp(), 0)
        self.assertFalse(DailyActivity.objects.filter(user=self.user, tests_completed__gt=0).exists())
        self.assertTrue(TestAttempt.objects.get(user=self.user, test=self.test).is_completed)

    def test_retake_only_pays_for_new_questions(self):
        # First attempt sends three of the four questions (two right, one wrong).
        self.assertEqual(self._run(self.test, ['A', 'A', 'B']), 2 * 10 + 5)
        # Retake after the review revealed those answers: only the question
        # never seen before pays, and there is no second completion bonus.
        self.assertEqual(self._run(self.test, ['A', 'A', 'A', 'A']), 10)
        self.assertEqual(self._xp(), 35)
        # A third run of the same test pays nothing at all.
        self.assertEqual(self._run(self.test, ['A', 'A', 'A', 'A']), 0)

    def test_reviewed_questions_do_not_pay_in_a_new_test(self):
        self.assertEqual(self._run(self.test, ['', '', '', '']), 0)  # reveals all four
        fresh = _q(self.subject, 99)
        other = Test.objects.create(title='XP second', test_type='mixed', negative_marking=False)
        other.questions.set([self.questions[0], fresh])
        self.assertEqual(self._run(other, ['A', 'A']), 10 + 5)

    def test_completion_bonus_has_a_daily_cap(self):
        for i in range(te_views.COMPLETION_BONUS_DAILY_CAP):
            done = Test.objects.create(title=f'Done {i}', test_type='mixed')
            TestAttempt.objects.create(user=self.user, test=done, is_completed=True,
                                       completed_at=timezone.now(), correct_count=1)
        self.assertEqual(self._run(self.test, ['A']), 10)


class GeneratedTestVisibilityAndListingTests(_ApiCase):
    """TE-26 / TE-14: generated tests are private; library and own tests are
    listed (and paginated) separately."""

    def setUp(self):
        super().setUp()
        self.subject = Subject.objects.create(name='Wave1 Listing')
        for i in range(5):
            _q(self.subject, i)

    def test_admin_generated_practice_test_is_private(self):
        admin = _user('w1-admin', role='admin')
        self.login(admin)
        r = self.generate({'test_type': 'mixed', 'num_questions': 3})
        self.assertEqual(r.status_code, 201, r.data)
        self.assertFalse(r.data['is_published'])
        mine = self.client.get('/api/tests/', {'scope': 'mine'}).data['results']
        self.assertIn(r.data['id'], [t['id'] for t in mine])

        self.login(_user('w1-student'))
        ids = [t['id'] for t in self.client.get('/api/tests/').data['results']]
        self.assertNotIn(r.data['id'], ids)
        self.assertEqual(self.client.post(f"/api/tests/{r.data['id']}/start/").status_code, 404)

    def test_library_and_own_tests_are_listed_separately(self):
        student = _user('w1-lister')
        official = [Test.objects.create(title=f'Official {i}', test_type='mixed') for i in range(3)]
        for i in range(25):
            Test.objects.create(title=f'Mine {i}', test_type='mixed', created_by=student, is_published=False)
        self.login(student)

        library = self.client.get('/api/tests/', {'scope': 'library'}).data
        self.assertEqual(sorted(t['id'] for t in library['results']), sorted(t.id for t in official))
        mine = self.client.get('/api/tests/', {'scope': 'mine'}).data
        self.assertEqual((mine['count'], len(mine['results'])), (25, 20))
        self.assertIsNotNone(mine['next'])
        page2 = self.client.get('/api/tests/', {'scope': 'mine', 'page': 2}).data
        self.assertEqual(len(page2['results']), 5)
        self.assertEqual(self.client.get('/api/tests/').data['count'], 28)


class QueryCountTests(_ApiCase):
    """TE-04 / TE-29 / FE-STU-29: start and list cost a constant number of
    queries, independent of the number of questions / tests."""

    def setUp(self):
        super().setUp()
        self.subject = Subject.objects.create(name='Wave1 Queries')
        self.user = _user('w1-queries', premium=True)
        self.login(self.user)

    def _test_with(self, n, title):
        questions = [_q(self.subject, f'{title}-{i}') for i in range(n)]
        for i, question in enumerate(questions):
            QuestionImage.objects.create(question=question, page_number=1, url='https://example.test/x.png')
            if i % 2 == 0:
                cluster = DuplicateCluster.objects.create(canonical_question=question)
                DuplicateMember.objects.create(cluster=cluster, question=question)
        test = Test.objects.create(title=title, test_type='mixed')
        test.questions.set(questions)
        return test

    def _queries(self, method, url, data=None):
        with CaptureQueriesContext(connection) as ctx:
            r = getattr(self.client, method)(url, data or {})
        self.assertLess(r.status_code, 300, getattr(r, 'data', None))
        return len(ctx.captured_queries)

    def test_start_does_not_scale_with_questions(self):
        small, large = self._test_with(4, 'small'), self._test_with(16, 'large')
        self._queries('get', '/api/tests/')  # warm-up (last-seen middleware etc.)
        small_q = self._queries('post', f'/api/tests/{small.id}/start/')
        large_q = self._queries('post', f'/api/tests/{large.id}/start/')
        self.assertEqual(small_q, large_q)

    def test_list_does_not_scale_with_tests(self):
        for i in range(3):
            self._test_with(1, f'list-a-{i}')
        self._queries('get', '/api/tests/')  # warm-up
        few = self._queries('get', '/api/tests/')
        for i in range(7):
            self._test_with(1, f'list-b-{i}')
        many = self._queries('get', '/api/tests/')
        self.assertEqual(few, many)
