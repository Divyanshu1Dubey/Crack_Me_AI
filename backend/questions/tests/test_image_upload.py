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
        def _fake_upload(*, file_obj, question_id, content_type, original_filename, role=None):
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
                role=role or "illustration",
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

    @patch("questions.views.upload_image_to_supabase")
    def test_upload_persists_role_from_form(self, mock_upload):
        """Bug 2026-08-01: admin editor uploads from the explanation
        field must persist `role='explanation'` so the stem pane stops
        showing the figure before the student attempts the question.
        Previously the form ignored the role and the row defaulted to
        'illustration'."""
        captured: dict = {}

        def _fake_upload(*, file_obj, question_id, content_type, original_filename, role=None):
            captured["role"] = role
            row = QuestionImage.objects.create(
                question_id=question_id,
                page_number=0,
                image_index_in_page=0,
                file="",
                mime=content_type,
                width=10,
                height=10,
                bytes=100,
                sha256="b" * 64,
                sha256_short="b" * 16,
                modality="other",
                role=role or "illustration",
                uploaded_by_admin=True,
                url="https://example.com/expl.png",
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
            data={"question_id": self.question.id, "file": file, "role": "explanation"},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(captured["role"], "explanation")
        self.assertEqual(
            QuestionImage.objects.get(uploaded_by_admin=True).role,
            "explanation",
        )

    @patch("questions.views.upload_image_to_supabase")
    def test_upload_rejects_invalid_role(self, mock_upload):
        """The upload endpoint must reject unknown role values so a
        typo in the admin editor can't create unfilterable rows."""
        def _fake_upload(*, file_obj, question_id, content_type, original_filename, role=None):
            raise AssertionError("upload_image_to_supabase must not be called for invalid role")

        mock_upload.side_effect = _fake_upload
        self.client.force_authenticate(self.admin)
        file = SimpleUploadedFile("x.png", _make_png_bytes(), content_type="image/png")
        resp = self.client.post(
            "/api/questions/images/",
            data={"question_id": self.question.id, "file": file, "role": "nope"},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("role", resp.json()["detail"].lower())

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

    def test_stem_images_filter_explanation_role(self):
        """Bug 2026-08-01: the detail serializer's `stem_images` getter
        must exclude `role='explanation'` so admin-uploaded explanation
        figures stop appearing in the bank detail pane before the
        student attempts the question. `images` (the full list) is
        kept unchanged so `[[img:N]]` tokens still resolve."""
        from questions.serializers import QuestionDetailSerializer

        # One legitimate stem image.
        QuestionImage.objects.create(
            question_id=self.question.id,
            page_number=0,
            image_index_in_page=0,
            file="",
            mime="image/png",
            width=10,
            height=10,
            bytes=100,
            sha256="c" * 64,
            sha256_short="c" * 16,
            modality="other",
            role="illustration",
            uploaded_by_admin=True,
            url="https://example.com/stem.png",
        )
        # One explanation-only image (admin uploaded from the
        # explanation editor).
        QuestionImage.objects.create(
            question_id=self.question.id,
            page_number=0,
            image_index_in_page=1,
            file="",
            mime="image/png",
            width=10,
            height=10,
            bytes=100,
            sha256="d" * 64,
            sha256_short="d" * 16,
            modality="other",
            role="explanation",
            uploaded_by_admin=True,
            url="https://example.com/expl.png",
        )

        data = QuestionDetailSerializer(self.question).data
        self.assertEqual(len(data["images"]), 2, "all rows still returned in `images`")
        self.assertEqual(len(data["stem_images"]), 1, "explanation row filtered out of `stem_images`")
        self.assertEqual(data["stem_images"][0]["role"], "illustration")
        self.assertNotIn("explanation", [img["role"] for img in data["stem_images"]])

    def test_runtime_role_correction(self):
        """Belt-and-suspenders: even when a row was uploaded with the
        WRONG role (e.g. via the pre-fix upload path that didn't forward
        role=), the detail serializer's runtime heuristic must reclassify
        it based on which text fields reference the image id. An image
        referenced from `explanation` but not `question_text` is treated
        as `role='explanation'` at response time so `stem_images` drops
        it before reaching the client. Bug 2026-08-01 production case."""
        from questions.serializers import QuestionDetailSerializer

        # Create one row that was uploaded with the WRONG role (the
        # legacy bug pattern: role='illustration' but referenced from
        # the explanation text). Force its id to match the token so the
        # heuristic can detect the leak.
        leaked = QuestionImage.objects.create(
            question_id=self.question.id,
            page_number=0,
            image_index_in_page=0,
            file="",
            mime="image/png",
            width=10,
            height=10,
            bytes=100,
            sha256="r" * 64,
            sha256_short="r" * 16,
            modality="other",
            role="illustration",  # wrong on purpose — the legacy bug
            uploaded_by_admin=True,
            url="https://example.com/leaked.png",
        )
        # Use raw SQL to set the id so we can reference it from the
        # explanation via [[img:N]] token. SQLite autoincrement is off
        # when we override pk.
        from django.db import connection
        with connection.cursor() as c:
            c.execute(
                "UPDATE questions_questionimage SET id=42000 WHERE id=%s",
                [leaked.id],
            )
        self.question.explanation = "[[img:42000]] The bell of the stethoscope is best."
        self.question.save(update_fields=["explanation"])

        data = QuestionDetailSerializer(self.question).data
        roles = {img["id"]: img["role"] for img in data["images"]}
        self.assertEqual(roles.get(42000), "explanation",
                         "runtime correction must reclassify leaked image to 'explanation'")
        self.assertEqual(
            [img["id"] for img in data["stem_images"]], [],
            "stem_images must drop the leaked image even when its stored role is wrong",
        )