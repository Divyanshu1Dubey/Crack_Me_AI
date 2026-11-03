"""Unit tests for question editorial workflows and endpoints (2026-11)."""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from questions.editorial import (
    change_answer_key,
    compute_explanation_status,
    save_explanation,
    unverify_question,
    verify_question,
)
from questions.explain_option import explain_selected_option
from questions.models import AnswerKeyChange, ExplanationSuggestion, Question, Subject

User = get_user_model()


class EditorialWorkflowTestCase(TestCase):
    def setUp(self):
        self.subject = Subject.objects.create(name="Internal Medicine", code="MED")
        self.admin = User.objects.create_superuser(
            username="admin_editor",
            email="admin@cracklabs.test",
            password="testpassword123",
        )
        self.student = User.objects.create_user(
            username="student_user",
            email="student@cracklabs.test",
            password="testpassword123",
        )
        self.question = Question.objects.create(
            question_text="A 45-year-old male presents with acute chest pain.",
            option_a="Aortic dissection",
            option_b="Acute myocardial infarction",
            option_c="Pneumothorax",
            option_d="Pulmonary embolism",
            correct_answer="A",
            subject=self.subject,
            year=2024,
            explanation="Initial explanation for option A.",
        )
        self.client = APIClient()

    def test_change_answer_key_success_and_immutability(self):
        old_key = self.question.correct_answer
        with self.captureOnCommitCallbacks(execute=True):
            change = change_answer_key(
                self.question,
                new_key="B",
                actor=self.admin,
                reason="ECG confirms STEMI; standard clinical protocol indicates AMI.",
                source="editor_test",
            )
        self.question.refresh_from_db()
        self.assertEqual(self.question.correct_answer, "B")
        # The audit re-classifies on commit: a staff change that cites no evidence is not "verified".
        self.assertEqual(self.question.answer_key_status, "likely_correct")
        self.assertEqual(change.old_key, "A")
        self.assertEqual(change.new_key, "B")
        self.assertEqual(change.changed_by, self.admin)
        self.assertEqual(change.explanation_action, "kept_stale")

        # Immutability check: modifying change record raises ValueError
        change.old_key = "C"
        with self.assertRaises(ValueError):
            change.save()

    def test_change_answer_key_validation(self):
        # Invalid key
        with self.assertRaises(ValidationError):
            change_answer_key(self.question, "Z", actor=self.admin, reason="Valid reason here")

        # Reason too short (< 10 chars)
        with self.assertRaises(ValidationError):
            change_answer_key(self.question, "B", actor=self.admin, reason="short")

        # Unchanged key
        with self.assertRaises(ValidationError):
            change_answer_key(self.question, "A", actor=self.admin, reason="Valid reason here")

    def test_explain_selected_option(self):
        suggestion = explain_selected_option(
            self.question,
            selected="B",
            actor=self.admin,
        )
        self.assertIsInstance(suggestion, ExplanationSuggestion)
        self.assertEqual(suggestion.for_key, "B")
        self.assertIn(suggestion.status, ["ok", "conflict", "insufficient_evidence", "image_context_missing"])

    def test_api_change_key_endpoint_permissions(self):
        url = f"/api/questions/{self.question.id}/change-key/"

        # Anonymous -> 401
        res = self.client.post(url, {"new_key": "B", "reason": "Reason with more than ten characters"})
        self.assertIn(res.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

        # Student -> 403
        self.client.force_authenticate(user=self.student)
        res = self.client.post(url, {"new_key": "B", "reason": "Reason with more than ten characters"})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # Admin -> 200
        self.client.force_authenticate(user=self.admin)
        res = self.client.post(url, {"new_key": "B", "reason": "Verified against textbook reference."})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["new_key"], "B")

    def test_api_explain_option_endpoint(self):
        self.client.force_authenticate(user=self.admin)
        url = f"/api/questions/{self.question.id}/explain-option/"
        res = self.client.post(url, {"selected": "B"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["for_key"], "B")

    def test_api_key_history_endpoint(self):
        self.client.force_authenticate(user=self.admin)
        change_answer_key(
            self.question,
            "B",
            actor=self.admin,
            reason="Verified against textbook reference.",
        )
        url = f"/api/questions/{self.question.id}/key-history/"
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["changes"]), 1)
        self.assertEqual(res.data["changes"][0]["new_key"], "B")
