"""Infrastructure/config regressions (audit group G6): client IP parsing,
pagination page_size, CORS If-Match, API cache headers, CORP on images,
SimpleJWT blacklist consistency, test_all.py import side effects and the
production posture check."""
from __future__ import annotations

import importlib
import importlib.util
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import clear_url_caches
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.test import APIRequestFactory

from crack_cms.cache_middleware import DisableApiCacheMiddleware
from crack_cms.client_ip import get_client_ip, header_to_meta_key, parse_num_proxies
from crack_cms.cross_origin import CrossOriginResourcePolicyMiddleware


def _png_bytes(size=(40, 20)):
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", size, color="blue").save(buf, format="PNG")
    return buf.getvalue()


class ClientIpTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_parse_num_proxies(self):
        self.assertIsNone(parse_num_proxies(None))
        self.assertIsNone(parse_num_proxies(""))
        self.assertIsNone(parse_num_proxies("  "))
        self.assertIsNone(parse_num_proxies("abc"))
        self.assertIsNone(parse_num_proxies("-1"))
        self.assertEqual(parse_num_proxies("0"), 0)
        self.assertEqual(parse_num_proxies(" 2 "), 2)

    def test_header_to_meta_key(self):
        self.assertEqual(header_to_meta_key("CF-Connecting-IP"), "HTTP_CF_CONNECTING_IP")
        self.assertEqual(header_to_meta_key("do-connecting-ip"), "HTTP_DO_CONNECTING_IP")
        self.assertEqual(header_to_meta_key("HTTP_X_REAL_IP"), "HTTP_X_REAL_IP")
        self.assertEqual(header_to_meta_key(""), "")

    def test_default_ignores_forwarded_for(self):
        request = self.factory.get("/", REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="203.0.113.9")
        self.assertEqual(get_client_ip(request), "10.0.0.1")

    def test_num_proxies_reads_from_the_right(self):
        conf = {**settings.REST_FRAMEWORK, "NUM_PROXIES": 2}
        with override_settings(REST_FRAMEWORK=conf):
            request = self.factory.get(
                "/", REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="6.6.6.6, 203.0.113.9, 172.16.0.4",
            )
            self.assertEqual(get_client_ip(request), "203.0.113.9")
            # Garbage in the trusted slot falls back to REMOTE_ADDR.
            request = self.factory.get("/", REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="x, not-an-ip, y")
            self.assertEqual(get_client_ip(request), "10.0.0.1")

    def test_num_proxies_zero_means_remote_addr(self):
        conf = {**settings.REST_FRAMEWORK, "NUM_PROXIES": 0}
        with override_settings(REST_FRAMEWORK=conf):
            request = self.factory.get("/", REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="203.0.113.9")
            self.assertEqual(get_client_ip(request), "10.0.0.1")

    def test_platform_header_with_port_and_ipv6(self):
        with override_settings(TRUSTED_CLIENT_IP_HEADER="X-Real-IP"):
            request = self.factory.get("/", REMOTE_ADDR="10.0.0.1", HTTP_X_REAL_IP="203.0.113.7:51234")
            self.assertEqual(get_client_ip(request), "203.0.113.7")
            request = self.factory.get("/", REMOTE_ADDR="10.0.0.1", HTTP_X_REAL_IP="[2001:db8::1]:443")
            self.assertEqual(get_client_ip(request), "2001:db8::1")

    def test_drf_throttles_share_the_num_proxies_setting(self):
        self.assertIn("NUM_PROXIES", settings.REST_FRAMEWORK)
        self.assertEqual(settings.REST_FRAMEWORK["NUM_PROXIES"], settings.NUM_PROXIES)


class _PaginatedTopicList(ListAPIView):
    """A list view on the project's default pagination class. (The taxonomy
    endpoints these tests used are unpaginated since contract C7.)"""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get_queryset(self):
        from questions.models import Topic

        return Topic.objects.filter(subject__code="PGN").order_by("name")

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response([topic.name for topic in page])


class PaginationTests(TestCase):
    """FE-STU-11: ?page_size= was ignored, so every list stopped at 20 rows."""

    @classmethod
    def setUpTestData(cls):
        from questions.models import Subject, Topic

        subject = Subject.objects.create(name="Pagination Subject", code="PGN")
        Topic.objects.bulk_create(
            [Topic(subject=subject, name=f"Topic {i:03d}") for i in range(130)]
        )
        cls.subject = subject

    def setUp(self):
        cache.clear()

    def _results(self, query="", url=None):
        from urllib.parse import urlsplit

        target = url or f"/paginated/?subject={self.subject.pk}{query}"
        parts = urlsplit(target)
        request = APIRequestFactory().get(f"{parts.path}?{parts.query}")
        response = _PaginatedTopicList.as_view()(request)
        self.assertEqual(response.status_code, 200)
        return response.data

    def test_default_class_is_configured(self):
        self.assertEqual(
            settings.REST_FRAMEWORK["DEFAULT_PAGINATION_CLASS"],
            "crack_cms.pagination.StandardResultsSetPagination",
        )
        self.assertEqual(settings.REST_FRAMEWORK["PAGE_SIZE"], 20)

    def test_default_page_is_still_20_with_the_same_shape(self):
        data = self._results()
        self.assertEqual(set(data), {"count", "next", "previous", "results"})
        self.assertEqual(len(data["results"]), 20)

    def test_page_size_is_honoured(self):
        self.assertEqual(len(self._results("&page_size=25")["results"]), 25)
        self.assertEqual(len(self._results("&page_size=100")["results"]), 100)

    def test_page_size_is_capped_at_100(self):
        data = self._results("&page_size=500")
        self.assertEqual(len(data["results"]), 100)
        self.assertIn("page=2", data["next"])

    def test_invalid_page_size_falls_back_to_default(self):
        for value in ("0", "-5", "abc", ""):
            self.assertEqual(len(self._results(f"&page_size={value}")["results"]), 20, value)

    def test_next_link_keeps_page_size(self):
        data = self._results("&page_size=50")
        self.assertIn("page_size=50", data["next"])
        second = self._results(url=data["next"])
        self.assertEqual(len(second["results"]), 50)
        self.assertNotEqual(second["results"][0], data["results"][0])


@override_settings(CORS_ALLOWED_ORIGINS=["https://frontend.example.test"])
class CorsIfMatchTests(TestCase):
    """ADM-03: PATCH with If-Match (optimistic locking) failed its preflight."""

    def test_if_match_is_an_allowed_cors_header(self):
        self.assertIn("if-match", [h.lower() for h in settings.CORS_ALLOW_HEADERS])

    def test_preflight_allows_if_match(self):
        origin = "https://frontend.example.test"
        response = self.client.options(
            "/api/questions/1/",
            HTTP_ORIGIN=origin,
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="PATCH",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="authorization, content-type, if-match",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get("Access-Control-Allow-Origin"), origin)
        allowed = [h.strip().lower() for h in response.get("Access-Control-Allow-Headers", "").split(",")]
        self.assertIn("if-match", allowed)


class ApiCacheHeaderTests(SimpleTestCase):
    """CFG-20: the global no-cache middleware overwrote the image view's
    Cache-Control."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_explicit_cache_control_is_kept(self):
        def view(request):
            response = HttpResponse(b"img", content_type="image/png")
            response["Cache-Control"] = "private, max-age=3600"
            return response

        response = DisableApiCacheMiddleware(view)(self.factory.get("/api/questions/images/1/serve/"))
        self.assertEqual(response["Cache-Control"], "private, max-age=3600")

    def test_api_responses_without_cache_control_are_never_cached(self):
        response = DisableApiCacheMiddleware(lambda r: HttpResponse("{}"))(self.factory.get("/api/questions/"))
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("max-age=0", response["Cache-Control"])

    def test_non_api_paths_are_untouched(self):
        response = DisableApiCacheMiddleware(lambda r: HttpResponse("ok"))(self.factory.get("/admin/login/"))
        self.assertFalse(response.has_header("Cache-Control"))


class CrossOriginResourcePolicyTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_image_responses_are_cross_origin(self):
        middleware = CrossOriginResourcePolicyMiddleware(lambda r: HttpResponse(b"x", content_type="image/jpeg"))
        response = middleware(self.factory.get("/api/textbooks/1/screenshot/"))
        self.assertEqual(response["Cross-Origin-Resource-Policy"], "cross-origin")

    def test_serve_endpoint_redirects_are_cross_origin(self):
        from django.http import HttpResponseRedirect

        middleware = CrossOriginResourcePolicyMiddleware(
            lambda r: HttpResponseRedirect("https://example.supabase.co/storage/v1/object/public/x.png")
        )
        response = middleware(self.factory.get("/api/questions/images/9/serve/"))
        self.assertEqual(response["Cross-Origin-Resource-Policy"], "cross-origin")

    def test_json_responses_get_no_policy(self):
        middleware = CrossOriginResourcePolicyMiddleware(
            lambda r: HttpResponse("{}", content_type="application/json")
        )
        response = middleware(self.factory.get("/api/questions/"))
        self.assertFalse(response.has_header("Cross-Origin-Resource-Policy"))

    def test_a_view_policy_is_kept(self):
        def view(request):
            response = HttpResponse(b"x", content_type="image/png")
            response["Cross-Origin-Resource-Policy"] = "same-site"
            return response

        response = CrossOriginResourcePolicyMiddleware(view)(self.factory.get("/api/questions/images/1/serve/"))
        self.assertEqual(response["Cross-Origin-Resource-Policy"], "same-site")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ImageServeHeadersTests(TestCase):
    """End to end: the serve view's headers survive the middleware stack."""

    @classmethod
    def setUpTestData(cls):
        from questions.models import Question, QuestionImage, Subject

        subject = Subject.objects.create(name="Image Headers", code="IMH")
        question = Question.objects.create(
            question_text="Identify the sign.", option_a="A", option_b="B", option_c="C", option_d="D",
            correct_answer="A", year=2024, subject=subject,
        )
        cls.image = QuestionImage.objects.create(
            question=question, page_number=0,
            file=SimpleUploadedFile("sign.png", _png_bytes(), content_type="image/png"),
            mime="image/png", width=40, height=20,
        )

    def setUp(self):
        cache.clear()

    def test_raw_image_keeps_cache_control_and_gets_corp(self):
        response = self.client.get(f"/api/questions/images/{self.image.pk}/serve/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, max-age=3600")
        self.assertEqual(response["Cross-Origin-Resource-Policy"], "cross-origin")

    def test_resized_image_keeps_cache_control_and_gets_corp(self):
        response = self.client.get(f"/api/questions/images/{self.image.pk}/serve/?w=10")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, max-age=3600")
        self.assertEqual(response["Cross-Origin-Resource-Policy"], "cross-origin")

    def test_other_api_responses_are_still_never_cached(self):
        response = self.client.get("/api/questions/topics/")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertFalse(response.has_header("Cross-Origin-Resource-Policy"))


VERCEL_JSON = Path(settings.BASE_DIR).parent / "frontend" / "vercel.json"


@unittest.skipUnless(VERCEL_JSON.exists(), "frontend/vercel.json not in this checkout")
class FrontendSecurityHeadersTests(SimpleTestCase):
    """CFG-04 / CSP-01 / PUB-29: the Vercel CSP blocked Razorpay checkout (the
    only purchase flow) and the analytics loaders, and COEP require-corp
    blocked cross-origin question images and the Razorpay iframe."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        import json

        config = json.loads(VERCEL_JSON.read_text(encoding="utf-8"))
        # The site-wide block; /ads/(.*) is the sandboxed partner-ad pages (own, looser CSP).
        cls.headers = {h["key"]: h["value"] for block in config["headers"]
                       if block["source"] != "/ads/(.*)" for h in block["headers"]}
        cls.csp = {}
        for directive in cls.headers["Content-Security-Policy"].split(";"):
            parts = directive.split()
            if parts:
                cls.csp[parts[0]] = parts[1:]

    def test_razorpay_checkout_is_allowed(self):
        self.assertIn("https://checkout.razorpay.com", self.csp["script-src"])
        self.assertIn("https://api.razorpay.com", self.csp["frame-src"])
        self.assertIn("https://checkout.razorpay.com", self.csp["frame-src"])
        self.assertIn("https://api.razorpay.com", self.csp["connect-src"])
        self.assertIn("https://lumberjack.razorpay.com", self.csp["connect-src"])

    def test_no_embedder_policy_that_blocks_cross_origin_embeds(self):
        self.assertNotEqual(self.headers.get("Cross-Origin-Embedder-Policy"), "require-corp")
        # Razorpay's payment-method popups need their opener reference.
        self.assertEqual(self.headers["Cross-Origin-Opener-Policy"], "same-origin-allow-popups")

    def test_loaded_analytics_hosts_are_allowed(self):
        self.assertIn("https://*.clarity.ms", self.csp["script-src"])
        self.assertIn("https://*.clarity.ms", self.csp["connect-src"])
        self.assertIn("https://*.posthog.com", self.csp["script-src"])
        self.assertIn("https://*.posthog.com", self.csp["connect-src"])
        self.assertIn("https://browser-intake-datadoghq.com", self.csp["connect-src"])
        self.assertIn("blob:", self.csp["worker-src"])
        self.assertIn("https://giscus.app", self.csp["frame-src"])

    def test_api_origin_and_question_videos_are_allowed(self):
        self.assertIn("https://api.cracklabs.app", self.csp["connect-src"])
        self.assertIn("https://*.supabase.co", self.csp["media-src"])


class SimpleJwtConfigTests(SimpleTestCase):
    """CFG-27: blacklist-after-rotation was on without the blacklist app."""

    def test_blacklist_flag_matches_installed_apps(self):
        installed = "rest_framework_simplejwt.token_blacklist" in settings.INSTALLED_APPS
        if not installed:
            self.assertFalse(settings.SIMPLE_JWT["BLACKLIST_AFTER_ROTATION"])


class TestAllScriptImportTests(SimpleTestCase):
    """CFG-17: backend/test_all.py matched test*.py, so the test runner
    imported it, which ran load_dotenv(override=True) and django.setup()."""

    SCRIPT = Path(settings.BASE_DIR) / "test_all.py"

    def _load(self):
        spec = importlib.util.spec_from_file_location("test_all_import_probe", self.SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_importing_has_no_side_effects(self):
        before = dict(os.environ)
        with mock.patch("dotenv.load_dotenv", side_effect=AssertionError("load_dotenv called")), \
                mock.patch("django.setup", side_effect=AssertionError("django.setup called")):
            module = self._load()
        self.assertEqual(dict(os.environ), before)
        self.assertFalse(module.__test__)

    def test_unittest_collects_nothing(self):
        module = self._load()
        suite = unittest.defaultTestLoader.loadTestsFromModule(module)
        self.assertEqual(suite.countTestCases(), 0)

    def test_script_never_overrides_the_environment(self):
        # Env loading is left to settings.py (DJANGO_ENV_FILE / .env, no
        # override); the script must not reload .env itself.
        source = self.SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("load_dotenv(", source)


class SecurityPostureCheckTests(SimpleTestCase):
    """CFG-25: the check's ImproperlyConfigured was swallowed as an
    'import failure'."""

    def tearDown(self):
        import crack_cms.urls

        importlib.reload(crack_cms.urls)
        clear_url_caches()

    def test_fatal_posture_error_is_not_swallowed(self):
        import crack_cms.urls

        with mock.patch(
            "crack_cms.security.security_posture_check",
            side_effect=ImproperlyConfigured("DJANGO_SECRET_KEY must be set"),
        ):
            with self.assertRaises(ImproperlyConfigured):
                importlib.reload(crack_cms.urls)

    def test_check_runs_and_passes_outside_production(self):
        import crack_cms.urls

        with mock.patch("crack_cms.security.security_posture_check") as check:
            importlib.reload(crack_cms.urls)
        check.assert_called_once()
        self.assertEqual(set(check.call_args.kwargs), {"is_production", "is_ci"})
        # The real check is a no-op outside production, so the reload in
        # tearDown (unpatched) must succeed as well.
