"""Mistake Notebook API hardening (QB-04 / AN-01 / AN-21).

POST used to accept any question id and answer with its correct answer and
explanation (a freemium bypass and an answer oracle during tests), and PATCH
could re-point an entry at another question or forge the review schedule.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Subscription
from accounts.models_freemium import FreeShowcaseQuestion
from questions.models import MistakeNotebook, Question, QuestionAttempt, Subject
from tests_engine.models import QuestionResponse, Test, TestAttempt

User = get_user_model()
URL = '/api/analytics/mistake-notebook/'


def _question(subject, i, **kw):
    data = dict(question_text=f'Notebook Q{i}', option_a='A1', option_b='B1', option_c='C1', option_d='D1',
                correct_answer='C', explanation=f'Explanation {i}', year=2024, subject=subject)
    data.update(kw)
    return Question.objects.create(**data)


class MistakeNotebookHardeningTests(TestCase):
    def setUp(self):
        self.subject = Subject.objects.create(name='MN Subject', code='MNS')
        self.q_premium = _question(self.subject, 1)
        self.q_answered = _question(self.subject, 2)
        self.q_other = _question(self.subject, 3)
        self.user = User.objects.create_user(username='mn-free', email='mn-free@example.com', password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _entry(self, question, **kw):
        data = dict(user=self.user, question=question, selected_answer='A', correct_answer='C', is_correct=False)
        data.update(kw)
        return MistakeNotebook.objects.create(**data)

    # ── POST ─────────────────────────────────────────────────────────────
    def test_post_unanswered_question_is_rejected_without_leaking_answer(self):
        r = self.client.post(URL, {'question': self.q_premium.id}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertNotIn('correct_answer', r.data)
        self.assertNotIn('explanation', r.data)
        self.assertFalse(MistakeNotebook.objects.filter(user=self.user).exists())

    def test_post_inactive_or_missing_question_is_404(self):
        hidden = _question(self.subject, 9, is_active=False)
        QuestionAttempt.objects.create(user=self.user, question=hidden, selected_answer='A', is_correct=False)
        self.assertEqual(self.client.post(URL, {'question': hidden.id}, format='json').status_code, 404)
        self.assertEqual(self.client.post(URL, {'question': 999999}, format='json').status_code, 404)
        self.assertEqual(self.client.post(URL, {'question': 'abc'}, format='json').status_code, 400)

    def test_post_real_bank_mistake_creates_entry_from_the_attempt(self):
        QuestionAttempt.objects.create(user=self.user, question=self.q_answered, selected_answer='B', is_correct=False)
        r = self.client.post(URL, {'question': self.q_answered.id, 'selected_answer': 'D',
                                   'review_status': 'mastered', 'user_note': 'remember'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        entry = MistakeNotebook.objects.get(user=self.user, question=self.q_answered)
        # Selected answer comes from the real attempt, review state from the server.
        self.assertEqual((entry.selected_answer, entry.review_status, entry.user_note), ('B', 'new', 'remember'))
        # Free plan, not a showcase question: the key stays locked.
        self.assertEqual((r.data['correct_answer'], r.data['explanation'], r.data['answer_locked']), ('', '', True))

    def test_post_counts_only_completed_test_mistakes(self):
        test = Test.objects.create(title='MN test', test_type='mixed')
        live = TestAttempt.objects.create(user=self.user, test=test)
        QuestionResponse.objects.create(attempt=live, question=self.q_answered, selected_answer='A', is_correct=False)
        # In-progress attempt: no answer oracle.
        r = self.client.post(URL, {'question': self.q_answered.id}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        TestAttempt.objects.filter(pk=live.pk).update(is_completed=True, completed_at=timezone.now())
        r = self.client.post(URL, {'question': self.q_answered.id}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        # Added, but a completed test does not unlock the key for a free user.
        self.assertEqual((r.data['correct_answer'], r.data['explanation']), ('', ''))

    def test_post_existing_entry_updates_only_note_and_flag(self):
        entry = self._entry(self.q_answered)
        QuestionAttempt.objects.create(user=self.user, question=self.q_answered, selected_answer='A', is_correct=False)
        r = self.client.post(URL, {'question': self.q_answered.id, 'is_flagged': 'true',
                                   'review_status': 'mastered'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        entry.refresh_from_db()
        self.assertTrue(entry.is_flagged)
        self.assertEqual(entry.review_status, 'new')

    # ── PATCH ────────────────────────────────────────────────────────────
    def test_patch_cannot_repoint_question_or_forge_review_state(self):
        entry = self._entry(self.q_answered)
        self._entry(self.q_other)  # already in the notebook: re-pointing used to 500
        r = self.client.patch(f'{URL}{entry.id}/', {
            'question': self.q_other.id, 'review_status': 'mastered', 'review_count': 9,
            'last_reviewed_at': timezone.now().isoformat(), 'next_review_at': timezone.now().isoformat(),
            'is_correct': True, 'selected_answer': 'C', 'user_note': 'my note', 'is_flagged': True,
        }, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        entry.refresh_from_db()
        self.assertEqual(entry.question_id, self.q_answered.id)
        self.assertEqual((entry.review_status, entry.review_count), ('new', 0))
        self.assertIsNone(entry.last_reviewed_at)
        self.assertFalse(entry.is_correct)
        self.assertEqual(entry.selected_answer, 'A')
        self.assertEqual((entry.user_note, entry.is_flagged), ('my note', True))

    def test_patch_rejects_oversized_note(self):
        entry = self._entry(self.q_answered)
        r = self.client.patch(f'{URL}{entry.id}/', {'user_note': 'x' * 5001}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_review_action_still_advances_schedule(self):
        entry = self._entry(self.q_answered, next_review_at=timezone.now() - timedelta(minutes=1))
        QuestionAttempt.objects.create(user=self.user, question=self.q_answered, selected_answer='A', is_correct=False)
        r = self.client.post(f'{URL}{entry.id}/review/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data['review_status'], r.data['review_count']), ('learning', 1))
        self.assertEqual((r.data['correct_answer'], r.data['answer_locked']), ('', True))
        FreeShowcaseQuestion.objects.create(question=self.q_answered, year=2024, position=1)
        r = self.client.post(f'{URL}{entry.id}/review/')
        self.assertEqual((r.data['review_count'], r.data['correct_answer'], r.data['answer_locked']), (2, 'C', False))

    # ── answer visibility on GET ─────────────────────────────────────────
    def _listed(self, client=None):
        data = (client or self.client).get(URL).data
        return {row['question']: row for row in data['results']}

    def test_planted_entry_hides_answer_for_free_user(self):
        self._entry(self.q_premium)  # e.g. created through the old unchecked POST
        row = self._listed()[self.q_premium.id]
        self.assertEqual((row['correct_answer'], row['explanation']), ('', ''))
        self.assertEqual(row['question_text'], 'Notebook Q1')  # the stem is not secret

    def test_answer_visible_only_for_showcase_or_premium(self):
        self._entry(self.q_premium)
        self._entry(self.q_answered)
        self._entry(self.q_other)
        # e.g. answered while subscribed: a bank attempt does not unlock the key later.
        QuestionAttempt.objects.create(user=self.user, question=self.q_answered, selected_answer='A', is_correct=False)
        FreeShowcaseQuestion.objects.create(question=self.q_other, year=2024, position=1)
        rows = self._listed()
        self.assertEqual(rows[self.q_premium.id]['correct_answer'], '')
        self.assertEqual((rows[self.q_answered.id]['correct_answer'], rows[self.q_answered.id]['answer_locked']),
                         ('', True))
        self.assertEqual(rows[self.q_other.id]['explanation'], 'Explanation 3')
        self.assertFalse(rows[self.q_other.id]['answer_locked'])

        Subscription.objects.create(user=self.user, plan='1_year', status='active',
                                    expires_at=timezone.now() + timedelta(days=30))
        rows = self._listed()
        self.assertEqual(rows[self.q_premium.id]['correct_answer'], 'C')
        self.assertEqual(rows[self.q_answered.id]['explanation'], 'Explanation 2')
        self.assertFalse(any(row['answer_locked'] for row in rows.values()))

    def test_other_users_entries_stay_private(self):
        entry = self._entry(self.q_answered)
        other = APIClient()
        other.force_authenticate(User.objects.create_user(username='mn-other', password='x'))
        self.assertEqual(other.get(URL).data['count'], 0)
        self.assertEqual(other.patch(f'{URL}{entry.id}/', {'user_note': 'x'}, format='json').status_code, 404)
        self.assertEqual(other.delete(f'{URL}{entry.id}/').status_code, 404)
