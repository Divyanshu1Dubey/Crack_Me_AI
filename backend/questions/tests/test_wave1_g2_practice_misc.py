"""Wave-1 G2: practice modes, quests, list performance and smaller fixes.

Issues: QB-07, QB-24, QB-28, QB-35, QB-19, QB-26, QB-20, ADM-08, QB-16,
QB-10, ACC-25, QB-29 and the related_pyqs empty-concept bug.
"""
from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Subscription
from questions.models import (
    Announcement, Discussion, DuplicateCluster, DuplicateMember, MistakeNotebook, Question, QuestionAttempt,
    QuestionBookmark, QuestionImage, QuestStreak, Subject, Topic, UserQuest,
)

User = get_user_model()


def _question(subject, i, **kw):
    defaults = dict(
        question_text=f'G2 misc stem {i}', option_a='alpha', option_b='beta', option_c='gamma',
        option_d='delta', correct_answer='A', year=2024, subject=subject,
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


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='G2 Misc Subject', code='G2MISC')
        cls.topic = Topic.objects.create(subject=cls.subject, name='G2 Misc Topic')
        cls.premium = _premium('g2-misc-premium')
        cls.admin = User.objects.create_user(username='g2-misc-admin', password='unused-pw-2', role='admin')

    def setUp(self):
        cache.clear()


class PracticeModesTests(_Base):
    def test_wrong_bookmarked_and_weak_topic_modes_work(self):
        wrong = _question(self.subject, 1, topic=self.topic)
        right = _question(self.subject, 2, topic=self.topic)
        marked = _question(self.subject, 3)
        archived = _question(self.subject, 4, is_active=False)
        QuestionAttempt.objects.create(user=self.premium, question=wrong, selected_answer='B', is_correct=False)
        QuestionAttempt.objects.create(user=self.premium, question=right, selected_answer='A', is_correct=True)
        QuestionAttempt.objects.create(user=self.premium, question=archived, selected_answer='B', is_correct=False)
        QuestionBookmark.objects.create(user=self.premium, question=marked)
        QuestionBookmark.objects.create(user=self.premium, question=archived)
        client = _client(self.premium)
        res = client.get('/api/questions/practice_queue/', {'mode': 'wrong'})
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['question_ids'], [wrong.id])
        res = client.get('/api/questions/practice_queue/', {'mode': 'bookmarked'})
        self.assertEqual(res.data['question_ids'], [marked.id])
        res = client.get('/api/questions/practice_queue/', {'mode': 'weak_topics'})
        self.assertEqual(res.status_code, 200)

    def test_weak_topics_ranks_the_topic_with_most_mistakes(self):
        from questions.practice_modes import build_queue
        weak = Topic.objects.create(subject=self.subject, name='G2 Weak')
        strong = Topic.objects.create(subject=self.subject, name='G2 Strong')
        for i in range(6):
            q = _question(self.subject, 100 + i, topic=weak)
            QuestionAttempt.objects.create(user=self.premium, question=q, selected_answer='B', is_correct=False)
            q2 = _question(self.subject, 200 + i, topic=strong)
            QuestionAttempt.objects.create(user=self.premium, question=q2, selected_answer='A', is_correct=True)
        ids = build_queue('weak_topics', self.premium, {'count': 50})
        topics = set(Question.objects.filter(id__in=ids).values_list('topic_id', flat=True))
        self.assertEqual(topics, {weak.id})

    def test_malformed_scope_params_are_a_400_not_a_500(self):
        res = _client(self.premium).get('/api/questions/practice_queue/', {'mode': 'year_wise', 'year': 'abc'})
        self.assertEqual(res.status_code, 400)


class PracticeCountsTowardsQuestsTests(_Base):
    def test_practice_attempt_updates_daily_activity_once(self):
        from analytics.models import DailyActivity, UserTopicPerformance
        q = _question(self.subject, 10, topic=self.topic)
        client = _client(self.premium)
        client.post(f'/api/questions/{q.id}/practice/attempt/', {'answer': 'A'}, format='json')
        client.post(f'/api/questions/{q.id}/practice/attempt/', {'answer': 'B'}, format='json')
        activity = DailyActivity.objects.get(user=self.premium, date=timezone.localdate())
        self.assertEqual((activity.questions_attempted, activity.correct_answers), (1, 1))
        perf = UserTopicPerformance.objects.get(user=self.premium, subject=self.subject, topic=self.topic)
        self.assertEqual((perf.total_attempts, perf.correct_answers), (1, 1))

    def test_practice_attempt_invalidates_the_users_list_cache(self):
        q = _question(self.subject, 13)
        before = int(cache.get(f'qlist_ver:{self.premium.id}') or 0)
        _client(self.premium).post(f'/api/questions/{q.id}/practice/attempt/', {'answer': 'B'}, format='json')
        self.assertGreater(int(cache.get(f'qlist_ver:{self.premium.id}') or 0), before)

    def test_qbank_attempt_counters_use_atomic_updates(self):
        from analytics.models import DailyActivity
        q1, q2 = _question(self.subject, 11), _question(self.subject, 12)
        DailyActivity.objects.create(user=self.premium, date=timezone.localdate(), questions_attempted=5)
        client = _client(self.premium)
        client.post(f'/api/questions/{q1.id}/attempt/', {'selected_answer': 'A'}, format='json')
        client.post(f'/api/questions/{q2.id}/attempt/', {'selected_answer': 'C'}, format='json')
        activity = DailyActivity.objects.get(user=self.premium, date=timezone.localdate())
        self.assertEqual((activity.questions_attempted, activity.correct_answers), (7, 1))


class StreakFreezeTests(_Base):
    def _claim_with_gap(self, days_since_last, frozen=True):
        from analytics.models import DailyActivity
        from questions.quest_service import claim_quest, ensure_daily_quests
        user = User.objects.create_user(username=f'g2-streak-{days_since_last}-{frozen}', password='unused-pw-3')
        ensure_daily_quests(user)
        DailyActivity.objects.create(user=user, date=timezone.localdate(), questions_attempted=25)
        QuestStreak.objects.create(user=user, current_streak=5, longest_streak=5, streak_frozen=frozen,
                                   last_quest_date=timezone.localdate() - timedelta(days=days_since_last))
        quest = UserQuest.objects.get(user=user, quest_type='solve_questions', quest_date=timezone.localdate())
        claim_quest(user, quest.id)
        return QuestStreak.objects.get(user=user)

    def test_freeze_bridges_exactly_one_missed_day(self):
        streak = self._claim_with_gap(2)
        self.assertEqual((streak.current_streak, streak.streak_frozen), (6, False))

    def test_freeze_does_not_bridge_a_longer_gap(self):
        self.assertEqual(self._claim_with_gap(10).current_streak, 1)

    def test_string_false_does_not_freeze(self):
        client = _client(self.premium)
        res = client.post('/api/questions/quests/streak/freeze/', {'streak_frozen': 'false'}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data['streak_frozen'])


class QuestionsAppMistakeRoutesTests(_Base):
    """The questions-app copies of the Mistake Notebook routes were removed
    (wave 2): they duplicated /api/analytics/mistake-notebook/ (the routes the
    frontend uses) with a writable review state and a weaker add check."""

    def test_duplicate_routes_are_gone(self):
        client = _client(self.premium)
        for path in ('/api/questions/mistake-notebook/', '/api/questions/mistake-notebook/due/',
                     '/api/questions/mistake-notebook/stats/', '/api/questions/mistake-notebook/1/review/'):
            self.assertEqual(client.get(path).status_code, 404, path)

    def test_post_cannot_create_or_reveal_anything(self):
        free = User.objects.create_user(username='g2-misc-free', password='unused-pw-4')
        q = _question(self.subject, 20)
        res = _client(free).post('/api/questions/mistake-notebook/', {'question': q.id}, format='json')
        self.assertIn(res.status_code, (403, 404, 405))
        self.assertNotIn('correct_answer', getattr(res, 'data', None) or {})
        self.assertFalse(MistakeNotebook.objects.filter(user=free).exists())

    def test_analytics_routes_still_serve_the_notebook(self):
        client = _client(self.premium)
        self.assertEqual(client.get('/api/analytics/mistake-notebook/').status_code, 200)
        self.assertEqual(client.get('/api/analytics/mistake-notebook/due/').status_code, 200)


class ListQueryCountTests(_Base):
    def _make(self, n, offset):
        rows = []
        for i in range(n):
            q = _question(self.subject, offset + i, topic=self.topic, verified_by=self.admin)
            QuestionImage.objects.create(question=q, page_number=1)
            cluster = DuplicateCluster.objects.create(canonical_question=q)
            DuplicateMember.objects.create(cluster=cluster, question=q, similarity_score=1.0)
            rows.append(q)
        return rows

    def _bookmark_queries(self, user):
        with CaptureQueriesContext(connection) as ctx:
            res = _client(user).get('/api/questions/bookmarks/')
        self.assertEqual(res.status_code, 200)
        return len(ctx.captured_queries), res

    def test_bookmarks_query_count_does_not_grow_with_bookmarks(self):
        small = _premium('g2-bm-small')
        large = _premium('g2-bm-large')
        for q in self._make(2, 300):
            QuestionBookmark.objects.create(user=small, question=q)
        for q in self._make(8, 400):
            QuestionBookmark.objects.create(user=large, question=q)
        n_small, _ = self._bookmark_queries(small)
        n_large, res = self._bookmark_queries(large)
        self.assertEqual(n_small, n_large)
        self.assertEqual(len(res.data), 8)
        self.assertEqual(res.data[0]['question_detail']['duplicate_count'], 1)

    def test_bookmarks_can_be_paginated(self):
        user = _premium('g2-bm-pages')
        for q in self._make(3, 500):
            QuestionBookmark.objects.create(user=user, question=q)
        res = _client(user).get('/api/questions/bookmarks/', {'page': 1})
        self.assertEqual(res.data['count'], 3)
        self.assertEqual(len(res.data['results']), 3)

    def test_similar_excludes_inactive_and_has_bounded_queries(self):
        main = _question(self.subject, 600, topic=self.topic)
        active = [_question(self.subject, 601 + i, topic=self.topic) for i in range(3)]
        inactive = _question(self.subject, 610, topic=self.topic, is_active=False)
        with CaptureQueriesContext(connection) as ctx:
            res = _client(self.premium).get(f'/api/questions/{main.id}/similar/')
        ids = [row['id'] for row in res.data]
        self.assertNotIn(inactive.id, ids)
        self.assertEqual(set(ids), {q.id for q in active})
        self.assertLess(len(ctx.captured_queries), 25)


class AccuracyTests(_Base):
    def test_admin_sees_accuracy_students_do_not_pay_for_it(self):
        from tests_engine.models import QuestionResponse, Test, TestAttempt
        q = _question(self.subject, 700, year=2027)
        for i, correct in enumerate((True, False)):
            test = Test.objects.create(title=f'G2 acc {i}', test_type='mixed')
            attempt = TestAttempt.objects.create(user=self.premium, test=test)
            QuestionResponse.objects.create(attempt=attempt, question=q, selected_answer='A', is_correct=correct)
        admin_row = _client(self.admin).get('/api/questions/', {'year': 2027}).data['results'][0]
        self.assertEqual(admin_row['accuracy'], 50.0)
        with CaptureQueriesContext(connection) as ctx:
            student_row = _client(self.premium).get('/api/questions/', {'year': 2027}).data['results'][0]
        self.assertIsNone(student_row['accuracy'])
        self.assertFalse(any('questionresponse' in q['sql'].lower() for q in ctx.captured_queries))


class RuntimeRoleCacheTests(_Base):
    def test_role_is_recomputed_for_every_response(self):
        from questions.serializers import QuestionDetailSerializer, QuestionListSerializer
        q = _question(self.subject, 800)
        img = QuestionImage.objects.create(question=q, page_number=1, role='primary')
        # An entitled viewer: list rows of locked questions drop explanation
        # figures (wave 3), which is not what this test is about.
        context = {'viewer_full_access': True}
        for serializer_cls in (QuestionDetailSerializer, QuestionListSerializer):
            q.explanation = ''
            q.save()
            q.refresh_from_db()
            self.assertEqual(serializer_cls(q, context=context).data['images'][0]['role'], 'primary')
            q.explanation = f'See [[img:{img.id}]]'
            q.save()
            q = Question.objects.prefetch_related('images').get(pk=q.pk)
            self.assertEqual(serializer_cls(q, context=context).data['images'][0]['role'], 'explanation')


class AnnouncementCacheTests(_Base):
    def test_cache_is_per_user_and_exam_targeting_matches_labels(self):
        cms_user = User.objects.create_user(username='g2-ann-cms', password='unused-pw-5', target_exam='UPSC CMS')
        pg_user = User.objects.create_user(username='g2-ann-pg', password='unused-pw-6', target_exam='NEET PG')
        personal = Announcement.objects.create(title='For you only', body='x')
        personal.target_users.add(cms_user)
        Announcement.objects.create(title='NEET PG news', body='y', target_exam_track='neet_pg')

        def titles(user):
            data = _client(user).get('/api/questions/announcements/').data
            rows = data['results'] if isinstance(data, dict) else data
            return {row['title'] for row in rows}

        self.assertEqual(titles(cms_user), {'For you only'})
        self.assertEqual(titles(pg_user), {'NEET PG news'})  # not served cms_user's cached list
        self.assertEqual(titles(cms_user), {'For you only'})


class DiscussionTests(_Base):
    def setUp(self):
        super().setUp()
        self.q1 = _question(self.subject, 900)
        self.q2 = _question(self.subject, 901)
        self.author = User.objects.create_user(username='g2-disc-author', password='unused-pw-7')
        self.other = User.objects.create_user(username='g2-disc-other', password='unused-pw-8')
        self.thread = Discussion.objects.create(question=self.q1, user=self.author, text='Thread')
        # Free accounts read the threads of free showcase questions only
        # (wave 3: threads discuss the answer); these tests are about
        # replies and moderation, so q1 is a showcase question.
        from accounts.models_freemium import FreeShowcaseQuestion
        FreeShowcaseQuestion.objects.create(question=self.q1, year=self.q1.year, position=9)

    def test_reply_must_belong_to_the_same_question(self):
        res = _client(self.other).post('/api/questions/discussions/',
                                       {'question': self.q2.id, 'parent': self.thread.id, 'text': 'x'}, format='json')
        self.assertEqual(res.status_code, 400)
        res = _client(self.other).post('/api/questions/discussions/',
                                       {'question': self.q1.id, 'parent': self.thread.id, 'text': 'ok'}, format='json')
        self.assertEqual(res.status_code, 201)
        rows = _client(self.other).get('/api/questions/discussions/', {'question': self.q1.id}).data['results']
        self.assertEqual(rows[0]['reply_count'], 1)

    def test_owner_edits_admin_moderates(self):
        url = f'/api/questions/discussions/{self.thread.id}/'
        self.assertEqual(_client(self.other).patch(url, {'text': 'hijack'}, format='json').status_code, 403)
        self.assertEqual(_client(self.other).delete(url).status_code, 403)
        res = _client(self.author).patch(url, {'text': 'Edited', 'question': self.q2.id}, format='json')
        self.assertEqual(res.status_code, 200)
        self.thread.refresh_from_db()
        self.assertEqual((self.thread.text, self.thread.question_id), ('Edited', self.q1.id))
        self.assertEqual(_client(self.admin).delete(url).status_code, 204)
        self.assertFalse(Discussion.objects.filter(pk=self.thread.pk).exists())

    def test_bad_question_filter_is_empty_not_500(self):
        res = _client(self.other).get('/api/questions/discussions/', {'question': 'abc'})
        self.assertEqual(res.status_code, 200)


class RelatedPyqsTests(_Base):
    def test_empty_concept_id_does_not_match_unrelated_questions(self):
        from questions.ai_per_question import related_pyqs
        q = _question(self.subject, 1000, question_text='zzqx unique stem', concept_id='')
        _question(self.subject, 1001, question_text='totally unrelated', concept_id='')
        self.assertEqual(related_pyqs(q), [])

    def test_inactive_rows_are_excluded_even_from_the_cache(self):
        from questions.ai_per_question import related_pyqs
        q = _question(self.subject, 1002, concept_id='shock-1')
        twin = _question(self.subject, 1003, concept_id='shock-1')
        self.assertEqual([r['id'] for r in related_pyqs(q)], [twin.id])
        Question.objects.filter(pk=twin.pk).update(is_active=False)
        self.assertEqual(related_pyqs(q), [])
