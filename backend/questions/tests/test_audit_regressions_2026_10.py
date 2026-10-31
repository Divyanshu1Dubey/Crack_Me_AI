"""Regression tests for the 2026-10 full-stack audit fixes.

Each test pins a bug that was reproducible before the fix:
practice-state crashes, quest XP farming, test-submit score tampering,
cross-user test visibility, token-refund minting, the feedback endpoint
500 and AI fallback text overwriting real explanations.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from questions.models import Question, Subject

User = get_user_model()


def _question(subject, i, **kw):
    defaults = dict(
        question_text=f'Audit Q{i}', option_a='A', option_b='B', option_c='C',
        option_d='D', correct_answer='A', year=2024, subject=subject,
    )
    defaults.update(kw)
    return Question.objects.create(**defaults)


class PracticeStateTests(TestCase):
    def setUp(self):
        self.subject = Subject.objects.create(name='Audit Practice')
        self.q = _question(self.subject, 1)
        self.user = User.objects.create_user(username='practice-u', password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_flag_confidence_time_elimination_round_trip(self):
        base = f'/api/questions/{self.q.id}/practice'
        self.assertEqual(self.client.post(f'{base}/flag/', {'flag': True}, format='json').status_code, 200)
        self.assertEqual(self.client.post(f'{base}/confidence/', {'rating': 9}, format='json').data['confidence'], 5)
        self.client.post(f'{base}/time/', {'seconds': 30}, format='json')
        self.client.post(f'{base}/time/', {'seconds': 15}, format='json')
        self.client.post(f'{base}/eliminate/', {'options': ['c', 'A', 'z']}, format='json')
        state = self.client.get(f'{base}/state/').data
        self.assertTrue(state['flag'])
        self.assertEqual(state['confidence'], 5)
        self.assertEqual(state['time_spent'], 45)
        self.assertEqual(state['eliminated'], ['A', 'C'])
        # Flagging must not create a bookmark.
        self.assertFalse(state['bookmarked'])

    def test_string_false_unflags(self):
        base = f'/api/questions/{self.q.id}/practice'
        self.client.post(f'{base}/flag/', {'flag': True}, format='json')
        self.client.post(f'{base}/flag/', {'flag': 'false'}, format='json')
        self.assertFalse(self.client.get(f'{base}/state/').data['flag'])


class QuestTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='quest-u', password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_daily_quests_are_generated_and_cannot_be_claimed_early(self):
        rows = self.client.get('/api/analytics/quests/').data
        self.assertGreaterEqual(len(rows), 3)
        quest = next(r for r in rows if r['quest_type'] == 'solve_questions')
        r = self.client.patch(f"/api/analytics/quests/{quest['id']}/", {'is_completed': True}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_client_cannot_set_xp_or_progress(self):
        from questions.models import UserQuest
        rows = self.client.get('/api/analytics/quests/').data
        quest = rows[0]
        r = self.client.patch(
            f"/api/analytics/quests/{quest['id']}/",
            {'xp_reward': 100000, 'current_value': 999, 'target_value': 1},
            format='json',
        )
        self.assertEqual(r.status_code, 400)
        q = UserQuest.objects.get(pk=quest['id'])
        self.assertNotEqual(q.xp_reward, 100000)
        self.assertNotEqual(q.current_value, 999)

    def test_claim_once_after_real_progress(self):
        from analytics.models import DailyActivity, StudyStreak
        from django.utils import timezone
        rows = self.client.get('/api/analytics/quests/').data
        quest = next(r for r in rows if r['quest_type'] == 'solve_questions')
        DailyActivity.objects.create(user=self.user, date=timezone.localdate(), questions_attempted=25)
        url = f"/api/analytics/quests/{quest['id']}/"
        self.assertEqual(self.client.patch(url, {'is_completed': True}, format='json').status_code, 200)
        self.assertEqual(self.client.patch(url, {'is_completed': True}, format='json').status_code, 400)
        self.assertEqual(StudyStreak.objects.get(user=self.user).xp_points, quest['xp_reward'])
        # Students cannot delete (and so regenerate + re-claim) quests.
        self.assertEqual(self.client.delete(url).status_code, 403)


class TestSubmitHardeningTests(TestCase):
    def setUp(self):
        from tests_engine.models import Test
        self.subject = Subject.objects.create(name='Audit Submit')
        self.in_test = [_question(self.subject, i) for i in range(4)]
        self.foreign = _question(self.subject, 99)
        self.user = User.objects.create_user(username='submit-u', password='x')
        self.test = Test.objects.create(title='Audit test', test_type='mixed', negative_marking=False)
        self.test.questions.set(self.in_test)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _start(self):
        r = self.client.post(f'/api/tests/{self.test.id}/start/')
        self.assertEqual(r.status_code, 200, r.data)
        return r.data['attempt_id']

    def test_foreign_duplicate_and_omitted_answers_do_not_inflate_score(self):
        attempt_id = self._start()
        answers = [
            {'question_id': self.in_test[0].id, 'selected_answer': 'A'},
            {'question_id': self.in_test[0].id, 'selected_answer': 'A'},   # duplicate
            {'question_id': self.foreign.id, 'selected_answer': 'A'},      # not in test
            {'question_id': self.in_test[1].id, 'selected_answer': 42},    # junk type
        ]
        r = self.client.post(f'/api/tests/{self.test.id}/submit/',
                             {'attempt_id': attempt_id, 'answers': answers}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        from tests_engine.models import TestAttempt
        attempt = TestAttempt.objects.get(pk=attempt_id)
        self.assertEqual(attempt.correct_count, 1)
        self.assertEqual(attempt.unanswered_count, 3)
        self.assertEqual(attempt.total_marks, 4)

    def test_second_submit_is_rejected(self):
        attempt_id = self._start()
        payload = {'attempt_id': attempt_id, 'answers': [{'question_id': self.in_test[0].id, 'selected_answer': 'A'}]}
        self.assertEqual(self.client.post(f'/api/tests/{self.test.id}/submit/', payload, format='json').status_code, 200)
        self.assertEqual(self.client.post(f'/api/tests/{self.test.id}/submit/', payload, format='json').status_code, 400)


class GeneratedTestVisibilityTests(TestCase):
    def test_students_do_not_see_each_others_generated_tests(self):
        from tests_engine.models import Test
        a = User.objects.create_user(username='vis-a', password='x')
        b = User.objects.create_user(username='vis-b', password='x')
        mine = Test.objects.create(title='A practice', test_type='mixed', created_by=a)
        official = Test.objects.create(title='Official', test_type='mixed')
        client = APIClient()
        client.force_authenticate(b)
        data = client.get('/api/tests/').data
        ids = {t['id'] for t in (data['results'] if isinstance(data, dict) else data)}
        self.assertIn(official.id, ids)
        self.assertNotIn(mine.id, ids)
        self.assertEqual(client.post(f'/api/tests/{mine.id}/start/').status_code, 404)


class TokenRefundAccuracyTests(TestCase):
    def test_refund_restores_exact_pool_without_minting(self):
        from accounts.models import TokenBalance
        user = User.objects.create_user(username='refund-u', password='x')
        bal, _ = TokenBalance.objects.get_or_create(user=user)
        bal.purchased_tokens = 5
        bal.purchased_tokens_max = 5
        bal.daily_tokens_used = 0
        bal.weekly_tokens_used = 0
        bal.save()
        before = TokenBalance.objects.get(pk=bal.pk).available_tokens
        for _ in range(3):
            self.assertTrue(bal.consume_token(1))
            bal.refund_token(1, breakdown=bal._last_consumption)
        bal = TokenBalance.objects.get(pk=bal.pk)
        self.assertEqual(bal.available_tokens, before)
        self.assertEqual(bal.purchased_tokens, 5)

    def test_legacy_refund_does_not_raise_high_water_mark(self):
        from accounts.models import TokenBalance
        user = User.objects.create_user(username='refund-legacy', password='x')
        bal, _ = TokenBalance.objects.get_or_create(user=user)
        bal.purchased_tokens = 4
        bal.purchased_tokens_max = 5
        bal.save()
        bal.refund_token(1)
        bal.refund_token(1)
        bal = TokenBalance.objects.get(pk=bal.pk)
        self.assertEqual(bal.purchased_tokens, 5)  # capped at what was paid for
        self.assertEqual(bal.purchased_tokens_max, 5)


class FeedbackEndpointTests(TestCase):
    def test_anonymous_feedback_submission_does_not_500(self):
        subject = Subject.objects.create(name='Audit Feedback')
        q = _question(subject, 1)
        r = APIClient().post('/api/questions/feedback/', {
            'question': q.id, 'category': 'typo', 'comment': 'typo in stem',
        }, format='json')
        self.assertIn(r.status_code, (200, 201, 400))


class AIPerQuestionPersistenceTests(TestCase):
    def setUp(self):
        self.subject = Subject.objects.create(name='Audit AI')

    def test_fallback_is_never_persisted_and_existing_content_kept(self):
        from django.core.cache import cache
        from questions import ai_per_question as ai
        cache.clear()
        q = _question(self.subject, 1, ai_clinical_pearl='Real curated pearl')
        q2 = _question(self.subject, 2)
        with mock.patch.object(ai, '_ai_call', return_value=''):
            self.assertEqual(ai.clinical_significance(q, allow_ai=True), 'Real curated pearl')
            ai.clinical_significance(q2, allow_ai=True)
            ai.memory_trick(q2, allow_ai=True)
        q2.refresh_from_db()
        self.assertEqual(q2.ai_clinical_pearl, '')
        self.assertEqual(q2.ai_mnemonic, '')

    def test_anonymous_request_never_calls_ai(self):
        from django.core.cache import cache
        from questions import ai_per_question as ai
        cache.clear()
        q = _question(self.subject, 3)
        with mock.patch.object(ai, '_ai_call', return_value='real output') as call:
            r = APIClient().get(f'/api/questions/{q.id}/ai/mnemonic/')
        self.assertEqual(r.status_code, 200)
        call.assert_not_called()
        q.refresh_from_db()
        self.assertEqual(q.ai_mnemonic, '')


class QuestionAdminActionPermissionTests(TestCase):
    """QuestionViewSet.get_permissions used to ignore @action permissions,
    leaving admin actions open to anonymous users."""

    def setUp(self):
        self.subject = Subject.objects.create(name='Audit Perms')
        self.q = _question(self.subject, 1)
        self.student = User.objects.create_user(username='perm-student', password='x')
        self.admin = User.objects.create_user(username='perm-admin', password='x', role='admin')

    def _post(self, user, suffix, data=None):
        client = APIClient()
        if user is not None:
            client.force_authenticate(user)
        return client.post(f'/api/questions/{self.q.id}/{suffix}/', data or {}, format='json')

    def test_admin_actions_reject_anonymous_and_students(self):
        for suffix, data in (
            ('remove-from-bank', {}),
            ('unremove-from-bank', {}),
            ('merge-duplicates', {'duplicate_ids': [self.q.id]}),
            ('resolve-dispute', {'corrected_answer': 'B', 'justification': 'x'}),
            ('generate-explanation', {'correct_answer': 'A'}),
        ):
            self.assertIn(self._post(None, suffix, data).status_code, (401, 403), suffix)
            self.assertEqual(self._post(self.student, suffix, data).status_code, 403, suffix)
        self.q.refresh_from_db()
        self.assertTrue(self.q.is_active)
        self.assertEqual(self.q.correct_answer, 'A')

    def test_admin_can_remove_from_bank(self):
        r = self._post(self.admin, 'remove-from-bank')
        self.assertEqual(r.status_code, 200, getattr(r, 'data', r))

    def test_anonymous_practice_state_is_401_not_500(self):
        r = APIClient().get(f'/api/questions/{self.q.id}/practice/state/')
        self.assertIn(r.status_code, (401, 403))

    def test_public_ai_endpoints_stay_public(self):
        r = APIClient().get(f'/api/questions/{self.q.id}/ai/concept/')
        self.assertEqual(r.status_code, 200)

    def test_image_facets_route_is_public(self):
        r = APIClient().get('/api/questions/images/facets/')
        self.assertEqual(r.status_code, 200)


class JobBookmarkPermissionTests(TestCase):
    def test_student_can_bookmark_job(self):
        from jobs.models import Job
        from django.utils import timezone
        fields = {f.name for f in Job._meta.get_fields()}
        data = {'title': 'Medical Officer'}
        for name, value in (('organization', 'Govt'), ('location', 'Delhi'), ('description', 'x'),
                            ('is_active', True), ('last_date', timezone.localdate())):
            if name in fields:
                data[name] = value
        try:
            job = Job.objects.create(**data)
        except Exception as exc:  # pragma: no cover - schema drift guard
            self.skipTest(f'Job fixture could not be created: {exc}')
        student = User.objects.create_user(username='job-student', password='x')
        client = APIClient()
        client.force_authenticate(student)
        r = client.post(f'/api/jobs/{job.id}/bookmark/')
        self.assertEqual(r.status_code, 200, getattr(r, 'data', r))
