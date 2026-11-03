"""Wave 4 (Z8): the public jobs board search uses the bounded search backend
(``crack_cms.filters.BoundedSearchFilter``): an explicit ``filter_backends``
bypasses the project default, so it must name the bounded filter itself.
"""
from __future__ import annotations

from django.test import TestCase
from rest_framework.filters import SearchFilter
from rest_framework.test import APIClient

from crack_cms.filters import MAX_SEARCH_TERMS, BoundedSearchFilter
from jobs.models import Job, JobCategory
from jobs.views import JobViewSet


def _ids(resp):
    data = resp.json()
    rows = data if isinstance(data, list) else data.get("results", [])
    return [row["id"] for row in rows]


class JobSearchIsBoundedTests(TestCase):
    def test_the_viewset_uses_the_bounded_search_filter(self):
        self.assertIn(BoundedSearchFilter, JobViewSet.filter_backends)
        self.assertNotIn(SearchFilter, JobViewSet.filter_backends)

    def test_search_still_matches_and_ignores_terms_past_the_cap(self):
        cat = JobCategory.objects.create(name="Govt", slug="govt-z8")
        words = [f"zqterm{i:02d}" for i in range(MAX_SEARCH_TERMS)]
        job = Job.objects.create(
            title="Senior Resident", hospital="H", location="L", category=cat,
            description=" ".join(words), apply_link="https://example.com/apply",
        )
        client = APIClient()
        self.assertEqual(_ids(client.get("/api/jobs/", {"search": "Senior Resident"})), [job.id])
        self.assertEqual(_ids(client.get("/api/jobs/", {"search": "Professor"})), [])
        # Terms are AND-ed; the unbounded filter also required the 11th term
        # (no match). The bounded one keeps the first 10 distinct terms.
        resp = client.get("/api/jobs/", {"search": " ".join(words + ["nomatchanywhere"])})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(_ids(resp), [job.id])
