"""seed_blogs with the real seed data (wave 3, Z8: M9 / C16).

build.sh runs seed_blogs on every deploy. The public blog stays static (C16),
so the seed must never publish a stub article, and must not point covers at
/blog/og/* files that frontend/public does not ship.
"""
from __future__ import annotations

import io
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase

from blog_engine.management.commands.seed_blogs import BLOG_POSTS, is_placeholder_body
from blog_engine.models import BlogPost


class RealSeedTests(TestCase):
    def test_fresh_seed_publishes_no_stub_and_no_missing_cover(self):
        call_command("seed_blogs", stdout=io.StringIO())
        self.assertEqual(BlogPost.objects.count(), len(BLOG_POSTS))

        app_form = BlogPost.objects.get(slug="upsc-cms-2026-application-form")
        self.assertFalse(app_form.is_published, "its seeded body is the placeholder text")
        self.assertEqual(app_form.cover_image, "")

        for post in BlogPost.objects.filter(is_published=True):
            self.assertFalse(is_placeholder_body(post.body), post.slug)
        self.assertFalse(BlogPost.objects.filter(cover_image__startswith="/blog/og/").exists())
        self.assertFalse(BlogPost.objects.filter(cover_image__startswith="/blog/obg/").exists())

        public = Path(settings.BASE_DIR).parent / "frontend" / "public"
        if public.is_dir():  # every cover the seed still writes is a shipped file
            for cover in BlogPost.objects.exclude(cover_image="").values_list("cover_image", flat=True):
                self.assertTrue((public / cover.lstrip("/")).is_file(), cover)

    def test_update_does_not_publish_a_stub_either(self):
        call_command("seed_blogs", stdout=io.StringIO())
        BlogPost.objects.filter(slug="upsc-cms-2026-application-form").update(is_published=True)
        call_command("seed_blogs", "--update", stdout=io.StringIO())
        self.assertFalse(BlogPost.objects.get(slug="upsc-cms-2026-application-form").is_published)

    def test_a_deploy_rerun_changes_nothing(self):
        call_command("seed_blogs", stdout=io.StringIO())
        BlogPost.objects.filter(slug="upsc-cms-2026-application-form").update(
            cover_image="/brand/cover.png", is_published=True, body="An admin-written article body.")
        out = io.StringIO()
        call_command("seed_blogs", stdout=out)
        self.assertIn(f"Skipped: {len(BLOG_POSTS)}", out.getvalue())
        post = BlogPost.objects.get(slug="upsc-cms-2026-application-form")
        self.assertEqual((post.cover_image, post.is_published), ("/brand/cover.png", True))
