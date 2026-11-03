"""Question-bank rate limiter (questions/middleware.py): bucket identity,
proxy handling, budget and exemptions (audit issues QB-05 / CFG-06 / AN-23).

The old limiter keyed every GET under /api/questions/ on REMOTE_ADDR with a
60/min budget. Behind the production proxy that address is shared by every
visitor, so a few students produced site-wide 429s, and the image endpoint
spent the same budget.
"""
from __future__ import annotations

import copy
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache, caches
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings

from questions import middleware as rl_middleware
from questions.middleware import RateLimitMiddleware, rate_limit_identity

# Middle of a 60 s window: a test that ran across a window boundary used to
# see its counters reset half-way (flaky 200 instead of 429).
FROZEN_NOW = 1_800_000_030.0


def _rest_framework(**overrides):
    conf = copy.deepcopy(settings.REST_FRAMEWORK)
    conf.update(overrides)
    return conf


class _FrozenLimiterMixin:
    """Freeze the limiter's clock and start every test with empty buckets."""

    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(rl_middleware, "_now", return_value=FROZEN_NOW)
        patcher.start()
        self.addCleanup(patcher.stop)
        cache.clear()
        caches[rl_middleware.CACHE_ALIAS].clear()


@override_settings(
    QUESTION_BANK_RATE_LIMIT=3,
    QUESTION_BANK_RATE_WINDOW=60,
    TRUSTED_CLIENT_IP_HEADER="",
)
class RateLimitIdentityTests(_FrozenLimiterMixin, TestCase):
    """Middleware-level tests with a stand-in for the DRF view."""

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.alice = User.objects.create_user(username="rl_alice", email="rl_alice@example.com", password="x" * 12)
        cls.bob = User.objects.create_user(username="rl_bob", email="rl_bob@example.com", password="x" * 12)

    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        # token -> user, i.e. what DRF's authentication would resolve.
        self.valid_tokens = {"token-alice": self.alice}

    def _view(self, request):
        """Mimic DRF: authenticate the bearer token and copy the user onto
        the Django request (rest_framework.request.Request.user's setter)."""
        header = request.META.get("HTTP_AUTHORIZATION", "")
        if header.startswith("Bearer "):
            request.user = self.valid_tokens.get(header[len("Bearer "):], AnonymousUser())
        return HttpResponse("ok")

    def _get(self, path="/api/questions/", *, user=None, token=None, remote="10.0.0.1", **meta):
        request = self.factory.get(path, REMOTE_ADDR=remote, **meta)
        request.user = user or AnonymousUser()
        if token:
            request.META["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        return RateLimitMiddleware(self._view)(request)

    def _statuses(self, n, **kwargs):
        return [self._get(**kwargs).status_code for _ in range(n)]

    # -- anonymous / IP keying ------------------------------------------------

    def test_anonymous_requests_from_one_address_share_a_bucket(self):
        self.assertEqual(self._statuses(3), [200, 200, 200])
        blocked = self._get()
        self.assertEqual(blocked.status_code, 429)
        self.assertTrue(blocked.has_header("Retry-After"))
        self.assertGreaterEqual(int(blocked["Retry-After"]), 1)
        # A different client address is unaffected.
        self.assertEqual(self._get(remote="10.0.0.2").status_code, 200)

    def test_spoofed_forwarded_for_is_ignored_without_num_proxies(self):
        for i in range(3):
            self.assertEqual(self._get(HTTP_X_FORWARDED_FOR=f"198.51.100.{i}").status_code, 200)
        # A fresh X-Forwarded-For value must not open a fresh bucket.
        self.assertEqual(self._get(HTTP_X_FORWARDED_FOR="198.51.100.99").status_code, 429)

    def test_num_proxies_uses_the_address_appended_by_the_trusted_proxy(self):
        with override_settings(REST_FRAMEWORK=_rest_framework(NUM_PROXIES=1)):
            proxy = "10.9.9.9"
            for _ in range(3):
                self.assertEqual(self._get(remote=proxy, HTTP_X_FORWARDED_FOR="203.0.113.5").status_code, 200)
            self.assertEqual(self._get(remote=proxy, HTTP_X_FORWARDED_FOR="203.0.113.5").status_code, 429)
            # Same client prepending a forged hop: still the same bucket.
            self.assertEqual(
                self._get(remote=proxy, HTTP_X_FORWARDED_FOR="1.2.3.4, 203.0.113.5").status_code, 429,
            )
            # Another client behind the same proxy has its own budget.
            self.assertEqual(self._get(remote=proxy, HTTP_X_FORWARDED_FOR="203.0.113.6").status_code, 200)

    def test_trusted_platform_header_is_honoured_when_configured(self):
        with override_settings(TRUSTED_CLIENT_IP_HEADER="CF-Connecting-IP"):
            for _ in range(3):
                self.assertEqual(self._get(HTTP_CF_CONNECTING_IP="203.0.113.10").status_code, 200)
            self.assertEqual(self._get(HTTP_CF_CONNECTING_IP="203.0.113.10").status_code, 429)
            self.assertEqual(self._get(HTTP_CF_CONNECTING_IP="203.0.113.11").status_code, 200)
            # A value that is not an IP address falls back to REMOTE_ADDR.
            request = self.factory.get("/api/questions/", REMOTE_ADDR="10.0.0.7", HTTP_CF_CONNECTING_IP="not-an-ip")
            request.user = AnonymousUser()
            self.assertEqual(rate_limit_identity(request), "ip:10.0.0.7")

    def test_platform_header_is_ignored_when_not_configured(self):
        for i in range(3):
            self.assertEqual(self._get(HTTP_CF_CONNECTING_IP=f"203.0.113.{20 + i}").status_code, 200)
        self.assertEqual(self._get(HTTP_CF_CONNECTING_IP="203.0.113.99").status_code, 429)

    # -- authenticated keying -------------------------------------------------

    def test_session_users_behind_one_address_get_separate_buckets(self):
        self.assertEqual(self._statuses(3, user=self.alice), [200, 200, 200])
        self.assertEqual(self._get(user=self.alice).status_code, 429)
        # Bob shares Alice's address (same proxy) but not her budget.
        self.assertEqual(self._statuses(3, user=self.bob), [200, 200, 200])
        # Anonymous traffic from that address is a separate bucket too.
        self.assertEqual(self._get().status_code, 200)

    def test_bearer_token_is_keyed_on_the_user_drf_resolved(self):
        from questions.middleware import _bearer_digest

        request = self.factory.get("/api/questions/", REMOTE_ADDR="10.0.0.1")
        request.user = AnonymousUser()
        request.META["HTTP_AUTHORIZATION"] = "Bearer token-alice"
        # Before DRF resolved it: the address's bearer bucket.
        self.assertEqual(rate_limit_identity(request, _bearer_digest(request)), "ipb:10.0.0.1")

        # First request with the new token teaches the token -> user mapping.
        self.assertEqual(self._get(token="token-alice").status_code, 200)
        self.assertEqual(rate_limit_identity(request, _bearer_digest(request)), f"u:{self.alice.pk}")

        # Anonymous traffic uses up the shared address bucket...
        self.assertEqual(self._statuses(3), [200, 200, 200])
        self.assertEqual(self._get().status_code, 429)
        # ...but Alice's token requests use her own bucket (her first,
        # unlearned request was charged to the address's bearer bucket).
        self.assertEqual(self._statuses(3, token="token-alice"), [200, 200, 200])
        self.assertEqual(self._get(token="token-alice").status_code, 429)

    def test_anonymous_load_cannot_starve_a_new_login(self):
        """The shared address bucket is full of anonymous traffic; a student's
        first request with a fresh token (new login / hourly refresh) still
        gets through and is learned."""
        self.assertEqual(self._statuses(3), [200, 200, 200])
        self.assertEqual(self._get().status_code, 429)
        self.assertEqual(self._get(token="token-alice").status_code, 200)
        self.assertEqual(self._get(token="token-alice").status_code, 200)   # now u:<alice>
        self.assertEqual(self._get().status_code, 429)   # anonymous still limited

    def test_forged_tokens_do_not_open_fresh_buckets(self):
        # Invalid tokens are served as anonymous by DRF, so they must be
        # charged to the client address (its bearer bucket), never to a
        # per-token bucket.
        self.assertEqual(
            [self._get(token=f"forged-{i}").status_code for i in range(3)],
            [200, 200, 200],
        )
        self.assertEqual(self._get(token="forged-final").status_code, 429)
        # Anonymous requests have their own budget, and another address too.
        self.assertEqual(self._get().status_code, 200)
        self.assertEqual(self._get(token="forged-other-host", remote="10.0.0.2").status_code, 200)

    # -- scope ------------------------------------------------------------------

    def test_image_serve_endpoint_is_exempt_and_not_charged(self):
        for _ in range(10):
            self.assertEqual(self._get("/api/questions/images/42/serve/").status_code, 200)
        # The image fetches did not spend the question-bank budget.
        self.assertEqual(self._statuses(3), [200, 200, 200])

    def test_only_question_bank_gets_are_limited(self):
        self.assertEqual(self._statuses(3), [200, 200, 200])
        self.assertEqual(self._get().status_code, 429)
        middleware = RateLimitMiddleware(self._view)
        post = self.factory.post("/api/questions/", REMOTE_ADDR="10.0.0.1")
        post.user = AnonymousUser()
        self.assertEqual(middleware(post).status_code, 200)
        for path in ("/api/tests/", "/api/admin/import/api/questions/", "/api/ai/"):
            self.assertEqual(self._get(path).status_code, 200, path)

    def test_zero_limit_disables_the_limiter(self):
        with override_settings(QUESTION_BANK_RATE_LIMIT=0):
            self.assertEqual(set(self._statuses(10)), {200})


class RateLimitDefaultBudgetTests(_FrozenLimiterMixin, TestCase):
    """The default budget covers a student in rapid revision (~12 GETs per
    question, a question every few seconds)."""

    def test_default_budget(self):
        self.assertGreaterEqual(settings.QUESTION_BANK_RATE_LIMIT, 300)
        self.assertEqual(settings.QUESTION_BANK_RATE_WINDOW, 60)

    def test_150_requests_in_a_minute_are_not_throttled(self):
        factory = RequestFactory()
        middleware = RateLimitMiddleware(lambda request: HttpResponse("ok"))
        statuses = set()
        for _ in range(150):
            request = factory.get("/api/questions/12/", REMOTE_ADDR="10.1.1.1")
            request.user = AnonymousUser()
            statuses.add(middleware(request).status_code)
        self.assertEqual(statuses, {200})


@override_settings(QUESTION_BANK_RATE_LIMIT=3, QUESTION_BANK_RATE_WINDOW=60, TRUSTED_CLIENT_IP_HEADER="")
class RateLimitThroughTheStackTests(_FrozenLimiterMixin, TestCase):
    """Full middleware stack + real DRF views (AllowAny taxonomy endpoint)."""

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.alice = User.objects.create_user(username="rl_stack_a", email="rl_stack_a@example.com", password="x" * 12)
        cls.bob = User.objects.create_user(username="rl_stack_b", email="rl_stack_b@example.com", password="x" * 12)

    def test_two_logged_in_students_behind_one_address_do_not_share_a_budget(self):
        self.client.force_login(self.alice)
        for _ in range(3):
            self.assertEqual(self.client.get("/api/questions/topics/").status_code, 200)
        self.assertEqual(self.client.get("/api/questions/topics/").status_code, 429)

        self.client.logout()
        self.client.force_login(self.bob)
        self.assertEqual(self.client.get("/api/questions/topics/").status_code, 200)

    def test_drf_bearer_authentication_is_learned_by_the_limiter(self):
        """Pins the assumption that DRF copies the authenticated user onto
        the Django request, so the limiter can learn token -> user."""
        alice = self.alice

        def fake_authenticate(self_auth, request):
            header = request.META.get("HTTP_AUTHORIZATION", "")
            if header == "Bearer stack-token-alice":
                return (alice, "stack-token-alice")
            return None

        with mock.patch(
            "accounts.supabase_rest_auth.SupabaseJWTAuthentication.authenticate",
            fake_authenticate,
        ):
            auth = {"HTTP_AUTHORIZATION": "Bearer stack-token-alice"}
            self.assertEqual(self.client.get("/api/questions/topics/", **auth).status_code, 200)
            # Exhaust the shared address bucket anonymously.
            for _ in range(3):
                self.assertEqual(self.client.get("/api/questions/topics/").status_code, 200)
            self.assertEqual(self.client.get("/api/questions/topics/").status_code, 429)
            # Alice's token now has its own budget.
            self.assertEqual(self.client.get("/api/questions/topics/", **auth).status_code, 200)
            # Learned from the real stack: keyed on her user, not the address.
            from questions.middleware import _bearer_digest, _token_user_key
            request = RequestFactory().get("/", HTTP_AUTHORIZATION="Bearer stack-token-alice")
            self.assertEqual(
                caches[rl_middleware.CACHE_ALIAS].get(_token_user_key(_bearer_digest(request))), alice.pk,
            )

    def test_image_serve_is_never_rate_limited(self):
        for _ in range(6):
            response = self.client.get("/api/questions/images/987654/serve/")
            self.assertNotEqual(response.status_code, 429)
            self.assertEqual(response.status_code, 404)

    @override_settings(CORS_ALLOWED_ORIGINS=["https://frontend.example.test"])
    def test_429_response_is_not_cacheable_and_keeps_cors_headers(self):
        origin = "https://frontend.example.test"
        for _ in range(3):
            self.client.get("/api/questions/topics/", HTTP_ORIGIN=origin)
        blocked = self.client.get("/api/questions/topics/", HTTP_ORIGIN=origin)
        self.assertEqual(blocked.status_code, 429)
        self.assertIn("no-store", blocked["Cache-Control"])
        self.assertEqual(blocked.get("Access-Control-Allow-Origin"), origin)
