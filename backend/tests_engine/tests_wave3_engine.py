"""Regression tests for the tests-engine fixes of fix wave 3 (group Z2).

The answer-key oracle: a free student must never be scored (right / wrong,
totals, retakes) on a question whose answer they may not see, and never on a
scholarship-challenge question. Generated practice tests draw from the free
showcase for them, full paper mocks / PYQ simulations stay premium, and
/start/ and /submit/ answer 402 for any other test. Premium, staff and admin
users keep the whole bank and the full review. Also: the paper-mock time
limit migration leaves tests with attempts in progress alone.
"""
import importlib
import itertools
from datetime import timedelta
from unittest import mock

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models_freemium import FreeShowcaseQuestion
from analytics.models import UserTopicPerformance
from questions.models import MistakeNotebook, Question, QuestionImage, Subject, Topic
from tests_engine.entitlement import answer_visibility
from tests_engine.models import QuestionResponse, Test, TestAttempt

User = get_user_model()

SECRET = 'wave3 secret explanation'
_positions = itertools.count()


def _q(subject, i, *, showcase=False, **kw):
    data = dict(
        question_text=f'Wave3 question {i}', option_a='A', option_b='B', option_c='C', option_d='D',
        correct_answer='C', year=2024, subject=subject, explanation=f'{SECRET} {i}',
        mnemonic='wave3 secret mnemonic',
    )
    data.update(kw)
    question = Question.objects.create(**data)
    if showcase:
        FreeShowcaseQuestion.objects.create(question=question, year=question.year or 2024,
                                            position=next(_positions))
    return question


def _user(name, *, premium=False, **extra):
    user = User.objects.create_user(username=name, password='x', **extra)
    if premium:
        from accounts.models import Subscription
        Subscription.objects.create(user=user, plan='1_year', status='active',
                                    expires_at=timezone.now() + timedelta(days=365))
    return user


class _ApiCase(TestCase):
    def setUp(self):
        self.client = APIClient()

    def login(self, user):
        self.client.force_authenticate(user)
        return user

    def generate(self, body, url='/api/tests/generate/'):
        return self.client.post(url, body, format='json')

    def start(self, test):
        return self.client.post(f'/api/tests/{test.id}/start/')

    def submit(self, test, attempt_id, answers):
        return self.client.post(f'/api/tests/{test.id}/submit/',
                                {'attempt_id': attempt_id, 'answers': answers}, format='json')

    def review(self, test, attempt_id):
        r = self.client.get(f'/api/tests/{test.id}/review/', {'attempt_id': attempt_id})
        self.assertEqual(r.status_code, 200, getattr(r, 'data', None))
        return {row['question_id']: row for row in r.data['questions']}

    @staticmethod
    def ids(test_id):
        return set(Test.objects.get(pk=test_id).questions.values_list('id', flat=True))

    def assert_upgrade_required(self, response):
        self.assertEqual(response.status_code, 402, getattr(response, 'data', None))
        self.assertEqual(response.data['code'], 'upgrade_required')
        self.assertEqual(response.data['feature'], 'Mock Tests')


class FreeGeneratedPoolTests(_ApiCase):
    """/generate/ and /generate-adaptive/: a free student's questions come
    from the free showcase only (never a scholarship question)."""

    def setUp(self):
        super().setUp()
        self.subject = Subject.objects.create(name='Wave3 Pool', code='W3POOL')
        self.topic = Topic.objects.create(subject=self.subject, name='Wave3 Pool Topic')
        self.free = [_q(self.subject, f'free-{i}', showcase=True, topic=self.topic) for i in range(3)]
        self.locked = [_q(self.subject, f'locked-{i}', topic=self.topic) for i in range(6)]
        # An admin also showcased a scholarship-challenge question: never free.
        self.scholarship = _q(self.subject, 'scholarship', showcase=True, topic=self.topic,
                              is_scholarship_eligible=True)
        self.free_ids = {q.id for q in self.free}
        self.user = self.login(_user('w3-pool-free'))

    def test_every_generator_draws_free_questions_only(self):
        bodies = [
            {'test_type': 'daily'},
            {'test_type': 'mixed', 'num_questions': 20},
            {'test_type': 'subject', 'subject_id': self.subject.id},
            {'test_type': 'topic', 'topic_id': self.topic.id},
            {'test_type': 'pyq_year', 'year': 2024},
            {'test_type': 'weak'},
        ]
        for body in bodies:
            r = self.generate(body)
            self.assertEqual(r.status_code, 201, (body, r.data))
            self.assertEqual(self.ids(r.data['id']), self.free_ids, body)
            self.assertTrue(r.data['is_free_for_current_user'], body)
        r = self.generate({'num_questions': 20}, url='/api/tests/generate-adaptive/')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self.ids(r.data['id']), self.free_ids)

    def test_free_generated_test_is_fully_reviewable_and_retakeable(self):
        test = Test.objects.get(pk=self.generate({'test_type': 'mixed', 'num_questions': 20}).data['id'])
        for _ in range(2):  # retakes are fine: these answers are free anyway
            started = self.start(test)
            self.assertEqual(started.status_code, 200, started.data)
            attempt_id = started.data['attempt_id']
            r = self.submit(test, attempt_id, [{'question_id': q.id, 'selected_answer': 'A'} for q in self.free])
            self.assertEqual(r.status_code, 200, r.data)
            rows = self.review(test, attempt_id)
            for question in self.free:
                self.assertFalse(rows[question.id]['answer_locked'])
                self.assertEqual(rows[question.id]['correct_answer'], 'C')
                self.assertEqual(rows[question.id]['explanation'], question.explanation)

    def test_selection_without_free_questions_is_a_402(self):
        other = Subject.objects.create(name='Wave3 Pool Other', code='W3POOL2')
        _q(other, 'other-locked')
        _q(other, 'neet-locked', exam_type='neet_pg', exam_source='NEET PG')
        before = Test.objects.count()
        self.assert_upgrade_required(self.generate({'test_type': 'subject', 'subject_id': other.id}))
        self.assert_upgrade_required(self.generate({'test_type': 'mixed', 'exam_type': 'neet_pg'}))
        self.assert_upgrade_required(self.generate({'exam_type': 'neet_pg'}, url='/api/tests/generate-adaptive/'))
        self.assertEqual(Test.objects.count(), before)
        # Nothing at all for the exam: a 400, not an empty test (adaptive
        # used to create one).
        r = self.generate({'exam_type': 'usmle'}, url='/api/tests/generate-adaptive/')
        self.assertEqual(r.status_code, 400, r.data)
        r = self.generate({'test_type': 'mixed', 'exam_type': 'usmle'})
        self.assertEqual(r.status_code, 400, r.data)

    def test_full_papers_keep_the_real_paper_and_stay_premium(self):
        # A small paper / PYQ year (at most 20 questions) used to be startable.
        for url, body in (('/api/tests/generate/', {'test_type': 'paper1'}),
                          ('/api/tests/pyq-simulation/', {'year': 2024})):
            r = self.generate(body, url=url)
            self.assertEqual(r.status_code, 201, (body, r.data))
            ids = self.ids(r.data['id'])
            self.assertEqual(ids, self.free_ids | {q.id for q in self.locked}, body)
            self.assertNotIn(self.scholarship.id, ids)
            self.assertFalse(r.data['is_free_for_current_user'])
            test = Test.objects.get(pk=r.data['id'])
            self.assert_upgrade_required(self.start(test))
            self.assertFalse(TestAttempt.objects.filter(test=test).exists())

    def test_premium_staff_and_admin_keep_the_whole_bank(self):
        staff = _user('w3-pool-staff', is_staff=True)
        everything = self.free_ids | {q.id for q in self.locked} | {self.scholarship.id}
        for user in (_user('w3-pool-premium', premium=True), _user('w3-pool-admin', role='admin'), staff):
            self.login(user)
            r = self.generate({'test_type': 'mixed', 'num_questions': 50})
            self.assertEqual(r.status_code, 201, r.data)
            self.assertEqual(self.ids(r.data['id']), everything, user.username)
            r = self.generate({'num_questions': 50}, url='/api/tests/generate-adaptive/')
            self.assertEqual(self.ids(r.data['id']), everything, user.username)


class AnswerKeyOracleTests(_ApiCase):
    """The attack from the wave-2 review: generate a test, submit all-A,
    all-B, all-C and read right / wrong off the results and the review. A
    free student can no longer be scored on a question they may not see."""

    def setUp(self):
        super().setUp()
        self.subject = Subject.objects.create(name='Wave3 Oracle', code='W3ORA')
        self.showcase = _q(self.subject, 'showcase', showcase=True)
        self.locked = _q(self.subject, 'locked')
        self.scholarship = _q(self.subject, 'scholarship', showcase=True, is_scholarship_eligible=True)
        self.user = self.login(_user('w3-oracle-free'))

    def _small_test(self, *questions, **kw):
        test = Test.objects.create(title='Wave3 small', test_type='mixed', negative_marking=False, **kw)
        test.questions.set(questions)
        return test

    def test_a_generated_test_never_contains_a_locked_question(self):
        for _ in range(5):
            r = self.generate({'test_type': 'mixed', 'num_questions': 1})
            self.assertEqual(r.status_code, 201, r.data)
            self.assertEqual(self.ids(r.data['id']), {self.showcase.id})

    def test_tests_with_locked_or_scholarship_questions_cannot_be_started(self):
        library = self._small_test(self.showcase, self.locked)
        scholarship = self._small_test(self.showcase, self.scholarship)
        free = self._small_test(self.showcase)
        rows = {row['id']: row for row in self.client.get('/api/tests/', {'scope': 'library'}).data['results']}
        self.assertEqual(
            {k: rows[t.id]['is_free_for_current_user'] for k, t in
             (('library', library), ('scholarship', scholarship), ('free', free))},
            {'library': False, 'scholarship': False, 'free': True},
        )
        for test in (library, scholarship):
            self.assert_upgrade_required(self.start(test))
            self.assertFalse(TestAttempt.objects.filter(test=test).exists())
        self.assertEqual(self.start(free).status_code, 200)

    def test_retakes_of_older_tests_are_closed(self):
        # A practice test generated from the whole bank before this rule, with
        # one completed attempt (its right / wrong already shown) and a retake
        # in progress.
        old = self._small_test(self.locked, self.scholarship, created_by=self.user, is_published=False)
        TestAttempt.objects.create(user=self.user, test=old, is_completed=True, completed_at=timezone.now(),
                                   correct_count=0, incorrect_count=2)
        in_flight = TestAttempt.objects.create(user=self.user, test=old)

        self.assert_upgrade_required(self.start(old))
        for letter in 'ABCD':
            r = self.submit(old, in_flight.id, [{'question_id': q.id, 'selected_answer': letter}
                                                for q in (self.locked, self.scholarship)])
            self.assert_upgrade_required(r)
            self.assertNotIn('correct_count', r.data)
        in_flight.refresh_from_db()
        self.assertFalse(in_flight.is_completed)
        self.assertFalse(QuestionResponse.objects.filter(attempt=in_flight).exists())
        self.assertFalse(MistakeNotebook.objects.filter(user=self.user).exists())
        self.assertFalse(UserTopicPerformance.objects.filter(user=self.user).exists())

        # The same attempt is scored once the student is premium again.
        from accounts.models import Subscription
        Subscription.objects.create(user=self.user, plan='1_year', status='active',
                                    expires_at=timezone.now() + timedelta(days=30))
        r = self.submit(old, in_flight.id, [{'question_id': self.locked.id, 'selected_answer': 'C'}])
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['correct_count'], 1)

    def test_historical_review_locks_scholarship_and_bank_answers(self):
        # Scored before this rule: the answer parts stay locked, scholarship
        # questions included, even though an admin showcased it.
        test = self._small_test(self.showcase, self.locked, self.scholarship)
        attempt = TestAttempt.objects.create(user=self.user, test=test, is_completed=True,
                                             completed_at=timezone.now(), correct_count=1, incorrect_count=2)
        for question, letter in ((self.showcase, 'C'), (self.locked, 'A'), (self.scholarship, 'B')):
            QuestionResponse.objects.create(attempt=attempt, question=question, selected_answer=letter,
                                            is_correct=letter == 'C')
        rows = self.review(test, attempt.id)
        for question in (self.locked, self.scholarship):
            row = rows[question.id]
            self.assertTrue(row['answer_locked'])
            self.assertIsNone(row['correct_answer'])
            self.assertEqual((row['explanation'], row['mnemonic'], row['concept_explanation'],
                              row['textbook_references']), ('', '', '', []))
            self.assertNotIn('secret', str(row))
        self.assertFalse(rows[self.showcase.id]['answer_locked'])
        self.assertEqual(rows[self.showcase.id]['correct_answer'], 'C')

        detail = self.client.get(f'/api/tests/attempts/{attempt.id}/').data
        details = {resp['question']: resp['question_detail'] for resp in detail['responses']}
        self.assertTrue(details[self.scholarship.id]['answer_locked'])
        self.assertIsNone(details[self.scholarship.id]['correct_answer'])
        self.assertNotIn('secret', str(details[self.scholarship.id]))

    def test_premium_users_still_get_the_full_review(self):
        self.login(_user('w3-oracle-premium', premium=True))
        test = self._small_test(self.showcase, self.locked, self.scholarship)
        attempt_id = self.start(test).data['attempt_id']
        r = self.submit(test, attempt_id, [{'question_id': q.id, 'selected_answer': 'C'}
                                           for q in (self.showcase, self.locked, self.scholarship)])
        self.assertEqual((r.status_code, r.data['correct_count']), (200, 3))
        for question, row in self.review(test, attempt_id).items():
            self.assertFalse(row['answer_locked'])
            self.assertEqual(row['correct_answer'], 'C')
            self.assertIn(SECRET, row['explanation'])


class SharedRuleConsistencyTests(TestCase):
    """answer_visibility (one query for a whole test) agrees with the
    question bank's per-question rule for every kind of user and question."""

    def test_matches_user_can_view_answer(self):
        from questions.views import user_can_view_answer

        subject = Subject.objects.create(name='Wave3 Rule', code='W3RULE')
        questions = [
            _q(subject, 'showcase', showcase=True),
            _q(subject, 'plain'),
            _q(subject, 'scholarship-showcase', showcase=True, is_scholarship_eligible=True),
            _q(subject, 'scholarship', is_scholarship_eligible=True),
        ]
        lapsed = _user('w3-rule-lapsed')
        from accounts.models import Subscription
        Subscription.objects.create(user=lapsed, plan='1_year', status='expired',
                                    expires_at=timezone.now() - timedelta(days=1))
        users = [_user('w3-rule-free'), lapsed, _user('w3-rule-premium', premium=True),
                 _user('w3-rule-staff', is_staff=True), _user('w3-rule-admin', role='admin')]
        ids = [q.id for q in questions]
        for user in users:
            with CaptureQueriesContext(connection) as ctx:
                visible = answer_visibility(user, ids)
            self.assertLessEqual(len(ctx.captured_queries), 3, user.username)
            self.assertEqual(visible, {qid: user_can_view_answer(user, qid) for qid in ids}, user.username)

    def test_narrowing_the_free_set_narrows_tests(self):
        subject = Subject.objects.create(name='Wave3 Rule 2', code='W3RULE2')
        question = _q(subject, 'showcase', showcase=True)
        user = _user('w3-rule-narrow')
        self.assertEqual(answer_visibility(user, [question.id]), {question.id: True})
        with mock.patch('questions.views.free_showcase_rows', return_value=FreeShowcaseQuestion.objects.none()):
            self.assertEqual(answer_visibility(user, [question.id]), {question.id: False})


class LockedPayloadTests(_ApiCase):
    """GET /tests/<id>/ and /start/ carry no answer media of questions
    outside the free set for a viewer without full access."""

    def setUp(self):
        super().setUp()
        subject = Subject.objects.create(name='Wave3 Media', code='W3MEDIA')
        self.showcase = _q(subject, 'media-showcase', showcase=True)
        self.locked = _q(subject, 'media-locked')
        self.scholarship = _q(subject, 'media-scholarship', showcase=True, is_scholarship_eligible=True,
                              video_url='https://example.test/explain.mp4', video_status='completed')
        self.explanation_image = {}
        for question in (self.showcase, self.locked, self.scholarship):
            QuestionImage.objects.create(question=question, page_number=1, role='primary',
                                         url=f'https://example.test/stem-{question.id}.png')
            self.explanation_image[question.id] = QuestionImage.objects.create(
                question=question, page_number=2, role='explanation',
                url=f'https://example.test/explanation-{question.id}.png',
            ).id
        self.test = Test.objects.create(title='Wave3 media', test_type='mixed', negative_marking=False)
        self.test.questions.set([self.showcase, self.locked, self.scholarship])

    def _detail_rows(self):
        r = self.client.get(f'/api/tests/{self.test.id}/')
        self.assertEqual(r.status_code, 200, getattr(r, 'data', None))
        return {row['id']: row for row in r.data['questions']}

    @staticmethod
    def _roles(row):
        return sorted(img.get('role') for img in row['images'])

    def test_free_viewer_gets_no_locked_explanation_figures(self):
        self.login(_user('w3-media-free'))
        rows = self._detail_rows()
        self.assertEqual(self._roles(rows[self.showcase.id]), ['explanation', 'primary'])
        for question in (self.locked, self.scholarship):
            row = rows[question.id]
            self.assertEqual(self._roles(row), ['primary'])
            image_ids = {img['id'] for img in row['images'] + row['stem_images']}
            self.assertNotIn(self.explanation_image[question.id], image_ids)
        self.assertFalse(rows[self.scholarship.id]['is_showcase'])
        self.assertIsNone(rows[self.scholarship.id]['video_url'])

    def test_premium_viewer_keeps_them(self):
        self.login(_user('w3-media-premium', premium=True))
        rows = self._detail_rows()
        for question in (self.showcase, self.locked, self.scholarship):
            self.assertEqual(self._roles(rows[question.id]), ['explanation', 'primary'])
        started = self.start(self.test)
        self.assertEqual(started.status_code, 200, started.data)
        by_id = {row['id']: row for row in started.data['questions']}
        self.assertEqual(by_id[self.scholarship.id]['video_url'], 'https://example.test/explain.mp4')


class FreeStartQueryCountTests(_ApiCase):
    def test_free_start_does_not_scale_with_questions(self):
        subject = Subject.objects.create(name='Wave3 Queries', code='W3Q')
        self.login(_user('w3-queries-free'))
        tests = []
        for n in (4, 16):
            test = Test.objects.create(title=f'Wave3 queries {n}', test_type='mixed')
            test.questions.set([_q(subject, f'{n}-{i}', showcase=True) for i in range(n)])
            tests.append(test)
        self.client.get('/api/tests/')  # warm-up
        counts = []
        for test in tests:
            with CaptureQueriesContext(connection) as ctx:
                r = self.start(test)
            self.assertEqual(r.status_code, 200, getattr(r, 'data', None))
            counts.append(len(ctx.captured_queries))
        self.assertEqual(counts[0], counts[1])


class PaperTimeLimitMigrationInFlightTests(TestCase):
    """LOW (wave-2 review): 0009 must not lower the limit under a student who
    is still inside the old one."""

    def test_tests_with_attempts_inside_the_old_limit_keep_it(self):
        migration = importlib.import_module('tests_engine.migrations.0009_cap_paper_mock_time_limits')
        student = _user('w3-migration-student')
        now = timezone.now()
        mid_exam = Test.objects.create(title='P1 mid exam', test_type='paper1', time_limit_minutes=180)
        abandoned = Test.objects.create(title='P1 abandoned', test_type='paper1', time_limit_minutes=180)
        finished = Test.objects.create(title='P2 finished', test_type='paper2', time_limit_minutes=180)
        untouched = Test.objects.create(title='P2 none', test_type='paper2', time_limit_minutes=150)
        for test, minutes_ago, completed in ((mid_exam, 150, False), (abandoned, 3 * 24 * 60, False),
                                             (finished, 30, True)):
            attempt = TestAttempt.objects.create(user=student, test=test, is_completed=completed)
            TestAttempt.objects.filter(pk=attempt.pk).update(started_at=now - timedelta(minutes=minutes_ago))

        migration.cap_paper_mock_time_limits(django_apps, None)
        limits = {t.title: Test.objects.get(pk=t.pk).time_limit_minutes
                  for t in (mid_exam, abandoned, finished, untouched)}
        self.assertEqual(limits, {'P1 mid exam': 180, 'P1 abandoned': 120, 'P2 finished': 120, 'P2 none': 120})

        # Once the attempt is over, running it again caps the rest.
        TestAttempt.objects.filter(test=mid_exam).update(is_completed=True)
        migration.cap_paper_mock_time_limits(django_apps, None)
        self.assertEqual(Test.objects.get(pk=mid_exam.pk).time_limit_minutes, 120)
