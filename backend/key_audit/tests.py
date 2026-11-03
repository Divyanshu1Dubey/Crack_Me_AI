"""Tests for the key_audit app: auditing, signals, priority, and review queue APIs."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from key_audit.models import AuditResolution, QuestionAudit, ReviewClaim
from key_audit.services import audit_question
from questions.models import AnswerKeyChange, Question, Subject

User = get_user_model()


class KeyAuditTestCase(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="audit_admin",
            email="admin@audit.test",
            password="adminpassword123",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)
        self.subject = Subject.objects.create(name="Medicine", code="MED")

        self.q_good = Question.objects.create(
            subject=self.subject,
            question_text="What is the first line treatment for anaphylaxis?",
            option_a="Epinephrine",
            option_b="Hydrocortisone",
            option_c="Chlorpheniramine",
            option_d="Salbutamol",
            correct_answer="A",
            explanation="Intramuscular adrenaline (epinephrine) is the drug of choice in anaphylaxis.",
            exam_type="upsc_cms",
            year=2024,
            is_active=True,
        )

        self.q_conflict = Question.objects.create(
            subject=self.subject,
            question_text="What is the primary treatment for Wilson disease?",
            option_a="D-Penicillamine",
            option_b="Zinc acetate",
            option_c="Trientine",
            option_d="Deferoxamine",
            correct_answer="D",  # Incorrect stored key
            explanation="Option A is correct because D-Penicillamine is the initial chelating agent of choice.",
            exam_type="upsc_cms",
            year=2023,
            is_active=True,
        )

    def test_audit_question_detects_explanation_conflict(self):
        audit = audit_question(self.q_conflict)
        self.assertEqual(audit.status, "needs_review")
        self.assertEqual(audit.status_reason, "explanation_states_other")
        self.assertEqual(audit.suggested_key, "A")
        self.assertGreaterEqual(audit.priority, 95.0)

        # Good question should be likely_correct with low priority
        audit_good = audit_question(self.q_good)
        self.assertEqual(audit_good.status, "likely_correct")
        self.assertEqual(audit_good.priority, 0.0)

    def test_review_queue_list_api(self):
        audit_question(self.q_conflict)
        audit_question(self.q_good)

        url = reverse("key_audit:queue-list")
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(res.data["count"], 1)
        # Highest priority should be first
        self.assertEqual(res.data["results"][0]["question_id"], self.q_conflict.id)

    def test_review_queue_resolve_key_changed(self):
        audit_question(self.q_conflict)

        resolve_url = reverse("key_audit:queue-resolve", kwargs={"question_id": self.q_conflict.id})
        payload = {
            "resolution": "key_changed",
            "new_key": "A",
            "reason": "Verified against textbook: D-Penicillamine is initial chelating agent.",
            "evidence": [{"kind": "textbook", "title": "Harrison 22e", "page": 2400}],
        }
        res = self.client.post(resolve_url, data=payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.q_conflict.refresh_from_db()
        self.assertEqual(self.q_conflict.correct_answer, "A")
        self.assertEqual(self.q_conflict.answer_key_status, "verified")

        # Verify AnswerKeyChange created
        key_change = AnswerKeyChange.objects.filter(question=self.q_conflict).first()
        self.assertIsNotNone(key_change)
        self.assertEqual(key_change.old_key, "D")
        self.assertEqual(key_change.new_key, "A")
        self.assertEqual(key_change.source, "review_queue")

        # Verify AuditResolution created
        resolution = AuditResolution.objects.filter(question=self.q_conflict).first()
        self.assertIsNotNone(resolution)
        self.assertEqual(resolution.resolution, "key_changed")

