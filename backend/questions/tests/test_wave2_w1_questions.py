"""Wave-2 W1 (questions app): cross-group contracts C1 / C4 / C5 / C7 and the
review / needs items of the wave-1 questions work.

No AI provider, Supabase or network call is made: every AI entry point is
patched and uploads stop before the storage helper.
"""
from __future__ import annotations

import io
import json
import os
import tempfile
from datetime import timedelta
from io import StringIO
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib import admin as django_admin
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from accounts.models import Subscription
from accounts.models_freemium import FreeShowcaseQuestion
from questions.models import (
    AdminAIPromptVersion, Discussion, Flashcard, Question, QuestionBookmark, QuestionImage,
    QuestionImportJob, QuestionRevisionSnapshot, QuestStreak, Subject, Topic, TopicNote, UserQuest,
)

User = get_user_model()

OUTAGE = 'All AI services are temporarily unavailable. Please try again in a moment.'


def _question(subject, i, **kw):
    defaults = dict(
        question_text=f'W1 wave2 stem {i}', option_a='alpha', option_b='beta', option_c='gamma',
        option_d='delta', correct_answer='C', year=2024, subject=subject,
        explanation=f'Gamma is right ({i}).',
    )
    defaults.update(kw)
    return Question.objects.create(**defaults)


def _premium(username):
    user = User.objects.create_user(username=username, email=f'{username}@example.com', password='unused-pw-1')
    Subscription.objects.create(user=user, plan='1_year', status='active',
                                expires_at=timezone.now() + timedelta(days=365))
    return user


def _client(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user)
    return client


def _png_bytes(size=(40, 20)) -> bytes:
    buf = io.BytesIO()
    Image.new('RGB', size, color='red').save(buf, format='PNG')
    return buf.getvalue()


SVG_BYTES = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(document.domain)</script></svg>'


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='W1 Wave2 Subject', code='W1W2')
        cls.free = User.objects.create_user(username='w1w2-free', email='w1w2-free@example.com', password='unused-pw-2')
        cls.premium = _premium('w1w2-premium')
        cls.admin = User.objects.create_user(username='w1w2-admin', password='unused-pw-3', role='admin')

    def setUp(self):
        cache.clear()


# ── C1: answer-submission response ─────────────────────────────────────────

class AttemptResponseContractTests(_Base):
    def test_attempt_returns_explanations_and_effective_mnemonic(self):
        q = _question(self.subject, 1, mnemonic='G for gamma', ai_mnemonic='AI gamma mnemonic',
                      admin_mnemonic_override='Admin mnemonic')
        res = _client(self.premium).post(f'/api/questions/{q.id}/attempt/', {'selected_answer': 'C'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertIs(res.data['is_correct'], True)
        self.assertEqual(res.data['correct_answer'], 'C')
        self.assertEqual(res.data['explanation'], 'Gamma is right (1).')
        self.assertEqual(res.data['effective_explanation'], 'Gamma is right (1).')
        self.assertEqual(res.data['mnemonic'], 'Admin mnemonic')

    def test_effective_explanation_is_never_blank(self):
        q = _question(self.subject, 2, explanation='', ai_explanation=OUTAGE)
        for path, body in ((f'/api/questions/{q.id}/attempt/', {'selected_answer': 'A'}),
                           (f'/api/questions/{q.id}/practice/attempt/', {'answer': 'A'})):
            res = _client(self.premium).post(path, body, format='json')
            self.assertEqual(res.status_code, 200, res.data)
            self.assertEqual(res.data['explanation'], '')
            self.assertIn('The correct answer is C: gamma.', res.data['effective_explanation'])
            self.assertNotIn('temporarily unavailable', res.data['effective_explanation'])
            self.assertEqual(res.data['mnemonic'], '')

    def test_ai_explanation_becomes_the_effective_explanation(self):
        q = _question(self.subject, 3, explanation='', ai_explanation='Gamma: the AI explanation.')
        res = _client(self.premium).post(f'/api/questions/{q.id}/practice/attempt/', {'answer': 'C'}, format='json')
        self.assertEqual(res.data['effective_explanation'], 'Gamma: the AI explanation.')
        self.assertIs(res.data['is_correct'], True)

    def test_non_entitled_attempts_stay_402(self):
        q = _question(self.subject, 4)
        for path, body in ((f'/api/questions/{q.id}/attempt/', {'selected_answer': 'A'}),
                           (f'/api/questions/{q.id}/practice/attempt/', {'answer': 'A'})):
            res = _client(self.free).post(path, body, format='json')
            self.assertEqual(res.status_code, 402)
            self.assertEqual(res.data['code'], 'upgrade_required')
            self.assertNotIn('mnemonic', res.data)


# ── C4: scholarship questions are never free content ───────────────────────

class ScholarshipQuestionTests(_Base):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.scholarship = _question(cls.subject, 10, is_scholarship_eligible=True,
                                    mnemonic='Secret mnemonic', ai_answer='Gamma because...')
        FreeShowcaseQuestion.objects.create(question=cls.scholarship, year=2024, position=0)
        cls.showcase = _question(cls.subject, 11)
        FreeShowcaseQuestion.objects.create(question=cls.showcase, year=2024, position=1)

    def test_rule(self):
        from questions.views import user_can_view_answer
        for subject in (self.scholarship, self.scholarship.pk):
            self.assertFalse(user_can_view_answer(None, subject))
            self.assertFalse(user_can_view_answer(self.free, subject))
            self.assertTrue(user_can_view_answer(self.premium, subject))
            self.assertTrue(user_can_view_answer(self.admin, subject))
        self.assertTrue(user_can_view_answer(self.free, self.showcase))

    def test_anonymous_detail_is_redacted_and_free_detail_404s(self):
        res = _client().get(f'/api/questions/{self.scholarship.id}/')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['answer_locked'])
        self.assertIsNone(res.data['correct_answer'])
        self.assertNotIn('Secret mnemonic', str(res.data))
        self.assertEqual(_client(self.free).get(f'/api/questions/{self.scholarship.id}/').status_code, 404)
        self.assertEqual(_client(self.premium).get(f'/api/questions/{self.scholarship.id}/').data['correct_answer'], 'C')

    def test_attempts_are_paywalled_for_free_users(self):
        for path, body in ((f'/api/questions/{self.scholarship.id}/attempt/', {'selected_answer': 'C'}),
                           (f'/api/questions/{self.scholarship.id}/practice/attempt/', {'answer': 'C'})):
            res = _client(self.free).post(path, body, format='json')
            self.assertEqual(res.status_code, 402, path)
            self.assertNotIn('correct_answer', res.data)

    def test_ai_text_is_locked(self):
        from questions import ai_per_question as ai
        with mock.patch.object(ai, '_ai_call', return_value='generated') as call:
            for user in (None, self.free):
                res = _client(user).get(f'/api/questions/{self.scholarship.id}/ai/why_correct/')
                self.assertIsNone(res.data['why_correct'])
                self.assertTrue(res.data['locked'])
        call.assert_not_called()

    def test_free_list_does_not_mark_it_free_and_practice_queue_skips_it(self):
        rows = {r['id']: r for r in _client(self.free).get('/api/questions/', {'year': 2024}).data['results']}
        self.assertFalse(rows[self.scholarship.id]['is_showcase'])
        self.assertTrue(rows[self.showcase.id]['is_showcase'])
        with mock.patch('questions.practice_modes.build_queue', return_value=[self.scholarship.id, self.showcase.id]):
            res = _client(self.free).get('/api/questions/practice_queue/')
        self.assertEqual(res.data['question_ids'], [self.showcase.id])

    def test_chat_context_never_carries_its_key(self):
        with mock.patch('ai_engine.services.AIService') as service:
            service.return_value.ask_tutor.return_value = 'A real tutor answer'
            _client(self.free).post('/api/questions/chat/', {'message': 'Explain',
                                                             'context_question_id': self.scholarship.id}, format='json')
        self.assertEqual(service.return_value.ask_tutor.call_args[0][1], '')


# ── C5: flashcard counters and analytics ───────────────────────────────────

class FlashcardStatsTests(_Base):
    def test_review_counters(self):
        card = Flashcard.objects.create(user=self.free, front='f', back='b')
        card.schedule_next_review(5)
        card.schedule_next_review(1)
        card.schedule_next_review(4)
        card.refresh_from_db()
        self.assertEqual((card.total_reviews, card.lapses, card.review_count), (3, 1, 1))

    def test_analytics_cover_every_card_not_a_page(self):
        cards = [Flashcard.objects.create(user=self.free, front=f'f{i}', back='b') for i in range(25)]
        # 10 reviewed cards: 8 recalled, 2 forgotten -> retention 0.8
        for card in cards[:8]:
            card.schedule_next_review(5)
        for card in cards[8:10]:
            card.schedule_next_review(1)
        Flashcard.objects.create(user=self.premium, front='other user', back='b')
        res = _client(self.free).get('/api/questions/flashcards/analytics/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['total_cards'], 25)
        self.assertEqual(res.data['reviewed_cards'], 10)
        self.assertEqual(res.data['retention_rate'], 0.8)
        # 15 never-reviewed cards were created due now; reviewed ones are not due.
        self.assertEqual(res.data['due_today'], 15)
        self.assertEqual(res.data['cards_due_today'], 15)

    def test_retention_is_null_without_reviews(self):
        Flashcard.objects.create(user=self.free, front='f', back='b')
        res = _client(self.free).get('/api/questions/flashcards/analytics/')
        self.assertIsNone(res.data['retention_rate'])
        self.assertEqual(res.data['reviewed_cards'], 0)
        empty = _client(self.premium).get('/api/questions/flashcards/analytics/').data
        self.assertEqual((empty['total_cards'], empty['due_today'], empty['retention_rate']), (0, 0, None))

    def test_review_endpoint_returns_counters(self):
        card = Flashcard.objects.create(user=self.free, front='f', back='b')
        res = _client(self.free).post(f'/api/questions/flashcards/{card.id}/review/', {'quality': 2}, format='json')
        self.assertEqual((res.data['total_reviews'], res.data['lapses']), (1, 1))


# ── C7: taxonomy is unpaginated ────────────────────────────────────────────

class TaxonomyTests(_Base):
    def test_subjects_and_topics_are_plain_ordered_arrays(self):
        for i in range(25):
            Subject.objects.create(name=f'W1 Tax {i:02d}', code=f'W1T{i:02d}', paper=1)
        topic_subject = Subject.objects.create(name='W1 Tax Topics', code='W1TT', paper=2)
        for name in ('Zeta', 'Alpha', 'Mu'):
            Topic.objects.create(subject=topic_subject, name=name)
        subjects = _client().get('/api/questions/subjects/').json()
        self.assertIsInstance(subjects, list)
        self.assertGreaterEqual(len(subjects), 27)
        keys = [(s['paper'], s['name']) for s in subjects]
        self.assertEqual(keys, sorted(keys))
        topics = _client().get('/api/questions/topics/', {'subject': topic_subject.id}).json()
        self.assertEqual([t['name'] for t in topics], ['Alpha', 'Mu', 'Zeta'])


# ── Discussions keep their order ───────────────────────────────────────────

class DiscussionOrderTests(_Base):
    def test_pinned_first_then_votes_and_replies_chronological(self):
        q = _question(self.subject, 20)
        old = Discussion.objects.create(question=q, user=self.free, text='old')
        pinned = Discussion.objects.create(question=q, user=self.free, text='pinned', is_pinned=True)
        voted = Discussion.objects.create(question=q, user=self.free, text='voted', upvotes=5)
        for i in range(3):
            Discussion.objects.create(question=q, user=self.premium, parent=old, text=f'reply {i}')
        res = _client(self.premium).get('/api/questions/discussions/', {'question': q.id})
        rows = res.data['results'] if isinstance(res.data, dict) else res.data
        self.assertEqual([r['id'] for r in rows], [pinned.id, voted.id, old.id])
        self.assertEqual(rows[2]['reply_count'], 3)
        replies = _client(self.premium).get(f'/api/questions/discussions/{old.id}/replies/').data
        replies = replies['results'] if isinstance(replies, dict) else replies
        self.assertEqual([r['text'] for r in replies], ['reply 0', 'reply 1', 'reply 2'])

    def test_queryset_is_explicitly_ordered(self):
        from questions.views import _discussion_queryset
        qs = _discussion_queryset(self.free)
        self.assertTrue(qs.ordered)
        self.assertIn('ORDER BY', str(qs.query))


# ── Admin editor: If-Match, writable rationale fields, list fields ─────────

class AdminEditorTests(_Base):
    def test_if_match_with_the_served_updated_at_saves(self):
        q = _question(self.subject, 30)
        api = _client(self.admin)
        served = api.get(f'/api/questions/{q.id}/').data['updated_at']
        self.assertTrue(served.endswith('+05:30'), served)  # TIME_ZONE, not UTC
        res = api.patch(f'/api/questions/{q.id}/', {'explanation': 'Edited'}, format='json', HTTP_IF_MATCH=served)
        self.assertEqual(res.status_code, 200, res.data)
        # the previous value is now stale
        stale = api.patch(f'/api/questions/{q.id}/', {'explanation': 'Again'}, format='json', HTTP_IF_MATCH=served)
        self.assertEqual(stale.status_code, 409)
        # ETag-style quoting and the list row's value work too
        row = next(r for r in api.get('/api/questions/', {'question_id': q.id}).data['results'] if r['id'] == q.id)
        res = api.patch(f'/api/questions/{q.id}/', {'explanation': 'Third'}, format='json',
                        HTTP_IF_MATCH=f'W/"{row["updated_at"]}"')
        self.assertEqual(res.status_code, 200, res.data)

    def test_rationale_fields_and_controversy_flag_are_saved(self):
        q = _question(self.subject, 31)
        payload = {'why_correct': 'Because gamma.', 'why_wrong_a': 'Not alpha.', 'why_wrong_b': 'Not beta.',
                   'why_wrong_c': '', 'why_wrong_d': 'Not delta.', 'is_controversial': True}
        res = _client(self.admin).patch(f'/api/questions/{q.id}/', payload, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        for key, value in payload.items():
            self.assertEqual(res.data[key], value, key)
        q.refresh_from_db()
        self.assertEqual((q.why_correct, q.why_wrong_d, q.is_controversial), ('Because gamma.', 'Not delta.', True))
        # ... and are answer content for anonymous readers
        anon = _client().get(f'/api/questions/{q.id}/').data
        for key in ('why_correct', 'why_wrong_a', 'why_wrong_b', 'why_wrong_d'):
            self.assertIsNone(anon[key], key)

    def test_admin_list_rows_carry_editor_fields(self):
        q = _question(self.subject, 32, is_controversial=True)
        related = _question(self.subject, 33)
        q.similar_questions.set([related])
        row = next(r for r in _client(self.admin).get('/api/questions/', {'question_id': q.id}).data['results'])
        self.assertTrue(row['is_controversial'])
        self.assertTrue(row['updated_at'])
        self.assertEqual(row['related_question_ids'], [related.id])

    def test_ordering_by_paper_and_display_number(self):
        rows = [_question(self.subject, 40 + i, paper=1, display_number=n, year=2031) for i, n in enumerate((3, 1, 2))]
        res = _client(self.admin).get('/api/questions/', {'year': 2031, 'ordering': 'paper,display_number'})
        self.assertEqual([r['display_number'] for r in res.data['results']], [1, 2, 3])
        self.assertEqual(len(rows), 3)


class GenerateExplanationTests(_Base):
    RESULT = {
        'explanation': 'Generated explanation', 'why_correct': 'Because gamma', 'mnemonic': OUTAGE,
        'why_wrong_a': 'Alpha is wrong',
    }

    def _post(self, q, body):
        with mock.patch('ai_engine.services.AIService') as service:
            service.return_value.generate_admin_explanation.return_value = dict(self.RESULT)
            res = _client(self.admin).post(f'/api/questions/{q.id}/generate-explanation/', body, format='json')
        return res, service.return_value.generate_admin_explanation

    def test_correct_answer_is_required(self):
        q = _question(self.subject, 50, explanation='')
        for body in ({}, {'correct_answer': ''}, {'correct_answer': 'Z'}, {'correct_answer': 'AB'}):
            res, call = self._post(q, body)
            self.assertEqual(res.status_code, 400, body)
            call.assert_not_called()

    def test_saved_output_is_never_marked_verified_and_uses_the_active_prompt(self):
        q = _question(self.subject, 51, explanation='')
        AdminAIPromptVersion.objects.create(name='w1', prompt_text='Lead with the mechanism.', is_active=True,
                                            created_by=self.admin)
        res, call = self._post(q, {'correct_answer': 'b', 'update_correct_answer': True})
        self.assertEqual(res.status_code, 200, res.data)
        self.assertTrue(res.data['saved'])
        self.assertEqual(call.call_args.kwargs['user_prompt'], 'Lead with the mechanism.')
        self.assertEqual(call.call_args.kwargs['correct_answer'], 'B')
        self.assertNotIn('mnemonic', res.data['generated_fields'])  # outage text dropped
        q.refresh_from_db()
        self.assertFalse(q.is_verified_by_admin)
        self.assertIsNone(q.verified_by)
        self.assertEqual((q.explanation, q.why_correct, q.mnemonic), ('Generated explanation', 'Because gamma', ''))
        self.assertEqual((q.correct_answer, q.lock_answer), ('B', True))
        self.assertTrue(QuestionRevisionSnapshot.objects.filter(question=q).exists())

    def test_dry_run_saves_nothing(self):
        q = _question(self.subject, 52, explanation='Existing explanation')
        before = q.updated_at
        res, _ = self._post(q, {'correct_answer': 'C', 'dry_run': True})
        self.assertEqual(res.status_code, 200, res.data)
        self.assertFalse(res.data['saved'])
        self.assertEqual(res.data['generated_fields']['explanation'], 'Generated explanation')
        q.refresh_from_db()
        self.assertEqual(q.explanation, 'Existing explanation')
        self.assertEqual(q.updated_at, before)
        self.assertFalse(QuestionRevisionSnapshot.objects.filter(question=q).exists())

    def test_existing_explanation_still_needs_confirmation(self):
        q = _question(self.subject, 53, explanation='Existing explanation')
        res, call = self._post(q, {'correct_answer': 'C', 'regenerate_if_exists': 'false'})
        self.assertEqual(res.status_code, 409)
        call.assert_not_called()


# ── Image endpoint / uploads ───────────────────────────────────────────────

@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ImageServeHardeningTests(_Base):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        q = _question(cls.subject, 60)
        cls.png = QuestionImage.objects.create(
            question=q, page_number=0, mime='image/png',
            file=SimpleUploadedFile('sign.png', _png_bytes(), content_type='image/png'),
        )
        cls.svg = QuestionImage.objects.create(
            question=q, page_number=0, mime='image/svg+xml',
            file=SimpleUploadedFile('legacy.svg', SVG_BYTES, content_type='image/svg+xml'),
        )
        cls.disguised = QuestionImage.objects.create(
            question=q, page_number=0, mime='image/png',
            file=SimpleUploadedFile('fake.png', SVG_BYTES, content_type='image/png'),
        )
        cls.traversal = QuestionImage.objects.create(question=q, page_number=0, url='/media/../../manage.py')

    def _get(self, image, query=''):
        return self.client.get(f'/api/questions/images/{image.pk}/serve/{query}')

    def _assert_hardened(self, res):
        self.assertEqual(res['Content-Security-Policy'], "default-src 'none'; sandbox")
        self.assertEqual(res['X-Content-Type-Options'], 'nosniff')

    def test_raster_images_are_inline_with_csp(self):
        for query in ('', '?w=10'):
            res = self._get(self.png, query)
            self.assertEqual(res.status_code, 200)
            self.assertIn(res['Content-Type'], ('image/png', 'image/jpeg'))
            self.assertEqual(res['Cache-Control'], 'private, max-age=3600')
            self._assert_hardened(res)

    def test_svg_and_disguised_svg_are_downloads(self):
        for image in (self.svg, self.disguised):
            for query in ('', '?w=10'):
                res = self._get(image, query)
                self.assertEqual(res.status_code, 200)
                self.assertEqual(res['Content-Type'], 'application/octet-stream')
                self.assertTrue(res['Content-Disposition'].startswith('attachment'))
                self._assert_hardened(res)

    def test_media_url_cannot_leave_media_root(self):
        self.assertEqual(self._get(self.traversal).status_code, 404)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ImageUploadValidationTests(_Base):
    @mock.patch('questions.views.upload_image_to_supabase')
    def test_content_is_checked_not_the_declared_type(self, upload):
        q = _question(self.subject, 61)
        api = _client(User.objects.create_superuser(username='w1w2-su', email='w1w2-su@example.com', password='pw'))
        bad = SimpleUploadedFile('x.png', SVG_BYTES, content_type='image/png')
        res = api.post('/api/questions/images/', {'question_id': q.id, 'file': bad}, format='multipart')
        self.assertEqual(res.status_code, 400)
        upload.assert_not_called()


# ── Years, quests, notes ───────────────────────────────────────────────────

class AvailableYearsTests(_Base):
    def test_years_filter_and_exclusions(self):
        _question(self.subject, 70, year=2021, exam_type='cms', exam_source='UPSC CMS')
        _question(self.subject, 71, year=2022, exam_type='neet_pg', exam_source='NEET PG (recall)')
        _question(self.subject, 72, year=0)
        _question(self.subject, 73, year=2019, is_active=False)
        years = _client().get('/api/questions/years/').data
        self.assertNotIn(0, years)
        self.assertNotIn(2019, years)
        self.assertEqual(years, sorted(years, reverse=True))
        self.assertEqual(_client().get('/api/questions/years/', {'exam_type': 'neet_pg'}).data, [2022])
        self.assertEqual(_client().get('/api/questions/years/', {'exam_source': 'NEET PG'}).data, [2022])
        self.assertIn(2019, _client(self.admin).get('/api/questions/years/').data)


class QuestServiceTests(_Base):
    def test_empty_test_submission_does_not_finish_the_test_quest(self):
        from questions.quest_service import _progress_for
        from tests_engine.models import Test, TestAttempt
        test = Test.objects.create(title='W1 quest test', test_type='mixed')
        now = timezone.now()
        TestAttempt.objects.create(user=self.free, test=test, is_completed=True, completed_at=now)
        self.assertEqual(_progress_for(self.free, 'complete_tests', timezone.localdate()), 0)
        TestAttempt.objects.create(user=self.free, test=test, is_completed=True, completed_at=now, correct_count=1)
        self.assertEqual(_progress_for(self.free, 'complete_tests', timezone.localdate()), 1)

    def test_a_broken_streak_also_ends_the_freeze(self):
        from analytics.models import DailyActivity
        from questions.quest_service import claim_quest, ensure_daily_quests
        ensure_daily_quests(self.free)
        DailyActivity.objects.create(user=self.free, date=timezone.localdate(), questions_attempted=25)
        QuestStreak.objects.create(user=self.free, current_streak=4, streak_frozen=True,
                                   last_quest_date=timezone.localdate() - timedelta(days=6))
        quest = UserQuest.objects.get(user=self.free, quest_type='solve_questions', quest_date=timezone.localdate())
        claim_quest(self.free, quest.id)
        streak = QuestStreak.objects.get(user=self.free)
        self.assertEqual((streak.current_streak, streak.streak_frozen), (1, False))


class TopicNoteDraftTests(_Base):
    def test_blank_draft_allowed_but_not_published(self):
        from questions.serializers import TopicNoteSerializer
        topic = Topic.objects.create(subject=self.subject, name='W1 note topic')
        base = {'subject': self.subject.id, 'topic': topic.id, 'exam_type': 'cms', 'title': 'Draft'}
        draft = TopicNoteSerializer(data={**base, 'content': ''})
        self.assertTrue(draft.is_valid(), draft.errors)
        published = TopicNoteSerializer(data={**base, 'content': ' ', 'is_published': True})
        self.assertFalse(published.is_valid())
        self.assertIn('content', published.errors)
        self.assertFalse(TopicNote.objects.exists())


# ── Search oracle / redaction / query counts ───────────────────────────────

class SearchAndRedactionTests(_Base):
    def test_explanation_is_searchable_only_for_entitled_callers(self):
        q = _question(self.subject, 80, question_text='W1 oracle stem', explanation='mentions zygomycosis only here')
        for user in (None, self.free):
            res = _client(user).get('/api/questions/', {'search': 'zygomycosis'})
            self.assertEqual(res.data['count'], 0, user)
        res = _client(self.premium).get('/api/questions/', {'search': 'zygomycosis'})
        self.assertEqual([r['id'] for r in res.data['results']], [q.id])
        # detail routes ignore list filters (no 200 / 404 probe)
        for term in ('zygomycosis', 'not-in-the-text'):
            self.assertEqual(_client().get(f'/api/questions/{q.id}/', {'search': term}).status_code, 200)

    def test_page_screenshot_is_answer_media(self):
        q = _question(self.subject, 81, page_screenshot='question_screenshots/answer-page.png')
        self.assertIsNone(_client().get(f'/api/questions/{q.id}/').data['page_screenshot'])
        rows = {r['id']: r for r in _client(self.free).get('/api/questions/', {'year': 2024}).data['results']}
        self.assertIsNone(rows[q.id]['page_screenshot'])
        rows = {r['id']: r for r in _client(self.premium).get('/api/questions/', {'year': 2024}).data['results']}
        self.assertTrue(rows[q.id]['page_screenshot'])

    def test_free_bookmark_list_with_videos_has_no_per_row_showcase_query(self):
        def _queries(user, n, offset):
            for i in range(n):
                q = _question(self.subject, offset + i, video_url=f'https://example.com/v/{offset + i}.mp4')
                QuestionBookmark.objects.create(user=user, question=q)
            with CaptureQueriesContext(connection) as ctx:
                res = _client(user).get('/api/questions/bookmarks/')
            self.assertEqual(res.status_code, 200)
            self.assertTrue(all(row['question_detail']['video_url'] is None for row in res.data))
            return len(ctx.captured_queries)

        small = User.objects.create_user(username='w1w2-bm-small', password='unused-pw-5')
        large = User.objects.create_user(username='w1w2-bm-large', password='unused-pw-6')
        self.assertEqual(_queries(small, 2, 900), _queries(large, 7, 950))


# ── Chat assistant failure contract ────────────────────────────────────────

class ChatAssistantFailureTests(_Base):
    def _grounded(self):
        from ai_engine.offline import OfflineAnswer
        return OfflineAnswer(grounded=True, answer='> Offline answer\n\nFrom the library.', citations=[])

    def test_provider_outage_falls_back_to_a_grounded_offline_answer(self):
        from accounts.models import TokenBalance
        from ai_engine.services import AIUnavailable
        balance, _ = TokenBalance.objects.get_or_create(user=self.premium)
        before = balance.available_tokens
        with mock.patch('ai_engine.services.AIService') as service, \
                mock.patch('ai_engine.views.compose_offline_answer', return_value=self._grounded()):
            service.return_value.ask_tutor.side_effect = AIUnavailable('down')
            res = _client(self.premium).post('/api/questions/chat/', {'message': 'Explain shock'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertTrue(res.data['offline'])
        self.assertIn('From the library.', res.data['reply'])
        balance.refresh_from_db()
        self.assertEqual(balance.available_tokens, before)

    def test_offline_mode_never_calls_a_provider(self):
        with mock.patch('ai_engine.services.AIService') as service, \
                mock.patch('ai_engine.views.ai_offline_mode', return_value=True), \
                mock.patch('ai_engine.views.compose_offline_answer', return_value=None):
            res = _client(self.premium).post('/api/questions/chat/', {'message': 'Explain shock'}, format='json')
        self.assertEqual(res.status_code, 503)
        self.assertEqual(res.data['code'], 'ai_unavailable')
        service.return_value.ask_tutor.assert_not_called()


# ── Per-question AI budget ─────────────────────────────────────────────────

class GenerationBudgetTests(_Base):
    @override_settings(AI_PER_QUESTION_HOURLY_LIMIT=1)
    def test_budget_is_spent_once_per_question(self):
        from questions import ai_per_question as ai
        q1 = _question(self.subject, 90, explanation='')
        q2 = _question(self.subject, 91, explanation='')
        with mock.patch.object(ai, '_ai_call', return_value='Generated text') as call:
            for path in ('concept', 'why_correct', 'clinical', 'mnemonic'):
                res = _client(self.premium).get(f'/api/questions/{q1.id}/ai/{path}/')
                self.assertEqual(res.status_code, 200)
            self.assertEqual(call.call_count, 4)
            self.assertNotIn('rate_limited', res.data)
            res = _client(self.premium).get(f'/api/questions/{q2.id}/ai/concept/')
        self.assertIsNone(res.data['concept'])
        self.assertTrue(res.data['rate_limited'])
        self.assertEqual(call.call_count, 4)


# ── AI fill rule (cache task / commands) ───────────────────────────────────

class AIFillRuleTests(_Base):
    GOOD = {'why_correct': 'Gamma is right because...', 'mnemonic': 'G', 'exam_tip': 'Tip',
            'around_concepts': ['x', 'y'], 'core_concept': 'Concept'}

    def test_curated_concept_keywords_are_kept(self):
        from questions.tasks import apply_explain_result
        q = _question(self.subject, 100, concept_keywords=['curated'])
        fields = apply_explain_result(q, dict(self.GOOD))
        self.assertNotIn('concept_keywords', fields)
        self.assertEqual(q.concept_keywords, ['curated'])
        self.assertTrue(q.ai_model.startswith('roundrobin'))

    def test_generate_missing_ai_never_persists_an_outage(self):
        q = _question(self.subject, 101, learning_technique='Curated technique', ai_explanation='')
        with mock.patch('questions.management.commands.generate_missing_ai.AIService') as service:
            service.return_value.explain_after_answer.return_value = {
                'why_correct': OUTAGE, 'why_wrong': {}, 'raw_response': OUTAGE,
            }
            call_command('generate_missing_ai', stdout=StringIO())
        q.refresh_from_db()
        self.assertEqual((q.ai_explanation, q.ai_answer, q.learning_technique), ('', '', 'Curated technique'))


# ── Fixture loader is safe to re-run ───────────────────────────────────────

class LoadExamFixtureSafetyTests(_Base):
    def setUp(self):
        super().setUp()
        from questions.management.commands import load_exam_fixture as loader
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / 'images' / 'cms').mkdir(parents=True)
        patcher = mock.patch.object(loader, 'FIXTURES_DIR', self.tmp)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _load(self, rows):
        (self.tmp / 'cms_fixture.json').write_text(json.dumps(rows), encoding='utf-8')
        out = StringIO()
        call_command('load_exam_fixture', 'cms', stdout=out, no_color=True)
        return out.getvalue()

    @staticmethod
    def _dumpdata_rows(text='Dumpdata stem', **fields):
        """The shape of the committed cms_fixture.json (a dumpdata export)."""
        question = {
            'subject': 7, 'topic': 9, 'question_text': text, 'option_a': 'a', 'option_b': 'b',
            'option_c': 'c', 'option_d': 'd', 'correct_answer': 'B', 'year': 2019, 'exam_source': 'UPSC CMS',
            'explanation': 'Fixture explanation', 'is_active': True, 'similar_questions': [],
            'verified_by': None, 'created_at': '2026-07-01T08:05:42.982Z', 'updated_at': '2026-07-01T08:05:42.982Z',
        }
        question.update(fields)
        return [
            {'model': 'questions.subject', 'pk': 7, 'fields': {'code': 'W1FX', 'name': 'W1 Fixture Subject'}},
            {'model': 'questions.topic', 'pk': 9, 'fields': {'subject': 7, 'name': 'W1 Fixture Topic'}},
            {'model': 'questions.question', 'pk': 880001, 'fields': question},
        ]

    def test_dumpdata_shape_loads_with_mapped_subject_and_topic(self):
        self._load(self._dumpdata_rows())
        q = Question.objects.get(pk=880001)
        self.assertEqual((q.subject.code, q.topic.name, q.exam_type), ('W1FX', 'W1 Fixture Topic', 'cms'))

    def test_admin_touched_rows_are_left_alone(self):
        self._load(self._dumpdata_rows())
        all_flags = ('admin_edited', 'lock_answer', 'lock_explanation', 'is_verified_by_admin')
        for flag in all_flags:
            flags = {name: name == flag for name in all_flags}
            Question.objects.filter(pk=880001).update(explanation='Admin fix', **flags)
            output = self._load(self._dumpdata_rows())
            self.assertEqual(Question.objects.get(pk=880001).explanation, 'Admin fix', flag)
            self.assertIn('Left 1 admin-edited', output)
        Question.objects.filter(pk=880001).update(is_verified_by_admin=False)
        self._load(self._dumpdata_rows())
        self.assertEqual(Question.objects.get(pk=880001).explanation, 'Fixture explanation')

    def test_archived_rows_are_not_revived(self):
        self._load(self._dumpdata_rows())
        Question.objects.filter(pk=880001).update(is_active=False)
        self._load(self._dumpdata_rows(explanation='Updated fixture explanation'))
        q = Question.objects.get(pk=880001)
        self.assertFalse(q.is_active)
        self.assertEqual(q.explanation, 'Updated fixture explanation')

    def test_a_pk_of_another_exam_is_skipped(self):
        other = _question(self.subject, 110, exam_type='neet_pg', question_text='NEET row')
        rows = self._dumpdata_rows()
        rows[2]['pk'] = other.pk
        output = self._load(rows)
        other.refresh_from_db()
        self.assertEqual(other.question_text, 'NEET row')
        self.assertIn("another exam's question", output)

    def test_rows_without_pk_or_exam_type_are_not_duplicated(self):
        rows = [
            {'model': 'questions.subject', 'fields': {'code': 'W1NP', 'name': 'W1 No-pk Subject'}},
            {'model': 'questions.question', 'fields': {
                'subject': 'W1NP', 'question_text': 'No pk stem', 'option_a': 'a', 'option_b': 'b',
                'option_c': 'c', 'option_d': 'd', 'correct_answer': 'A', 'year': 2020,
            }},
        ]
        self._load(rows)
        self._load(rows)
        self.assertEqual(Question.objects.filter(question_text='No pk stem').count(), 1)


class ExportBackupLocationTests(_Base):
    def test_output_dir_is_required_and_must_be_outside_the_repo(self):
        with self.assertRaises(CommandError):
            call_command('export_questions_backup', stdout=StringIO())
        inside = Path(settings.BASE_DIR) / 'backup' / 'w1-should-not-exist'
        with self.assertRaises(CommandError):
            call_command('export_questions_backup', output_dir=str(inside), stdout=StringIO())
        self.assertFalse(inside.exists())
        with tempfile.TemporaryDirectory() as tmp:
            call_command('export_questions_backup', output_dir=tmp, stdout=StringIO())


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class MiscAdminSurfaceTests(_Base):
    def test_import_job_list_hides_server_paths(self):
        QuestionImportJob.objects.create(job_type='pdf', status='queued', source_filename='x.pdf',
                                         stored_file_path='/srv/private/recall/x.pdf')
        res = _client(self.admin).get('/api/questions/extraction/jobs/')
        self.assertEqual(res.status_code, 200)
        self.assertNotIn('stored_file_path', res.data['results'][0])
        self.assertNotIn('/srv/private', json.dumps(res.data))

    def test_discussions_are_registered_for_moderation(self):
        self.assertIn(Discussion, django_admin.site._registry)

    def test_extraction_upload_checks_the_bytes(self):
        fake_pdf = SimpleUploadedFile('paper.pdf', b'<html>not a pdf</html>', content_type='application/pdf')
        res = _client(self.admin).post('/api/questions/extraction/upload/', {'file': fake_pdf}, format='multipart')
        self.assertEqual(res.status_code, 400)
        self.assertFalse(QuestionImportJob.objects.filter(source_filename='paper.pdf').exists())
        self.assertFalse(os.path.exists(os.path.join(settings.MEDIA_ROOT, 'pyq_uploads', 'paper.pdf')))
