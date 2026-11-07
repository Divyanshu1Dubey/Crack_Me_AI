"""Explanation videos on the retired Supabase storage (2026-11-03) are never linked.

The question list / detail payloads (questions.serializers.hide_retired_video) and the test review
(tests_engine.views._review_media) send no player URL for them and report the video as failed;
videos stored anywhere else are unchanged.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Subscription
from questions.models import Question, Subject
from questions.serializers import RETIRED_VIDEO_ERROR, hide_retired_video, playable_video_url
from tests_engine.views import _review_media

User = get_user_model()

STORAGE = 'https://abcdefghijklmnop.supabase.co/storage/v1/object/public/educational_videos'
RETIRED = f'{STORAGE}/q_1_video.mp4'
RETIRED_THUMB = f'{STORAGE}/q_1_thumb.png'
LIVE = 'https://videos.example.org/q_1_video.mp4'


class RetiredVideoHelperTests(SimpleTestCase):

    def test_playable_video_url(self):
        self.assertEqual(playable_video_url(RETIRED), '')
        self.assertEqual(playable_video_url(f'  {LIVE} '), LIVE)
        self.assertEqual(playable_video_url(None), '')

    def test_a_retired_video_loses_its_links_and_says_why(self):
        data = {'video_url': RETIRED, 'video_thumbnail': RETIRED_THUMB, 'video_subtitles_url': f'{STORAGE}/q_1_video.vtt',
                'video_status': 'completed', 'video_error': ''}
        hide_retired_video(data)
        self.assertEqual(data, {'video_url': '', 'video_thumbnail': '', 'video_subtitles_url': '',
                                'video_status': 'failed', 'video_error': RETIRED_VIDEO_ERROR})

    def test_other_payloads_are_untouched(self):
        for data in ({'video_url': LIVE, 'video_status': 'completed'}, {'video_url': '', 'video_status': 'pending'}, {}):
            before = dict(data)
            hide_retired_video(data)
            self.assertEqual(data, before)


class RetiredVideoPayloadTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        subject = Subject.objects.create(name='Retired video', code='RETVID')
        common = dict(option_a='alpha', option_b='beta', option_c='gamma', option_d='delta', correct_answer='A',
                      explanation='Alpha is right.', year=2020, exam_type='cms', subject=subject,
                      video_status='completed')
        cls.retired = Question.objects.create(question_text='Which video is on the retired storage?', video_url=RETIRED,
                                              video_thumbnail=RETIRED_THUMB, **common)
        cls.live = Question.objects.create(question_text='Which video is on a live store?', video_url=LIVE, **common)
        cls.student = User.objects.create_user(username='retired-video-premium', email='retired-video@example.com',
                                               password='unused-pw-rv')
        now = timezone.now()
        Subscription.objects.create(user=cls.student, plan='1_month', plan_display_name='1 month', status='active',
                                    starts_at=now - timedelta(days=1), expires_at=now + timedelta(days=30))

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.student)

    def test_detail_sends_no_link_to_a_retired_video(self):
        data = self.client.get(f'/api/questions/{self.retired.id}/').data
        self.assertEqual(data['video_url'], '')
        self.assertEqual(data['video_thumbnail'], '')
        self.assertEqual(data['video_subtitles_url'], '')
        self.assertEqual(data['video_status'], 'failed')
        self.assertNotIn('supabase.co', str(data))

    def test_detail_keeps_a_video_stored_elsewhere(self):
        data = self.client.get(f'/api/questions/{self.live.id}/').data
        self.assertEqual(data['video_url'], LIVE)
        self.assertEqual(data['video_status'], 'completed')

    def test_list_sends_no_link_to_a_retired_video(self):
        res = self.client.get('/api/questions/', {'year': 2020, 'page_size': 50})
        rows = res.data.get('results', res.data) if isinstance(res.data, dict) else res.data
        by_id = {row['id']: row for row in rows}
        self.assertIn(self.retired.id, by_id)
        self.assertFalse(by_id[self.retired.id].get('video_url'))
        self.assertNotIn('supabase.co', str(by_id[self.retired.id]))

    def test_test_review_sends_no_link_to_a_retired_video(self):
        media = _review_media(self.retired, visible=True, request=None, memo={})
        self.assertIsNone(media['video_url'])
        self.assertEqual(media['video_status'], 'failed')
        media = _review_media(self.live, visible=True, request=None, memo={})
        self.assertEqual(media['video_url'], LIVE)
        self.assertEqual(media['video_status'], 'completed')
