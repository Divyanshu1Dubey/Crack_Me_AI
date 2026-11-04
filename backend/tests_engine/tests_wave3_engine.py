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
from tests_engine import views as te_views
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
    """Answer media of test questions: the exam payload (GET /tests/<id>/
    for students, /start/) carries none, for any viewer; /review/ returns
    them after submit, on the rows whose answer the student may see.

    Contract change (2026-11): the exam payload used to keep explanation
    figures (with signed URLs) and the explanation video for premium
    viewers and on free showcase questions, so a student could page through
    the explanation figures in the zoom viewer, or play the video, in the
    middle of a test. They now leave the exam payload for everyone, and the
    results page reads them from /review/. The entitlement half of these
    tests is unchanged: a free viewer never receives the explanation media
    of a question outside the free set (locked, scholarship), neither during
    the test nor in the review.
    """

    VIDEO = 'https://example.test/explain.mp4'

    def setUp(self):
        super().setUp()
        subject = Subject.objects.create(name='Wave3 Media', code='W3MEDIA')
        self.showcase = _q(subject, 'media-showcase', showcase=True, video_url=self.VIDEO,
                           video_status='completed')
        self.locked = _q(subject, 'media-locked', video_url=self.VIDEO, video_status='completed')
        self.scholarship = _q(subject, 'media-scholarship', showcase=True, is_scholarship_eligible=True,
                              video_url=self.VIDEO, video_status='completed')
        self.questions = (self.showcase, self.locked, self.scholarship)
        self.stem_image, self.explanation_image = {}, {}
        for question in self.questions:
            self.stem_image[question.id] = QuestionImage.objects.create(
                question=question, page_number=1, role='primary',
                url=f'https://example.test/stem-{question.id}.png',
            ).id
            self.explanation_image[question.id] = QuestionImage.objects.create(
                question=question, page_number=2, role='explanation',
                url=f'https://example.test/explanation-{question.id}.png',
            ).id
        self.test = Test.objects.create(title='Wave3 media', test_type='mixed', negative_marking=False)
        self.test.questions.set(self.questions)

    def _detail_rows(self):
        r = self.client.get(f'/api/tests/{self.test.id}/')
        self.assertEqual(r.status_code, 200, getattr(r, 'data', None))
        return {row['id']: row for row in r.data['questions']}

    def assert_no_answer_media(self, rows, who):
        for question in self.questions:
            row = rows[question.id]
            self.assertEqual([img['id'] for img in row['images']], [self.stem_image[question.id]], who)
            self.assertEqual([img['id'] for img in row['stem_images']], [self.stem_image[question.id]], who)
            for field in ('video_url', 'video_status', 'page_screenshot', 'book_name', 'chapter'):
                self.assertNotIn(field, row, who)
            self.assertNotIn(f'images/{self.explanation_image[question.id]}/', str(row), who)
            self.assertNotIn('explain.mp4', str(row), who)

    def _completed_attempt(self, user, picks=('C', 'A', 'C')):
        """A scored attempt (a free student cannot start this test any more;
        theirs date from before the rule, or from a premium period)."""
        attempt = TestAttempt.objects.create(user=user, test=self.test, is_completed=True,
                                             completed_at=timezone.now())
        for question, letter in zip(self.questions, picks):
            QuestionResponse.objects.create(attempt=attempt, question=question, selected_answer=letter,
                                            is_correct=letter == question.correct_answer)
        return attempt.id

    def test_exam_payload_has_no_answer_media_for_any_student(self):
        self.login(_user('w3-media-free'))
        self.assert_no_answer_media(self._detail_rows(), 'free detail')
        self.login(_user('w3-media-premium', premium=True))
        self.assert_no_answer_media(self._detail_rows(), 'premium detail')
        started = self.start(self.test)
        self.assertEqual(started.status_code, 200, started.data)
        self.assert_no_answer_media({row['id']: row for row in started.data['questions']}, 'premium start')

    def test_admin_test_preview_keeps_the_stored_payload(self):
        self.login(_user('w3-media-admin', role='admin'))
        rows = self._detail_rows()
        self.assertEqual(sorted(img['role'] for img in rows[self.locked.id]['images']), ['explanation', 'primary'])
        self.assertEqual(rows[self.locked.id]['video_url'], self.VIDEO)

    def test_free_review_has_the_explanation_media_of_free_questions_only(self):
        user = self.login(_user('w3-media-review-free'))
        rows = self.review(self.test, self._completed_attempt(user))
        showcase = rows[self.showcase.id]
        self.assertFalse(showcase['answer_locked'])
        self.assertEqual([img['id'] for img in showcase['explanation_images']],
                         [self.explanation_image[self.showcase.id]])
        self.assertIn('?t=', showcase['explanation_images'][0]['url'])
        self.assertEqual(showcase['explanation_images'][0]['role'], 'explanation')
        self.assertEqual(showcase['video_url'], self.VIDEO)
        for question in (self.locked, self.scholarship):
            row = rows[question.id]
            self.assertTrue(row['answer_locked'])
            self.assertEqual(row['explanation_images'], [])
            self.assertEqual([img['id'] for img in row['stem_images']], [self.stem_image[question.id]])
            self.assertEqual({field: row[field] for field in te_views.REVIEW_VIDEO_FIELDS},
                             dict.fromkeys(te_views.REVIEW_VIDEO_FIELDS))
            self.assertNotIn(f'images/{self.explanation_image[question.id]}/', str(row))

    def test_premium_review_returns_the_figures_and_the_video(self):
        self.login(_user('w3-media-review-premium', premium=True))
        attempt_id = self.start(self.test).data['attempt_id']
        answers = [{'question_id': q.id, 'selected_answer': 'C'} for q in self.questions]
        self.assertEqual(self.submit(self.test, attempt_id, answers).status_code, 200)
        rows = self.review(self.test, attempt_id)
        for question in self.questions:
            row = rows[question.id]
            self.assertFalse(row['answer_locked'])
            self.assertEqual([img['id'] for img in row['explanation_images']],
                             [self.explanation_image[question.id]])
            self.assertEqual([img['id'] for img in row['stem_images']], [self.stem_image[question.id]])
            self.assertEqual((row['video_url'], row['video_status']), (self.VIDEO, 'completed'))
            self.assertEqual(row['video_subtitles_url'], 'https://example.test/explain.vtt')

    def test_review_figure_urls_load_where_the_bare_url_is_refused(self):
        user = self.login(_user('w3-media-review-url', premium=True))
        rows = self.review(self.test, self._completed_attempt(user))
        url = rows[self.locked.id]['explanation_images'][0]['url']
        image_id = self.explanation_image[self.locked.id]
        anonymous = APIClient()
        bare = anonymous.get(f'/api/questions/images/{image_id}/serve/')
        self.assertEqual(bare.status_code, 403)
        self.assertEqual(bare.data['code'], 'image_token_required')
        signed = anonymous.get(url.replace('http://testserver', ''))
        self.assertEqual(signed.status_code, 302)   # stored public URL: redirect
        self.assertEqual(signed['Location'], f'https://example.test/explanation-{self.locked.id}.png')

    def test_an_option_figure_the_explanation_cites_is_reviewed_as_a_question_figure(self):
        """An option's figure that the explanation also cites is an option figure everywhere
        (questions.image_context.runtime_role, which resolve_runtime_image_role delegates to): the
        student needs it during the test, and the review lists it with the question side, public URL.
        (The old serializer rule read it as 'explanation' and the exam payload left it out.)"""
        figure = QuestionImage.objects.create(question=self.locked, page_number=3, role='option',
                                              url='https://example.test/option-b.png')
        Question.objects.filter(pk=self.locked.pk).update(
            option_b=f'B [[img:{figure.id}]]', explanation=f'{SECRET} see [[img:{figure.id}]]')
        user = self.login(_user('w3-media-option-figure', premium=True))
        exam_rows = self._detail_rows()
        exam_images = {img['id']: img for img in exam_rows[self.locked.id]['images']}
        self.assertIn(figure.id, exam_images)
        self.assertEqual(exam_images[figure.id]['role'], 'option')
        row = self.review(self.test, self._completed_attempt(user))[self.locked.id]
        stem = {img['id']: img for img in row['stem_images']}
        self.assertEqual(stem[figure.id]['role'], 'option')
        self.assertEqual(stem[figure.id]['option_label'], 'B')
        self.assertNotIn('?t=', stem[figure.id]['url'])
        self.assertNotIn(figure.id, [img['id'] for img in row['explanation_images']])

    def test_unfinished_video_is_not_linked(self):
        Question.objects.filter(pk=self.locked.pk).update(video_status='processing')
        user = self.login(_user('w3-media-review-processing', premium=True))
        rows = self.review(self.test, self._completed_attempt(user))
        row = rows[self.locked.id]
        self.assertEqual(row['video_status'], 'processing')
        self.assertIsNone(row['video_url'])

    def test_review_does_not_scale_with_questions(self):
        user = self.login(_user('w3-media-review-queries', premium=True))
        subject = Subject.objects.create(name='Wave3 Review Queries', code='W3RQ')
        counts = []
        for n in (3, 12):
            questions = [_q(subject, f'rq-{n}-{i}') for i in range(n)]
            for question in questions:
                QuestionImage.objects.create(question=question, page_number=1, role='primary',
                                             url='https://example.test/s.png')
                QuestionImage.objects.create(question=question, page_number=2, role='explanation',
                                             url='https://example.test/e.png')
            test = Test.objects.create(title=f'Wave3 review queries {n}', test_type='mixed')
            test.questions.set(questions)
            attempt = TestAttempt.objects.create(user=user, test=test, is_completed=True,
                                                 completed_at=timezone.now())
            for question in questions:
                QuestionResponse.objects.create(attempt=attempt, question=question, selected_answer='C',
                                                is_correct=True)
            self.review(test, attempt.id)  # warm-up
            with CaptureQueriesContext(connection) as ctx:
                rows = self.review(test, attempt.id)
            self.assertEqual(sum(len(row['explanation_images']) for row in rows.values()), n)
            counts.append(len(ctx.captured_queries))
        self.assertEqual(counts[0], counts[1])


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
