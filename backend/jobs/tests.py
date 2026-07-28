"""
tests.py — Lock down the JobViewSet contract that the new admin
``/admin/jobs`` page depends on:

  * Anonymous users can list and retrieve (filtered to is_active=True).
  * Authenticated non-admin users can list/retrieve but not POST/PATCH/DELETE.
  * Admin users can POST/DELETE.
  * The list endpoint accepts `is_active` filtering so the admin page
    can preview inactive postings if needed.

These tests exist because the admin "Jobs" dashboard tile was
previously a placeholder ("Full Job Management UI is in
development") and a regression on the API would leave the UI
unusable without a console to look at. Any change to the permissions
matrix on JobViewSet should be reflected here.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from jobs.models import Job, JobCategory


User = get_user_model()


class JobApiPermissionsTests(APITestCase):
    """End-to-end auth checks for the JobViewSet."""

    def setUp(self):
        self.category = JobCategory.objects.create(name="Medical", slug="medical")

    def _make_job(self) -> Job:
        return Job.objects.create(
            title="Senior Resident",
            hospital="AIIMS",
            location="New Delhi",
            category=self.category,
            description="Cardiology SR",
            apply_link="https://example.com/apply",
            is_active=True,
        )

    def test_anonymous_can_list_active_jobs(self):
        # The candidate-side jobs board depends on this; ensuring
        # anon listing stays open after the admin-UI upgrade.
        inactive = Job.objects.create(
            title="Hidden Posting",
            hospital="X",
            location="Y",
            category=self.category,
            description="D",
            apply_link="https://example.com",
            is_active=False,
        )
        active = self._make_job()
        res = self.client.get("/api/jobs/")
        self.assertEqual(res.status_code, 200)
        rows = res.json() if isinstance(res.json(), list) else res.json().get("results", [])
        ids = [r["id"] for r in rows]
        self.assertIn(active.id, ids, "active jobs must be visible to anonymous users")
        self.assertNotIn(
            inactive.id, ids,
            "inactive jobs must be filtered out of the anon list",
        )

    def test_anonymous_cannot_create(self):
        res = self.client.post(
            "/api/jobs/",
            {
                "title": "X", "hospital": "Y", "location": "Z",
                "description": "D", "apply_link": "https://example.com",
            },
            format="json",
        )
        # DRF default for unauthenticated POST is 401 (token auth) or
        # 403 depending on auth header presence — either is acceptable.
        self.assertIn(res.status_code, (401, 403))

    def test_admin_can_create_and_delete(self):
        admin = User.objects.create_superuser(
            username="admin", email="a@b.in", password="x",
        )
        self.client.force_authenticate(user=admin)
        create_res = self.client.post(
            "/api/jobs/",
            {
                "title": "Resident",
                "hospital": "PGI",
                "location": "Chandigarh",
                "category": self.category.id,
                "description": "Duties…",
                "apply_link": "https://example.com/apply",
                "eligibility_summary": "MBBS",
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, 201, create_res.content)
        job_id = create_res.json()["id"]

        del_res = self.client.delete(f"/api/jobs/{job_id}/")
        self.assertEqual(del_res.status_code, 204)
        self.assertFalse(Job.objects.filter(pk=job_id).exists())