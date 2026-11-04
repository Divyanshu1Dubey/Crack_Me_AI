"""seed_blogs once the database is the source of truth of the public blog.

* Rows the previous seed wrote (placeholder or one-paragraph summary bodies)
  are completed with the static post while nobody edited them; its rows
  under slugs the public blog never had are unpublished.
* An admin's edit, unpublish, delete or rename survives every deploy;
  ``--update`` / ``--restore`` override that on purpose.
* A static post nobody edited follows its static file.
* ``--dry-run`` writes nothing.
"""
from __future__ import annotations

import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from rest_framework.test import APIClient

from blog_engine.management.commands.seed_blogs import BLOG_POSTS
from blog_engine.models import BlogPost, BlogSeedImport
from blog_engine.seeding import (
    CONTENT_FIELDS,
    SeedDataError,
    content_hash,
    field_defaults,
    is_placeholder_body,
    legacy_fingerprint,
    load_legacy_fingerprints,
    load_static_posts,
    row_values,
    seed_values,
)

User = get_user_model()
COMMAND = "blog_engine.management.commands.seed_blogs"
SAMPLES_FILE = Path(__file__).resolve().parent / "test_fixtures" / "legacy_seed_samples.json"
LEGACY_SAMPLES = {p["slug"]: p for p in json.loads(SAMPLES_FILE.read_text(encoding="utf-8"))["posts"]}
STATIC = {r["slug"]: r for r in BLOG_POSTS}

STUB = "neet-pg-vs-upsc-cms"                       # placeholder body, static slug
SUMMARY = "surgery-suturing-techniques-upsc-cms"   # summary body, static slug
ORPHAN = "blood-physiology-upsc-cms"               # summary body, slug the public blog never had


def seed(*args) -> str:
    out = io.StringIO()
    call_command("seed_blogs", *args, stdout=out)
    return out.getvalue()


def old_seed_row(slug, *, first_production_run=False, **changes):
    """The row the previous seed_blogs created for one of its posts.

    ``first_production_run``: the 2026-08-30 run, which still published stubs
    and kept the unshipped /blog/og/ covers (the 14 rows of the restored
    production backup look like this)."""
    data = {k: v for k, v in LEGACY_SAMPLES[slug].items() if k != "slug"}
    if not first_production_run:
        if is_placeholder_body(data.get("body")):
            data["is_published"] = False
        if str(data.get("cover_image") or "").startswith(("/blog/og/", "/blog/obg/")):
            data["cover_image"] = ""
    data.update(changes)
    return BlogPost.objects.create(slug=slug, **data)


def assert_is_static_post(test, slug):
    post = BlogPost.objects.get(slug=slug)
    expected = seed_values(STATIC[slug], field_defaults())
    for name in CONTENT_FIELDS:
        test.assertEqual(getattr(post, name), expected[name], f"{slug}.{name}")
    return post


class LegacyRowsTests(TestCase):
    def test_the_fingerprints_cover_the_old_seed_and_match_the_rows_it_wrote(self):
        fingerprints = load_legacy_fingerprints()
        self.assertEqual(len(fingerprints), 125)
        self.assertEqual(len([s for s in fingerprints if s not in STATIC]), 24)
        for slug in LEGACY_SAMPLES:
            for first_run in (False, True):
                row = old_seed_row(slug, first_production_run=first_run)
                self.assertEqual(legacy_fingerprint(row_values(row)), fingerprints[slug], slug)
                # Migration 0002's byline rewrite is not an edit either.
                row.author_id, row.author = "crackcms-editorial", "CrackCMS Editorial Team"
                self.assertEqual(legacy_fingerprint(row_values(row)), fingerprints[slug], slug)
                row.title = "An admin's title"
                self.assertNotEqual(legacy_fingerprint(row_values(row)), fingerprints[slug], slug)
                row.delete()

    def test_first_run_completes_untouched_rows_and_unpublishes_the_orphan(self):
        old_seed_row(STUB, first_production_run=True)  # published stub with an /blog/og/ cover
        old_seed_row(SUMMARY)
        old_seed_row(ORPHAN)
        out = seed()

        for slug in (STUB, SUMMARY):
            post = assert_is_static_post(self, slug)
            self.assertTrue(post.is_published, slug)
            self.assertIn(f"update {slug}", out)
        orphan = BlogPost.objects.get(slug=ORPHAN)
        self.assertFalse(orphan.is_published)
        self.assertEqual(orphan.body, LEGACY_SAMPLES[ORPHAN]["body"], "nothing but the publish state changes")
        self.assertIn(f"unpublish {ORPHAN}", out)
        self.assertEqual(BlogPost.objects.count(), len(BLOG_POSTS) + 1, "nothing is deleted")
        self.assertEqual(BlogPost.objects.filter(is_published=True).count(), len(BLOG_POSTS))
        self.assertEqual(BlogSeedImport.objects.count(), len(BLOG_POSTS) + 1, "every static post and the orphan")
        self.assertEqual(BlogSeedImport.objects.get(slug=ORPHAN).content_hash, "")
        self.assertIn(f"created: {len(BLOG_POSTS) - 2}, updated: 2", out)

        out = seed()  # the next deploy
        self.assertIn(f"created: 0, updated: 0, unchanged: {len(BLOG_POSTS)}", out)
        self.assertNotIn(f"unpublish {ORPHAN}", out)
        self.assertFalse(BlogPost.objects.get(slug=ORPHAN).is_published)

        # The orphan is the admin's from now on: publishing it again sticks.
        BlogPost.objects.filter(slug=ORPHAN).update(is_published=True)
        out = seed()
        self.assertNotIn(f"unpublish {ORPHAN}", out)
        self.assertTrue(BlogPost.objects.get(slug=ORPHAN).is_published)

    def test_a_stub_unpublished_by_the_old_seed_is_published_once_it_has_the_article(self):
        self.assertFalse(old_seed_row(STUB).is_published)
        seed("--slug", STUB)
        self.assertTrue(assert_is_static_post(self, STUB).is_published)

    def test_an_edited_legacy_row_is_kept_until_update(self):
        old_seed_row(SUMMARY, title="An admin's suturing title", is_published=False)
        out = seed()
        post = BlogPost.objects.get(slug=SUMMARY)
        self.assertEqual((post.title, post.body), ("An admin's suturing title", LEGACY_SAMPLES[SUMMARY]["body"]))
        self.assertIn(f"keep {SUMMARY}: edited in the admin", out)
        self.assertEqual(BlogSeedImport.objects.get(slug=SUMMARY).content_hash, "")

        seed()
        self.assertEqual(BlogPost.objects.get(slug=SUMMARY).title, "An admin's suturing title")

        out = seed("--update", "--slug", SUMMARY)
        post = assert_is_static_post(self, SUMMARY)
        self.assertFalse(post.is_published, "the publish state stays the admin's")
        self.assertIn(f"overwrite {SUMMARY}", out)
        self.assertEqual(BlogSeedImport.objects.get(slug=SUMMARY).content_hash, content_hash(row_values(post)))

    def test_an_edited_orphan_is_left_alone(self):
        old_seed_row(ORPHAN, body="An article an admin wrote under this slug.")
        out = seed()
        post = BlogPost.objects.get(slug=ORPHAN)
        self.assertTrue(post.is_published)
        self.assertEqual(post.body, "An article an admin wrote under this slug.")
        self.assertIn(f"keep {ORPHAN}", out)

    def test_dry_run_reports_and_writes_nothing(self):
        old_seed_row(STUB, first_production_run=True)
        old_seed_row(SUMMARY, title="An admin's title")
        old_seed_row(ORPHAN)
        before = list(BlogPost.objects.order_by("slug").values())
        out = seed("--dry-run")
        self.assertEqual(list(BlogPost.objects.order_by("slug").values()), before)
        self.assertFalse(BlogSeedImport.objects.exists())
        self.assertIn(f"[DRY-RUN] update {STUB}", out)
        self.assertIn(f"[DRY-RUN] keep {SUMMARY}", out)
        self.assertIn(f"[DRY-RUN] unpublish {ORPHAN}", out)
        self.assertIn(f"Would be created: {len(BLOG_POSTS) - 2}, updated: 1", out)


def record(slug, **changes):
    data = {"slug": slug, "title": f"Static {slug}", "description": "d", "excerpt": "e", "category": "UPSC CMS",
            "author": "CrackCMS Editorial Team", "author_role": "Clinical Content Editors, CrackCMS",
            "date_published": "2026-10-01", "reading_time": "5 min", "tags": ["UPSC CMS"],
            "body": f"## {slug}\n\nA real article body, version 1."}
    data.update(changes)
    return data


class AdminChangesSurviveDeploysTests(TestCase):
    """A small patched snapshot, edited through the admin API between deploys."""

    V1 = [record("post-a"), record("post-b")]
    V2 = [record("post-a", body="## post-a\n\nVersion 2."), record("post-b", body="## post-b\n\nVersion 2.")]

    def setUp(self):
        self.admin = User.objects.create_user(username="blog_seed_admin", password="x-Strong-Pass-1", role="admin")
        self.api = APIClient()
        self.api.force_authenticate(self.admin)

    def seed(self, snapshot, *args):
        with patch(f"{COMMAND}.BLOG_POSTS", snapshot), patch(f"{COMMAND}.LEGACY_FINGERPRINTS", {}):
            return seed(*args)

    def post(self, slug):
        return BlogPost.objects.get(slug=slug)

    def test_an_admin_edit_survives_and_unedited_posts_follow_their_static_file(self):
        self.seed(self.V1)
        r = self.api.patch(f"/api/blog/posts/{self.post('post-a').id}/", {"title": "Admin title"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        out = self.seed(self.V2)  # the static files changed, then a deploy
        self.assertEqual((self.post("post-a").title, self.post("post-a").body),
                         ("Admin title", "## post-a\n\nA real article body, version 1."))
        self.assertEqual(self.post("post-b").body, "## post-b\n\nVersion 2.")
        self.assertIn("keep post-a: edited in the admin", out)
        self.assertIn("update post-b (not edited since it was imported)", out)

        self.seed(self.V2, "--update")
        self.assertEqual((self.post("post-a").title, self.post("post-a").body), ("Static post-a", "## post-a\n\nVersion 2."))

    def test_an_unpublished_post_stays_unpublished_when_its_static_file_changes(self):
        self.seed(self.V1)
        r = self.api.post(f"/api/blog/posts/{self.post('post-a').id}/toggle-publish/")
        self.assertEqual((r.status_code, r.data["is_published"]), (200, False))
        self.seed(self.V2)
        post = self.post("post-a")
        self.assertEqual((post.body, post.is_published), ("## post-a\n\nVersion 2.", False))

    def test_deleted_and_renamed_posts_are_not_recreated(self):
        self.seed(self.V1)
        self.assertEqual(self.api.delete(f"/api/blog/posts/{self.post('post-a').id}/").status_code, 204)
        r = self.api.patch(f"/api/blog/posts/{self.post('post-b').id}/", {"slug": "post-b-renamed"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        out = self.seed(self.V2)
        self.assertEqual(sorted(BlogPost.objects.values_list("slug", flat=True)), ["post-b-renamed"])
        self.assertIn("skip post-a: deleted or renamed in the admin", out)
        self.assertIn("skip post-b:", out)

        out = self.seed(self.V2, "--restore", "--slug", "post-a")
        self.assertTrue(self.post("post-a").is_published)
        self.assertEqual(self.post("post-a").body, "## post-a\n\nVersion 2.")
        self.assertFalse(BlogPost.objects.filter(slug="post-b").exists(), "--slug limits the run")
        self.assertIn("re-create post-a", out)

    def test_a_stub_record_is_never_published(self):
        self.seed([record("stub-post", body="Full article content here.")])
        self.assertFalse(self.post("stub-post").is_published)

    def test_clear_resets_to_the_static_posts(self):
        self.seed(self.V1)
        self.api.patch(f"/api/blog/posts/{self.post('post-a').id}/", {"title": "Admin title"}, format="json")
        r = self.api.post("/api/blog/posts/", {**record("admin-post"), "is_published": True}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.seed(self.V1, "--clear")
        self.assertEqual(sorted(BlogPost.objects.values_list("slug", flat=True)), ["post-a", "post-b"])
        self.assertEqual(self.post("post-a").title, "Static post-a")
        self.assertEqual(BlogSeedImport.objects.count(), 2)

    def test_an_unknown_slug_is_reported(self):
        out = self.seed(self.V1, "--slug", "no-such-post", "--dry-run")
        self.assertIn("No static post has the slug 'no-such-post'", out)
        self.assertFalse(BlogPost.objects.exists())


class SeedDataFileTests(TestCase):
    def test_a_malformed_snapshot_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "posts.json"
            path.write_text(json.dumps({"posts": [{"slug": "x", "title": "No body"}]}), encoding="utf-8")
            with self.assertRaisesRegex(SeedDataError, "missing"):
                load_static_posts(path)
            path.write_text(json.dumps({"posts": [record("x"), record("x")]}), encoding="utf-8")
            with self.assertRaisesRegex(SeedDataError, "duplicate slug"):
                load_static_posts(path)
            path.write_text(json.dumps({"posts": [record("x", colour="red")]}), encoding="utf-8")
            with self.assertRaisesRegex(SeedDataError, "unknown"):
                load_static_posts(path)
            path.write_text("not json", encoding="utf-8")
            with self.assertRaisesRegex(SeedDataError, "cannot read"):
                load_static_posts(path)

    def test_the_command_fails_cleanly_on_a_broken_snapshot(self):
        with patch(f"{COMMAND}._LOAD_ERROR", SeedDataError("broken snapshot")):
            with self.assertRaisesRegex(CommandError, "broken snapshot"):
                seed()
