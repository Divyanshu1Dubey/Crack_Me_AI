"""The retired 'dr-aarav-mehta' byline (wave 3, Z8 for Z10).

Its MBBS, MD credential could not be verified, so the static blog credits the
CrackCMS Editorial Team. The DB seed must carry the same byline, and rows
seeded before the change (seed_blogs skips existing rows) are rewritten by
migration 0002, without deleting or unpublishing anything (C17).
"""
from __future__ import annotations

import importlib
import io

from django.apps import apps
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from blog_engine.management.commands.seed_blogs import BLOG_POSTS
from blog_engine.models import BlogPost

migration = importlib.import_module("blog_engine.migrations.0002_credit_editorial_team")

RETIRED_ID = "dr-aarav-mehta"
RETIRED_TEXT = ("Aarav", "MBBS, MD (Internal Medicine)", "Senior Editor", "Internist", "A clinician’s")
EDITORIAL = ("crackcms-editorial", "CrackCMS Editorial Team", "Clinical Content Editors, CrackCMS")
LAST_5_DAYS = "upsc-cms-last-5-days-strategy"
NEW_TITLE = "UPSC CMS Last 5 Days: A Day-by-Day Revision Plan"


def byline(post: BlogPost) -> tuple[str, str, str]:
    return (post.author_id, post.author, post.author_role)


class SeedBylineTests(TestCase):
    def test_seed_data_carries_no_retired_byline(self):
        for post in BLOG_POSTS:
            self.assertNotEqual(post.get("author_id"), RETIRED_ID, post["slug"])
            self.assertNotEqual(post.get("reviewed_by"), RETIRED_ID, post["slug"])
            text = "\n".join(str(post.get(k) or "") for k in ("author", "author_role", "title", "description"))
            for retired in RETIRED_TEXT:
                self.assertNotIn(retired, text, post["slug"])

    def test_fresh_seed_serves_the_editorial_byline(self):
        call_command("seed_blogs", stdout=io.StringIO())
        self.assertFalse(BlogPost.objects.filter(author_id=RETIRED_ID).exists())
        self.assertFalse(BlogPost.objects.filter(reviewed_by=RETIRED_ID).exists())
        post = BlogPost.objects.get(slug=LAST_5_DAYS)
        self.assertEqual((*byline(post), post.reviewed_by), (*EDITORIAL, "crackcms-editorial"))
        self.assertEqual(post.title, NEW_TITLE)

        # A published post with a real body (served publicly) that used to carry the byline.
        r = APIClient().get("/api/blog/posts/by-slug/surgery-suturing-techniques-upsc-cms/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.data["author_id"], r.data["author"], r.data["author_role"], r.data["reviewed_by"]),
                         (*EDITORIAL, "crackcms-editorial"))

    def test_blog_engine_has_no_model_change_without_a_migration(self):
        out = io.StringIO()
        try:
            call_command("makemigrations", "blog_engine", "--check", "--dry-run", stdout=out, stderr=io.StringIO())
        except SystemExit:
            self.fail(f"blog_engine has model changes without a migration:\n{out.getvalue()}")


class CreditEditorialMigrationTests(TestCase):
    BASE = {"excerpt": "e", "category": "UPSC CMS", "date_published": "2026-07-28",
            "body": "A real article body.", "is_published": True}
    OLD_TITLE, OLD_DESCRIPTION = migration.RETITLED[0][1], migration.RETITLED[1][1]

    def _post(self, slug, **fields):
        return BlogPost.objects.create(slug=slug, **{"title": "T", "description": "d", **self.BASE, **fields})

    def test_rewrites_rows_seeded_with_the_retired_byline_only(self):
        seeded = self._post(LAST_5_DAYS, title=self.OLD_TITLE, description=self.OLD_DESCRIPTION,
                            author_id=RETIRED_ID, reviewed_by=RETIRED_ID, author=migration.RETIRED_AUTHOR,
                            author_role="Senior Editor — Medicine, CrackCMS")
        hyphen_role = self._post("hyphen-role", author_id=RETIRED_ID, reviewed_by=RETIRED_ID,
                                 author=migration.RETIRED_AUTHOR, author_role="Senior Editor - Medicine, CrackCMS")
        admin_title = self._post("admin-title", title="Admin's own title", author_id=RETIRED_ID,
                                 author=migration.RETIRED_AUTHOR, author_role="Senior Editor - Medicine, CrackCMS",
                                 is_published=False)
        reviewed_only = self._post("reviewed-only", author_id=EDITORIAL[0], reviewed_by=RETIRED_ID,
                                   author=EDITORIAL[1], author_role=EDITORIAL[2])
        other = self._post("guest", title="Guest post", author_id="guest-writer", reviewed_by="",
                           author="Guest Writer", author_role="Contributor")

        migration.credit_editorial_team(apps, None)
        for post in (seeded, hyphen_role, admin_title, reviewed_only, other):
            post.refresh_from_db()

        for post in (seeded, hyphen_role, admin_title):
            self.assertEqual(byline(post), EDITORIAL, post.slug)
        self.assertEqual((seeded.reviewed_by, hyphen_role.reviewed_by, reviewed_only.reviewed_by),
                         ("crackcms-editorial",) * 3)
        self.assertEqual(seeded.title, NEW_TITLE)
        self.assertEqual(seeded.description, migration.RETITLED[1][2])
        # Admin edits and other authors are left alone; nothing is (un)published or deleted.
        self.assertEqual((admin_title.title, admin_title.is_published), ("Admin's own title", False))
        self.assertEqual((byline(other), other.reviewed_by, other.title),
                         (("guest-writer", "Guest Writer", "Contributor"), "", "Guest post"))
        self.assertTrue(seeded.is_published)
        self.assertEqual(BlogPost.objects.count(), 5)

        migration.credit_editorial_team(apps, None)  # idempotent
        self.assertFalse(BlogPost.objects.filter(author_id=RETIRED_ID).exists())
        self.assertEqual(BlogPost.objects.get(slug=LAST_5_DAYS).title, NEW_TITLE)
