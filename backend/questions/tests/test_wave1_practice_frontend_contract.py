"""
API contract the practice frontend relies on (wave-1 fix group G10).

The frontend fixes for FE-STU-03, EQB-01, FE-STU-21, FE-STU-30 / AI-08 read
these shapes; the tests pin them so a backend change that breaks the
contract fails here instead of silently blanking a panel:

* /questions/practice grades a pick from POST /api/questions/<id>/attempt/
  because the list payload withholds correct_answer / explanation from
  students. The question detail endpoint fills in anything missing.
* Exam mode and /questions/practice page through the list by following the
  `next` link, whatever page size the server applies.
* RelatedPanel reads related-topic rows as `topic_id` / `topic__name`.
* "Find in Textbook" reads a `references` list from
  /api/ai/textbook-reference/ and only uses `screenshot_url` from
  /api/ai/screenshot/<id>/.

No AI provider is called: the textbook lookup is patched and the
per-question AI endpoints are hit anonymously (no AI for anonymous users).
"""
from __future__ import annotations

from datetime import timedelta
from unittest import mock
from urllib.parse import urlsplit

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Subscription
from questions.models import Question, Subject, Topic

User = get_user_model()

ANSWER_FIELDS = ('correct_answer', 'explanation', 'mnemonic')


def _premium_user(username: str):
    user = User.objects.create_user(username=username, email=f'{username}@example.com', password='unused-pw-1')
    now = timezone.now()
    Subscription.objects.create(
        user=user,
        plan='1_month',
        plan_display_name='1 month',
        status='active',
        starts_at=now - timedelta(days=1),
        expires_at=now + timedelta(days=30),
    )
    return user


class PracticeFrontendContractTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='G10 Medicine', code='G10MED')
        cls.topic = Topic.objects.create(subject=cls.subject, name='G10 Shock')
        cls.questions = [
            Question.objects.create(
                question_text=f'G10 contract stem number {i}',
                option_a='alpha', option_b='beta', option_c='gamma', option_d='delta',
                correct_answer='C',
                explanation=f'Gamma is right ({i}).',
                mnemonic='G for gamma',
                year=2019,
                exam_type='cms',
                subject=cls.subject,
                topic=cls.topic if i < 4 else None,
            )
            for i in range(25)
        ]
        cls.premium = _premium_user('g10-premium')
        cls.student = User.objects.create_user(
            username='g10-student', email='g10-student@example.com', password='unused-pw-2',
        )

    def setUp(self):
        cache.clear()
        self.client = APIClient()

    # ── list payload ────────────────────────────────────────────────────

    def test_student_list_rows_carry_no_answer_or_explanation(self):
        """Why /questions/practice must not grade from the list rows."""
        for user in (self.student, self.premium):
            self.client.force_authenticate(user=user)
            res = self.client.get('/api/questions/', {'year': 2019, 'exam_type': 'cms'})
            self.assertEqual(res.status_code, 200)
            row = res.data['results'][0]
            for field in ANSWER_FIELDS:
                self.assertNotIn(field, row, f'list row leaked {field} to {user.username}')
            self.assertIn(row.get('effective_answer'), (None, ''))
            self.assertIn(row.get('effective_explanation'), (None, ''))

    def test_following_next_links_collects_the_whole_year(self):
        """Exam mode / fullscreen practice page by `next`, not by page size."""
        self.client.force_authenticate(user=self.premium)
        seen: list[int] = []
        url, params = '/api/questions/', {'year': 2019, 'exam_type': 'cms', 'page_size': 100}
        for _ in range(10):
            res = self.client.get(url, params)
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.data['count'], 25)
            seen.extend(row['id'] for row in res.data['results'])
            nxt = res.data.get('next')
            if not nxt:
                break
            parts = urlsplit(nxt)
            url, params = parts.path, parts.query
        self.assertEqual(sorted(seen), sorted(q.id for q in self.questions))
        self.assertEqual(len(seen), len(set(seen)), 'pages overlapped')

    # ── reveal after a pick ─────────────────────────────────────────────

    def test_attempt_response_grades_the_pick_for_an_entitled_user(self):
        q = self.questions[0]
        self.client.force_authenticate(user=self.premium)
        wrong = self.client.post(f'/api/questions/{q.id}/attempt/', {'selected_answer': 'a', 'time_spent_seconds': 12}, format='json')
        self.assertEqual(wrong.status_code, 200, wrong.content)
        self.assertIs(wrong.data['is_correct'], False)
        self.assertEqual(wrong.data['correct_answer'], 'C')

        right = self.client.post(f'/api/questions/{q.id}/attempt/', {'selected_answer': 'C'}, format='json')
        self.assertEqual(right.status_code, 200, right.content)
        self.assertIs(right.data['is_correct'], True)
        self.assertEqual(right.data['correct_answer'], 'C')
        # If the attempt carries the explanation, it is the question's own text.
        if 'explanation' in right.data:
            self.assertEqual(right.data['explanation'], q.explanation)

    def test_detail_fills_explanation_and_mnemonic_for_an_entitled_user(self):
        q = self.questions[1]
        self.client.force_authenticate(user=self.premium)
        res = self.client.get(f'/api/questions/{q.id}/')
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.data['correct_answer'], 'C')
        self.assertEqual(res.data['explanation'], q.explanation)
        self.assertEqual(res.data['mnemonic'], q.mnemonic)

    def test_attempt_rejects_a_non_letter_pick(self):
        self.client.force_authenticate(user=self.premium)
        res = self.client.post(f'/api/questions/{self.questions[2].id}/attempt/', {'selected_answer': 'Z'}, format='json')
        self.assertEqual(res.status_code, 400)

    # ── side panels ─────────────────────────────────────────────────────

    def test_related_topics_rows_use_topic_id_and_topic__name(self):
        res = self.client.get(f'/api/questions/{self.questions[10].id}/ai/related_topics/')
        self.assertEqual(res.status_code, 200)
        rows = res.data['related_topics']
        named = [r for r in rows if r.get('topic_id')]
        self.assertTrue(named, rows)
        self.assertEqual(named[0]['topic_id'], self.topic.id)
        self.assertEqual(named[0]['topic__name'], self.topic.name)
        self.assertNotIn('topic', named[0])

    def test_per_question_ai_endpoints_use_their_own_keys(self):
        """RevealExplanation reads `concept` from ai/concept and
        `why_incorrect` from ai/why_incorrect (it used to swap them)."""
        q = self.questions[3]
        concept = self.client.get(f'/api/questions/{q.id}/ai/concept/')
        why_not = self.client.get(f'/api/questions/{q.id}/ai/why_incorrect/')
        self.assertEqual(concept.status_code, 200)
        self.assertEqual(why_not.status_code, 200)
        self.assertIn('concept', concept.data)
        self.assertNotIn('why_incorrect', concept.data)
        self.assertIn('why_incorrect', why_not.data)
        self.assertNotIn('concept', why_not.data)

    def test_textbook_reference_returns_a_references_list(self):
        refs = [{'book': 'Harrison', 'page': 1234, 'excerpt': 'Septic shock …', 'relevance_score': 0.8}]
        self.client.force_authenticate(user=self.premium)
        with mock.patch('ai_engine.views.AIService') as service:
            service.return_value.find_textbook_reference.return_value = refs
            res = self.client.post('/api/ai/textbook-reference/', {'question_text': 'septic shock'}, format='json')
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.data, {'references': refs})
        for legacy in ('book_name', 'page_range', 'chapter', 'reference'):
            self.assertNotIn(legacy, res.data)

    def test_screenshot_endpoint_has_no_url_without_a_stored_screenshot(self):
        """The UI only renders `screenshot_url`; nothing usable comes back
        for a question without a stored page screenshot."""
        self.client.force_authenticate(user=self.premium)
        res = self.client.get(f'/api/ai/screenshot/{self.questions[4].id}/')
        self.assertNotIn('screenshot_url', res.data or {})
