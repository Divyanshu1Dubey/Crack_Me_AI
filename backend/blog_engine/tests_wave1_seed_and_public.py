"""Regression tests for the blog seed + public read API (wave 1, G11: M9)."""
from __future__ import annotations

import io
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from blog_engine.models import BlogPost

User = get_user_model()

SEED = [
    {"slug": "real-article", "title": "Seed title", "description": "d", "excerpt": "e",
     "category": "UPSC CMS", "author": "A", "author_role": "R", "date_published": "2026-01-01",
     "body": "A real article body " * 20, "is_published": True},
    {"slug": "stub-article", "title": "Stub", "description": "d", "excerpt": "e",
     "category": "UPSC CMS", "author": "A", "author_role": "R", "date_published": "2026-01-02",
     "body": "Full article content here.", "is_published": True},
]


class SeedBlogsTests(TestCase):
    def _seed(self, *args):
        with patch("blog_engine.management.commands.seed_blogs.BLOG_POSTS", SEED):
            call_command("seed_blogs", *args, stdout=io.StringIO())

    def test_seed_is_create_only_and_keeps_admin_edits(self):
        self._seed()
        self.assertEqual(BlogPost.objects.count(), 2)
        self.assertFalse(BlogPost.objects.get(slug="stub-article").is_published,
                         "a placeholder-body post must not be created published")
        BlogPost.objects.filter(slug="real-article").update(title="Admin title", is_published=False)
        self._seed()  # next deploy
        post = BlogPost.objects.get(slug="real-article")
        self.assertEqual((post.title, post.is_published), ("Admin title", False))
        self._seed("--update")  # explicit opt-in still overwrites
        self.assertEqual(BlogPost.objects.get(slug="real-article").title, "Seed title")


class PublicBlogApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        base = {"description": "d", "excerpt": "e", "category": "c", "author": "a",
                "author_role": "r", "date_published": "2026-01-01"}
        self.pub = BlogPost.objects.create(slug="pub", title="P", body="Real body text", is_published=True, **base)
        self.draft = BlogPost.objects.create(slug="draft", title="D", body="Draft body", is_published=False, **base)
        self.stub = BlogPost.objects.create(slug="stub", title="S", body="Full article content here.",
                                            is_published=True, **base)

    def test_anonymous_reads_published_real_posts_only(self):
        r = self.client.get("/api/blog/posts/")
        self.assertEqual(r.status_code, 200)
        rows = r.data if isinstance(r.data, list) else r.data["results"]
        self.assertEqual([row["slug"] for row in rows], ["pub"])
        self.assertEqual(self.client.get("/api/blog/posts/by-slug/pub/").status_code, 200)
        self.assertEqual(self.client.get("/api/blog/posts/by-slug/draft/").status_code, 404)
        self.assertEqual(self.client.get(f"/api/blog/posts/{self.stub.id}/").status_code, 404)

    def test_writes_stay_admin_only(self):
        self.assertIn(self.client.post("/api/blog/posts/", {"slug": "x"}).status_code, (401, 403))
        self.assertIn(self.client.post(f"/api/blog/posts/{self.pub.id}/toggle-publish/").status_code, (401, 403))
        staff = User.objects.create_user(username="g11_blog_staff", password="x", is_staff=True)
        self.client.force_authenticate(staff)
        rows = self.client.get("/api/blog/posts/").data
        rows = rows if isinstance(rows, list) else rows["results"]
        self.assertEqual({row["slug"] for row in rows}, {"pub", "draft", "stub"})
