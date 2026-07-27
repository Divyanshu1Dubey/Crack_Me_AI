"""Django unit tests for the Admin Import Center REST API.

These exercise the staff-gated endpoints, the upload→batch lifecycle, and
the review-queue decision flow without needing the real parser pipeline —
uploaded test files are tiny synthetic DOCX/PDF/PPTX placeholders.

Run:
    python manage.py test material_importer.tests.test_api --keepdb
"""
from __future__ import annotations

import io
import zipfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from material_importer.models import (
    ExtractedQuestion,
    ImportBatch,
    ImportMaterial,
)


User = get_user_model()


def _docx_bytes() -> bytes:
    """Return a minimal (but parseable) empty DOCX."""
    from docx import Document
    buf = io.BytesIO()
    doc = Document()
    doc.save(buf)
    return buf.getvalue()


class ImportCenterAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="admin_test", password="testpass123",
            is_staff=True, is_superuser=True,
        )
        cls.user = User.objects.create_user(
            username="normal_user", password="testpass123",
        )

    def setUp(self):
        self.client = APIClient()

    def login_admin(self):
        self.client.force_authenticate(user=self.admin)

    def login_user(self):
        self.client.force_authenticate(user=self.user)

    # ----- Auth ------------------------------------------------------------

    def test_dashboard_requires_admin(self):
        r = self.client.get("/api/admin/import/dashboard/")
        self.assertIn(r.status_code, (401, 403))

        self.login_user()
        r = self.client.get("/api/admin/import/dashboard/")
        self.assertEqual(r.status_code, 403)

        self.login_admin()
        r = self.client.get("/api/admin/import/dashboard/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("total_batches", r.data)

    def test_health_endpoint(self):
        self.login_admin()
        r = self.client.get("/api/admin/import/health/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("checks", r.data)

    def test_lookups_endpoint(self):
        self.login_admin()
        r = self.client.get("/api/admin/import/lookups/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("subjects", r.data)
        self.assertIn("topics", r.data)

    def test_search_requires_term(self):
        self.login_admin()
        r = self.client.get("/api/admin/import/search/")
        self.assertEqual(r.status_code, 400)
        r = self.client.get("/api/admin/import/search/?q=heart")
        self.assertEqual(r.status_code, 200)
        self.assertIn("term", r.data)

    # ----- Upload ----------------------------------------------------------

    def test_upload_rejects_non_admin(self):
        f = SimpleUploadedFile("test.docx", _docx_bytes(), content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        r = self.client.post("/api/admin/import/upload/", {"files": f}, format="multipart")
        self.assertIn(r.status_code, (401, 403))

    def test_upload_rejects_bad_extension(self):
        self.login_admin()
        f = SimpleUploadedFile("hack.exe", b"bad", content_type="application/octet-stream")
        r = self.client.post("/api/admin/import/upload/", {"files": f}, format="multipart")
        self.assertEqual(r.status_code, 400)
        self.assertIn("No usable", r.data["error"])

    def test_upload_accepts_docx(self):
        self.login_admin()
        f = SimpleUploadedFile(
            "tiny.docx",
            _docx_bytes(),
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        r = self.client.post(
            "/api/admin/import/upload/",
            {"files": f, "source_label": "Test upload"},
            format="multipart",
        )
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIn("batch_id", r.data)
        batch = ImportBatch.objects.get(pk=r.data["batch_id"])
        self.assertEqual(batch.source_label, "Test upload")
        # Background thread may still be running; just verify state was created.
        self.assertIn(batch.status, {"queued", "processing", "completed", "partial"})

    def test_upload_accepts_zip(self):
        self.login_admin()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("inner.docx", _docx_bytes())
        f = SimpleUploadedFile("bundle.zip", buf.getvalue(), content_type="application/zip")
        r = self.client.post("/api/admin/import/upload/", {"files": f}, format="multipart")
        self.assertEqual(r.status_code, 201, r.data)

    # ----- Batch list / detail / cancel -----------------------------------

    def _make_batch(self) -> ImportBatch:
        return ImportBatch.objects.create(
            source_label="Test batch", root_path="/tmp/test", status="completed",
        )

    def test_batch_list(self):
        b = self._make_batch()
        self.login_admin()
        r = self.client.get("/api/admin/import/batches/")
        self.assertEqual(r.status_code, 200)
        # DRF default returns paginated results
        items = r.data if isinstance(r.data, list) else r.data.get("results", [])
        self.assertTrue(any(x["id"] == b.id for x in items))

    def test_batch_detail(self):
        b = self._make_batch()
        self.login_admin()
        r = self.client.get(f"/api/admin/import/batches/{b.id}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["id"], b.id)

    def test_batch_cancel(self):
        b = ImportBatch.objects.create(
            source_label="Cancel test", root_path="/tmp", status="processing",
        )
        self.login_admin()
        r = self.client.post(f"/api/admin/import/batches/{b.id}/cancel/")
        self.assertEqual(r.status_code, 200)
        b.refresh_from_db()
        self.assertEqual(b.status, "cancelled")

    def test_batch_cancel_completed_is_409(self):
        b = self._make_batch()  # status=completed
        self.login_admin()
        r = self.client.post(f"/api/admin/import/batches/{b.id}/cancel/")
        self.assertEqual(r.status_code, 409)

    # ----- Questions review queue -----------------------------------------

    def _make_question(self, status: str = "pending") -> ExtractedQuestion:
        m = ImportMaterial.objects.create(
            batch=self._make_batch(), original_filename="q.docx",
            file_format="docx", file_size_bytes=10, file_sha256="x" * 64,
        )
        return ExtractedQuestion.objects.create(
            material=m,
            position_index=1,
            question_text="Sample Q?",
            option_a="A", option_b="B", option_c="C", option_d="D",
            correct_answer="A",
            content_hash="abc" * 20 + "abcdef0",
            status=status,
        )

    def test_list_questions(self):
        q = self._make_question()
        self.login_admin()
        r = self.client.get("/api/admin/import/questions/")
        self.assertEqual(r.status_code, 200)
        items = r.data if isinstance(r.data, list) else r.data.get("results", [])
        self.assertTrue(any(x["id"] == q.id for x in items))

    def test_decision_approve(self):
        q = self._make_question("pending")
        self.login_admin()
        r = self.client.post(
            f"/api/admin/import/questions/{q.id}/decision/",
            {"decision": "approve", "note": "looks good"},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        q.refresh_from_db()
        self.assertEqual(q.status, "approved")
        self.assertEqual(q.review_note, "looks good")

    def test_decision_reject(self):
        q = self._make_question("pending")
        self.login_admin()
        r = self.client.post(
            f"/api/admin/import/questions/{q.id}/decision/",
            {"decision": "reject", "note": "bad layout"},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        q.refresh_from_db()
        self.assertEqual(q.status, "rejected")

    def test_decision_reset(self):
        q = self._make_question("approved")
        self.login_admin()
        r = self.client.post(
            f"/api/admin/import/questions/{q.id}/decision/",
            {"decision": "reset"},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        q.refresh_from_db()
        self.assertEqual(q.status, "pending")

    def test_bulk_decision(self):
        q1 = self._make_question("pending")
        q2 = self._make_question("pending")
        self.login_admin()
        r = self.client.post(
            "/api/admin/import/questions/bulk-decision/",
            {"ids": [q1.id, q2.id], "decision": "approve", "note": "batch OK"},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["updated"], 2)
        q1.refresh_from_db(); q2.refresh_from_db()
        self.assertEqual(q1.status, "approved")
        self.assertEqual(q2.status, "approved")

    def test_bulk_decision_rejects_empty(self):
        self.login_admin()
        r = self.client.post(
            "/api/admin/import/questions/bulk-decision/",
            {"ids": [], "decision": "approve"},
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    def test_rollback_requires_confirm(self):
        b = self._make_batch()
        self.login_admin()
        r = self.client.post(
            f"/api/admin/import/batches/{b.id}/rollback/",
            {"delete_published": False},  # missing confirm
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    def test_rollback_happy_path(self):
        b = self._make_batch()
        self.login_admin()
        r = self.client.post(
            f"/api/admin/import/batches/{b.id}/rollback/",
            {"delete_published": False, "confirm": True},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        b.refresh_from_db()
        self.assertEqual(b.status, "cancelled")

    def test_generate_mock_test_no_questions(self):
        b = self._make_batch()
        self.login_admin()
        r = self.client.post(
            f"/api/admin/import/batches/{b.id}/generate-mock/",
            {"strategy": "by_subject", "question_count": 10},
            format="json",
        )
        # No publishable questions → 400
        self.assertEqual(r.status_code, 400)

    def test_republish(self):
        b = self._make_batch()
        self.login_admin()
        r = self.client.post(f"/api/admin/import/batches/{b.id}/republish/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("tests_built", r.data)
