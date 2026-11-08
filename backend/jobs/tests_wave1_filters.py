"""Regression tests for the jobs board API (wave 1, G11: M11 / PUB-14 / PUB-15).

* ?exam_track= filters (it used to be ignored),
* expired postings are hidden from students,
* the list runs a constant number of queries (no per-row N+1),
* is_bookmarked is still correct.
"""
from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from jobs.models import JobBookmark, JobCategory
from jobs.testing import published_job
from questions.models import ExamTrack

User = get_user_model()


def _rows(resp):
    data = resp.json()
    return data if isinstance(data, list) else data.get("results", [])


class JobsBoardTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.cat = JobCategory.objects.create(name="Govt", slug="govt")
        self.cms = ExamTrack.objects.create(name="UPSC CMS G11", code="cms")
        self.neet = ExamTrack.objects.create(name="NEET PG G11", code="neet_pg")

    def _job(self, title, *, tracks=(), tags=(), expires_in_days=None):
        job = published_job(
            title=title, hospital="H", location="L", category=self.cat, description="D",
            exam_track_tags=list(tags),
            expires_at=(timezone.now() + timedelta(days=expires_in_days)) if expires_in_days is not None else None,
        )
        job.exam_tracks.set(tracks)
        return job

    def test_exam_track_filter_matches_m2m_and_tags(self):
        by_m2m = self._job("CMS via M2M", tracks=[self.cms])
        by_tag = self._job("CMS via tag", tags=["cms"])
        neet = self._job("NEET only", tracks=[self.neet], tags=["neet_pg"])
        ids = {r["id"] for r in _rows(self.client.get("/api/jobs/", {"exam_track": "cms"}))}
        self.assertEqual(ids, {by_m2m.id, by_tag.id})
        ids = {r["id"] for r in _rows(self.client.get("/api/jobs/", {"exam_track": "all"}))}
        self.assertEqual(ids, {by_m2m.id, by_tag.id, neet.id})

    def test_expired_jobs_are_hidden_from_students_but_not_admins(self):
        live = self._job("Open", expires_in_days=5)
        expired = self._job("Closed", expires_in_days=-1)
        ids = {r["id"] for r in _rows(self.client.get("/api/jobs/"))}
        self.assertIn(live.id, ids)
        self.assertNotIn(expired.id, ids)
        admin = User.objects.create_user(username="g11_jobs_admin", password="x", is_superuser=True)
        self.client.force_authenticate(admin)
        ids = {r["id"] for r in _rows(self.client.get("/api/jobs/"))}
        self.assertIn(expired.id, ids)

    def test_list_query_count_does_not_grow_with_rows(self):
        user = User.objects.create_user(username="g11_jobs_user", password="x")
        self.client.force_authenticate(user)
        for i in range(2):
            self._job(f"J{i}", tracks=[self.cms])
        with CaptureQueriesContext(connection) as small:
            self.assertEqual(self.client.get("/api/jobs/").status_code, 200)
        for i in range(2, 8):
            self._job(f"J{i}", tracks=[self.cms, self.neet])
        with CaptureQueriesContext(connection) as large:
            self.assertEqual(self.client.get("/api/jobs/").status_code, 200)
        self.assertEqual(len(small.captured_queries), len(large.captured_queries))

    def test_is_bookmarked_flag(self):
        user = User.objects.create_user(username="g11_jobs_bm", password="x")
        a = self._job("A")
        b = self._job("B")
        JobBookmark.objects.create(user=user, job=a)
        self.client.force_authenticate(user)
        flags = {r["id"]: r["is_bookmarked"] for r in _rows(self.client.get("/api/jobs/"))}
        self.assertEqual(flags, {a.id: True, b.id: False})
        self.assertTrue(self.client.get(f"/api/jobs/{a.id}/").json()["is_bookmarked"])
