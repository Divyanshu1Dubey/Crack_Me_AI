"""The blog API behind /admin/blog and the public /blog pages.

Public reads (list, retrieve, by-slug, catalog) show published posts with a
real body only, whoever asks (the catalog even to admins); drafts and every
write need a blog admin: role 'admin' / superuser (the /admin pages' rule) or
a staff account. Writes are validated so a saved post cannot break its page.
"""
from __future__ import annotations

import copy

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from blog_engine.management.commands.seed_blogs import BLOG_POSTS
from blog_engine.models import BlogPost
from blog_engine.seeding import CONTENT_FIELDS
from blog_engine.serializers import BlogPostSerializer
from blog_engine.views import BlogPostViewSet, BlogReadThrottle

User = get_user_model()
BASE = {"description": "d", "excerpt": "e", "category": "UPSC CMS", "author": "CrackCMS Editorial Team",
        "author_role": "Clinical Content Editors, CrackCMS", "date_published": "2026-10-01"}


def rows(response):
    data = response.data
    return data if isinstance(data, list) else data["results"]


def full_payload(**changes):
    payload = {
        "slug": "renal-physiology-in-ten-minutes",
        "title": "Renal Physiology in Ten Minutes",
        "description": "GFR, tubular transport and acid-base for UPSC CMS, in ten minutes.",
        "excerpt": "The renal facts UPSC CMS asks every year.",
        "cover_image": "",
        "category": "Subject Prep",
        "subcategory": "Physiology",
        "tags": ["Physiology", "Renal", "UPSC CMS"],
        "difficulty": "advanced",
        "author_id": "crackcms-editorial",
        "reviewed_by": "crackcms-editorial",
        "author": "CrackCMS Editorial Team",
        "author_role": "Clinical Content Editors, CrackCMS",
        "date_published": "2026-11-04",
        "date_modified": "2026-11-04",
        "updated_at": "2026-11-04",
        "reading_time": "10 min",
        "word_count": 1200,
        "primary_cta": {"label": "Practise renal PYQs", "href": "/questions?exam=cms&subject=physiology",
                        "event_name": "blog_practice_intent", "event_params": {"source": "renal", "surface": "hero"}},
        "related_exam_paths": ["/cms", "/neet-pg"],
        "faqs": [{"q": "What is a normal GFR?", "a": "About 125 mL/min."}],
        "toc": [{"id": "gfr", "label": "GFR"}],
        "references": [{"label": "Guyton & Hall, 14th ed."}, {"label": "UPSC", "url": "https://upsc.gov.in/"}],
        "revision_log": [{"date": "2026-11-04", "note": "First published."}],
        "body": "## GFR\n\nGFR is about 125 mL/min.\n\n| Segment | Reabsorbs |\n|---|---|\n| PCT | 65% |",
        "prelude": "",
        "outro": "",
        "pinned": True,
        "trending": False,
        "is_published": True,
    }
    payload.update(changes)
    return payload


class BlogApiTestCase(TestCase):
    def setUp(self):
        self.anon = APIClient()
        self.student = self.client_for(User.objects.create_user(username="blog_student", password="x-Strong-Pass-1"))
        self.admin = self.client_for(User.objects.create_user(username="blog_admin", password="x-Strong-Pass-1",
                                                              role="admin"))
        self.staff = self.client_for(User.objects.create_user(username="blog_staff", password="x-Strong-Pass-1",
                                                              is_staff=True))
        self.pub = BlogPost.objects.create(slug="pub", title="P", body="## Real\n\nA real body.", is_published=True, **BASE)
        self.draft = BlogPost.objects.create(slug="draft", title="D", body="A draft body.", is_published=False, **BASE)
        self.stub = BlogPost.objects.create(slug="stub", title="S", body="Full article content here.",
                                            is_published=True, **BASE)

    @staticmethod
    def client_for(user):
        client = APIClient()
        client.force_authenticate(user)
        return client


class PublicReadTests(BlogApiTestCase):
    def test_anonymous_and_students_read_published_posts_with_a_body_only(self):
        for client in (self.anon, self.student):
            self.assertEqual([r["slug"] for r in rows(client.get("/api/blog/posts/"))], ["pub"])
            self.assertEqual([r["slug"] for r in rows(client.get("/api/blog/posts/catalog/"))], ["pub"])
            self.assertEqual(client.get("/api/blog/posts/by-slug/pub/").status_code, 200)
            for slug in ("draft", "stub", "missing"):
                self.assertEqual(client.get(f"/api/blog/posts/by-slug/{slug}/").status_code, 404, slug)
            for post in (self.draft, self.stub):
                self.assertEqual(client.get(f"/api/blog/posts/{post.id}/").status_code, 404, post.slug)
            self.assertEqual(client.get("/api/blog/posts/", {"is_published": "false"}).data["count"], 0)

    def test_admins_see_drafts_but_the_catalog_stays_public_only(self):
        for client in (self.admin, self.staff):
            self.assertEqual({r["slug"] for r in rows(client.get("/api/blog/posts/"))}, {"pub", "draft", "stub"})
            self.assertEqual(client.get("/api/blog/posts/by-slug/draft/").status_code, 200)
            self.assertEqual([r["slug"] for r in rows(client.get("/api/blog/posts/catalog/"))], ["pub"])
        drafts = rows(self.admin.get("/api/blog/posts/", {"is_published": "false"}))
        self.assertEqual([r["slug"] for r in drafts], ["draft"])

    def test_the_catalog_carries_the_summary_fields_without_bodies(self):
        response = self.anon.get("/api/blog/posts/catalog/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        row = response.data["results"][0]
        for name in ("slug", "title", "description", "excerpt", "category", "subcategory", "tags", "difficulty",
                     "author_id", "reviewed_by", "author", "author_role", "date_published", "date_modified",
                     "updated_at", "reading_time", "word_count", "pinned", "trending", "is_published", "is_stub"):
            self.assertIn(name, row)
        self.assertNotIn("body", row)
        self.assertFalse(row["is_stub"])

    def test_admin_list_rows_flag_stubs(self):
        flags = {r["slug"]: r["is_stub"] for r in rows(self.admin.get("/api/blog/posts/"))}
        self.assertEqual(flags, {"pub": False, "draft": False, "stub": True})

    def test_posts_of_the_same_day_list_the_newest_created_first(self):
        BlogPost.objects.all().delete()
        for slug in ("first", "second", "third"):
            BlogPost.objects.create(slug=slug, title=slug, body="Body.", **BASE)
        self.assertEqual([r["slug"] for r in rows(self.anon.get("/api/blog/posts/catalog/"))],
                         ["third", "second", "first"])

    def test_search_matches_the_slug_and_the_category(self):
        BlogPost.objects.create(slug="zq-unique-slug", title="T", body="Body.", **{**BASE, "category": "Zqcategory"})
        self.assertEqual([r["slug"] for r in rows(self.anon.get("/api/blog/posts/", {"search": "zq-unique"}))],
                         ["zq-unique-slug"])
        self.assertEqual([r["slug"] for r in rows(self.anon.get("/api/blog/posts/", {"search": "zqcategory"}))],
                         ["zq-unique-slug"])

    def test_public_reads_have_their_own_generous_throttle(self):
        self.assertEqual(BlogReadThrottle().get_rate(), "1200/min")
        view = BlogPostViewSet()
        for action in ("list", "retrieve", "by_slug", "catalog"):
            view.action = action
            self.assertIn(BlogReadThrottle, [type(t) for t in view.get_throttles()], action)
        view.action = "create"
        self.assertNotIn(BlogReadThrottle, [type(t) for t in view.get_throttles()])


class WritePermissionTests(BlogApiTestCase):
    def test_anonymous_and_students_cannot_write_or_see_facets(self):
        for client in (self.anon, self.student):
            expected = (401, 403) if client is self.anon else (403,)
            self.assertIn(client.post("/api/blog/posts/", full_payload(), format="json").status_code, expected)
            self.assertIn(client.patch(f"/api/blog/posts/{self.pub.id}/", {"title": "X"}, format="json").status_code,
                          expected)
            self.assertIn(client.delete(f"/api/blog/posts/{self.pub.id}/").status_code, expected)
            self.assertIn(client.post(f"/api/blog/posts/{self.draft.id}/toggle-publish/").status_code, expected)
            self.assertIn(client.get("/api/blog/posts/facets/").status_code, expected)
        self.pub.refresh_from_db()
        self.draft.refresh_from_db()
        self.assertEqual((self.pub.title, self.draft.is_published), ("P", False))
        self.assertEqual(BlogPost.objects.count(), 3)

    def test_a_role_admin_without_staff_can_do_everything(self):
        r = self.admin.post("/api/blog/posts/", full_payload(), format="json")
        self.assertEqual(r.status_code, 201, r.data)
        created = BlogPost.objects.get(slug="renal-physiology-in-ten-minutes")
        detail = self.admin.get(f"/api/blog/posts/{created.id}/").data
        for name, value in full_payload().items():
            self.assertEqual(detail[name], value, name)

        r = self.admin.patch(f"/api/blog/posts/{created.id}/", {"title": "Renal, revised", "faqs": []}, format="json")
        self.assertEqual((r.status_code, r.data["title"], r.data["faqs"]), (200, "Renal, revised", []))
        r = self.admin.post(f"/api/blog/posts/{created.id}/toggle-publish/")
        self.assertEqual((r.status_code, r.data["is_published"]), (200, False))
        self.assertEqual(self.anon.get("/api/blog/posts/by-slug/renal-physiology-in-ten-minutes/").status_code, 404)
        r = self.admin.post(f"/api/blog/posts/{created.id}/toggle-publish/")
        self.assertEqual(r.data["is_published"], True)
        self.assertEqual(self.anon.get("/api/blog/posts/by-slug/renal-physiology-in-ten-minutes/").status_code, 200)

        self.assertEqual(self.admin.delete(f"/api/blog/posts/{created.id}/").status_code, 204)
        self.assertFalse(BlogPost.objects.filter(slug="renal-physiology-in-ten-minutes").exists())

    def test_staff_accounts_keep_write_access(self):
        r = self.staff.post("/api/blog/posts/", full_payload(slug="staff-post"), format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self.staff.delete(f"/api/blog/posts/{r.data['id']}/").status_code, 204)

    def test_facets_count_every_post(self):
        BlogPost.objects.create(slug="career", title="C", body="Body.", **{**BASE, "category": "Career"})
        r = self.admin.get("/api/blog/posts/facets/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.data["total"], r.data["published"], r.data["drafts"]), (4, 3, 1))
        self.assertEqual(r.data["categories"], [{"name": "UPSC CMS", "count": 3}, {"name": "Career", "count": 1}])


class WriteValidationTests(BlogApiTestCase):
    def assert_rejected(self, field, **changes):
        r = self.admin.post("/api/blog/posts/", full_payload(**changes), format="json")
        self.assertEqual(r.status_code, 400, (field, changes))
        self.assertIn(field, r.data, (field, r.data))

    def test_what_would_break_a_public_page_is_rejected(self):
        self.assert_rejected("slug", slug="Has Spaces")
        self.assert_rejected("slug", slug="category")
        self.assert_rejected("slug", slug="pub")  # taken
        self.assert_rejected("date_published", date_published="04/11/2026")
        self.assert_rejected("date_modified", date_modified="2026-02-30")
        self.assert_rejected("primary_cta", primary_cta={"label": "Go", "href": "javascript:alert(1)"})
        self.assert_rejected("primary_cta", primary_cta={"label": "Go", "href": "//evil.example"})
        self.assert_rejected("primary_cta", primary_cta={"label": "Go"})
        self.assert_rejected("primary_cta", primary_cta={"label": "Go", "href": "/x", "colour": "red"})
        self.assert_rejected("faqs", faqs="not a list")
        self.assert_rejected("faqs", faqs=[{"q": "Only a question"}])
        self.assert_rejected("toc", toc=[{"id": "Has Space", "label": "L"}])
        self.assert_rejected("references", references=[{"label": "L", "url": "javascript:alert(1)"}])
        self.assert_rejected("revision_log", revision_log=[{"date": "yesterday", "note": "n"}])
        self.assert_rejected("related_exam_paths", related_exam_paths=["https://example.com"])
        self.assert_rejected("cover_image", cover_image="javascript:alert(1)")
        self.assert_rejected("tags", tags="UPSC CMS")
        self.assert_rejected("is_published", body="Full article content here.", is_published=True)
        self.assert_rejected("is_published", body="   ", is_published=True)

    def test_inputs_are_normalised(self):
        r = self.admin.post("/api/blog/posts/", full_payload(
            tags=[" Renal ", "renal", "", "UPSC CMS"],
            primary_cta={"label": " Practise ", "href": "/questions", "eventName": "blog_practice_intent"},
            faqs=[{"q": " Q? ", "a": " A. "}],
        ), format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["tags"], ["Renal", "UPSC CMS"])
        self.assertEqual(r.data["primary_cta"], {"label": "Practise", "href": "/questions",
                                                 "event_name": "blog_practice_intent"})
        self.assertEqual(r.data["faqs"], [{"q": "Q?", "a": "A."}])

    def test_a_draft_may_have_no_body_yet_but_cannot_be_published(self):
        r = self.admin.post("/api/blog/posts/", full_payload(slug="empty-draft", body="", is_published=False),
                            format="json")
        self.assertEqual(r.status_code, 201, r.data)
        r = self.admin.post(f"/api/blog/posts/{r.data['id']}/toggle-publish/")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(BlogPost.objects.get(slug="empty-draft").is_published)
        # Unpublishing a legacy published stub still works.
        r = self.admin.post(f"/api/blog/posts/{self.stub.id}/toggle-publish/")
        self.assertEqual((r.status_code, r.data["is_published"]), (200, False))

    def test_every_static_post_can_be_saved_unchanged(self):
        """An admin saving a seeded post without edits changes nothing (and is not refused)."""
        for record in BLOG_POSTS:
            serializer = BlogPostSerializer(data={**copy.deepcopy(record), "is_published": True})
            self.assertTrue(serializer.is_valid(), (record["slug"], serializer.errors))
            for name in CONTENT_FIELDS:
                if name in ("cover_image", "word_count") or name not in serializer.validated_data:
                    continue
                self.assertEqual(serializer.validated_data[name], record[name], f"{record['slug']}.{name}")
