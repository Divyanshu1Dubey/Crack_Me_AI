"""crack_cms.client_ip / crack_cms.throttling: the edge header only counts from the edge.

Verifier finding (Railway behind Cloudflare): with TRUSTED_CLIENT_IP_HEADER=CF-Connecting-IP
any request that reaches the service around Cloudflare (*.up.railway.app) could name its own
client address, and DRF's throttles keyed on the raw X-Forwarded-For. Now the header is read
only when the hop the platform proxy appended (NUM_PROXIES) is one of the edge's addresses
(Cloudflare's published ranges by default), and every throttle keys on the same address.
"""
from __future__ import annotations

import copy
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework.throttling import BaseThrottle

from crack_cms import client_ip
from crack_cms.client_ip import client_ip_known, edge_header_trusted, get_client_ip
from crack_cms.throttling import AnonRateThrottle, ClientIPScopedRateThrottle, ScopedRateThrottle

CLOUDFLARE_EDGE = "173.245.48.10"     # 173.245.48.0/20
CLOUDFLARE_EDGE_V6 = "2606:4700::1111"  # 2606:4700::/32
RAILWAY_PROXY = "100.64.0.2"


def _framework(**overrides):
    conf = copy.deepcopy(settings.REST_FRAMEWORK)
    conf.update(overrides)
    return conf


class EdgeHeaderTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def request(self, remote=RAILWAY_PROXY, xff=None, **meta):
        if xff is not None:
            meta["HTTP_X_FORWARDED_FOR"] = xff
        return self.factory.get("/", REMOTE_ADDR=remote, **meta)

    @override_settings(TRUSTED_CLIENT_IP_HEADER="CF-Connecting-IP", REST_FRAMEWORK=_framework(NUM_PROXIES=1))
    def test_cloudflare_header_only_from_a_cloudflare_hop(self):
        via_cf = self.request(xff=f"203.0.113.7, {CLOUDFLARE_EDGE}", HTTP_CF_CONNECTING_IP="203.0.113.7")
        self.assertEqual(get_client_ip(via_cf), "203.0.113.7")
        via_cf_v6 = self.request(xff=f"203.0.113.8, {CLOUDFLARE_EDGE_V6}", HTTP_CF_CONNECTING_IP="203.0.113.8")
        self.assertEqual(get_client_ip(via_cf_v6), "203.0.113.8")
        mapped = self.request(xff=f"::ffff:{CLOUDFLARE_EDGE}", HTTP_CF_CONNECTING_IP="203.0.113.9")
        self.assertEqual(get_client_ip(mapped), "203.0.113.9")
        # Around Cloudflare: the hop is the visitor itself; a forged header or forged left entries do nothing.
        direct = self.request(xff=f"{CLOUDFLARE_EDGE}, 198.51.100.9", HTTP_CF_CONNECTING_IP="203.0.113.7")
        self.assertEqual(get_client_ip(direct), "198.51.100.9")
        self.assertFalse(edge_header_trusted(direct))

    @override_settings(TRUSTED_CLIENT_IP_HEADER="CF-Connecting-IP", REST_FRAMEWORK=_framework(NUM_PROXIES=None))
    def test_without_num_proxies_the_peer_is_remote_addr(self):
        behind_proxy = self.request(xff="198.51.100.1", HTTP_CF_CONNECTING_IP="198.51.100.1")
        self.assertEqual(get_client_ip(behind_proxy), RAILWAY_PROXY)
        self.assertFalse(client_ip_known())
        # Cloudflare connecting to Django directly is still recognised.
        direct_cf = self.request(remote=CLOUDFLARE_EDGE, HTTP_CF_CONNECTING_IP="203.0.113.70")
        self.assertEqual(get_client_ip(direct_cf), "203.0.113.70")

    @override_settings(REST_FRAMEWORK=_framework(NUM_PROXIES=1))
    def test_header_from_setting(self):
        req = self.request(xff="198.51.100.9", HTTP_CF_CONNECTING_IP="203.0.113.7")
        with override_settings(TRUSTED_CLIENT_IP_HEADER="CF-Connecting-IP", TRUSTED_CLIENT_IP_HEADER_FROM="any"):
            self.assertEqual(get_client_ip(req), "203.0.113.7")
        with override_settings(TRUSTED_CLIENT_IP_HEADER="CF-Connecting-IP",
                               TRUSTED_CLIENT_IP_HEADER_FROM="198.51.100.0/24, 2001:db8::/32"):
            self.assertEqual(get_client_ip(req), "203.0.113.7")
        with override_settings(TRUSTED_CLIENT_IP_HEADER="CF-Connecting-IP", TRUSTED_CLIENT_IP_HEADER_FROM="cloudflare"):
            self.assertEqual(get_client_ip(req), "198.51.100.9")
        with override_settings(TRUSTED_CLIENT_IP_HEADER="CF-Connecting-IP", TRUSTED_CLIENT_IP_HEADER_FROM="not-a-net"):
            self.assertEqual(get_client_ip(req), "198.51.100.9")  # nothing valid: fail closed
        # Other headers (an edge every request passes, e.g. DigitalOcean's) stay trusted from any peer.
        with override_settings(TRUSTED_CLIENT_IP_HEADER="DO-Connecting-IP"):
            do = self.request(xff="198.51.100.9", HTTP_DO_CONNECTING_IP="203.0.113.5")
            self.assertEqual(get_client_ip(do), "203.0.113.5")
            self.assertTrue(client_ip_known())

    @override_settings(TRUSTED_CLIENT_IP_HEADER="CF-Connecting-IP", REST_FRAMEWORK=_framework(NUM_PROXIES=1),
                       TRUSTED_CLIENT_IP_SECRET="edge-s3cret-value", TRUSTED_CLIENT_IP_SECRET_HEADER="X-Edge-Auth")
    def test_optional_secret_from_our_cloudflare_zone(self):
        xff = f"203.0.113.7, {CLOUDFLARE_EDGE}"
        without = self.request(xff=xff, HTTP_CF_CONNECTING_IP="203.0.113.7")
        self.assertEqual(get_client_ip(without), CLOUDFLARE_EDGE)
        wrong = self.request(xff=xff, HTTP_CF_CONNECTING_IP="203.0.113.7", HTTP_X_EDGE_AUTH="guess")
        self.assertEqual(get_client_ip(wrong), CLOUDFLARE_EDGE)
        right = self.request(xff=xff, HTTP_CF_CONNECTING_IP="203.0.113.7", HTTP_X_EDGE_AUTH="edge-s3cret-value")
        self.assertEqual(get_client_ip(right), "203.0.113.7")

    def test_cloudflare_ranges_parse(self):
        import ipaddress

        for network in client_ip.CLOUDFLARE_IP_RANGES:
            ipaddress.ip_network(network)  # raises on a typo

    def test_num_proxies_defaults_to_one_on_railway_only(self):
        from crack_cms.client_ip import num_proxies_from_env

        self.assertIsNone(num_proxies_from_env({}))
        self.assertIsNone(num_proxies_from_env({"NUM_PROXIES": ""}))
        self.assertEqual(num_proxies_from_env({"RAILWAY_ENVIRONMENT_ID": "env-1"}), 1)
        self.assertEqual(num_proxies_from_env({"RAILWAY_ENVIRONMENT_ID": "env-1", "NUM_PROXIES": ""}), 1)
        self.assertEqual(num_proxies_from_env({"RAILWAY_ENVIRONMENT_ID": "env-1", "NUM_PROXIES": "2"}), 2)
        self.assertEqual(num_proxies_from_env({"RAILWAY_ENVIRONMENT_ID": "env-1", "NUM_PROXIES": "0"}), 0)
        self.assertEqual(num_proxies_from_env({"NUM_PROXIES": "1"}), 1)

    def test_posture_check_knows_the_railway_default(self):
        import os

        from crack_cms import security

        base = {"DATABASE_URL": "postgresql://db.internal/app", "SUPABASE_DATABASE_URL": "",
                "DJANGO_SECRET_KEY": "s3cure-" + "q" * 40, "NUM_PROXIES": "",
                "TRUSTED_CLIENT_IP_HEADER": "CF-Connecting-IP"}
        for railway, warns in (("", True), ("env-1", False)):
            with mock.patch.dict(os.environ, {**base, "RAILWAY_ENVIRONMENT_ID": railway}, clear=False), \
                    mock.patch.object(security.LOG, "warning") as warning:
                security.security_posture_check(is_production=True, is_ci=False)
            hits = [c for c in warning.call_args_list if "NUM_PROXIES is not set" in str(c)]
            self.assertEqual(bool(hits), warns, railway)


class ThrottleIdentTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def ident(self, throttle_class, **meta):
        request = self.factory.get("/", REMOTE_ADDR=RAILWAY_PROXY, **meta)
        return throttle_class().get_ident(request)

    @override_settings(TRUSTED_CLIENT_IP_HEADER="CF-Connecting-IP", REST_FRAMEWORK=_framework(NUM_PROXIES=None))
    def test_unconfigured_general_throttles_keep_drfs_key_sign_in_ones_do_not(self):
        meta = {"HTTP_X_FORWARDED_FOR": "198.51.100.1", "HTTP_CF_CONNECTING_IP": "198.51.100.1"}
        request = self.factory.get("/", REMOTE_ADDR=RAILWAY_PROXY, **meta)
        self.assertEqual(self.ident(AnonRateThrottle, **meta), BaseThrottle().get_ident(request))  # unchanged
        self.assertEqual(self.ident(ClientIPScopedRateThrottle, **meta), RAILWAY_PROXY)  # never steerable

    @override_settings(TRUSTED_CLIENT_IP_HEADER="CF-Connecting-IP", REST_FRAMEWORK=_framework(NUM_PROXIES=1))
    def test_configured_throttles_key_on_the_visitor(self):
        meta = {"HTTP_X_FORWARDED_FOR": f"203.0.113.7, {CLOUDFLARE_EDGE}", "HTTP_CF_CONNECTING_IP": "203.0.113.7"}
        for throttle_class in (AnonRateThrottle, ScopedRateThrottle, ClientIPScopedRateThrottle):
            self.assertEqual(self.ident(throttle_class, **meta), "203.0.113.7", throttle_class)
        # DRF's own rule would have keyed every visitor of this Cloudflare edge on the edge.
        request = self.factory.get("/", REMOTE_ADDR=RAILWAY_PROXY, **meta)
        self.assertEqual(BaseThrottle().get_ident(request), CLOUDFLARE_EDGE)

    def test_default_throttle_classes_are_the_client_ip_ones(self):
        self.assertEqual(settings.REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"], (
            "crack_cms.throttling.AnonRateThrottle",
            "crack_cms.throttling.UserRateThrottle",
            "crack_cms.throttling.ScopedRateThrottle",
        ))


class SupabaseBudgetTests(SimpleTestCase):
    def test_a_cloudflare_header_without_num_proxies_does_not_enable_the_per_ip_budget(self):
        from accounts import supabase_rest_auth as sra

        with mock.patch.dict("os.environ", {"SUPABASE_AUTH_VERIFY_RATE_PER_IP": ""}):
            with override_settings(TRUSTED_CLIENT_IP_HEADER="CF-Connecting-IP",
                                   REST_FRAMEWORK=_framework(NUM_PROXIES=None)):
                self.assertEqual(sra._verification_rate_per_ip(), 0)  # one shared proxy address: off
            with override_settings(TRUSTED_CLIENT_IP_HEADER="CF-Connecting-IP",
                                   REST_FRAMEWORK=_framework(NUM_PROXIES=1)):
                self.assertGreater(sra._verification_rate_per_ip(), 0)


class DiagnosticsTests(TestCase):
    def test_client_ip_diagnostics_show_the_peer_and_the_decision(self):
        admin = get_user_model().objects.create_user(username="diag", email="diag@example.com", password=None,
                                                     role="admin", is_staff=True)
        client = APIClient()
        client.force_authenticate(admin)
        with override_settings(TRUSTED_CLIENT_IP_HEADER="CF-Connecting-IP", REST_FRAMEWORK=_framework(NUM_PROXIES=1)):
            via_cf = client.get("/api/health/client-ip/", REMOTE_ADDR=RAILWAY_PROXY,
                                HTTP_X_FORWARDED_FOR=f"203.0.113.7, {CLOUDFLARE_EDGE}",
                                HTTP_CF_CONNECTING_IP="203.0.113.7").json()
            direct = client.get("/api/health/client-ip/", REMOTE_ADDR=RAILWAY_PROXY,
                                HTTP_X_FORWARDED_FOR="198.51.100.9", HTTP_CF_CONNECTING_IP="203.0.113.7").json()
        self.assertEqual((via_cf["peer"], via_cf["edge_header_honoured"], via_cf["rate_limit_client_ip"],
                          via_cf["drf_throttle_ident"], via_cf["sign_in_throttle_ident"]),
                         (CLOUDFLARE_EDGE, True, "203.0.113.7", "203.0.113.7", "203.0.113.7"))
        self.assertEqual((direct["peer"], direct["edge_header_honoured"], direct["rate_limit_client_ip"]),
                         ("198.51.100.9", False, "198.51.100.9"))
        self.assertFalse(via_cf["trusted_client_ip_secret_set"])
