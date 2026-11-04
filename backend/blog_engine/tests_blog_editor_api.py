"""The blog editor's backend: honest counts, thin posts, and blog images.

* ``word_count`` / ``reading_time`` come from the body (BlogPost.body_word_count,
  blog_engine.text_stats), never from the request or the seed's columns.
* /admin/blog filters thin posts (``?thin=true``) and sorts by length.
* ``POST /api/blog/images/`` (blog admins only) stores real raster images under
  MEDIA_ROOT/blog; ``GET /api/blog/images/<name>`` serves them publicly with
  the hardening of QuestionImageServeView.
"""
from __future__ import annotations

import importlib
import io
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from blog_engine.images import STORED_NAME, URL_PREFIX
from blog_engine.management.commands.seed_blogs import BLOG_POSTS
from blog_engine.models import BlogPost
from blog_engine.text_stats import THIN_POST_WORDS, count_words, reading_minutes, reading_time_label

User = get_user_model()
BASE = {"description": "d", "excerpt": "e", "category": "UPSC CMS", "author": "CrackCMS Editorial Team",
        "author_role": "Clinical Content Editors, CrackCMS", "date_published": "2026-10-01"}

# Shared with frontend/tests/unit/blog-article.test.ts (the TypeScript port must agree).
COUNT_VECTORS = [
    ("", 0),
    ("## One two\n\nthree **four**", 4),
    ("1. First item\n2. Second\n- third", 4),
    ("See [the guide](/blog/x) and ![diagram](/a.png) now", 5),
    ("> [!NOTE]\n> Keep it short.", 3),
    ("| Drug | Dose |\n|---|---|\n| Atropine | 0.6 mg |", 5),
    ("Visit https://upsc.gov.in/ today <br> ok <!-- hidden note -->", 3),
    ("pH ~7.4 — normal; e.g. **Na⁺**", 5),
    ("Pédiatrie ça va", 3),
    ("snake_case and C++", 4),
    ("Line one\r\nLine two\\\nLine three", 6),
]


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def results(response):
    data = response.data
    return data if isinstance(data, list) else data["results"]


def png_bytes(size=(3, 2), fmt="PNG") -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", size, (200, 30, 30)).save(buffer, format=fmt)
    return buffer.getvalue()


class CountRuleTests(SimpleTestCase):
    def test_the_shared_vectors(self):
        for markdown, expected in COUNT_VECTORS:
            self.assertEqual(count_words(markdown), expected, repr(markdown))

    def test_reading_time_rounds_half_up_and_is_at_least_a_minute(self):
        cases = {0: 1, 99: 1, 299: 1, 300: 2, 500: 3, 1000: 5, 2731: 14}
        self.assertEqual({words: reading_minutes(words) for words in cases}, cases)
        self.assertEqual(reading_time_label(99), "1 min")

    def test_the_migration_counts_with_the_same_rule(self):
        migration = importlib.import_module("blog_engine.migrations.0004_blogpost_body_word_count")
        for markdown, expected in COUNT_VECTORS:
            self.assertEqual(migration._count_words(markdown), expected, repr(markdown))
        for record in BLOG_POSTS:
            self.assertEqual(migration._count_words(record["body"]), count_words(record["body"]), record["slug"])

    def test_the_seeded_posts_are_honestly_short(self):
        """The seed claims ~2,000 words per post; most bodies are about a hundred words."""
        counts = sorted(count_words(record["body"]) for record in BLOG_POSTS)
        self.assertEqual(len(counts), 129)
        self.assertLess(counts[len(counts) // 2], THIN_POST_WORDS)
        claimed = [record.get("word_count") or 0 for record in BLOG_POSTS]
        self.assertGreater(sum(claimed), 5 * sum(counts))


class ComputedCountTests(TestCase):
    def setUp(self):
        self.admin = client_for(User.objects.create_user(username="ed_admin", password="x-Strong-Pass-1", role="admin"))
        self.anon = APIClient()

    def payload(self, **changes):
        data = {"slug": "computed-counts", "title": "Counts", "author_id": "crackcms-editorial", "tags": [],
                "body": "## GFR\n\n" + "word " * 450, "is_published": True, **BASE}
        data.update(changes)
        return data

    def test_counts_come_from_the_body_not_from_the_request(self):
        r = self.admin.post("/api/blog/posts/", self.payload(word_count=5, reading_time="99 min"), format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data["word_count"], r.data["reading_time"]), (451, "2 min"))
        post = BlogPost.objects.get(slug="computed-counts")
        self.assertEqual(post.body_word_count, 451)
        self.assertEqual((post.word_count, post.reading_time), (None, "10 min"))  # seed metadata untouched

        r = self.admin.patch(f"/api/blog/posts/{post.id}/", {"body": "Short body."}, format="json")
        self.assertEqual((r.status_code, r.data["word_count"], r.data["reading_time"]), (200, 2, "1 min"))
        row = results(self.anon.get("/api/blog/posts/catalog/"))[0]
        self.assertEqual((row["word_count"], row["reading_time"], row["is_thin"]), (2, "1 min", True))
        detail = self.anon.get("/api/blog/posts/by-slug/computed-counts/").data
        self.assertEqual((detail["word_count"], detail["reading_time"]), (2, "1 min"))

    def test_every_save_path_counts_the_body(self):
        post = BlogPost.objects.create(slug="orm-save", title="T", body="One two three.", **BASE)
        self.assertEqual(post.body_word_count, 3)
        post.body = "One two three four five."
        post.save(update_fields=["body"])
        post.refresh_from_db()
        self.assertEqual(post.body_word_count, 5)
        post.title = "Retitled"
        post.save(update_fields=["title"])  # a save of other fields leaves the count alone
        post.refresh_from_db()
        self.assertEqual(post.body_word_count, 5)
        r = self.admin.post(f"/api/blog/posts/{post.id}/toggle-publish/")
        self.assertEqual(r.status_code, 200)
        post.refresh_from_db()
        self.assertEqual(post.body_word_count, 5)

    def test_the_migration_counts_existing_rows(self):
        post = BlogPost.objects.create(slug="legacy-row", title="T", body="Alpha beta gamma delta.", **BASE)
        BlogPost.objects.filter(pk=post.pk).update(body_word_count=0)
        migration = importlib.import_module("blog_engine.migrations.0004_blogpost_body_word_count")
        migration.count_existing_posts(django_apps, None)
        post.refresh_from_db()
        self.assertEqual(post.body_word_count, 4)

    def test_thin_filter_ordering_and_facets(self):
        for slug, words in (("short-one", 30), ("long-one", THIN_POST_WORDS + 20), ("short-two", 80)):
            BlogPost.objects.create(slug=slug, title=slug, body="word " * words, **BASE)
        def slugs(response):
            return [row["slug"] for row in results(response)]

        self.assertEqual(set(slugs(self.admin.get("/api/blog/posts/", {"thin": "true"}))), {"short-one", "short-two"})
        self.assertEqual(slugs(self.admin.get("/api/blog/posts/", {"thin": "false"})), ["long-one"])
        self.assertEqual(slugs(self.admin.get("/api/blog/posts/", {"ordering": "body_word_count"})),
                         ["short-one", "short-two", "long-one"])
        rows = {row["slug"]: row for row in results(self.admin.get("/api/blog/posts/"))}
        self.assertEqual((rows["short-one"]["is_thin"], rows["long-one"]["is_thin"]), (True, False))
        self.assertEqual(rows["long-one"]["word_count"], THIN_POST_WORDS + 20)
        facets = self.admin.get("/api/blog/posts/facets/").data
        self.assertEqual((facets["thin"], facets["thin_words"]), (2, THIN_POST_WORDS))

    def test_seed_blogs_counts_created_and_updated_posts(self):
        def record(body):
            return {"slug": "seeded", "title": "Seeded", "author_id": "crackcms-editorial", "reading_time": "9 min",
                    "word_count": 2700, "tags": [], "body": body, **BASE}

        command = "blog_engine.management.commands.seed_blogs"
        with patch(f"{command}.BLOG_POSTS", [record("One two three.")]), patch(f"{command}.LEGACY_FINGERPRINTS", {}):
            call_command("seed_blogs", stdout=io.StringIO())
        post = BlogPost.objects.get(slug="seeded")
        self.assertEqual((post.body_word_count, post.word_count), (3, 2700))
        with patch(f"{command}.BLOG_POSTS", [record("One two three four five six.")]), \
                patch(f"{command}.LEGACY_FINGERPRINTS", {}):
            call_command("seed_blogs", stdout=io.StringIO())  # untouched since imported -> updated
        post.refresh_from_db()
        self.assertEqual(post.body_word_count, 6)


class BlogImageTests(TestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp(prefix="blog-media-")
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=self.media)
        override.enable()
        self.addCleanup(override.disable)
        self.anon = APIClient()
        self.student = client_for(User.objects.create_user(username="img_student", password="x-Strong-Pass-1"))
        self.admin = client_for(User.objects.create_user(username="img_admin", password="x-Strong-Pass-1", role="admin"))
        self.staff = client_for(User.objects.create_user(username="img_staff", password="x-Strong-Pass-1", is_staff=True))

    def upload(self, client, data, name="figure.png", content_type="image/png"):
        return client.post("/api/blog/images/", {"file": SimpleUploadedFile(name, data, content_type=content_type)},
                           format="multipart")

    def stored_files(self):
        root = Path(self.media) / "blog"
        return sorted(p for p in root.rglob("*") if p.is_file()) if root.exists() else []

    def test_only_blog_admins_upload(self):
        self.assertIn(self.upload(self.anon, png_bytes()).status_code, (401, 403))
        self.assertEqual(self.upload(self.student, png_bytes()).status_code, 403)
        self.assertEqual(self.stored_files(), [])
        for client, size in ((self.admin, (5, 4)), (self.staff, (6, 4))):
            r = self.upload(client, png_bytes(size))
            self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(len(self.stored_files()), 2)

    def test_an_upload_is_stored_once_and_served_publicly_and_hardened(self):
        data = png_bytes((7, 3))
        r = self.upload(self.admin, data)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data["width"], r.data["height"], r.data["mime"], r.data["bytes"]), (7, 3, "image/png", len(data)))
        src = r.data["src"]
        self.assertTrue(src.startswith(URL_PREFIX), src)
        self.assertRegex(src[len(URL_PREFIX):], STORED_NAME)
        self.assertEqual(self.upload(self.admin, data, name="again.png").data["src"], src)  # same bytes, same file
        self.assertEqual(len(self.stored_files()), 1)

        served = self.anon.get(src)
        self.assertEqual(served.status_code, 200)
        self.assertEqual(served["Content-Type"], "image/png")
        self.assertEqual(served["X-Content-Type-Options"], "nosniff")
        self.assertEqual(served["Content-Security-Policy"], "default-src 'none'; sandbox")
        self.assertIn("immutable", served["Cache-Control"])
        self.assertEqual(b"".join(served.streaming_content), data)

    def test_the_type_comes_from_the_content_not_the_name(self):
        r = self.upload(self.admin, png_bytes(fmt="JPEG"), name="photo.png", content_type="image/png")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(r.data["src"].endswith(".jpg"))
        self.assertEqual(self.anon.get(r.data["src"])["Content-Type"], "image/jpeg")
        gif = self.upload(self.admin, png_bytes(fmt="GIF"), name="anim.gif", content_type="image/gif")
        self.assertEqual((gif.status_code, gif.data["mime"]), (201, "image/gif"))

    def test_what_is_not_a_raster_image_is_refused(self):
        svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
        cases = {
            "no file": self.admin.post("/api/blog/images/", {}, format="multipart"),
            "text named .png": self.upload(self.admin, b"just some text, not an image"),
            "svg": self.upload(self.admin, svg, name="x.svg", content_type="image/svg+xml"),
            "svg named .png": self.upload(self.admin, svg),
            "html": self.upload(self.admin, b"<!doctype html><script>alert(1)</script>", name="x.html",
                                content_type="text/html"),
            "truncated png": self.upload(self.admin, png_bytes()[:40]),
            "empty": self.upload(self.admin, b""),
        }
        for label, response in cases.items():
            self.assertEqual(response.status_code, 400, label)
            self.assertIn("file", response.data, label)
        self.assertEqual(self.stored_files(), [])

    def test_size_and_dimension_limits(self):
        with override_settings(BLOG_IMAGE_MAX_BYTES=100):
            r = self.upload(self.admin, png_bytes((40, 40)) + b"\0" * 200)
            self.assertEqual(r.status_code, 400)
            self.assertIn("larger than", str(r.data["file"]))
        with patch("blog_engine.images.MAX_SIDE", 4):
            self.assertEqual(self.upload(self.admin, png_bytes((5, 2))).status_code, 400)
        self.assertEqual(self.stored_files(), [])

    def test_the_serve_view_opens_only_stored_raster_files(self):
        for path in ("/api/blog/images/../../settings.py", "/api/blog/images/2026/11/not-a-hash.png",
                     f"/api/blog/images/2026/11/{'A' * 32}.png", f"/api/blog/images/2026/11/{'a' * 32}.svg",
                     f"/api/blog/images/2026/11/{'a' * 32}.png"):  # well formed, missing
            self.assertEqual(self.anon.get(path).status_code, 404, path)
        planted = Path(self.media) / "blog" / "2026" / "11" / f"{'b' * 32}.png"
        planted.parent.mkdir(parents=True)
        planted.write_bytes(b'<svg xmlns="http://www.w3.org/2000/svg"></svg>')
        self.assertEqual(self.anon.get(f"/api/blog/images/2026/11/{'b' * 32}.png").status_code, 404)
