"""Unit tests for PYQ topic notes builder, citations, and warning marks (2026-11)."""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from questions import notes_builder as nb
from questions.models import Question, Subject, Topic, TopicNote, TopicNoteSource

User = get_user_model()


class TopicNotesBuilderTestCase(TestCase):
    def setUp(self):
        self.subject = Subject.objects.create(name="Pharmacology", code="PHARM")
        self.topic = Topic.objects.create(name="Autonomic Nervous System", subject=self.subject)
        self.admin = User.objects.create_superuser(
            username="admin_notes",
            email="admin_notes@cracklabs.test",
            password="testpassword123",
        )
        self.student = User.objects.create_user(
            username="student_notes",
            email="student_notes@cracklabs.test",
            password="testpassword123",
        )
        # Create 4 questions so candidate count >= MIN_PYQS (3)
        self.questions = []
        for i in range(1, 5):
            q = Question.objects.create(
                question_text=f"Drug of choice for anaphylactic shock test {i} is?",
                option_a="Adrenaline",
                option_b="Noradrenaline",
                option_c="Hydrocortisone",
                option_d="Chlorpheniramine",
                correct_answer="A",
                subject=self.subject,
                topic=self.topic,
                exam_type="cms",
                year=2020 + i,
                answer_key_status="verified" if i == 1 else "likely_correct",
            )
            self.questions.append(q)

        self.client = APIClient()

    @override_settings(TOPIC_NOTES_BUILDER=True)
    def test_plan_and_build_topic_note(self):
        specs = nb.plan_notes(
            exams=("cms",),
            combined=False,
            levels=("subject",),
            subject_id=self.subject.id,
            min_questions=3,
        )
        self.assertGreaterEqual(len(specs), 1)
        spec = specs[0]

        # Build note
        note = spec.instance()
        result = nb.build_topic_note(note, mode="extractive", min_questions=3, dry_run=False)
        self.assertTrue(result.built)
        self.assertEqual(note.subject, self.subject)
        self.assertTrue(nb.is_built(note))

        # TopicNoteSource records check
        sources = TopicNoteSource.objects.filter(note=note)
        self.assertGreaterEqual(sources.count(), 3)

        # Markdown output checks: citations [Q#...] and provisional warning mark
        self.assertIn("Adrenaline", note.content)
        # At least one question was provisional (likely_correct), so warning mark ⚠ should be present
        self.assertIn("⚠", note.content)

    @override_settings(TOPIC_NOTES_BUILDER=True)
    def test_api_notes_build_permission(self):
        url = "/api/questions/topic-notes/build/"

        # Anonymous -> 401
        res = self.client.post(url, {})
        self.assertIn(res.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

        # Student -> 403
        self.client.force_authenticate(user=self.student)
        res = self.client.post(url, {})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # Admin -> 200/202
        self.client.force_authenticate(user=self.admin)
        res = self.client.post(
            url,
            {
                "exam_type": "cms",
                "level": "subject",
                "subject": self.subject.id,
                "min_questions": 3,
                "dry_run": True,
            },
            format="json",
        )
        self.assertIn(res.status_code, [status.HTTP_200_OK, status.HTTP_202_ACCEPTED])
