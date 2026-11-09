"""Questions UPSC dropped, and questions without an answer key, are shown but not scored; past attempts are scored
again after an answer-key change (tests_engine.scoring, ``manage.py rescore_key_changes``), keeping the original
score and an audit row."""
import io
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from analytics.models import UserTopicPerformance
from questions.models import AnswerKeyChange, MistakeNotebook, Question, QuestionAttempt, Subject
from tests_engine.models import AttemptRescore, QuestionResponse, Test, TestAttempt
from tests_engine.scoring import rescore_pending_key_changes

User = get_user_model()


def _premium(name):
    from accounts.models import Subscription
    user = User.objects.create_user(username=name, password='x', role='student')
    Subscription.objects.create(user=user, plan='1_year', status='active',
                                expires_at=timezone.now() + timedelta(days=365))
    return user


class _Case(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.subject = Subject.objects.create(name='Rescore Medicine', code='RS-M')
        self.q = [Question.objects.create(question_text=f'Rescore question {i}', option_a='a', option_b='b',
                                          option_c='c', option_d='d', correct_answer='A', year=2020,
                                          exam_type='cms', subject=self.subject) for i in range(4)]
        self.test = Test.objects.create(title='Rescore test', test_type='mixed', negative_marking=True,
                                        negative_mark_value=0.33)
        self.test.questions.set(self.q)
        self.user = _premium('rescore-student')
        self.client.force_authenticate(self.user)

    def take(self, letters):
        attempt_id = self.client.post(f'/api/tests/{self.test.id}/start/').data['attempt_id']
        answers = [{'question_id': q.id, 'selected_answer': letter} for q, letter in zip(self.q, letters)]
        r = self.client.post(f'/api/tests/{self.test.id}/submit/', {'attempt_id': attempt_id, 'answers': answers},
                             format='json')
        self.assertEqual(r.status_code, 200, r.data)
        return TestAttempt.objects.get(pk=attempt_id), r.data

    def change_key(self, question, new):
        old = question.correct_answer
        Question.objects.filter(pk=question.pk).update(correct_answer=new)
        return AnswerKeyChange.objects.create(question=question, old_key=old, new_key=new, source='official_key',
                                              reason='Official UPSC answer key')


class DroppedQuestionTests(_Case):

    def test_a_question_upsc_dropped_is_shown_but_not_scored(self):
        Question.objects.filter(pk=self.q[2].pk).update(is_dropped=True)
        attempt, data = self.take(['A', 'B', 'A', ''])  # right, wrong, dropped, unanswered
        self.assertEqual((attempt.correct_count, attempt.incorrect_count, attempt.unanswered_count), (1, 1, 1))
        self.assertEqual(attempt.total_marks, 3)
        self.assertAlmostEqual(attempt.score, 1 - 0.33)
        self.assertEqual(attempt.not_scored, [self.q[2].id])
        self.assertEqual(data['not_scored_count'], 1)
        dropped = QuestionResponse.objects.get(attempt=attempt, question=self.q[2])
        self.assertEqual((dropped.selected_answer, dropped.is_correct), ('A', None))  # answer kept, not scored
        perf = UserTopicPerformance.objects.get(user=self.user, subject=self.subject, topic=None)
        self.assertEqual((perf.total_attempts, perf.correct_answers, perf.incorrect_answers), (2, 1, 1))
        self.assertEqual(set(MistakeNotebook.objects.filter(user=self.user).values_list('question_id', flat=True)),
                         {self.q[1].id})

        review = self.client.get(f'/api/tests/{self.test.id}/review/', {'attempt_id': attempt.id}).data
        rows = {row['question_id']: row for row in review['questions']}
        self.assertTrue(rows[self.q[2].id]['dropped_by_upsc'])
        self.assertTrue(rows[self.q[2].id]['not_scored'])
        self.assertFalse(rows[self.q[0].id]['dropped_by_upsc'])
        self.assertEqual(review['not_scored_count'], 1)
        self.assertEqual(sum(b['correct'] + b['incorrect'] + b['unanswered']
                             for b in review['subject_breakdown'].values()), 3)

    def test_a_removed_question_is_not_called_dropped_by_upsc(self):
        Question.objects.filter(pk=self.q[3].pk).update(is_dropped=True, is_active=False)  # removed from the bank
        self.assertFalse(Question.objects.get(pk=self.q[3].pk).dropped_by_upsc)
        attempt, _data = self.take(['A', 'A', 'A', 'A'])
        self.assertEqual((attempt.total_marks, attempt.not_scored), (4, []))

    def test_the_question_api_says_dropped_by_upsc(self):
        Question.objects.filter(pk=self.q[0].pk).update(is_dropped=True)
        detail = self.client.get(f'/api/questions/{self.q[0].id}/').data
        self.assertTrue(detail['dropped_by_upsc'])


class RescoreTests(_Case):

    def setUp(self):
        super().setUp()
        # right, wrong, wrong, unanswered: 1 - 2 x 0.33 = 0.34 of 4
        self.attempt, _data = self.take(['A', 'B', 'C', ''])
        self.assertAlmostEqual(self.attempt.score, 0.34)

    def _run(self, apply=True):
        return rescore_pending_key_changes(apply=apply)

    def test_dry_run_writes_nothing(self):
        change = self.change_key(self.q[1], 'B')
        stats = self._run(apply=False)
        self.assertEqual(stats['attempts rescored'], 1)
        self.attempt.refresh_from_db()
        self.assertAlmostEqual(self.attempt.score, 0.34)
        self.assertFalse(AttemptRescore.objects.exists())
        change.refresh_from_db()
        self.assertEqual(change.rescore_status, 'pending')

    def test_a_key_change_and_a_dropped_question_rescore_the_attempt_keeping_the_original(self):
        change = self.change_key(self.q[1], 'B')  # the student's B is now right
        Question.objects.filter(pk=self.q[2].pk).update(is_dropped=True)  # the wrong C is no longer scored
        stats = self._run()
        self.assertEqual(stats['attempts rescored'], 1)
        self.attempt.refresh_from_db()
        self.assertEqual((self.attempt.correct_count, self.attempt.incorrect_count, self.attempt.unanswered_count),
                         (2, 0, 1))
        self.assertEqual((self.attempt.score, self.attempt.total_marks), (2.0, 3))
        self.assertAlmostEqual(self.attempt.original_score, 0.34)
        self.assertEqual(self.attempt.original_total_marks, 4)
        self.assertIsNotNone(self.attempt.rescored_at)
        self.assertEqual(self.attempt.not_scored, [self.q[2].id])
        audit = AttemptRescore.objects.get(attempt=self.attempt)
        self.assertEqual(audit.key_changes, [change.pk])
        self.assertEqual({row['question_id']: (row['was'], row['now']) for row in audit.answers},
                         {self.q[1].id: (False, True), self.q[2].id: (False, None)})
        self.assertAlmostEqual(audit.old_score, 0.34)
        self.assertEqual(audit.new_score, 2.0)
        responses = {r.question_id: r.is_correct for r in QuestionResponse.objects.filter(attempt=self.attempt)}
        self.assertEqual((responses[self.q[1].id], responses[self.q[2].id]), (True, None))
        change.refresh_from_db()
        self.assertEqual(change.rescore_status, 'done')
        self.assertEqual(change.affected['test_attempts'], 1)

        again = self._run()  # a second run changes nothing
        self.assertEqual(again['attempts rescored'], 0)
        self.assertEqual(AttemptRescore.objects.count(), 1)

        Question.objects.filter(pk=self.q[2].pk).update(is_dropped=False)  # restored: scored again
        self._run()
        self.attempt.refresh_from_db()
        self.assertEqual((self.attempt.correct_count, self.attempt.incorrect_count, self.attempt.total_marks),
                         (2, 1, 4))
        self.assertAlmostEqual(self.attempt.score, 2 - 0.33)
        self.assertAlmostEqual(self.attempt.original_score, 0.34)  # still the first score
        self.assertEqual(self.attempt.not_scored, [])
        self.assertEqual(AttemptRescore.objects.count(), 2)

    def test_the_negative_mark_of_the_attempt_is_kept_when_the_test_changed_since(self):
        Test.objects.filter(pk=self.test.pk).update(negative_marking=False)  # an admin edit after the attempt
        self.change_key(self.q[2], 'C')  # the student's C is now right
        self._run()
        self.attempt.refresh_from_db()
        self.assertEqual((self.attempt.correct_count, self.attempt.incorrect_count), (2, 1))
        self.assertAlmostEqual(self.attempt.score, 2 - 0.33)  # still marked like the original

    def test_question_bank_answers_and_the_notebook_follow_the_corrected_key(self):
        other = _premium('rescore-bank')
        QuestionAttempt.objects.create(user=other, question=self.q[1], selected_answer='B', is_correct=False)
        QuestionAttempt.objects.create(user=self.user, question=self.q[1], selected_answer='A', is_correct=True)
        from analytics.views import _notebook_queryset
        self.assertEqual(_notebook_queryset(self.user).filter(question=self.q[1]).count(), 1)  # the test's B
        self.change_key(self.q[1], 'B')
        stats = self._run()
        self.assertEqual(stats['question-bank answers re-marked'], 2)
        self.assertTrue(QuestionAttempt.objects.get(user=other, question=self.q[1]).is_correct)
        self.assertFalse(QuestionAttempt.objects.get(user=self.user, question=self.q[1]).is_correct)
        self.assertEqual(_notebook_queryset(self.user).filter(question=self.q[1]).count(), 0)  # B is right now
        self.assertTrue(MistakeNotebook.objects.filter(user=self.user, question=self.q[1]).exists())  # kept

    def test_the_command_and_the_editorial_helper(self):
        change = self.change_key(self.q[1], 'B')
        out = io.StringIO()
        call_command('rescore_key_changes', stdout=out)
        self.assertIn('attempts rescored 1', out.getvalue())
        self.assertIn('nothing was written', out.getvalue())
        from questions.editorial import rescore_key_change
        admin = User.objects.create_user(username='rescore-admin', password='x', role='admin', is_staff=True)
        result = rescore_key_change(change, actor=admin, apply=True)
        self.assertEqual(result['attempts_rescored'], 1)
        change.refresh_from_db()
        self.assertEqual((change.rescore_status, change.rescored_by_id), ('done', admin.pk))


class KeylessQuestionTests(_Case):
    """A question without a valid A-D key (none, or an import placeholder such as 'F') has no right or wrong answer:
    like the question bank, a test leaves it out of the score and files no mistake; past attempts that scored it as
    wrong are scored again (an audit row, the original score kept)."""

    def test_a_question_without_an_answer_key_is_not_scored(self):
        Question.objects.filter(pk=self.q[2].pk).update(correct_answer='F')  # an import placeholder
        Question.objects.filter(pk=self.q[3].pk).update(correct_answer='')
        attempt, data = self.take(['A', 'B', 'C', ''])  # right, wrong, no key (answered), no key (unanswered)
        self.assertEqual((attempt.correct_count, attempt.incorrect_count, attempt.unanswered_count), (1, 1, 0))
        self.assertEqual(attempt.total_marks, 2)
        self.assertAlmostEqual(attempt.score, 1 - 0.33)
        self.assertEqual(attempt.not_scored, sorted([self.q[2].id, self.q[3].id]))
        self.assertEqual(data['not_scored_count'], 2)
        keyless = QuestionResponse.objects.get(attempt=attempt, question=self.q[2])
        self.assertEqual((keyless.selected_answer, keyless.is_correct), ('C', None))  # answer kept, not scored
        perf = UserTopicPerformance.objects.get(user=self.user, subject=self.subject, topic=None)
        self.assertEqual((perf.total_attempts, perf.correct_answers, perf.incorrect_answers), (2, 1, 1))
        self.assertEqual(set(MistakeNotebook.objects.filter(user=self.user).values_list('question_id', flat=True)),
                         {self.q[1].id})

        review = self.client.get(f'/api/tests/{self.test.id}/review/', {'attempt_id': attempt.id}).data
        rows = {row['question_id']: row for row in review['questions']}
        self.assertTrue(rows[self.q[2].id]['not_scored'])
        self.assertTrue(rows[self.q[2].id]['no_answer_key'])
        self.assertFalse(rows[self.q[2].id]['dropped_by_upsc'])
        self.assertFalse(rows[self.q[0].id]['no_answer_key'])
        self.assertEqual(review['not_scored_count'], 2)

    def test_past_attempts_that_scored_it_as_wrong_are_scored_again(self):
        attempt, _data = self.take(['A', 'B', 'C', ''])  # 1 - 2 x 0.33 of 4, scored while every question had a key
        self.assertAlmostEqual(attempt.score, 0.34)
        Question.objects.filter(pk=self.q[2].pk).update(correct_answer='F')  # the student's C counted as wrong
        Question.objects.filter(pk=self.q[3].pk).update(correct_answer='')   # unanswered, counted in the total
        stats = rescore_pending_key_changes(apply=True)
        self.assertEqual((stats['attempts rescored'], stats['questions without an answer key']), (1, 2))
        attempt.refresh_from_db()
        self.assertEqual((attempt.correct_count, attempt.incorrect_count, attempt.unanswered_count,
                          attempt.total_marks), (1, 1, 0, 2))
        self.assertAlmostEqual(attempt.score, 1 - 0.33)
        self.assertAlmostEqual(attempt.original_score, 0.34)
        self.assertEqual(attempt.original_total_marks, 4)
        self.assertEqual(attempt.not_scored, sorted([self.q[2].id, self.q[3].id]))
        audit = AttemptRescore.objects.get(attempt=attempt)
        self.assertIn('without an answer key not scored', audit.reason)
        self.assertEqual({row['question_id']: (row['was'], row['now'], row['not_scored_reason'])
                          for row in audit.answers},
                         {self.q[2].id: (False, None, 'no_answer_key'), self.q[3].id: (None, None, 'no_answer_key')})
        self.assertIsNone(QuestionResponse.objects.get(attempt=attempt, question=self.q[2]).is_correct)
        self.assertEqual(rescore_pending_key_changes(apply=True)['attempts rescored'], 0)  # a second run: nothing

        Question.objects.filter(pk=self.q[2].pk).update(correct_answer='C')  # a key added later (an admin edit)
        rescore_pending_key_changes(apply=True)
        attempt.refresh_from_db()
        self.assertEqual((attempt.correct_count, attempt.incorrect_count, attempt.total_marks, attempt.not_scored),
                         (2, 1, 3, [self.q[3].id]))
        self.assertAlmostEqual(attempt.score, 2 - 0.33)
        self.assertAlmostEqual(attempt.original_score, 0.34)  # still the first score
        self.assertEqual(AttemptRescore.objects.filter(attempt=attempt).count(), 2)

    def test_a_question_added_to_the_test_since_leaves_the_attempt_alone(self):
        attempt, _data = self.take(['A', 'B', 'C', ''])
        added = Question.objects.create(question_text='Added after the attempt', option_a='a', option_b='b',
                                        option_c='c', option_d='d', correct_answer='', year=2020, exam_type='cms',
                                        subject=self.subject)
        self.test.questions.add(added)  # an admin edit: the stored figures never counted it
        rescore_pending_key_changes(apply=True)
        attempt.refresh_from_db()
        self.assertEqual((attempt.total_marks, attempt.unanswered_count, attempt.not_scored), (4, 1, []))
        self.assertFalse(AttemptRescore.objects.exists())

    def test_the_notebook_does_not_list_answers_to_a_question_without_an_answer_key(self):
        from analytics.views import _notebook_queryset
        self.take(['A', 'B', 'C', ''])  # B and C filed as mistakes while every question had a key
        Question.objects.filter(pk=self.q[2].pk).update(correct_answer='')
        self.assertEqual(set(_notebook_queryset(self.user).values_list('question_id', flat=True)), {self.q[1].id})
        self.assertTrue(MistakeNotebook.objects.filter(user=self.user, question=self.q[2]).exists())  # kept
        Question.objects.filter(pk=self.q[2].pk).update(correct_answer='D')  # a key again: listed again
        self.assertEqual(set(_notebook_queryset(self.user).values_list('question_id', flat=True)),
                         {self.q[1].id, self.q[2].id})
