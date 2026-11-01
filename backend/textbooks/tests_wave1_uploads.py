"""Regression tests for textbook "My Uploads" + chunk explorer (wave 1, G11).

M5 / FE-STU-23: uploads are type/size validated, quota-limited, cannot be
attached to an official textbook, create no placeholder chunk, and are
downloadable by their owner only through an authenticated endpoint.
L1: the chunk explorer says it does not feed the AI tutor and hides the
legacy placeholder rows.
"""
from __future__ import annotations

import io
import shutil
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from questions.models import Subject
from textbooks.models import PDFUpload, Textbook, TextbookChunk

User = get_user_model()

PDF_BYTES = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def _docx_bytes() -> bytes:
    from docx import Document
    buf = io.BytesIO()
    Document().save(buf)
    return buf.getvalue()


class UploadValidationTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()  # the per-user upload throttle counts live in the cache
        self.media = tempfile.mkdtemp(prefix="g11_tb_media_")
        self._override = override_settings(MEDIA_ROOT=self.media)
        self._override.enable()
        self.user = User.objects.create_user(username="g11_tb_user", password="x")
        self.other = User.objects.create_user(username="g11_tb_other", password="x")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.subject = Subject.objects.create(name="Surgery TB", code="SURTB")
        self.book = Textbook.objects.create(name="SRB", author="Bhat", subject=self.subject)

    def tearDown(self):
        self._override.disable()
        shutil.rmtree(self.media, ignore_errors=True)

    def _post(self, name, data, **extra):
        f = SimpleUploadedFile(name, data)
        return self.client.post("/api/textbooks/uploads/", {"file": f, "title": "t", **extra},
                                format="multipart")

    def test_valid_pdf_and_docx_are_accepted_without_placeholder_chunks(self):
        r = self._post("notes.pdf", PDF_BYTES)
        self.assertEqual(r.status_code, 201, r.data)
        r = self._post("notes.docx", _docx_bytes())
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(TextbookChunk.objects.count(), 0)
        self.assertTrue(r.data["download_url"].endswith("/download/"))

    def test_disguised_and_unsupported_files_are_rejected(self):
        self.assertEqual(self._post("evil.pdf", b"<html><script>alert(1)</script></html>").status_code, 400)
        self.assertEqual(self._post("run.exe", b"MZ\x90\x00").status_code, 400)
        self.assertEqual(self._post("notes.txt", b"\x00\x01binary").status_code, 400)
        self.assertEqual(self._post("notes.txt", b"plain notes").status_code, 201)
        self.assertEqual(PDFUpload.objects.count(), 1)

    def test_oversized_file_is_rejected(self):
        with patch("textbooks.serializers.MAX_UPLOAD_BYTES", 10):
            self.assertEqual(self._post("big.pdf", PDF_BYTES).status_code, 400)

    def test_per_user_quota(self):
        with patch("textbooks.serializers.MAX_UPLOADS_PER_USER", 1):
            self.assertEqual(self._post("a.pdf", PDF_BYTES).status_code, 201)
            self.assertEqual(self._post("b.pdf", PDF_BYTES).status_code, 400)

    def test_upload_cannot_be_attached_to_an_official_textbook(self):
        r = self._post("notes.pdf", PDF_BYTES, textbook=self.book.id)
        self.assertEqual(r.status_code, 201)
        self.assertIsNone(PDFUpload.objects.get().textbook_id)

    def test_download_is_owner_only_and_safe(self):
        r = self._post("notes.pdf", PDF_BYTES)
        upload_id = r.data["id"]
        res = self.client.get(f"/api/textbooks/uploads/{upload_id}/download/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("attachment", res["Content-Disposition"])
        self.assertEqual(res["X-Content-Type-Options"], "nosniff")
        self.assertEqual(b"".join(res.streaming_content), PDF_BYTES)
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(f"/api/textbooks/uploads/{upload_id}/download/").status_code, 404)


class ChunkExplorerHonestyTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="g11_tb_admin", password="x", is_superuser=True)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        TextbookChunk.objects.create(book_name="x", chunk_text="Real chunk text", quality_score=0.9)
        TextbookChunk.objects.create(
            book_name="y", quality_score=0.5,
            chunk_text="Uploaded source placeholder for notes. Replace with parser-derived chunks.",
        )

    def test_explorer_hides_placeholders_and_says_it_does_not_feed_the_tutor(self):
        r = self.client.get("/api/textbooks/books/chunks/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 1)
        self.assertFalse(r.data["affects_ai_tutor"])
        d = self.client.get("/api/textbooks/books/chunks/diagnostics/")
        self.assertEqual(d.data["total_chunks"], 1)
        self.assertFalse(d.data["affects_ai_tutor"])
