"""Unit tests for evidence tracking, access control, and student citations (2026-11)."""
import hashlib
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from evidence.models import EvidenceSource, QuestionEvidence
from evidence.services import citation_label, review, student_citations
from questions.models import Question, Subject

User = get_user_model()


class EvidenceServicesTestCase(TestCase):
    def setUp(self):
        self.subject = Subject.objects.create(name="Pediatrics", code="PED")
        self.admin = User.objects.create_superuser(
            username="admin_evidence",
            email="admin_ev@cracklabs.test",
            password="testpassword123",
        )
        self.student = User.objects.create_user(
            username="student_evidence",
            email="student_ev@cracklabs.test",
            password="testpassword123",
        )
        self.question = Question.objects.create(
            question_text="Most common cause of congenital stridor in an infant is?",
            option_a="Laryngomalacia",
            option_b="Subglottic stenosis",
            option_c="Vocal cord palsy",
            option_d="Laryngeal web",
            correct_answer="A",
            subject=self.subject,
            year=2023,
        )
        self.source = EvidenceSource.objects.create(
            sha256="a" * 64,
            title="Nelson Textbook of Pediatrics",
            edition="21st",
            year=2020,
            tier=3,
            kind="textbook",
            student_display="snippet",
        )
        self.client = APIClient()

    def test_record_and_review_evidence(self):
        snippet_text = "Laryngomalacia is the most common congenital anomaly of the larynx and the most frequent cause of congenital stridor."
        ev = QuestionEvidence.objects.create(
            question=self.question,
            source=self.source,
            page_start=1450,
            page_end=1450,
            page_label="1450",
            snippet=snippet_text,
            snippet_sha1=hashlib.sha1(snippet_text.encode()).hexdigest(),
            option_letter="A",
            stance="supports",
            origin="admin_manual",
            review_status="pending",
            key_at_creation="A",
            content_sha256="fake_stem_hash",
            created_by=self.admin,
        )

        # Before review: pending, not visible to students
        citations_before = student_citations(self.question, revealed=True)
        self.assertEqual(len(citations_before), 0)

        # Admin reviews and accepts
        review(ev, actor=self.admin, status="accepted", student_visible=True)
        ev.refresh_from_db()
        self.assertEqual(ev.review_status, "accepted")
        self.assertTrue(ev.student_visible)

        # After review: visible to students as citation
        citations_after = student_citations(self.question, revealed=True)
        self.assertEqual(len(citations_after), 1)
        c = citations_after[0]
        self.assertEqual(c["option_letter"], "A")
        self.assertIn("Nelson Textbook of Pediatrics", c["citation"])
        self.assertIn("Laryngomalacia is the most common congenital anomaly", c["snippet"])
        # Protect copyright: no raw file paths or sha256 leaked to student
        self.assertNotIn("sha256", c)
        self.assertNotIn("path", c)

    def test_evidence_page_permissions(self):
        url = f"/api/evidence/pages/{self.source.sha256}/1450/image.png"

        # Anonymous -> 401
        res = self.client.get(url)
        self.assertIn(res.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

        # Student -> 403 Forbidden (Ground rule: students never see full copyrighted pages)
        self.client.force_authenticate(user=self.student)
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # Admin -> Allowed access check
        self.client.force_authenticate(user=self.admin)
        res = self.client.get(url)
        # Returns 404 if physical PDF not mounted on disk, but passes permission check (not 403)
        self.assertNotEqual(res.status_code, status.HTTP_403_FORBIDDEN)
