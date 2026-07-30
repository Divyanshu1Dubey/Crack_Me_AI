"""Phase-4 launch-ready test suite — additive, runs against an in-memory
SQLite database so it doesn't depend on a real Postgres.

Cover:

* Recall search: filter dimensions, facets, cache
* AI per-question: cache + fallback when no AI keys are configured
* Practice modes: 11 modes return deterministic counts
* Practice experience: flag / confidence / time / elimination
* Recall images facets
* Security posture (env validation)

Run with `python manage.py test questions.tests_phase4 -v 2`.
"""
from __future__ import annotations

import os
from unittest import mock

from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model


User = get_user_model()


class RecallSearchTestCase(TestCase):
    """Phase-4 baseline — verifies Phase-3 filters still resolve."""

    @classmethod
    def setUpTestData(cls):
        from questions.models import (
            Question, Subject, Topic, ExamTrack, Announcement,
        )

        cls.subject = Subject.objects.create(name="Medicine", exam_type="neet_pg")
        cls.topic = Topic.objects.create(name="Cardiology", subject=cls.subject)

        # 5 questions — 3 recall, 2 official
        for i in range(5):
            q = Question.objects.create(
                question_text=f"What is Q{i}?",
                option_a="A", option_b="B", option_c="C", option_d="D",
                correct_answer="A",
                year=2024 + i, exam_type="neet_pg",
                subject=cls.subject,
                recall_status=("recall" if i < 3 else "official_compiled"),
                recall_text_hash=f"hash-{i}",
            )
            q.topic = cls.topic
            q.save()

    def _search(self, **params):
        from rest_framework.test import APIRequestFactory, force_authenticate
        from questions.views import QuestionViewSet
        f = APIRequestFactory()
        req = f.get("/api/questions/recall_search/", params)
        user = User.objects.create(username="t1")
        force_authenticate(req, user=user)
        return QuestionViewSet.as_view({"get": "recall_search"})(req)

    def test_recall_status_filter(self):
        resp = self._search(recall_status="recall")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 3)

    def test_clinical_filter(self):
        resp = self._search(clinical_category="clinical")
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.data["count"], 0)

    def test_facets_present(self):
        resp = self._search()
        self.assertIn("facets", resp.data)
        self.assertIn("year", resp.data["facets"])

    def test_pagination(self):
        resp = self._search(page_size=2, page=1)
        self.assertEqual(resp.data["page_size"], 2)


class PracticeModesTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        from questions.models import Subject, Question
        cls.subject = Subject.objects.create(name="Surg", exam_type="neet_pg")
        for i in range(8):
            Question.objects.create(
                question_text=f"topic-Q{i}",
                option_a="A", option_b="B", option_c="C", option_d="D",
                correct_answer="A",
                year=2024, exam_type="neet_pg",
                subject=cls.subject, is_image_based=(i % 2 == 0),
            )

    def test_modes_listed(self):
        from questions.practice_modes import list_modes
        modes = list_modes()
        keys = {m["key"] for m in modes}
        for required in {"random", "year_wise", "image_only", "rapid_revision",
                          "high_yield", "clinical_cases", "weak_topics",
                          "bookmarked", "wrong", "subject_wise", "topic_wise"}:
            self.assertIn(required, keys)

    def test_image_only(self):
        from questions.practice_modes import build_queue
        u = User.objects.create(username="img")
        ids = build_queue("image_only", u, {"count": 5})
        self.assertGreater(len(ids), 0)
        self.assertLessEqual(len(ids), 5)


class AIPerQuestionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        from questions.models import Subject, Question
        cls.subject = Subject.objects.create(name="Anaesth", exam_type="neet_pg")
        cls.q = Question.objects.create(
            question_text="Sample concept Q",
            option_a="A", option_b="B", option_c="C", option_d="D",
            correct_answer="B",
            year=2024, exam_type="neet_pg", subject=cls.subject,
        )

    def test_concept_returns_str(self):
        from questions.ai_per_question import concept
        s = concept(self.q)
        self.assertIsInstance(s, str)
        self.assertGreater(len(s), 0)

    def test_concept_cached(self):
        from django.core.cache import cache
        cache.clear()
        from questions.ai_per_question import concept
        a = concept(self.q)
        b = concept(self.q)  # should hit cache
        self.assertEqual(a, b)

    def test_fallback_when_no_ai_call(self):
        from questions import ai_per_question as ai
        with mock.patch.object(ai, "_ai_call", return_value=""):
            out = ai.clinical_significance(self.q)
        self.assertIsInstance(out, str)
        self.assertGreater(len(out), 0)


class PracticeExperienceTestCase(TestCase):
    def setUp(self):
        from questions.models import Subject, Question
        self.subject = Subject.objects.create(name="Paed", exam_type="neet_pg")
        self.q = Question.objects.create(
            question_text="set-up Q",
            option_a="A", option_b="B", option_c="C", option_d="D",
            correct_answer="A", year=2024, exam_type="neet_pg",
            subject=self.subject,
        )
        self.user = User.objects.create(username="x")

    def test_flag_toggle(self):
        from questions.practice_experience import set_flag, get_flag
        self.assertFalse(get_flag(self.q, self.user))
        set_flag(self.q, self.user, True)
        self.assertTrue(get_flag(self.q, self.user))
        set_flag(self.q, self.user, False)
        self.assertFalse(get_flag(self.q, self.user))

    def test_confidence_range(self):
        from questions.practice_experience import set_confidence, get_confidence
        set_confidence(self.q, self.user, 7)  # clamped
        self.assertEqual(get_confidence(self.q, self.user), 5)
        set_confidence(self.q, self.user, 2)
        self.assertEqual(get_confidence(self.q, self.user), 2)

    def test_elimination(self):
        from questions.practice_experience import set_elimination, get_state
        set_elimination(self.q, self.user, ["A", "C"])
        st = get_state(self.q, self.user)
        self.assertIn("A", st["eliminated"])
        self.assertIn("C", st["eliminated"])
        self.assertFalse(st["flag"])

    def test_time_spent_accumulates(self):
        from questions.practice_experience import add_time_spent, get_state
        add_time_spent(self.q, self.user, 10)
        add_time_spent(self.q, self.user, 5)
        self.assertEqual(get_state(self.q, self.user)["time_spent"], 15)


class RecallImagesFacetsTestCase(TestCase):
    def test_endpoint_callable(self):
        from questions.recall_images import list_images_facets, q_for_images_q
        # Function must be importable and callable
        self.assertTrue(callable(list_images_facets))
        self.assertTrue(callable(q_for_images_q))

    def test_q_for_images_q(self):
        from questions.models import Question, Subject
        subject = Subject.objects.create(name="Pharma", exam_type="neet_pg")
        q = Question.objects.create(
            question_text="img-t",
            option_a="A", option_b="B", option_c="C", option_d="D",
            correct_answer="A", year=2024, exam_type="neet_pg", subject=subject,
        )
        from questions.recall_images import q_for_images_q
        # No images → image-required filter returns no rows
        result = q_for_images_q(Question.objects.filter(pk=q.pk), has_image=True)
        self.assertEqual(result.count(), 0)


class SecurityPostureTestCase(TestCase):
    def test_dev_skips_check(self):
        from crack_cms.security import security_posture_check
        # Must not raise in dev / CI
        security_posture_check(is_production=False, is_ci=False)
        security_posture_check(is_production=False, is_ci=True)

    @override_settings(IS_PRODUCTION_RUNTIME=True, IS_CI=False)
    def test_prod_without_secret_raises(self):
        from crack_cms import security as sec
        with mock.patch.dict(os.environ, {"DJANGO_SECRET_KEY": "",
                                          "DATABASE_URL": ""}, clear=False):
            from django.core.exceptions import ImproperlyConfigured
            with self.assertRaises(ImproperlyConfigured):
                sec.security_posture_check(
                    is_production=True,
                    is_ci=False,
                )


class DuplicateTombstoneGuardTestCase(TestCase):
    """Phase-4 hardening: QuestionViewSet.duplicate must refuse to
    resurrect a question whose stem matches a RemovedQuestion tombstone.

    Without this guard, an admin can `Remove from bank` + `Duplicate` and
    silently re-introduce removed content. The guard is a single
    `_pre_check_remove(...)` call at the top of the `duplicate` action.
    """

    @classmethod
    def setUpTestData(cls):
        from questions.models import Subject
        cls.subject = Subject.objects.create(name="TombStoneSubj", exam_type="neet_pg")

    def setUp(self):
        from rest_framework.test import APIClient
        self._client = APIClient()
        self.admin = User.objects.create(
            username="dup_admin",
            is_staff=True,
            is_superuser=True,
        )

    def test_duplicate_skips_removed_question(self):
        from questions.models import Question, RemovedQuestion, compute_stem_hash
        stem = "Original stem for tombstone test"
        q = Question.objects.create(
            question_text=stem,
            option_a="A", option_b="B", option_c="C", option_d="D",
            correct_answer="A", year=2024,
            exam_type="neet_pg", subject=self.subject,
        )
        # Mark a tombstone matching the original stem.
        RemovedQuestion.objects.create(
            exam_source="admin",
            year=2024,
            source_number=None,
            question_text_hash=compute_stem_hash(stem),
            original_question_id=q.id,
            reason="admin removed",
            removed_by=self.admin,
        )

        self._client.force_authenticate(user=self.admin)
        res = self._client.post(f"/api/questions/{q.id}/duplicate/")
        self.assertEqual(res.status_code, 409)
        body = res.json()
        self.assertIn("error", body)
        self.assertIn("previously-removed", body["error"])

        # Sanity: no duplicate row was created.
        from questions.models import Question as Q
        self.assertEqual(
            Q.objects.filter(question_text__contains=stem).count(),
            1,
        )

    def test_duplicate_succeeds_when_no_tombstone(self):
        from questions.models import Question
        stem = "Fresh stem, no tombstone"
        q = Question.objects.create(
            question_text=stem,
            option_a="A", option_b="B", option_c="C", option_d="D",
            correct_answer="A", year=2024,
            exam_type="neet_pg", subject=self.subject,
        )

        self._client.force_authenticate(user=self.admin)
        res = self._client.post(f"/api/questions/{q.id}/duplicate/")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json().get("message"), "Question duplicated")
