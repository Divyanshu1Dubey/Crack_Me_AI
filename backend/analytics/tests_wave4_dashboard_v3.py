"""Wave-4 follow-ups of the security / performance review (analytics, Z3).

* dashboard_v3 used to load the user's whole answer history four times per
  request (90-day, 60-day, all-time and 365-day windows), load every
  practice-state row, and send an IN list of every answered question id;
  its sub-endpoints had no cache and ``?nocache=1`` skipped the dashboard
  cache for anyone. Now one load per request, every result cached per user
  for CACHE_TTL (a new answer shows up within a minute), ``nocache`` only for
  admins / staff -- and every response field identical to the old code's
  (LegacyEquivalenceTests compares both on the same history).
* The loader's "Imported" subject reads "Expert Curated" in every analytics
  payload (the question serializers' helper: questions.serializers
  .public_subject_name / PublicSubjectNameField).
* Mistake Notebook rows whose answer the viewer may not see have answer /
  explanation labels cut out of the stem and options
  (questions.answer_leak.redact_public_text) and, since wave 4b, lose
  correctness flags such as "(correct)" on their options -- the redaction
  of a locked test-review row (tests_engine.entitlement).
"""
import json
import random
import time
from collections import defaultdict
from datetime import timedelta
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.db.models import Count
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Subscription
from accounts.models_freemium import FreeShowcaseQuestion
from analytics import dashboard_v3
from analytics.models import UserTopicPerformance
from analytics.serializers import (MistakeNotebookSerializer, StudyTimeBreakdownSerializer,
                                   TopicPerformanceSerializer, UserQuestSerializer)
from questions.models import (MistakeNotebook, Question, QuestionAttempt, QuestionPracticeState,
                              StudyTimeBreakdown, Subject, Topic, UserQuest)
from questions.serializers import PublicSubjectNameField, public_subject_name
from tests_engine.models import QuestionResponse, Test, TestAttempt

User = get_user_model()

DASH = '/api/analytics/dashboard_v3/'
HEATMAP = '/api/analytics/heatmap/subject/'
REVISION = '/api/analytics/revision_progress/'
PYQ = '/api/analytics/pyq_coverage/'
AVERAGE = '/api/analytics/average_time/'
SUB_ENDPOINTS = (HEATMAP, REVISION, PYQ, AVERAGE)
ANSWER_TABLES = ('tests_engine_questionresponse', 'questions_questionattempt', 'questions_questionpracticestate')


# ─── The old implementation (git HEAD before this change), as the oracle ──


def _legacy_answer_events(user, days=90):
    since = timezone.now() - timedelta(days=days) if days else None
    fields = ("question_id", "question__subject_id", "question__subject__name",
              "question__topic_id", "question__topic__name", "is_correct")
    events = []
    responses = QuestionResponse.objects.filter(
        attempt__user=user, attempt__is_completed=True, is_correct__isnull=False)
    if since:
        responses = responses.filter(attempt__started_at__gte=since)
    for r in responses.values(*fields, "time_taken_seconds", "confidence_level",
                              "attempt__completed_at", "attempt__started_at").iterator():
        events.append({
            **{k: r[k] for k in fields},
            "when": r["attempt__completed_at"] or r["attempt__started_at"],
            "seconds": r["time_taken_seconds"] or None,
            "confidence": r["confidence_level"] or None,
        })
    state = {
        qid: (conf, secs) for qid, conf, secs in QuestionPracticeState.objects.filter(user=user)
        .values_list("question_id", "confidence", "time_spent_seconds")
    }
    attempts = QuestionAttempt.objects.filter(user=user)
    if since:
        attempts = attempts.filter(attempted_at__gte=since)
    for a in attempts.values(*fields, "attempted_at").iterator():
        conf, secs = state.get(a["question_id"], (None, None))
        events.append({
            **{k: a[k] for k in fields},
            "when": a["attempted_at"],
            "seconds": secs or None,
            "confidence": conf or None,
        })
    return events


def _legacy_accuracy(events):
    n = len(events)
    c = sum(1 for e in events if e["is_correct"])
    return {"total": n, "correct": c, "accuracy_pct": round((c / n) * 100, 1) if n else 0.0}


def _legacy_average_time(events):
    timed = [e["seconds"] for e in events if e["seconds"]]
    return {"average_seconds": int(sum(timed) / len(timed)) if timed else 0}


def _legacy_weak_groups(events, key, limit):
    groups = {}
    for e in events:
        k = e[key]
        if k is None:
            continue
        g = groups.setdefault(k, {"n": 0, "mistakes": 0, "first": e})
        g["n"] += 1
        g["mistakes"] += 0 if e["is_correct"] else 1
    rows = [(k, g) for k, g in groups.items() if g["n"] >= 3]
    rows.sort(key=lambda kg: (-kg[1]["mistakes"], -(kg[1]["mistakes"] / kg[1]["n"])))
    return rows[:limit]


def _legacy_weak_subjects(events, limit=6):
    return [{
        "subject_id": sid,
        "subject": g["first"]["question__subject__name"],
        "attempts": g["n"],
        "mistakes": g["mistakes"],
        "mistake_rate_pct": round((g["mistakes"] / g["n"]) * 100, 1),
    } for sid, g in _legacy_weak_groups(events, "question__subject_id", limit)]


def _legacy_weak_topics(events, limit=6):
    return [{
        "topic_id": tid,
        "topic": g["first"]["question__topic__name"],
        "subject": g["first"]["question__subject__name"],
        "attempts": g["n"],
        "mistakes": g["mistakes"],
        "mistake_rate_pct": round((g["mistakes"] / g["n"]) * 100, 1),
    } for tid, g in _legacy_weak_groups(events, "question__topic_id", limit)]


def _legacy_performance_trend(user, days=60):
    per_day = defaultdict(lambda: {"n": 0, "correct": 0})
    for e in _legacy_answer_events(user, days=days):
        if not e["when"]:
            continue
        day = timezone.localdate(e["when"])
        per_day[day]["n"] += 1
        per_day[day]["correct"] += 1 if e["is_correct"] else 0
    return [{"date": day.isoformat(), "attempts": per_day[day]["n"], "correct": per_day[day]["correct"],
             "accuracy_pct": round((per_day[day]["correct"] / per_day[day]["n"]) * 100, 1) if per_day[day]["n"] else 0}
            for day in sorted(per_day)]


def _legacy_revision_progress(user):
    seen = defaultdict(dict)
    topics = {}
    for e in _legacy_answer_events(user, days=None):
        tid = e["question__topic_id"]
        if tid is None:
            continue
        topics[tid] = e["question__topic__name"]
        conf = int(e["confidence"] or 0)
        seen[tid][e["question_id"]] = max(conf, seen[tid].get(e["question_id"], 0))
    out = []
    for tid, name in topics.items():
        buckets = defaultdict(int)
        for conf in seen[tid].values():
            buckets[conf] += 1
        out.append({"topic_id": tid, "topic": name, "by_confidence": dict(buckets), "total": len(seen[tid])})
    out.sort(key=lambda t: -t["total"])
    return {"topics": out}


def _legacy_pyq_coverage(user):
    attempted_qids = {e["question_id"] for e in _legacy_answer_events(user, days=365)}
    grid = defaultdict(lambda: {"attempted": 0, "total": 0, "years": defaultdict(lambda: {"a": 0, "t": 0})})
    qs = Question.objects.filter(is_active=True, exam_type__in=["cms", "neet_pg", "ini_cet", "aiims_pg"])
    for r in qs.values("exam_type", "year").annotate(t=Count("id")):
        grid[r["exam_type"]]["total"] += r["t"]
        grid[r["exam_type"]]["years"][r["year"]]["t"] += r["t"]
    if attempted_qids:
        for r in qs.filter(id__in=attempted_qids).values("exam_type", "year").annotate(a=Count("id")):
            grid[r["exam_type"]]["attempted"] += r["a"]
            grid[r["exam_type"]]["years"][r["year"]]["a"] += r["a"]
    return {exam: {
        "attempted": p["attempted"],
        "total": p["total"],
        "coverage_pct": round((p["attempted"] / p["total"]) * 100, 1) if p["total"] else 0.0,
        "years": {y: p["years"][y] for y in sorted(p["years"])},
    } for exam, p in grid.items()}


def _legacy_heatmap_subject(user):
    matrix = defaultdict(lambda: defaultdict(lambda: {"n": 0, "correct": 0}))
    for e in _legacy_answer_events(user, days=60):
        if not e["when"] or e["question__subject_id"] is None:
            continue
        local = timezone.localtime(e["when"])
        cell = matrix[str(e["question__subject_id"])][str((local.weekday() + 1) % 7)]
        cell["n"] += 1
        cell["correct"] += 1 if e["is_correct"] else 0
    return {s: dict(days) for s, days in matrix.items()}


def _legacy_dashboard(user):
    events = _legacy_answer_events(user)
    return {
        "accuracy": _legacy_accuracy(events),
        "average_time": _legacy_average_time(events),
        "weak_subjects": _legacy_weak_subjects(events),
        "weak_topics": _legacy_weak_topics(events),
        "performance_trend": _legacy_performance_trend(user),
        "revision_progress": _legacy_revision_progress(user),
        "pyq_coverage": _legacy_pyq_coverage(user),
    }


def _legacy(path, user):
    return {
        DASH: _legacy_dashboard,
        HEATMAP: _legacy_heatmap_subject,
        REVISION: _legacy_revision_progress,
        PYQ: _legacy_pyq_coverage,
        AVERAGE: lambda u: _legacy_average_time(_legacy_answer_events(u)),
    }[path](user)


def _ordered(value):
    """``value`` as JSON whose objects are lists of (key, value) pairs, so an
    equality check covers key order as well as values."""
    text = value.decode() if isinstance(value, bytes) else json.dumps(value)
    return json.loads(text, object_pairs_hook=list)


# ─── Fixture: an answer history over every window ────────────────────────


def _build_history(user, now, tests, bank, states):
    """``tests``: [(days_ago, is_completed, has_completed_at, [(question,
    is_correct, seconds, confidence), ...])]; ``bank``: [(question,
    is_correct, days_ago)]; ``states``: [(question, confidence, seconds)].

    Rows are created in the order the database returns them under any plan
    (attempts by start time, responses and bank answers by question id), as
    in production where ids grow with time, so the old windowed queries and
    the new single load list the same events in the same order.
    """
    for days_ago, completed, has_completed_at, answers in sorted(tests, key=lambda t: -t[0]):
        started = now - timedelta(days=days_ago)
        test = Test.objects.create(title=f'W4 dv3 test {days_ago:.2f}', test_type='mixed')
        attempt = TestAttempt.objects.create(
            user=user, test=test, is_completed=completed,
            completed_at=started + timedelta(minutes=50) if (completed and has_completed_at) else None)
        TestAttempt.objects.filter(pk=attempt.pk).update(started_at=started)
        for question, is_correct, seconds, confidence in sorted(answers, key=lambda a: a[0].id):
            QuestionResponse.objects.create(
                attempt=attempt, question=question, is_correct=is_correct, time_taken_seconds=seconds,
                confidence_level=confidence, selected_answer=None if is_correct is None else 'A')
    for question, is_correct, days_ago in sorted(bank, key=lambda b: b[0].id):
        attempt = QuestionAttempt.objects.create(user=user, question=question, selected_answer='A',
                                                 is_correct=is_correct)
        QuestionAttempt.objects.filter(pk=attempt.pk).update(attempted_at=now - timedelta(days=days_ago))
    for question, confidence, seconds in states:
        QuestionPracticeState.objects.create(user=user, question=question, confidence=confidence,
                                             time_spent_seconds=seconds)


def _away_from_window_edges(days):
    """Keep a random age at least 0.2 day from a 60 / 90 / 365-day edge (the
    old code took `now` once per query, the new code once per request)."""
    for edge in (60, 90, 365):
        if abs(days - edge) < 0.2:
            return edge + 0.5
    return days


class LegacyEquivalenceTests(TestCase):
    """Same fields, values and order as the old implementation, for the
    dashboard and every sub-endpoint, computed on their own or filled by a
    dashboard miss."""

    @classmethod
    def setUpTestData(cls):
        now = timezone.now()
        med = Subject.objects.create(name='W4D Medicine', code='W4DMED')
        sur = Subject.objects.create(name='W4D Surgery', code='W4DSUR', paper=2)
        psm = Subject.objects.create(name='W4D PSM', code='W4DPSM', paper=2)
        cardio = Topic.objects.create(name='W4D Cardiology', subject=med)
        renal = Topic.objects.create(name='W4D Nephrology', subject=med)
        trauma = Topic.objects.create(name='W4D Trauma', subject=sur)
        epi = Topic.objects.create(name='W4D Epidemiology', subject=psm)
        subjects = (med, sur, psm)
        # Topic per question: None for some, and cardiology also on surgery /
        # PSM questions (mis-tagged rows: a topic's "subject" comes from its
        # first event).
        topic_cycle = (cardio, trauma, epi, renal, None, cardio, cardio)
        exams = ('cms', 'neet_pg', 'ini_cet', 'aiims_pg', 'fmge')
        cls.questions = [Question.objects.create(
            question_text=f'W4 dv3 Q{i}', option_a='A', option_b='B', option_c='C', option_d='D',
            correct_answer='A', year=2018 + i % 6, subject=subjects[i % 3], topic=topic_cycle[i % 7],
            exam_type=exams[i % 5], is_active=i % 9 != 8) for i in range(36)]
        q = cls.questions

        # A fixed history: every window, skipped answers, an unfinished test,
        # a test without completed_at, timings / confidences of 0 and None,
        # ties between subjects and between topics.
        cls.user = User.objects.create_user(username='w4-dv3-fixed', password='x')
        tests = [
            (400.0, True, True, [(q[0], False, 30, 2), (q[1], True, 50, None), (q[2], False, None, 4)]),
            (200.0, True, False, [(q[3], False, 20, 0), (q[4], True, 0, 5), (q[5], False, 15, 3),
                                  (q[6], None, 9, 1)]),
            (75.0, True, True, [(q[7], False, 40, 1), (q[8], False, 10, None), (q[9], True, 70, 2),
                                (q[10], False, 25, 5), (q[11], True, 33, 3)]),
            (50.0, False, False, [(q[12], False, 60, 1), (q[13], True, 60, 1)]),   # never submitted
            (20.0, True, True, [(q[0], False, 12, 1), (q[3], False, 18, 2), (q[14], True, 22, None),
                                (q[15], False, 5, 4), (q[16], False, 8, 0), (q[17], None, 3, None)]),
            (2.0, True, True, [(q[1], True, 41, 5), (q[18], False, 16, 3), (q[19], False, 26, 2),
                               (q[20], True, 36, 1), (q[21], False, 46, None)]),
        ]
        bank = [(q[22], False, 500.0), (q[23], True, 300.0), (q[24], False, 80.0), (q[25], False, 45.0),
                (q[26], True, 10.0), (q[27], False, 0.05), (q[28], False, 30.0), (q[29], True, 59.0),
                (q[30], False, 89.0), (q[31], False, 364.0), (q[2], True, 5.0), (q[7], False, 15.0)]
        states = [(q[22], 3, 40), (q[24], 0, 0), (q[25], 5, 90), (q[27], 2, 0), (q[28], 0, 75),
                  (q[30], 4, 12), (q[2], 1, 30), (q[33], 5, 500)]   # q33: practised, never answered
        _build_history(cls.user, now, tests, bank, states)

        # A seeded random history, many more ties and mixes.
        rng = random.Random(20261101)
        cls.random_user = User.objects.create_user(username='w4-dv3-random', password='x')
        random_tests = []
        for _ in range(9):
            picked = rng.sample(q, 12)
            random_tests.append((
                _away_from_window_edges(rng.uniform(0, 420)), rng.random() > 0.12, rng.random() > 0.2,
                [(question, rng.choice((True, False, False, None)), rng.choice((None, 0, rng.randint(1, 240))),
                  rng.choice((None, 0, 1, 2, 3, 4, 5))) for question in picked]))
        random_bank = [(question, rng.random() > 0.55, _away_from_window_edges(rng.uniform(0, 500)))
                       for question in rng.sample(q, 28)]
        random_states = [(question, rng.randint(0, 5), rng.choice((0, rng.randint(1, 300))))
                         for question in rng.sample(q, 20)]
        _build_history(cls.random_user, now, random_tests, random_bank, random_states)

    def setUp(self):
        cache.clear()

    def _get(self, path, user):
        client = APIClient()
        client.force_authenticate(user)
        r = client.get(path)
        self.assertEqual(r.status_code, 200, getattr(r, 'data', None))
        return r

    def _assert_same_as_legacy(self, path, user, response):
        got = _ordered(response.content)
        if path == DASH:
            got = [pair for pair in got if pair[0] not in ('generated_at', 'cache')]
        self.assertEqual(got, _ordered(_legacy(path, user)), path)

    def test_fixture_has_every_case(self):
        # Answers per window (skipped answers and the unsubmitted test never count).
        self.assertEqual([len(_legacy_answer_events(self.user, days)) for days in (60, 90, 365, None)],
                         [17, 24, 29, 33])
        legacy = _legacy_dashboard(self.user)
        self.assertTrue(legacy['weak_subjects'] and legacy['weak_topics'])
        # A mis-tagged topic takes its subject from its first event (a surgery stem).
        cardio = next(row for row in legacy['weak_topics'] if row['topic'] == 'W4D Cardiology')
        self.assertEqual(cardio['subject'], 'W4D Surgery')
        self.assertTrue(legacy['pyq_coverage']['cms']['attempted'])
        self.assertTrue(legacy['revision_progress']['topics'])

    def test_each_endpoint_computed_on_its_own_matches_the_old_code(self):
        for user in (self.user, self.random_user):
            for path in (DASH, *SUB_ENDPOINTS):
                cache.clear()
                with self.subTest(user=user.username, path=path):
                    self._assert_same_as_legacy(path, user, self._get(path, user))

    def test_sub_endpoints_filled_by_a_dashboard_miss_match_the_old_code(self):
        for user in (self.user, self.random_user):
            cache.clear()
            self._assert_same_as_legacy(DASH, user, self._get(DASH, user))
            for path in SUB_ENDPOINTS:
                with self.subTest(user=user.username, path=path):
                    with CaptureQueriesContext(connection) as ctx:
                        response = self._get(path, user)
                    self.assertFalse(_answer_queries(ctx), path)   # served from the dashboard's load
                    self._assert_same_as_legacy(path, user, response)

    def test_cache_hits_return_the_same_fields(self):
        miss = self._get(DASH, self.random_user).data
        hit = self._get(DASH, self.random_user).data
        self.assertEqual((miss['cache'], hit['cache']), ('miss', 'hit'))
        self.assertEqual(list(miss), list(hit))
        self.assertEqual({k: v for k, v in miss.items() if k != 'cache'},
                         {k: v for k, v in hit.items() if k != 'cache'})


def _answer_queries(ctx):
    return [q['sql'] for q in ctx.captured_queries if any(table in q['sql'] for table in ANSWER_TABLES)]


class EventOrderTests(TestCase):
    """Events come by attempt start, then question id (bank answers: by
    question id), whatever order the rows were written in."""

    def test_a_topics_subject_comes_from_its_earliest_answer(self):
        cache.clear()
        first = Subject.objects.create(name='W4 Order First', code='W4ORD1')
        later = Subject.objects.create(name='W4 Order Later', code='W4ORD2')
        topic = Topic.objects.create(name='W4 Order Topic', subject=first)
        questions = [Question.objects.create(
            question_text=f'W4 order Q{i}', option_a='A', option_b='B', option_c='C', option_d='D',
            correct_answer='A', year=2022, subject=first if i == 2 else later, topic=topic) for i in range(6)]
        user = User.objects.create_user(username='w4-dv3-order', password='x')
        now = timezone.now()
        # The later test is written first, its answers in reverse question order.
        for days_ago, picked in ((3, questions[4:6]), (5, questions[2:4])):
            test = Test.objects.create(title=f'W4 order {days_ago}', test_type='mixed')
            attempt = TestAttempt.objects.create(user=user, test=test, is_completed=True, completed_at=now)
            TestAttempt.objects.filter(pk=attempt.pk).update(started_at=now - timedelta(days=days_ago))
            for question in reversed(picked):
                QuestionResponse.objects.create(attempt=attempt, question=question, selected_answer='B',
                                                is_correct=False)
        client = APIClient()
        client.force_authenticate(user)
        data = client.get(DASH).data
        # The earliest attempt's lowest question (questions[2], the only one
        # filed under "first") is the topic's first event; the rows were
        # written starting from questions[5].
        self.assertEqual(data['weak_topics'][0]['subject'], 'W4 Order First')
        # Bank answers follow the test answers, by question id, though
        # written in reverse.
        for question in reversed(questions[:2]):
            QuestionAttempt.objects.create(user=user, question=question, selected_answer='B', is_correct=False)
        events = dashboard_v3._answer_events(user, days=None)
        self.assertEqual([e['question_id'] for e in events],
                         [questions[i].id for i in (2, 3, 4, 5, 0, 1)])


class QueryBudgetTests(TestCase):
    """One load of the history per request, whatever its size."""

    def setUp(self):
        cache.clear()
        subject = Subject.objects.create(name='W4 Budget', code='W4BUD')
        topic = Topic.objects.create(name='W4 Budget Topic', subject=subject)
        self.user = User.objects.create_user(username='w4-dv3-budget', password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.subject, self.topic = subject, topic

    def _answer(self, start, n, days_ago=1.0):
        now = timezone.now()
        questions = [Question.objects.create(
            question_text=f'W4 budget Q{start + i}', option_a='A', option_b='B', option_c='C', option_d='D',
            correct_answer='A', year=2020 + i % 4, subject=self.subject, topic=self.topic)
            for i in range(n)]
        test = Test.objects.create(title=f'W4 budget {start}', test_type='mixed')
        attempt = TestAttempt.objects.create(user=self.user, test=test, is_completed=True, completed_at=now)
        QuestionResponse.objects.bulk_create([
            QuestionResponse(attempt=attempt, question=question, selected_answer='A', is_correct=i % 3 != 0,
                             time_taken_seconds=10 + i) for i, question in enumerate(questions)])
        QuestionAttempt.objects.bulk_create([
            QuestionAttempt(user=self.user, question=question, selected_answer='B', is_correct=False)
            for question in questions[: n // 2]])
        QuestionAttempt.objects.filter(user=self.user).update(attempted_at=now - timedelta(days=days_ago))
        QuestionPracticeState.objects.bulk_create([
            QuestionPracticeState(user=self.user, question=question, confidence=3, time_spent_seconds=20)
            for question in questions[: n // 4]])

    def _miss_queries(self):
        cache.clear()
        with CaptureQueriesContext(connection) as ctx:
            r = self.client.get(DASH)
        self.assertEqual((r.status_code, r.data['cache']), (200, 'miss'))
        return ctx

    def test_a_dashboard_miss_loads_the_history_once(self):
        self._answer(0, 12)
        ctx = self._miss_queries()
        sql = [q['sql'] for q in ctx.captured_queries]
        self.assertEqual(sum('tests_engine_questionresponse' in s for s in sql), 1, sql)
        self.assertEqual(sum('questions_questionpracticestate' in s for s in sql), 1, sql)
        # The bank answers: their own query and the practice-state semi-join.
        self.assertEqual(sum('questions_questionattempt' in s for s in sql), 2, sql)
        self.assertLessEqual(len(_answer_queries(ctx)), 3, sql)
        # The practice state is restricted to the answered questions.
        state_sql = next(s for s in sql if 'questions_questionpracticestate' in s)
        self.assertIn('questions_questionattempt', state_sql)

    def test_query_count_and_size_do_not_grow_with_the_history(self):
        self._answer(0, 10)
        small = self._miss_queries()
        self._answer(100, 240)
        large = self._miss_queries()
        self.assertEqual(len(_answer_queries(small)), len(_answer_queries(large)))
        for sql in (q['sql'] for q in large.captured_queries if 'questions_question' in q['sql']):
            # No `id IN (<every answered question id>)` list any more.
            self.assertNotRegex(sql, r'"questions_question"\."id" IN \(\d')
            self.assertLess(len(sql), 4000, sql[:300])

    def test_bank_totals_are_shared_between_users(self):
        self._answer(0, 6)
        other = User.objects.create_user(username='w4-dv3-budget-2', password='x')
        client = APIClient()
        client.force_authenticate(other)
        self.assertEqual(self.client.get(PYQ).status_code, 200)
        with CaptureQueriesContext(connection) as ctx:
            self.assertEqual(client.get(PYQ).status_code, 200)
        grouped = [q['sql'] for q in ctx.captured_queries
                   if 'FROM "questions_question"' in q['sql'] and 'GROUP BY' in q['sql']]
        self.assertEqual(grouped, [])


class CacheTests(TestCase):
    """Every v3 result is cached per user for at most a minute; nocache is
    for admins / staff only."""

    def setUp(self):
        cache.clear()
        self.subject = Subject.objects.create(name='W4 Cache', code='W4CAC')
        self.topic = Topic.objects.create(name='W4 Cache Topic', subject=self.subject)
        self.questions = [Question.objects.create(
            question_text=f'W4 cache Q{i}', option_a='A', option_b='B', option_c='C', option_d='D',
            correct_answer='A', year=2022, subject=self.subject, topic=self.topic) for i in range(8)]
        self.user, self.client = self._learner('w4-dv3-cache')
        for question in self.questions[:3]:
            self._answer(self.user, question)

    @staticmethod
    def _learner(username, **extra):
        user = User.objects.create_user(username=username, password='x', **extra)
        client = APIClient()
        client.force_authenticate(user)
        return user, client

    @staticmethod
    def _answer(user, question, correct=False):
        QuestionAttempt.objects.create(user=user, question=question, selected_answer='B', is_correct=correct)
        QuestionPracticeState.objects.update_or_create(
            user=user, question=question, defaults={'confidence': 2, 'time_spent_seconds': 30})

    def _get(self, client, path):
        r = client.get(path)
        self.assertEqual(r.status_code, 200, getattr(r, 'data', None))
        return r.data

    def _totals(self, client):
        """How many answers each endpoint counts right now."""
        dash = self._get(client, DASH)
        heat = self._get(client, HEATMAP)
        return {
            'dashboard': dash['accuracy']['total'],
            'heatmap': sum(cell['n'] for cells in heat.values() for cell in cells.values()),
            'revision': sum(t['total'] for t in self._get(client, REVISION)['topics']),
            'pyq': self._get(client, PYQ)['cms']['attempted'],
            'average': self._get(client, AVERAGE)['average_seconds'] is not None,
        }

    def test_ttl_is_at_most_a_minute(self):
        self.assertLessEqual(dashboard_v3.CACHE_TTL, 60)
        with mock.patch.object(dashboard_v3.cache, 'set_many', wraps=dashboard_v3.cache.set_many) as spy:
            self._get(self.client, DASH)
        user_writes = [c for c in spy.call_args_list if any(f':{self.user.id}' in k for k in c.args[0])]
        self.assertTrue(user_writes)
        for call in user_writes:
            self.assertEqual(call.args[1], dashboard_v3.CACHE_TTL)

    def test_every_endpoint_is_cached_per_user(self):
        for path in (DASH, *SUB_ENDPOINTS):
            cache.clear()
            with self.subTest(path=path):
                with CaptureQueriesContext(connection) as first:
                    data = self._get(self.client, path)
                self.assertTrue(_answer_queries(first), path)
                with CaptureQueriesContext(connection) as second:
                    again = self._get(self.client, path)
                self.assertEqual(_answer_queries(second), [], path)
                if path == DASH:
                    self.assertEqual((data['cache'], again['cache']), ('miss', 'hit'))
                    data, again = dict(data, cache=None), dict(again, cache=None)
                self.assertEqual(again, data)
        # Another learner gets their own numbers, not a cached copy.
        other, other_client = self._learner('w4-dv3-cache-other')
        self._answer(other, self.questions[5])
        self.assertEqual(self._get(other_client, DASH)['accuracy']['total'], 1)
        self.assertEqual(self._get(self.client, DASH)['accuracy']['total'], 3)

    def test_nocache_is_ignored_for_students(self):
        self.assertEqual(self._get(self.client, DASH)['accuracy']['total'], 3)
        self._answer(self.user, self.questions[3])
        for path in (DASH, *SUB_ENDPOINTS):
            self._get(self.client, path)   # cached (sub-endpoints: filled by the dashboard miss)
        with CaptureQueriesContext(connection) as ctx:
            data = self._get(self.client, f'{DASH}?nocache=1')
            for path in SUB_ENDPOINTS:
                self._get(self.client, f'{path}?nocache=1')
        self.assertEqual(_answer_queries(ctx), [])
        self.assertEqual((data['cache'], data['accuracy']['total']), ('hit', 3))

    def test_nocache_recomputes_for_admins_and_staff(self):
        for username, extra in (('w4-dv3-admin', {'role': 'admin'}), ('w4-dv3-staff', {'is_staff': True}),
                                ('w4-dv3-super', {'is_superuser': True})):
            with self.subTest(user=username):
                user, client = self._learner(username, **extra)
                self._answer(user, self.questions[0])
                self.assertEqual(self._get(client, DASH)['accuracy']['total'], 1)
                self._get(client, REVISION)
                self._answer(user, self.questions[1])
                self.assertEqual(self._get(client, DASH)['accuracy']['total'], 1)   # cached
                fresh = self._get(client, f'{DASH}?nocache=1')
                self.assertEqual((fresh['cache'], fresh['accuracy']['total']), ('miss', 2))
                self.assertEqual(self._get(client, DASH)['accuracy']['total'], 2)   # and stored
                self.assertEqual(sum(t['total'] for t in self._get(client, f'{REVISION}?nocache=1')['topics']), 2)

    def test_a_new_answer_shows_up_within_a_minute(self):
        before = self._totals(self.client)
        self.assertEqual(before['dashboard'], 3)
        self._answer(self.user, self.questions[6])
        self.assertEqual(self._totals(self.client), before)   # still cached
        with mock.patch('time.time', return_value=time.time() + dashboard_v3.CACHE_TTL + 1):
            after = self._totals(self.client)
        self.assertEqual((after['dashboard'], after['heatmap'], after['revision'], after['pyq']),
                         (4, 4, 4, 4))

    def test_invalidate_user_cache_drops_every_entry_of_that_user(self):
        other, other_client = self._learner('w4-dv3-cache-keep')
        self._answer(other, self.questions[0])
        self.assertEqual(self._totals(self.client)['dashboard'], 3)
        self.assertEqual(self._totals(other_client)['dashboard'], 1)
        self._answer(self.user, self.questions[7])
        self._answer(other, self.questions[1])
        dashboard_v3.invalidate_user_cache(self.user.id)
        after = self._totals(self.client)
        self.assertEqual((after['dashboard'], after['heatmap'], after['revision'], after['pyq']), (4, 4, 4, 4))
        self.assertEqual(self._totals(other_client)['dashboard'], 1)   # the other user's entries stay


# ─── "Imported" reads "Expert Curated" ───────────────────────────────────


class DisplaySubjectNameTests(TestCase):
    def test_helper(self):
        for raw in ('Imported', ' imported ', 'IMPORTED'):
            self.assertEqual(public_subject_name(raw), 'Expert Curated', raw)
        for raw in ('Medicine', 'Imported Drugs', 'Expert Curated', '', None):
            self.assertEqual(public_subject_name(raw), raw, raw)

    def test_analytics_serializers_use_the_display_field(self):
        # One helper everywhere: every subject_name field of the analytics
        # serializers is the question serializers' display field.
        for serializer in (TopicPerformanceSerializer, StudyTimeBreakdownSerializer, UserQuestSerializer,
                           MistakeNotebookSerializer):
            with self.subTest(serializer=serializer.__name__):
                self.assertIsInstance(serializer().fields['subject_name'], PublicSubjectNameField)
        # Quests have no subject today: still '' -- and the display name if one is set.
        quest = UserQuest(user=User(username='w4-quest'), quest_type='study_subject', title='Study',
                          target_value=5, quest_date=timezone.localdate(), expires_at=timezone.now())
        self.assertEqual(UserQuestSerializer(quest).data['subject_name'], '')
        quest.subject = SimpleNamespace(name='Imported')
        self.assertEqual(UserQuestSerializer(quest).data['subject_name'], 'Expert Curated')


class ExpertCuratedPayloadTests(TestCase):
    """Every student-facing analytics payload naming the loader's subject."""

    def setUp(self):
        cache.clear()
        # The loader bucket, as material_importer.publishing creates it.
        self.imported = Subject.objects.create(name='Imported', code='IMPORTED')
        self.topic = Topic.objects.create(name='W4 Loader Topic', subject=self.imported)
        self.questions = [Question.objects.create(
            question_text=f'W4 loader Q{i}', option_a='A', option_b='B', option_c='C', option_d='D',
            correct_answer='A', year=2023, subject=self.imported, topic=self.topic,
            exam_source='UPSC CMS') for i in range(4)]
        self.user = User.objects.create_user(username='w4-loader-student', password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        now = timezone.now()
        for question in self.questions[:3]:
            QuestionAttempt.objects.create(user=self.user, question=question, selected_answer='B', is_correct=False)
        UserTopicPerformance.objects.create(user=self.user, subject=self.imported, topic=None,
                                            total_attempts=5, correct_answers=1, incorrect_answers=4)
        UserTopicPerformance.objects.create(user=self.user, subject=self.imported, topic=self.topic,
                                            total_attempts=5, correct_answers=1, incorrect_answers=4)
        StudyTimeBreakdown.objects.create(user=self.user, subject=self.imported, date=timezone.localdate(),
                                          seconds=600, question_count=3)
        MistakeNotebook.objects.create(user=self.user, question=self.questions[0], selected_answer='B',
                                       correct_answer='A', is_correct=False, next_review_at=now)
        test = Test.objects.create(title='W4 loader test', test_type='mixed')
        for _ in range(3):
            TestAttempt.objects.create(user=self.user, test=test, is_completed=True, completed_at=now,
                                       correct_count=1, incorrect_count=1, score=1)

    def _json(self, path, client=None):
        r = (client or self.client).get(path)
        self.assertEqual(r.status_code, 200, getattr(r, 'data', None))
        text = r.content.decode()
        self.assertNotIn('Imported', text, path)
        self.assertIn('Expert Curated', text, path)
        return r.data

    def test_student_payloads(self):
        data = self._json(DASH)
        self.assertEqual(data['weak_subjects'][0]['subject'], 'Expert Curated')
        self.assertEqual(data['weak_topics'][0]['subject'], 'Expert Curated')
        self.assertEqual(self._json('/api/analytics/dashboard/')['subject_performance'][0]['subject'],
                         'Expert Curated')
        bundle = self._json('/api/analytics/dashboard/bundle/')
        self.assertEqual(bundle['dashboard']['subject_performance'][0]['subject'], 'Expert Curated')
        prediction = self._json('/api/analytics/score-prediction/')
        self.assertEqual(prediction['subject_predictions'][0]['subject'], 'Expert Curated')
        self.assertEqual(self._json('/api/analytics/topic-performance/')[0]['subject_name'], 'Expert Curated')
        weak = self._json('/api/analytics/weak-topics/')
        self.assertEqual(weak['weak_topics'][0]['subject_name'], 'Expert Curated')
        self.assertIn('Revise from Expert Curated', weak['suggestions'][0])
        study = self._json('/api/analytics/study-time/')
        self.assertEqual(study['breakdown'][0]['subject_name'], 'Expert Curated')
        for path in ('/api/analytics/mistake-notebook/', '/api/analytics/mistake-notebook/due/'):
            self.assertEqual(self._json(path)['results'][0]['subject_name'], 'Expert Curated')
        trends = self._json('/api/analytics/pyq-trends/?exam_source=UPSC CMS')
        self.assertIn('Expert Curated', [s['name'] for s in trends['subjects']])
        self.assertIn('Expert Curated', {t['subject__name'] for t in trends['trends']})

    def test_admin_weak_area_control(self):
        admin = User.objects.create_user(username='w4-loader-admin', password='x', role='admin')
        client = APIClient()
        client.force_authenticate(admin)
        data = self._json(f'/api/analytics/admin/weak-area-control/?user_id={self.user.id}', client)
        for key in ('most_difficult_topics', 'cohort_weak_areas', 'student_weak_areas'):
            self.assertEqual({row['subject__name'] for row in data[key]}, {'Expert Curated'}, key)
        self.assertIn('in Expert Curated', data['revision_recommendations'][0])

    def test_other_subjects_keep_their_names(self):
        medicine = Subject.objects.create(name='W4 Real Medicine', code='W4RMED')
        StudyTimeBreakdown.objects.create(user=self.user, subject=medicine, date=timezone.localdate(),
                                          seconds=60, question_count=1)
        names = {row['subject_name'] for row in self._json('/api/analytics/study-time/')['breakdown']}
        self.assertEqual(names, {'Expert Curated', 'W4 Real Medicine'})


# ─── Mistake Notebook: answer labels in the stem / options ───────────────


NOTEBOOK_TEXT_FIELDS = ('question_text', 'option_a', 'option_b', 'option_c', 'option_d')


class MistakeNotebookLabelRedactionTests(TestCase):
    """A locked notebook row's stem and options are cut at their first answer
    / explanation label. MistakeNotebookOptionFlagTests runs these scenarios
    again on options that carry correctness flags."""
    # The stored question text.
    TEXT = {
        'question_text': 'W4 Which drug is first line in type 2 diabetes?\n\nExplanation: W4SECRET metformin lowers glucose.',
        'option_a': 'Metformin', 'option_b': 'Glipizide', 'option_c': 'Acarbose',
        'option_d': 'Insulin Correct Answer: A. Metformin',
    }
    KEY = 'A'
    # What a viewer who may not see the answer gets.
    LOCKED_TEXT = {
        'question_text': 'W4 Which drug is first line in type 2 diabetes?',
        'option_a': 'Metformin', 'option_b': 'Glipizide', 'option_c': 'Acarbose', 'option_d': 'Insulin',
    }
    # Never in a locked row.
    GONE = ('W4SECRET', 'Correct Answer')

    def setUp(self):
        subject = Subject.objects.create(name='W4 Leaky', code='W4LEAK')

        def leaky(**kw):
            return Question.objects.create(**self.TEXT, correct_answer=self.KEY,
                                           explanation='W4 key explanation', year=2024, subject=subject, **kw)

        self.locked = leaky()
        self.showcase = leaky()
        self.scholarship = leaky(is_scholarship_eligible=True)
        FreeShowcaseQuestion.objects.create(question=self.showcase, year=2024, position=0)
        # An admin also showcased a scholarship question: it stays locked.
        FreeShowcaseQuestion.objects.create(question=self.scholarship, year=2024, position=1)
        self.client = APIClient()

    def _login(self, username, premium=False, **extra):
        user = User.objects.create_user(username=username, password='x', **extra)
        if premium:
            Subscription.objects.create(user=user, plan='1_year', status='active',
                                        expires_at=timezone.now() + timedelta(days=30))
        for question in (self.locked, self.showcase, self.scholarship):
            QuestionAttempt.objects.create(user=user, question=question, selected_answer='D', is_correct=False)
            MistakeNotebook.objects.create(user=user, question=question, selected_answer='D', correct_answer='A',
                                           is_correct=False, next_review_at=timezone.now())
        self.client.force_authenticate(user)
        return user

    def _rows(self, path):
        r = self.client.get(path)
        self.assertEqual(r.status_code, 200, getattr(r, 'data', None))
        return {row['question']: row for row in r.data['results']}

    def _assert_cut(self, row):
        self.assertEqual({name: row[name] for name in NOTEBOOK_TEXT_FIELDS}, self.LOCKED_TEXT)
        self.assertEqual((row['correct_answer'], row['explanation'], row['answer_locked']), ('', '', True))
        for text in self.GONE:
            self.assertNotIn(text, str(row))

    def _assert_full(self, row):
        self.assertEqual({name: row[name] for name in NOTEBOOK_TEXT_FIELDS}, self.TEXT)
        self.assertFalse(row['answer_locked'])

    def test_free_user_locked_rows_are_cut_everywhere(self):
        user = self._login('w4-leak-free')
        for path in ('/api/analytics/mistake-notebook/', '/api/analytics/mistake-notebook/due/',
                     '/api/analytics/mistake-notebook/?due=true'):
            rows = self._rows(path)
            self._assert_cut(rows[self.locked.id])
            self._assert_cut(rows[self.scholarship.id])
            self._assert_full(rows[self.showcase.id])   # a free question: nothing to hide
        entry = MistakeNotebook.objects.get(user=user, question=self.locked)
        r = self.client.patch(f'/api/analytics/mistake-notebook/{entry.id}/', {'user_note': 'why'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self._assert_cut(r.data)
        r = self.client.post(f'/api/analytics/mistake-notebook/{entry.id}/review/')
        self.assertEqual(r.status_code, 200, r.data)
        self._assert_cut(r.data)
        r = self.client.post('/api/analytics/mistake-notebook/', {'question': self.scholarship.id,
                                                                   'is_flagged': True}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self._assert_cut(r.data)
        # The stored question is untouched.
        self.locked.refresh_from_db()
        self.assertEqual({name: getattr(self.locked, name) for name in NOTEBOOK_TEXT_FIELDS}, self.TEXT)

    def test_premium_admin_and_staff_keep_the_full_text(self):
        for username, premium, extra in (('w4-leak-premium', True, {}), ('w4-leak-admin', False, {'role': 'admin'}),
                                         ('w4-leak-staff', False, {'is_staff': True})):
            with self.subTest(user=username):
                self._login(username, premium=premium, **extra)
                rows = self._rows('/api/analytics/mistake-notebook/')
                for question in (self.locked, self.showcase, self.scholarship):
                    self._assert_full(rows[question.id])
                    self.assertEqual(rows[question.id]['correct_answer'], self.KEY)

    def test_same_text_as_the_locked_test_review_row(self):
        """A locked question reads the same in the notebook as in the /review/
        of a test scored before the free-plan rule (one redaction helper)."""
        user = self._login('w4-leak-review-free')
        test = Test.objects.create(title='W4 legacy test', test_type='mixed')
        test.questions.add(self.locked)
        attempt = TestAttempt.objects.create(user=user, test=test, is_completed=True, completed_at=timezone.now())
        QuestionResponse.objects.create(attempt=attempt, question=self.locked, selected_answer='D', is_correct=False)
        r = self.client.get(f'/api/tests/{test.id}/review/', {'attempt_id': attempt.id})
        self.assertEqual(r.status_code, 200, getattr(r, 'data', None))
        review = next(row for row in r.data['questions'] if row['question_id'] == self.locked.id)
        note = self._rows('/api/analytics/mistake-notebook/')[self.locked.id]
        self._assert_cut(note)
        self.assertTrue(review['answer_locked'])
        self.assertEqual(
            (review['question_text'], review['options']),
            (note['question_text'], {letter: note[f'option_{letter.lower()}'] for letter in 'ABCD'}),
        )


class MistakeNotebookOptionFlagTests(MistakeNotebookLabelRedactionTests):
    """Wave 4b: a locked row's options also lose correctness flags --
    "(correct)", "[Correct answer]", "(Ans)", "(wrong)", ticks and crosses.
    They name no letter, so redact_public_text kept them: a free user's
    notebook read "Adrenaline (correct)" next to answer_locked true. The
    notebook now applies the redaction of a locked test-review row
    (tests_engine.entitlement). The inherited tests run every path (list,
    due/, ?due=true, PATCH, review, POST) on these options; a free showcase
    row, premium, admin and staff keep the flags."""
    TEXT = {
        'question_text': 'W4F Which drug is first line in anaphylaxis?',
        # One flag kind per option (a real paper flags one option).
        'option_a': 'Noradrenaline (wrong) ✗',
        'option_b': 'Adrenaline (correct)',
        'option_c': 'Dopamine [Correct answer]',
        'option_d': 'Dobutamine (Ans) ✔',
    }
    KEY = 'B'
    LOCKED_TEXT = {
        'question_text': 'W4F Which drug is first line in anaphylaxis?',
        'option_a': 'Noradrenaline', 'option_b': 'Adrenaline', 'option_c': 'Dopamine', 'option_d': 'Dobutamine',
    }
    GONE = ('(correct)', 'Correct answer', '(wrong)', '(Ans)', '✔', '✗')

    def test_ordinary_option_wording_is_kept(self):
        """Not flags: "(right)" (a side), "Statement II is correct", "R is
        the correct explanation of A". A locked row keeps them."""
        plain = {
            'option_a': 'Both statements are correct', 'option_b': 'Statement II is correct',
            'option_c': 'A is true and R is the correct explanation of A',
            'option_d': '(right) ventricular hypertrophy',
        }
        Question.objects.filter(pk=self.locked.pk).update(**plain)
        self._login('w4f-plain-free')
        row = self._rows('/api/analytics/mistake-notebook/')[self.locked.id]
        self.assertEqual({name: row[name] for name in plain}, plain)
        self.assertEqual((row['correct_answer'], row['answer_locked']), ('', True))
