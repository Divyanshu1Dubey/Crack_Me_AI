"""Regression tests for the tests-engine fixes of fix wave 2 (group W2).

Covers: entitlement-masked /review/ and attempt detail (free users see right
/ wrong only), late submissions (scored, flagged, no XP), the per-exam paper
mock rule (C3), distinct generated titles, answer time in topic analytics,
accuracy-based adaptive tests, exam payloads without answer-revealing study
aids, the retrieve / attempt-detail N+1 fixes, last_completed_attempt_id,
the paper-mock time-limit data migration and the unpublish_generated_tests
command.
"""
import importlib
import io
from datetime import timedelta
from unittest import mock

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models_freemium import FreeShowcaseQuestion
from analytics.models import DailyActivity, StudyStreak, UserTopicPerformance, XPEvent
from questions.models import DuplicateCluster, DuplicateMember, Question, QuestionImage, Subject, Topic
from tests_engine import views as te_views
from tests_engine.models import QuestionResponse, Test, TestAttempt

User = get_user_model()

SECRET_EXPLANATION = 'Because the ductus arteriosus closes (wave2 secret)'
SECRET_EXCERPT = 'Textbook excerpt that names the answer (wave2 secret)'


def _q(subject, i, **kw):
    defaults = dict(
        question_text=f'Wave2 question {i}', option_a='A', option_b='B', option_c='C',
        option_d='D', correct_answer='A', year=2024, subject=subject,
    )
    defaults.update(kw)
    return Question.objects.create(**defaults)


def _user(name, *, role='student', premium=False, superuser=False):
    user = User.objects.create_user(username=name, password='x', role=role)
    if superuser:
        User.objects.filter(pk=user.pk).update(is_superuser=True)
        user.refresh_from_db()
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


class ReviewEntitlementTests(_ApiCase):
    """A free student's test must not reveal the answer key: the review
    locks the answer parts, except for showcase questions. Since wave 3 a
    free student cannot take this test at all (it has non-showcase
    questions: see tests_wave3_engine), so their attempts here are ones
    scored before that rule."""

    def setUp(self):
        super().setUp()
        subject = Subject.objects.create(name='Wave2 Review', code='W2REV')
        rich = dict(
            explanation=SECRET_EXPLANATION, mnemonic='Wave2 mnemonic secret',
            concept_explanation='Wave2 concept secret',
            textbook_references=[{'book': 'Ghai', 'excerpt': SECRET_EXCERPT}],
        )
        self.questions = [_q(subject, i, **rich) for i in range(3)]
        self.showcase = self.questions[2]
        FreeShowcaseQuestion.objects.create(question=self.showcase, year=2024, position=0)
        self.test = Test.objects.create(title='Review test', test_type='mixed', negative_marking=False)
        self.test.questions.set(self.questions)

    PICKS = ('A', 'B', 'C')   # right, wrong, wrong (showcase)

    def _finish(self, user):
        self.login(user)
        attempt_id = self.start(self.test).data['attempt_id']
        r = self.submit(self.test, attempt_id, [
            {'question_id': q.id, 'selected_answer': letter} for q, letter in zip(self.questions, self.PICKS)
        ])
        self.assertEqual(r.status_code, 200, r.data)
        return attempt_id

    def _finish_before_wave3(self, user):
        """A free student's attempt scored before wave 3 (the API now
        refuses to start or submit this test for them)."""
        self.login(user)
        self.assertEqual(self.client.post(f'/api/tests/{self.test.id}/start/').status_code, 402)
        attempt = TestAttempt.objects.create(user=user, test=self.test, is_completed=True,
                                             completed_at=timezone.now(), correct_count=1, incorrect_count=2)
        for question, letter in zip(self.questions, self.PICKS):
            QuestionResponse.objects.create(attempt=attempt, question=question, selected_answer=letter,
                                            is_correct=letter == question.correct_answer)
        return attempt.id

    def _review(self, attempt_id):
        r = self.client.get(f'/api/tests/{self.test.id}/review/', {'attempt_id': attempt_id})
        self.assertEqual(r.status_code, 200, getattr(r, 'data', None))
        return r, {row['question_id']: row for row in r.data['questions']}

    def test_free_user_sees_right_or_wrong_only(self):
        attempt_id = self._finish_before_wave3(_user('w2-review-free'))
        response, rows = self._review(attempt_id)
        q0, q1, q2 = self.questions
        for question, picked, correct in ((q0, 'A', True), (q1, 'B', False)):
            row = rows[question.id]
            self.assertTrue(row['answer_locked'])
            self.assertEqual((row['selected_answer'], row['is_correct']), (picked, correct))
            self.assertIsNone(row['correct_answer'])
            self.assertEqual(
                (row['explanation'], row['mnemonic'], row['concept_explanation'], row['textbook_references']),
                ('', '', '', []),
            )
        # The curated showcase question keeps its answer and explanation.
        self.assertFalse(rows[q2.id]['answer_locked'])
        self.assertEqual(rows[q2.id]['correct_answer'], 'A')
        self.assertEqual(rows[q2.id]['explanation'], SECRET_EXPLANATION)
        # Totals are unaffected by the masking.
        self.assertEqual((response.data['correct'], response.data['incorrect']), (1, 2))
        # Nothing of the locked rows leaks anywhere in the payload.
        locked_payload = str([rows[q0.id], rows[q1.id]])
        self.assertNotIn('secret', locked_payload)

    def test_premium_admin_and_staff_see_every_answer(self):
        staff = _user('w2-review-staff')
        User.objects.filter(pk=staff.pk).update(is_staff=True)
        staff.refresh_from_db()
        for user in (_user('w2-review-premium', premium=True), _user('w2-review-admin', role='admin'), staff):
            _, rows = self._review(self._finish(user))
            for question in self.questions:
                self.assertFalse(rows[question.id]['answer_locked'], user.username)
                self.assertEqual(rows[question.id]['correct_answer'], 'A')
                self.assertEqual(rows[question.id]['explanation'], SECRET_EXPLANATION)

    def test_showcase_rows_still_go_through_the_shared_rule(self):
        # A narrowing of the shared free set (questions.views.free_showcase_rows,
        # which user_can_view_answer checks; e.g. scholarship questions) must
        # apply to tests too.
        attempt_id = self._finish_before_wave3(_user('w2-review-rule'))
        with mock.patch('questions.views.free_showcase_rows', return_value=FreeShowcaseQuestion.objects.none()):
            _, rows = self._review(attempt_id)
        self.assertTrue(all(row['answer_locked'] for row in rows.values()))

    def test_attempt_detail_follows_the_same_rule(self):
        attempt_id = self._finish_before_wave3(_user('w2-detail-free'))
        r = self.client.get(f'/api/tests/attempts/{attempt_id}/')
        self.assertEqual(r.status_code, 200, getattr(r, 'data', None))
        details = {resp['question']: resp['question_detail'] for resp in r.data['responses']}
        q0, q1, q2 = self.questions
        for question in (q0, q1):
            self.assertTrue(details[question.id]['answer_locked'])
            self.assertIsNone(details[question.id]['correct_answer'])
            self.assertEqual(details[question.id]['explanation'], '')
        self.assertFalse(details[q2.id]['answer_locked'])
        self.assertEqual(details[q2.id]['correct_answer'], 'A')
        self.assertNotIn('secret', str([details[q0.id], details[q1.id]]))

        premium_attempt = self._finish(_user('w2-detail-premium', premium=True))
        r = self.client.get(f'/api/tests/attempts/{premium_attempt}/')
        self.assertTrue(all(not resp['question_detail']['answer_locked'] for resp in r.data['responses']))

    def test_other_users_attempt_detail_is_not_reachable(self):
        attempt_id = self._finish(_user('w2-detail-owner', premium=True))
        self.login(_user('w2-detail-intruder'))
        self.assertEqual(self.client.get(f'/api/tests/attempts/{attempt_id}/').status_code, 404)


class LateSubmissionTests(_ApiCase):
    """Past the time limit + grace a submit is scored but flagged late: no
    XP (so off the XP leaderboard), never recorded as on time."""

    def setUp(self):
        super().setUp()
        subject = Subject.objects.create(name='Wave2 Late', code='W2LATE')
        self.questions = [_q(subject, i) for i in range(4)]
        self.test = Test.objects.create(title='Late test', test_type='mixed', time_limit_minutes=30,
                                        negative_marking=False)
        self.test.questions.set(self.questions)
        self.user = _user('w2-late', premium=True)
        self.login(self.user)

    def _start_aged(self, seconds_ago, test=None):
        test = test or self.test
        attempt_id = self.start(test).data['attempt_id']
        TestAttempt.objects.filter(pk=attempt_id).update(
            started_at=timezone.now() - timedelta(seconds=seconds_ago))
        return attempt_id

    def _answer_first(self, test, attempt_id):
        question = test.questions.order_by('id').first()
        return self.submit(test, attempt_id, [{'question_id': question.id, 'selected_answer': 'A'}])

    def test_submit_inside_the_grace_period_is_on_time(self):
        attempt_id = self._start_aged(30 * 60 + 60)  # the 0:00 auto-submit arriving a minute late
        r = self._answer_first(self.test, attempt_id)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(r.data['is_late'])
        self.assertEqual(r.data['xp_earned'], te_views.XP_PER_NEW_CORRECT + te_views.XP_COMPLETION_BONUS)

    def test_expired_resume_is_scored_but_late(self):
        attempt_id = self._start_aged(3 * 24 * 3600)
        resumed = self.start(self.test).data
        self.assertEqual((resumed['attempt_id'], resumed['remaining_seconds']), (attempt_id, 0))

        r = self._answer_first(self.test, attempt_id)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data['correct_count'], r.data['is_late'], r.data['xp_earned']), (1, True, 0))

        attempt = TestAttempt.objects.get(pk=attempt_id)
        self.assertTrue(attempt.is_completed and attempt.is_late)
        self.assertEqual(attempt.time_taken_seconds, 1800)
        self.assertEqual(StudyStreak.objects.get(user=self.user).xp_points, 0)
        self.assertFalse(XPEvent.objects.filter(user=self.user).exists())
        # Still counted as practice.
        self.assertEqual(DailyActivity.objects.get(user=self.user).tests_completed, 1)

        review = self.client.get(f'/api/tests/{self.test.id}/review/', {'attempt_id': attempt_id})
        self.assertTrue(review.data['is_late'])
        listed = self.client.get('/api/tests/attempts/').data
        rows = listed['results'] if isinstance(listed, dict) else listed
        self.assertTrue(next(row for row in rows if row['id'] == attempt_id)['is_late'])

    def test_untimed_test_is_never_late(self):
        untimed = Test.objects.create(title='Untimed', test_type='mixed', time_limit_minutes=0,
                                      negative_marking=False)
        untimed.questions.set(self.questions[:2])
        attempt_id = self._start_aged(5 * 24 * 3600, test=untimed)
        r = self._answer_first(untimed, attempt_id)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(r.data['is_late'])
        self.assertGreater(r.data['xp_earned'], 0)


class PaperMockExamRuleTests(_ApiCase):
    """C3: CMS paper mocks go by the question's paper; other exams (whose
    importers set paper=1 everywhere) follow the subject's paper."""

    @classmethod
    def setUpTestData(cls):
        cls.medicine = Subject.objects.create(name='Wave2 Medicine', code='W2MED', paper=1)
        cls.surgery = Subject.objects.create(name='Wave2 Surgery', code='W2SUR', paper=2)
        neet = dict(exam_type='neet_pg', exam_source='NEET PG', paper=1)
        cls.neet_p1 = [_q(cls.medicine, f'n1-{i}', **neet) for i in range(3)]
        cls.neet_p2 = [_q(cls.surgery, f'n2-{i}', **neet) for i in range(2)]
        # CMS rows whose own paper differs from their subject's paper.
        cls.cms_p2_in_medicine = [_q(cls.medicine, f'c2-{i}', paper=2) for i in range(2)]
        cls.cms_p1_in_surgery = [_q(cls.surgery, f'c1-{i}', paper=1) for i in range(2)]

    def setUp(self):
        super().setUp()
        self.login(_user('w2-paper', premium=True))

    @staticmethod
    def _ids(test_id):
        return set(Test.objects.get(pk=test_id).questions.values_list('id', flat=True))

    def test_non_cms_paper_mocks_follow_the_subject_paper(self):
        r1 = self.generate({'test_type': 'paper1', 'exam_type': 'neet_pg'})
        self.assertEqual(r1.status_code, 201, r1.data)
        self.assertEqual(self._ids(r1.data['id']), {q.id for q in self.neet_p1})
        r2 = self.generate({'test_type': 'paper2', 'exam_type': 'neet_pg'})
        self.assertEqual(r2.status_code, 201, r2.data)  # was 400: every NEET row has paper=1
        self.assertEqual(self._ids(r2.data['id']), {q.id for q in self.neet_p2})
        self.assertEqual(r2.data['exam_type'], 'neet_pg')

    def test_cms_paper_mocks_still_follow_the_question_paper(self):
        r1 = self.generate({'test_type': 'paper1'})
        self.assertEqual(self._ids(r1.data['id']), {q.id for q in self.cms_p1_in_surgery})
        r2 = self.generate({'test_type': 'paper2', 'exam_type': 'cms'})
        self.assertEqual(self._ids(r2.data['id']), {q.id for q in self.cms_p2_in_medicine})


class GeneratedTitleTests(_ApiCase):
    def setUp(self):
        super().setUp()
        subject = Subject.objects.create(name='Wave2 Titles', code='W2TTL')
        for i in range(5):
            _q(subject, i)
        self.login(_user('w2-titles', premium=True))

    def test_daily_and_mixed_tests_have_their_own_titles(self):
        daily = self.generate({'test_type': 'daily'})
        mixed = self.generate({'test_type': 'mixed', 'num_questions': 3})
        self.assertEqual(daily.data['title'], 'Daily Quick Test — 5 Questions')
        self.assertEqual(mixed.data['title'], 'Mixed Practice — 3 Questions')


class TopicTimeTests(_ApiCase):
    """AN-30: test answers feed UserTopicPerformance.total_time_seconds (the
    /analytics "Avg Time" column), capped by how long the attempt lasted."""

    def setUp(self):
        super().setUp()
        self.subject = Subject.objects.create(name='Wave2 Time', code='W2TIME')
        self.topic = Topic.objects.create(subject=self.subject, name='Wave2 Time Topic')
        self.questions = [_q(self.subject, i, topic=self.topic) for i in range(3)]
        self.test = Test.objects.create(title='Timed analytics', test_type='mixed', time_limit_minutes=30,
                                        negative_marking=False)
        self.test.questions.set(self.questions)
        self.user = _user('w2-time', premium=True)
        self.login(self.user)

    def _run(self, aged_seconds, timings):
        attempt_id = self.start(self.test).data['attempt_id']
        TestAttempt.objects.filter(pk=attempt_id).update(
            started_at=timezone.now() - timedelta(seconds=aged_seconds))
        answers = [
            {'question_id': q.id, 'selected_answer': letter, 'time_taken_seconds': seconds}
            for q, (letter, seconds) in zip(self.questions, timings)
        ]
        r = self.submit(self.test, attempt_id, answers)
        self.assertEqual(r.status_code, 200, r.data)
        return TestAttempt.objects.get(pk=attempt_id)

    def _times(self):
        rows = UserTopicPerformance.objects.filter(user=self.user, subject=self.subject)
        return {row.topic_id: (row.total_time_seconds, row.total_attempts) for row in rows}

    def test_answer_time_is_recorded_per_subject_and_topic(self):
        # The skipped question's time does not count (it is not an attempt).
        self._run(600, [('A', 30), ('B', 45), ('', 500)])
        self.assertEqual(self._times(), {None: (75, 2), self.topic.id: (75, 2)})

    def test_inflated_timings_are_scaled_to_the_attempt_duration(self):
        attempt = self._run(60, [('A', 1000), ('A', 1000), ('A', 0)])
        budget = attempt.time_taken_seconds
        self.assertLessEqual(budget, 70)
        expected = 2 * (1000 * budget // 2000)
        self.assertEqual(self._times()[None], (expected, 3))


class AdaptiveWeakAreaTests(_ApiCase):
    """AN-30: generate-adaptive targets the lowest-accuracy areas with enough
    answers, not the areas with the fewest correct answers."""

    def setUp(self):
        super().setUp()
        self.user = _user('w2-adaptive', premium=True)
        self.login(self.user)
        self.subject = Subject.objects.create(name='Wave2 Adaptive', code='W2ADP')
        self.weak, self.strong, self.rare = (
            Topic.objects.create(subject=self.subject, name=f'Wave2 {name}') for name in ('weak', 'strong', 'rare')
        )
        self.by_topic = {
            topic.pk: {_q(self.subject, f'{topic.name}-{i}', topic=topic).id for i in range(4)}
            for topic in (self.weak, self.strong, self.rare)
        }

    def _perf(self, topic, subject, total, correct):
        UserTopicPerformance.objects.create(
            user=self.user, subject=subject, topic=topic,
            total_attempts=total, correct_answers=correct, incorrect_answers=total - correct,
        )

    def _adaptive_ids(self, n=4):
        r = self.client.post('/api/tests/generate-adaptive/', {'num_questions': n}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        return set(Test.objects.get(pk=r.data['id']).questions.values_list('id', flat=True))

    def test_weakest_topic_by_accuracy_wins(self):
        self._perf(self.weak, self.subject, 10, 3)     # 30 %
        self._perf(self.strong, self.subject, 10, 9)   # 90 %
        self._perf(self.rare, self.subject, 2, 0)      # 0 %, but too few answers to judge
        with mock.patch.object(te_views, 'ADAPTIVE_WEAK_AREAS', 1):
            self.assertEqual(self._adaptive_ids(), self.by_topic[self.weak.pk])

    def test_weak_subject_row_targets_the_subject(self):
        other = Subject.objects.create(name='Wave2 Adaptive Other', code='W2ADO')
        other_ids = {_q(other, f'other-{i}').id for i in range(4)}
        self._perf(self.weak, self.subject, 10, 5)     # 50 %
        self._perf(None, other, 20, 2)                 # 10 %: whole subject is weak
        with mock.patch.object(te_views, 'ADAPTIVE_WEAK_AREAS', 1):
            self.assertEqual(self._adaptive_ids(), other_ids)


class ExamPayloadAndQueryTests(_ApiCase):
    """The exam payload carries no answer-revealing study aids; retrieve and
    the attempt detail cost a constant number of queries."""

    def setUp(self):
        super().setUp()
        self.subject = Subject.objects.create(name='Wave2 Payload', code='W2PAY')
        self.user = _user('w2-payload', premium=True)
        self.login(self.user)

    def _test_with(self, n, title):
        questions = [
            _q(self.subject, f'{title}-{i}', textbook_references=[{'book': 'Bailey', 'excerpt': SECRET_EXCERPT}],
               reference_text=SECRET_EXCERPT, concept_tags=['wave2 secret tag'], concept_id='wave2-secret')
            for i in range(n)
        ]
        for i, question in enumerate(questions):
            QuestionImage.objects.create(question=question, page_number=1, url='https://example.test/x.png')
            if i % 2 == 0:
                cluster = DuplicateCluster.objects.create(canonical_question=question)
                DuplicateMember.objects.create(cluster=cluster, question=question)
        test = Test.objects.create(title=title, test_type='mixed', negative_marking=False)
        test.questions.set(questions)
        return test

    def _queries(self, method, url, data=None):
        with CaptureQueriesContext(connection) as ctx:
            r = getattr(self.client, method)(url, data or {})
        self.assertLess(r.status_code, 300, getattr(r, 'data', None))
        return len(ctx.captured_queries)

    def test_start_and_detail_leave_out_answer_revealing_study_aids(self):
        test = self._test_with(2, 'aids')
        started = self.start(test)
        for row in started.data['questions']:
            for field in te_views.EXAM_HIDDEN_FIELDS:
                self.assertNotIn(field, row)
        self.assertNotIn('secret', started.content.decode())

        detail = self.client.get(f'/api/tests/{test.id}/')
        self.assertEqual(detail.status_code, 200)
        self.assertNotIn('secret', detail.content.decode())

        self.login(_user('w2-payload-admin', role='admin'))
        admin_detail = self.client.get(f'/api/tests/{test.id}/')
        self.assertIn('textbook_references', admin_detail.data['questions'][0])

    def test_retrieve_does_not_scale_with_clustered_questions(self):
        small, large = self._test_with(3, 'small'), self._test_with(12, 'large')
        self._queries('get', '/api/tests/')  # warm-up
        self.assertEqual(self._queries('get', f'/api/tests/{small.id}/'),
                         self._queries('get', f'/api/tests/{large.id}/'))

    def test_attempt_detail_does_not_scale_with_responses(self):
        counts = []
        for n, title in ((3, 'detail-small'), (12, 'detail-large')):
            test = self._test_with(n, title)
            attempt_id = self.start(test).data['attempt_id']
            answers = [{'question_id': q.id, 'selected_answer': 'A'} for q in test.questions.all()]
            self.assertEqual(self.submit(test, attempt_id, answers).status_code, 200)
            self._queries('get', '/api/tests/attempts/')  # warm-up
            counts.append(self._queries('get', f'/api/tests/attempts/{attempt_id}/'))
        self.assertEqual(counts[0], counts[1])


class ListOrderTests(_ApiCase):
    def test_library_is_listed_newest_first(self):
        # The question-count annotation adds a GROUP BY, which drops
        # Meta.ordering; the list must still page newest first.
        now = timezone.now()
        tests = [Test.objects.create(title=f'Order {i}', test_type='mixed') for i in range(3)]
        for age, test in zip((1, 3, 2), tests):
            Test.objects.filter(pk=test.pk).update(created_at=now - timedelta(days=age))
        self.login(_user('w2-order'))
        rows = self.client.get('/api/tests/', {'scope': 'library'}).data['results']
        self.assertEqual([row['id'] for row in rows], [tests[0].id, tests[2].id, tests[1].id])


class LastCompletedAttemptTests(_ApiCase):
    def test_start_reports_the_latest_completed_attempt(self):
        subject = Subject.objects.create(name='Wave2 Last', code='W2LAST')
        test = Test.objects.create(title='Last result', test_type='mixed', negative_marking=False)
        test.questions.set([_q(subject, i) for i in range(2)])
        self.login(_user('w2-last', premium=True))

        first = self.start(test).data
        self.assertIsNone(first['last_completed_attempt_id'])
        self.assertEqual(self.submit(test, first['attempt_id'], []).status_code, 200)
        second = self.start(test).data
        self.assertNotEqual(second['attempt_id'], first['attempt_id'])
        self.assertEqual(second['last_completed_attempt_id'], first['attempt_id'])


class PaperTimeLimitMigrationTests(TestCase):
    def test_paper_mocks_are_capped_at_120_minutes(self):
        migration = importlib.import_module('tests_engine.migrations.0009_cap_paper_mock_time_limits')
        rows = {
            'paper1_old': Test.objects.create(title='P1', test_type='paper1', time_limit_minutes=180),
            'paper2_old': Test.objects.create(title='P2', test_type='paper2', time_limit_minutes=150),
            'paper1_short': Test.objects.create(title='P1 short', test_type='paper1', time_limit_minutes=45),
            'combined_pyq': Test.objects.create(title='PYQ', test_type='pyq_year', time_limit_minutes=240),
        }
        migration.cap_paper_mock_time_limits(django_apps, None)
        limits = {key: Test.objects.get(pk=test.pk).time_limit_minutes for key, test in rows.items()}
        self.assertEqual(limits, {'paper1_old': 120, 'paper2_old': 120, 'paper1_short': 45, 'combined_pyq': 240})


class UnpublishGeneratedTestsCommandTests(TestCase):
    def setUp(self):
        admin = _user('w2-cmd-admin', role='admin')
        superuser = _user('w2-cmd-super', superuser=True)
        student = _user('w2-cmd-student')
        make = Test.objects.create
        self.generated = [
            make(title='Practice Test — 20 Questions', test_type='daily', created_by=admin),
            make(title='UPSC CMS 2019 — Combined Simulation', test_type='pyq_year', created_by=admin,
                 description='Full CMS 2019 Combined examination simulation with actual PYQ questions.'),
            make(title='AI Adaptive Test — 30 Questions', test_type='adaptive', created_by=superuser),
        ]
        self.kept = [
            make(title='CMS Exclusive Grand Test — Q4 2026', test_type='mixed', created_by=admin),
            make(title='High-yield — 20 Questions', test_type='mixed', created_by=admin,
                 description='Hand-picked by the faculty.'),
            make(title='General Medicine — 20 Questions', test_type='subject', created_by=admin),
            make(title='Practice Test — 20 Questions', test_type='daily', created_by=None),
            make(title='Practice Test — 20 Questions', test_type='daily', created_by=student),
        ]

    def _run(self, *args):
        out = io.StringIO()
        call_command('unpublish_generated_tests', *args, stdout=out)
        return out.getvalue()

    def _published(self, tests):
        return [Test.objects.get(pk=test.pk).is_published for test in tests]

    def test_dry_run_lists_only_generated_admin_tests(self):
        output = self._run()
        listed = {int(line.split('\t')[0]) for line in output.splitlines() if '\t' in line}
        self.assertEqual(listed, {test.pk for test in self.generated})
        self.assertIn('Dry run', output)
        self.assertEqual(self._published(self.generated + self.kept), [True] * 8)

    def test_apply_with_ids_unpublishes_only_the_reviewed_tests(self):
        self._run('--apply', '--ids', str(self.generated[0].pk))
        self.assertEqual(self._published(self.generated), [False, True, True])
        self._run('--apply')
        self.assertEqual(self._published(self.generated), [False, False, False])
        self.assertEqual(self._published(self.kept), [True] * 5)
        with self.assertRaises(CommandError):
            self._run('--apply', '--ids', str(self.kept[0].pk))
