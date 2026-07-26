"""Tests for the admin QuestionImage upload/CRUD endpoints."""
import io
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from questions.models import Question, Subject, QuestionImage


def _make_png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color="red").save(buf, format="PNG")
    return buf.getvalue()


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class QuestionImageUploadTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="pw"
        )
        cls.regular = User.objects.create_user(
            username="user", email="user@example.com", password="pw"
        )
        cls.subject = Subject.objects.create(name="Medicine", code="MED")
        cls.question = Question.objects.create(
            question_text="What?",
            option_a="A",
            option_b="B",
            option_c="C",
            option_d="D",
            correct_answer="A",
            year=2025,
            subject=cls.subject,
        )

    def test_upload_requires_admin(self):
        self.client.force_authenticate(self.regular)
        file = SimpleUploadedFile("x.png", _make_png_bytes(), content_type="image/png")
        resp = self.client.post(
            "/api/questions/images/",
            data={"question_id": self.question.id, "file": file},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    @patch("questions.views.upload_image_to_supabase")
    def test_upload_happy_path(self, mock_upload):
        def _fake_upload(*, file_obj, question_id, content_type, original_filename):
            row = QuestionImage.objects.create(
                question_id=question_id,
                page_number=0,
                image_index_in_page=0,
                file="",
                mime=content_type,
                width=10,
                height=10,
                bytes=100,
                sha256="a" * 64,
                sha256_short="a" * 16,
                modality="other",
                uploaded_by_admin=True,
                url="https://example.com/x.png",
            )
            return type(
                "U", (), {
                    "id": row.id, "url": row.url, "sha256": row.sha256,
                    "sha256_short": row.sha256_short, "width": row.width,
                    "height": row.height, "bytes": row.bytes, "mime": row.mime,
                }
            )()

        mock_upload.side_effect = _fake_upload
        self.client.force_authenticate(self.admin)
        file = SimpleUploadedFile("x.png", _make_png_bytes(), content_type="image/png")
        resp = self.client.post(
            "/api/questions/images/",
            data={"question_id": self.question.id, "file": file},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(QuestionImage.objects.filter(uploaded_by_admin=True).exists())

    def test_rejects_oversize_file(self):
        self.client.force_authenticate(self.admin)
        big = SimpleUploadedFile("x.png", b"0" * (6 * 1024 * 1024), content_type="image/png")
        resp = self.client.post(
            "/api/questions/images/",
            data={"question_id": self.question.id, "file": big},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_bad_mime(self):
        self.client.force_authenticate(self.admin)
        bad = SimpleUploadedFile("x.txt", b"hello", content_type="text/plain")
        resp = self.client.post(
            "/api/questions/images/",
            data={"question_id": self.question.id, "file": bad},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)