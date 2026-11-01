"""Mistake Notebook auto-capture and server-side study time (2026-11).

Before: nothing created MistakeNotebook rows or StudyTimeBreakdown rows,
so the Mistake Notebook and Study Time pages were always empty (and both
pages crashed on the wrapped API payloads).
"""
from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from questions.models import MistakeNotebook, Question, QuestionAttempt, StudyTimeBreakdown, Subject
from questions.study_time import clamp_seconds, rows_for_test_submission

User = get_user_model()


def _question(subject, i, **kw):
    defaults = dict(
        question_text=f'Mistake Q{i}', option_a='A', option_b='B', option_c='C',
        option_d='D', correct_answer='A', year=2024, subject=subject,
    )
    defaults.update(kw)
    return Question.objects.create(**defaults)


class RowsForTestSubmissionTests(SimpleTestCase):
    def test_plausible_timings_are_kept(self):
        rows = rows_for_test_submission([(1, 30, True), (1, 20, False), (2, 10, True)], 600, 30)
        self.assertEqual(rows, [(1, 30, 1), (1, 20, 0), (2, 10, 1)])

    def test_timings_cannot_exceed_elapsed_time(self):
        rows = rows_for_test_submission([(1, 1800, True), (2, 1800, True)], 600, 30)
        self.assertEqual([r[1] for r in rows], [300, 300])
        # Submitting instantly cannot claim hours of study.
        rows = rows_for_test_submission([(1, 1800, True), (2, 1800, True)], 0.02, 30)
        self.assertEqual([r[1] for r in rows], [0, 0])

    def test_missing_timings_spread_capped_duration(self):
        rows = rows_for_test_submission([(1, None, True), (2, 0, True)], 10 * 3600, 30)
        self.assertEqual([r[1] for r in rows], [900, 900])

    def test_unknown_elapsed_does_not_scale(self):
        self.assertEqual(rows_for_test_submission([(1, 120, True)], None, 30), [(1, 120, 1)])

    def test_questions_without_subject_are_ignored(self):
        self.assertEqual(rows_for_test_submission([(None, 50, True)], 100, 30), [])

    def test_clamp_seconds(self):
        self.assertEqual(clamp_seconds('abc'), 0)
        self.assertEqual(clamp_seconds(-5), 0)
        self.assertEqual(clamp_seconds(10 ** 9), 1800)
        self.assertEqual(clamp_seconds('12.7'), 12)
        self.assertEqual(clamp_seconds(float('inf')), 0)


class QuestionBankCaptureTests(TestCase):
    def setUp(self):
        from accounts.models import Subscription

        self.subject = Subject.objects.create(name='Mistake Subject')
        self.q = _question(self.subject, 1)
        self.user = User.objects.create_user(username='mistake-u', password='x')
        # Answers to non-showcase questions are a paid feature (402 for free
        # users, covered by test_wave1_g2_entitlement); these tests are about
        # mistake capture and study time, so the student is a subscriber.
        Subscription.objects.create(user=self.user, plan='1_year', status='active',
                                    expires_at=timezone.now() + timedelta(days=365))
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _answer(self, letter, question=None, **extra):
        q = question or self.q
        return self.client.post(f'/api/questions/{q.id}/attempt/', {'selected_answer': letter, **extra}, format='json')

    def test_wrong_answer_creates_entry_and_correct_does_not(self):
        r = self._answer('b')
        self.assertEqual(r.status_code, 200, r.data)
        entry = MistakeNotebook.objects.get(user=self.user, question=self.q)
        self.assertEqual((entry.selected_answer, entry.correct_answer, entry.review_status), ('B', 'A', 'new'))
        self.assertIsNotNone(entry.attempt_id)
        q2 = _question(self.subject, 2)
        self._answer('a', question=q2)
        self.assertFalse(MistakeNotebook.objects.filter(question=q2).exists())
        self.assertTrue(QuestionAttempt.objects.get(user=self.user, question=q2).is_correct)

    def test_invalid_letters_are_rejected(self):
        for bad in ['Z', '', 42, None]:
            self.assertEqual(self._answer(bad).status_code, 400, bad)
        self.assertFalse(QuestionAttempt.objects.exists())

    def test_wrong_again_after_mastery_goes_back_to_learning(self):
        self._answer('B')
        MistakeNotebook.objects.filter(user=self.user).update(
            review_status='mastered', next_review_at=timezone.now() + timedelta(days=7))
        self._answer('C')
        entry = MistakeNotebook.objects.get(user=self.user, question=self.q)
        self.assertEqual((entry.review_status, entry.selected_answer), ('learning', 'C'))
        self.assertLessEqual(entry.next_review_at, timezone.now())
        self.assertEqual(MistakeNotebook.objects.filter(user=self.user).count(), 1)

    def test_answer_records_capped_study_time(self):
        self._answer('A', time_spent_seconds=99999)
        self._answer('A', question=_question(self.subject, 3), time_spent_seconds='40')
        row = StudyTimeBreakdown.objects.get(user=self.user, subject=self.subject)
        self.assertEqual((row.seconds, row.question_count), (1800 + 40, 2))

    def test_practice_mode_attempt(self):
        base = f'/api/questions/{self.q.id}/practice/attempt/'
        r = self.client.post(base, {'answer': ' d', 'time_spent': 75}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(r.data['correct'])
        self.assertEqual(MistakeNotebook.objects.get(user=self.user, question=self.q).selected_answer, 'D')
        row = StudyTimeBreakdown.objects.get(user=self.user, subject=self.subject)
        self.assertEqual((row.seconds, row.question_count), (75, 1))
        self.assertEqual(self.client.post(base, {'answer': 'Q'}, format='json').status_code, 400)

    def test_notebook_api_contract_and_isolation(self):
        self._answer('B')
        data = self.client.get('/api/analytics/mistake-notebook/').data
        self.assertEqual(data['count'], 1)
        entry = data['results'][0]
        self.assertEqual(entry['question'], self.q.id)
        self.assertEqual(entry['option_b'], 'B')
        stats = self.client.get('/api/analytics/mistake-notebook/stats/').data
        self.assertEqual(set(stats['by_status']), {'new', 'learning', 'reviewing', 'mastered'})
        self.assertEqual((stats['total'], stats['due_today']), (1, 1))
        self.assertEqual(self.client.get('/api/analytics/mistake-notebook/due/').data['count'], 1)
        reviewed = self.client.post(f"/api/analytics/mistake-notebook/{entry['id']}/review/").data
        self.assertEqual(reviewed['review_status'], 'learning')
        self.assertEqual(self.client.get('/api/analytics/mistake-notebook/due/').data['count'], 0)

        other = APIClient()
        other.force_authenticate(User.objects.create_user(username='other-u', password='x'))
        self.assertEqual(other.get('/api/analytics/mistake-notebook/').data['count'], 0)
        self.assertEqual(other.post(f"/api/analytics/mistake-notebook/{entry['id']}/review/").status_code, 404)

    def test_study_time_api_contract(self):
        self._answer('A', time_spent_seconds=90)
        data = self.client.get('/api/analytics/study-time/').data
        self.assertEqual(len(data['breakdown']), 1)
        self.assertEqual(data['breakdown'][0]['subject_name'], 'Mistake Subject')
        self.assertEqual(data['totals'][0]['total_seconds'], 90)


class TestSubmissionCaptureTests(TestCase):
    def setUp(self):
        from tests_engine.models import Test
        self.subj_a = Subject.objects.create(name='Submit A', code='SUBA')
        self.subj_b = Subject.objects.create(name='Submit B', code='SUBB')
        self.qa = [_question(self.subj_a, i) for i in (1, 2)]
        self.qb = [_question(self.subj_b, i) for i in (3, 4)]
        self.user = User.objects.create_user(username='submit-capture-u', password='x')
        self.test = Test.objects.create(title='Capture test', test_type='mixed', negative_marking=False,
                                        time_limit_minutes=30)
        self.test.questions.set(self.qa + self.qb)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _start(self, minutes_ago=10):
        from tests_engine.models import TestAttempt
        r = self.client.post(f'/api/tests/{self.test.id}/start/')
        self.assertEqual(r.status_code, 200, r.data)
        TestAttempt.objects.filter(pk=r.data['attempt_id']).update(
            started_at=timezone.now() - timedelta(minutes=minutes_ago))
        return r.data['attempt_id']

    def _submit(self, attempt_id, answers):
        r = self.client.post(f'/api/tests/{self.test.id}/submit/',
                             {'attempt_id': attempt_id, 'answers': answers}, format='json')
        self.assertEqual(r.status_code, 200, r.data)

    def test_submit_records_mistakes_and_per_subject_time(self):
        self._submit(self._start(), [
            {'question_id': self.qa[0].id, 'selected_answer': 'A', 'time_taken_seconds': 30},   # right
            {'question_id': self.qa[1].id, 'selected_answer': 'B', 'time_taken_seconds': 45},   # wrong
            {'question_id': self.qb[0].id, 'selected_answer': 'c', 'time_taken_seconds': 20},   # wrong
            {'question_id': self.qb[1].id, 'selected_answer': '', 'time_taken_seconds': 5},     # skipped
        ])
        mistakes = set(MistakeNotebook.objects.filter(user=self.user).values_list('question_id', flat=True))
        self.assertEqual(mistakes, {self.qa[1].id, self.qb[0].id})
        rows = {r.subject_id: (r.seconds, r.question_count) for r in StudyTimeBreakdown.objects.filter(user=self.user)}
        self.assertEqual(rows, {self.subj_a.id: (75, 2), self.subj_b.id: (25, 1)})

    def test_instant_submit_cannot_claim_hours(self):
        self._submit(self._start(minutes_ago=0), [
            {'question_id': q.id, 'selected_answer': 'A', 'time_taken_seconds': 1800} for q in self.qa + self.qb
        ])
        total = sum(StudyTimeBreakdown.objects.filter(user=self.user).values_list('seconds', flat=True))
        self.assertLess(total, 60)


class BackfillCommandTests(TestCase):
    def test_backfills_are_idempotent(self):
        from tests_engine.models import QuestionResponse, Test, TestAttempt
        subject = Subject.objects.create(name='Backfill S')
        q1, q2 = _question(subject, 1), _question(subject, 2)
        user = User.objects.create_user(username='backfill-u', password='x')
        QuestionAttempt.objects.create(user=user, question=q1, selected_answer='B', is_correct=False)
        test = Test.objects.create(title='Old test', test_type='mixed', time_limit_minutes=30)
        now = timezone.now()
        attempt = TestAttempt.objects.create(user=user, test=test, is_completed=True,
                                             completed_at=now, time_taken_seconds=600)
        QuestionResponse.objects.create(attempt=attempt, question=q2, selected_answer='C',
                                        is_correct=False, time_taken_seconds=120)

        for _ in range(2):
            call_command('backfill_mistake_notebook', stdout=StringIO())
            call_command('backfill_study_time', stdout=StringIO())
            self.assertEqual(
                set(MistakeNotebook.objects.filter(user=user).values_list('question_id', 'selected_answer')),
                {(q1.id, 'B'), (q2.id, 'C')},
            )
            row = StudyTimeBreakdown.objects.get(user=user, subject=subject)
            self.assertEqual((row.seconds, row.question_count), (120, 2))
