"""Announcement delivery and the quest streak freeze (AN-18 / BC-01 / FE-STU-09 / AN-24)."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from analytics.models import Announcement
from questions.models import QuestStreak, UserQuest

User = get_user_model()
STUDENT_FIELDS = {'id', 'title', 'message', 'image_url', 'deep_link', 'priority', 'is_expired', 'expires_at', 'created_at'}


class AnnouncementDeliveryTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_user(username='ann-admin', password='x', role='admin')
        self.student = User.objects.create_user(username='ann-student', password='x')
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(self.admin)
        self.client = APIClient()
        self.client.force_authenticate(self.student)

    def test_scheduled_campaign_goes_live_when_due(self):
        soon = timezone.now() + timedelta(hours=1)
        r = self.admin_client.post('/api/analytics/admin/campaigns/', {
            'title': 'Mock test Sunday', 'message': 'Join the live mock', 'scheduled_for': soon.isoformat(),
            'audience_filter': {'role': 'student'},
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['delivery_status'], 'scheduled')
        self.assertEqual(self.client.get('/api/analytics/announcements/').data, [])

        # Time passes: nothing ever flipped 'scheduled' to 'sent' before.
        Announcement.objects.filter(pk=r.data['id']).update(scheduled_for=timezone.now() - timedelta(minutes=1))
        feed = self.client.get('/api/analytics/announcements/').data
        self.assertEqual([a['title'] for a in feed], ['Mock test Sunday'])
        ann = Announcement.objects.get(pk=r.data['id'])
        self.assertEqual(ann.delivery_status, 'sent')
        self.assertIsNotNone(ann.sent_at)
        self.assertEqual(ann.delivery_count, 1)  # one student matches the audience

        bundle = self.client.get('/api/analytics/dashboard/bundle/').data
        self.assertEqual([a['message'] for a in bundle['announcements']], ['Join the live mock'])

    def test_students_get_student_fields_only(self):
        Announcement.objects.create(title='Hi', message='Body text', delivery_status='sent',
                                    audience_filter={'role': 'student'}, failure_report='internal',
                                    delivery_count=42, created_by=self.admin)
        feed = self.client.get('/api/analytics/announcements/').data
        self.assertEqual(set(feed[0]), STUDENT_FIELDS)
        bundle = self.client.get('/api/analytics/dashboard/bundle/').data
        self.assertEqual(set(bundle['announcements'][0]), STUDENT_FIELDS)
        self.assertEqual(bundle['announcements'][0]['message'], 'Body text')

    def test_admin_sees_student_targeted_and_all_scopes(self):
        live = Announcement.objects.create(title='Students only', message='m', delivery_status='sent',
                                           audience_filter={'role': 'student'})
        draft = Announcement.objects.create(title='Draft', message='m', delivery_status='draft')
        ids = {a['id'] for a in self.admin_client.get('/api/analytics/announcements/').data}
        self.assertEqual(ids, {live.id})  # used to be hidden by the admin's own role
        ids = {a['id'] for a in self.admin_client.get('/api/analytics/announcements/', {'scope': 'all'}).data}
        self.assertEqual(ids, {live.id, draft.id})
        self.assertEqual(self.admin_client.delete(f'/api/analytics/announcements/{live.id}/').status_code, 204)


class QuestStreakFreezeTests(TestCase):
    URL = '/api/analytics/quests/streak/freeze/'

    def setUp(self):
        self.user = User.objects.create_user(username='freeze-u', password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.today = timezone.localdate()

    def _streak(self, days_since_last_claim=0, current=4, frozen=False):
        streak, _ = QuestStreak.objects.get_or_create(user=self.user)
        streak.current_streak = current
        streak.longest_streak = current
        streak.last_quest_date = self.today - timedelta(days=days_since_last_claim)
        streak.streak_frozen = frozen
        streak.save()
        return streak

    def test_strict_boolean_parsing(self):
        self._streak()
        self.assertTrue(self.client.post(self.URL, {'streak_frozen': True}, format='json').data['streak_frozen'])
        # bool('false') is True -- the string used to freeze instead of unfreezing.
        self.assertFalse(self.client.post(self.URL, {'streak_frozen': 'false'}, format='json').data['streak_frozen'])
        self.assertEqual(self.client.post(self.URL, {'streak_frozen': 'maybe'}, format='json').status_code, 400)

    def test_no_body_toggles(self):
        self._streak()
        self.assertTrue(self.client.post(self.URL).data['streak_frozen'])
        self.assertFalse(self.client.post(self.URL).data['streak_frozen'])

    def test_needs_a_live_streak(self):
        self.assertEqual(self.client.post(self.URL, {'streak_frozen': True}, format='json').status_code, 400)
        self._streak(days_since_last_claim=3)
        self.assertEqual(self.client.post(self.URL, {'streak_frozen': True}, format='json').status_code, 400)
        self.assertFalse(QuestStreak.objects.get(user=self.user).streak_frozen)

    def test_one_freeze_per_week(self):
        self._streak()
        self.assertEqual(self.client.post(self.URL, {'streak_frozen': True}, format='json').status_code, 200)
        self.assertEqual(self.client.post(self.URL, {'streak_frozen': False}, format='json').status_code, 200)
        r = self.client.post(self.URL, {'streak_frozen': True}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('7 days', r.data['error'])

    def _claimable_quest(self):
        now = timezone.now()
        return UserQuest.objects.create(
            user=self.user, quest_type='streak_maintain', title='custom', target_value=1, current_value=1,
            xp_reward=5, quest_date=self.today, expires_at=now + timedelta(hours=2))

    def test_freeze_bridges_one_missed_day(self):
        self._streak(days_since_last_claim=2, current=4, frozen=True)
        quest = self._claimable_quest()
        r = self.client.patch(f'/api/analytics/quests/{quest.id}/', {'is_completed': True}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        streak = QuestStreak.objects.get(user=self.user)
        self.assertEqual((streak.current_streak, streak.streak_frozen), (5, False))

    def test_stale_freeze_does_not_bridge_a_long_gap(self):
        self._streak(days_since_last_claim=10, current=4, frozen=True)
        quest = self._claimable_quest()
        r = self.client.patch(f'/api/analytics/quests/{quest.id}/', {'is_completed': True}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        streak = QuestStreak.objects.get(user=self.user)
        self.assertEqual((streak.current_streak, streak.streak_frozen), (1, False))

    def test_streak_view_drops_stale_freeze(self):
        self._streak(days_since_last_claim=5, frozen=True)
        self.assertFalse(self.client.get('/api/analytics/quests/streak/').data['streak_frozen'])
