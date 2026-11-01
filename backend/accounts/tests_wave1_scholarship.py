"""Wave 1 regression tests: scholarship challenge (ACC-10, CFG-21).

The server now chooses the five questions (POST /api/auth/scholarship/start/)
and /verify-scholarship/ only scores that signed, user- and attempt-bound
set, once, with the attempt counter checked under a row lock.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from questions.models import Question, Subject

User = get_user_model()
START = '/api/auth/scholarship/start/'
VERIFY = '/api/auth/verify-scholarship/'


class ScholarshipChallengeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        subject = Subject.objects.create(name='Medicine', code='med-sch')
        cls.eligible = [
            Question.objects.create(
                question_text=f'Eligible question {i}?', option_a='A1', option_b='B1', option_c='C1', option_d='D1',
                correct_answer='ABCD'[i % 4], year=2024, subject=subject, is_scholarship_eligible=True,
            )
            for i in range(7)
        ]
        cls.known = Question.objects.create(
            question_text='Ineligible question?', option_a='A', option_b='B', option_c='C', option_d='D',
            correct_answer='A', year=2024, subject=subject, is_scholarship_eligible=False,
        )

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='scholar', email='scholar@local.test', password='x-Long-passw0rd')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def start(self):
        r = self.client.post(START)
        self.assertEqual(r.status_code, 200, r.data)
        return r.data

    @staticmethod
    def answers(question_ids, correct=True):
        out = {}
        for qid in question_ids:
            answer = Question.objects.get(pk=qid).correct_answer
            out[str(qid)] = answer if correct else ('B' if answer == 'A' else 'A')
        return out

    def submit(self, answers, token):
        return self.client.post(VERIFY, {'answers': answers, 'challenge_token': token}, format='json')

    def test_start_issues_five_server_chosen_questions_without_answers(self):
        data = self.start()
        self.assertEqual(len(data['questions']), 5)
        self.assertTrue(data['challenge_token'])
        eligible_ids = {q.id for q in self.eligible}
        for q in data['questions']:
            self.assertIn(q['id'], eligible_ids)
            self.assertNotIn('correct_answer', q)
            self.assertEqual(set(q), {'id', 'question_text', 'option_a', 'option_b', 'option_c', 'option_d'})

    def test_issued_set_with_correct_answers_passes_at_79(self):
        data = self.start()
        ids = [q['id'] for q in data['questions']]
        r = self.submit(self.answers(ids), data['challenge_token'])
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['status'], 'passed')
        self.user.refresh_from_db()
        self.assertEqual((self.user.scholarship_test_passed, self.user.scholarship_granted_price, self.user.scholarship_test_attempts), (True, 79, 1))

    def test_client_chosen_questions_are_rejected(self):
        data = self.start()
        issued = {q['id'] for q in data['questions']}
        others = [q.id for q in self.eligible if q.id not in issued]
        chosen = list(issued)[:3] + others[:2]
        r = self.submit(self.answers(chosen), data['challenge_token'])
        self.assertEqual(r.status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.scholarship_test_attempts, 0)

    def test_submission_without_a_started_challenge_is_rejected(self):
        ids = [q.id for q in self.eligible[:5]]
        r = self.client.post(VERIFY, {'answers': self.answers(ids)}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'scholarship_not_started')
        r = self.submit(self.answers(ids), 'forged-token')
        self.assertEqual(r.data['code'], 'scholarship_not_started')

    def test_a_challenge_can_be_submitted_only_once(self):
        data = self.start()
        ids = [q['id'] for q in data['questions']]
        first = self.submit(self.answers(ids, correct=False), data['challenge_token'])
        self.assertEqual(first.data['status'], 'failed')
        again = self.submit(self.answers(ids), data['challenge_token'])
        self.assertEqual(again.status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.scholarship_test_attempts, 1)
        self.assertFalse(self.user.scholarship_test_passed)

    def test_second_attempt_passes_at_99_and_then_the_challenge_locks(self):
        data = self.start()
        self.submit(self.answers([q['id'] for q in data['questions']], correct=False), data['challenge_token'])
        data = self.start()
        r = self.submit(self.answers([q['id'] for q in data['questions']], correct=False), data['challenge_token'])
        self.assertIn('No attempts remaining', r.data['message'])
        self.assertEqual(self.client.post(START).status_code, 403)

    def test_second_attempt_pass_price(self):
        data = self.start()
        self.submit(self.answers([q['id'] for q in data['questions']], correct=False), data['challenge_token'])
        data = self.start()
        r = self.submit(self.answers([q['id'] for q in data['questions']]), data['challenge_token'])
        self.assertEqual(r.data['status'], 'passed')
        self.user.refresh_from_db()
        self.assertEqual(self.user.scholarship_granted_price, 99)

    def test_token_of_another_user_is_rejected(self):
        data = self.start()
        other = User.objects.create_user(username='other', email='other@local.test', password='x-Long-passw0rd')
        client = APIClient()
        client.force_authenticate(other)
        r = client.post(VERIFY, {'answers': self.answers([q['id'] for q in data['questions']]), 'challenge_token': data['challenge_token']}, format='json')
        self.assertEqual(r.status_code, 400)
        other.refresh_from_db()
        self.assertEqual(other.scholarship_test_attempts, 0)

    def test_expired_challenge_is_rejected(self):
        data = self.start()
        with mock.patch('accounts.views.SCHOLARSHIP_CHALLENGE_MAX_AGE', -1):
            r = self.submit(self.answers([q['id'] for q in data['questions']]), data['challenge_token'])
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'scholarship_expired')

    def test_stale_counter_cannot_exceed_the_attempt_cap(self):
        # Simulates parallel submissions: the request's user object still
        # says 0 attempts while the database already holds the cap.
        data = self.start()
        User.objects.filter(pk=self.user.pk).update(scholarship_test_attempts=2)
        r = self.submit(self.answers([q['id'] for q in data['questions']]), data['challenge_token'])
        self.assertEqual(r.status_code, 403)
        self.user.refresh_from_db()
        self.assertEqual(self.user.scholarship_test_attempts, 2)
        self.assertFalse(self.user.scholarship_test_passed)

    def test_passed_user_cannot_start_again(self):
        User.objects.filter(pk=self.user.pk).update(scholarship_test_passed=True, scholarship_test_attempts=1)
        self.user.refresh_from_db()
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.post(START).status_code, 400)

    def test_not_enough_eligible_questions_returns_an_empty_set(self):
        Question.objects.filter(is_scholarship_eligible=True).exclude(pk__in=[q.id for q in self.eligible[:4]]).update(is_scholarship_eligible=False)
        data = self.start()
        self.assertEqual(data['questions'], [])
        self.assertIsNone(data['challenge_token'])
