"""seed_blogs with the real seed data (wave 3, Z8: M9 / C16).

The database is the source of truth of the public blog, and release.sh /
build.sh run seed_blogs on every deploy. A fresh database must therefore get
every static post completely (every field), published, with no cover pointing
at the /blog/og/* files frontend/public does not ship, listed in the static
blog's order; a rerun changes nothing.
"""
from __future__ import annotations

import io
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from blog_engine.management.commands.seed_blogs import BLOG_POSTS
from blog_engine.models import BlogPost, BlogSeedImport
from blog_engine.seeding import CONTENT_FIELDS, content_hash, is_placeholder_body, row_values


def seed(*args) -> str:
    out = io.StringIO()
    call_command("seed_blogs", *args, stdout=out)
    return out.getvalue()


class RealSeedTests(TestCase):
    def test_the_snapshot_holds_every_static_post_with_a_real_body(self):
        self.assertEqual(len(BLOG_POSTS), 129)
        self.assertEqual(len({r["slug"] for r in BLOG_POSTS}), 129)
        for record in BLOG_POSTS:
            self.assertFalse(is_placeholder_body(record["body"]), record["slug"])
            self.assertEqual(set(record), set(CONTENT_FIELDS) | {"slug"}, record["slug"])

    def test_fresh_seed_imports_every_static_post_completely_and_published(self):
        out = seed()
        self.assertIn("created: 129", out)
        self.assertEqual(BlogPost.objects.count(), 129)
        self.assertEqual(BlogPost.objects.filter(is_published=True).count(), 129)
        for record in BLOG_POSTS:
            post = BlogPost.objects.get(slug=record["slug"])
            for name in CONTENT_FIELDS:
                if name == "cover_image":
                    continue
                self.assertEqual(getattr(post, name), record[name], f"{record['slug']}.{name}")
        self.assertFalse(BlogPost.objects.filter(cover_image__startswith="/blog/og/").exists())
        self.assertFalse(BlogPost.objects.filter(cover_image__startswith="/blog/obg/").exists())
        public = Path(settings.BASE_DIR).parent / "frontend" / "public"
        if public.is_dir():  # every cover the seed still writes is a shipped file
            for cover in BlogPost.objects.exclude(cover_image="").values_list("cover_image", flat=True):
                self.assertTrue((public / cover.lstrip("/")).is_file(), cover)
        # Each import records the hash of what was written; it reads back equal.
        self.assertEqual(BlogSeedImport.objects.count(), 129)
        for item in BlogSeedImport.objects.all():
            self.assertEqual(item.content_hash, content_hash(row_values(BlogPost.objects.get(slug=item.slug))))

    def test_a_deploy_rerun_changes_nothing(self):
        seed()
        before = dict(BlogPost.objects.values_list("slug", "updated"))
        out = seed()
        self.assertIn("created: 0, updated: 0, unchanged: 129", out)
        self.assertEqual(dict(BlogPost.objects.values_list("slug", "updated")), before)

    def test_the_public_catalog_lists_the_posts_in_the_static_blog_order(self):
        seed()
        response = APIClient().get("/api/blog/posts/catalog/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 129)
        # Newest first; posts of the same day in the order the static blog shows them.
        self.assertEqual([row["slug"] for row in response.data["results"]], [r["slug"] for r in BLOG_POSTS])
