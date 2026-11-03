"""Wave 4 (Z8): the public blog search uses the bounded search backend
(``crack_cms.filters.BoundedSearchFilter``): an explicit ``filter_backends``
bypasses the project default, so it must name the bounded filter itself.
"""
from __future__ import annotations

from django.test import TestCase
from rest_framework.filters import SearchFilter
from rest_framework.test import APIClient

from blog_engine.models import BlogPost
from blog_engine.views import BlogPostViewSet
from crack_cms.filters import MAX_SEARCH_TERMS, BoundedSearchFilter


def _slugs(resp):
    data = resp.json()
    rows = data if isinstance(data, list) else data.get("results", [])
    return [row["slug"] for row in rows]


class BlogSearchIsBoundedTests(TestCase):
    def test_the_viewset_uses_the_bounded_search_filter(self):
        self.assertIn(BoundedSearchFilter, BlogPostViewSet.filter_backends)
        self.assertNotIn(SearchFilter, BlogPostViewSet.filter_backends)

    def test_search_still_matches_and_ignores_terms_past_the_cap(self):
        words = [f"zqterm{i:02d}" for i in range(MAX_SEARCH_TERMS)]
        BlogPost.objects.create(
            slug="z8-search", title="Renal physiology made simple", body=" ".join(words),
            description="d", excerpt="e", category="c", author="a", author_role="r",
            date_published="2026-01-01", is_published=True,
        )
        client = APIClient()
        self.assertEqual(_slugs(client.get("/api/blog/posts/", {"search": "renal"})), ["z8-search"])
        self.assertEqual(_slugs(client.get("/api/blog/posts/", {"search": "cardiology"})), [])
        # Terms are AND-ed; the unbounded filter also required the 11th term
        # (no match). The bounded one keeps the first 10 distinct terms.
        resp = client.get("/api/blog/posts/", {"search": " ".join(words + ["nomatchanywhere"])})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(_slugs(resp), ["z8-search"])
