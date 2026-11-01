"""Infrastructure/config regressions, wave 2 (group W6-infra): the production
posture check, URL mounts, the client-IP diagnostics endpoint, the
limiter's dedicated cache, the secret scanner, the Vercel CSP, CI gates and
removed dead scripts."""
from __future__ import annotations

import importlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.cache import caches
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import Resolver404, clear_url_caches, resolve, reverse
from rest_framework.test import APIClient

from crack_cms import security
from questions import middleware as rl_middleware

BACKEND_DIR = Path(settings.BASE_DIR)
REPO_ROOT = BACKEND_DIR.parent

try:
    import yaml
except ImportError:  # pragma: no cover - PyYAML ships with bandit / huggingface_hub
    yaml = None


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# -- production posture check (CFG-25 review) ------------------------------

class SecretKeyResolutionTests(SimpleTestCase):
    def _check(self, env):
        base = {"DATABASE_URL": "postgresql://db.internal/app", "SUPABASE_DATABASE_URL": ""}
        with mock.patch.dict(os.environ, {**base, **env}, clear=False):
            for name in ("DJANGO_SECRET_KEY", "SECRET_KEY"):
                if name not in env:
                    os.environ.pop(name, None)
            security.security_posture_check(is_production=True, is_ci=False)

    def test_empty_django_secret_key_falls_back_to_secret_key_like_settings(self):
        # settings.py accepts this deploy; the check used to read
        # os.getenv("DJANGO_SECRET_KEY", fallback) == "" and fail every request.
        self._check({"DJANGO_SECRET_KEY": "", "SECRET_KEY": "s3cure-" + "x" * 40})

    def test_missing_or_insecure_key_still_fails(self):
        for env in ({}, {"DJANGO_SECRET_KEY": "  "}, {"SECRET_KEY": "django-insecure-local-dev-only"}):
            with self.subTest(env=env), self.assertRaises(ImproperlyConfigured):
                self._check(env)

    def test_configured_secret_key_matches_settings_resolution(self):
        with mock.patch.dict(os.environ, {"DJANGO_SECRET_KEY": "", "SECRET_KEY": " abc "}, clear=False):
            self.assertEqual(security.configured_secret_key(), "abc")

    def test_unconfigured_client_ip_is_reported(self):
        env = {"NUM_PROXIES": "", "TRUSTED_CLIENT_IP_HEADER": ""}
        with self.assertLogs("crack_cms.security", level="WARNING") as logs:
            self._check({**env, "DJANGO_SECRET_KEY": "s3cure-" + "y" * 40})
        self.assertTrue(any("NUM_PROXIES" in line for line in logs.output))
        with mock.patch.object(security.LOG, "warning") as warning:
            self._check({"NUM_PROXIES": "1", "TRUSTED_CLIENT_IP_HEADER": "", "DJANGO_SECRET_KEY": "s3cure-" + "z" * 40})
        self.assertFalse([c for c in warning.call_args_list if "NUM_PROXIES" in str(c)])


class PostureCheckUnderTheTestRunnerTests(SimpleTestCase):
    """A non-DEBUG local `manage.py test` is IS_PRODUCTION_RUNTIME, but settings
    substitutes a test SECRET_KEY there; the check must not fail every request."""

    def tearDown(self):
        import crack_cms.urls

        importlib.reload(crack_cms.urls)
        clear_url_caches()

    def _reload_with_check(self, **overrides):
        import crack_cms.urls

        with override_settings(**overrides), mock.patch("crack_cms.security.security_posture_check") as check:
            importlib.reload(crack_cms.urls)
        return check.call_args.kwargs

    def test_testing_flag_is_exposed(self):
        self.assertTrue(settings.TESTING)

    def test_skipped_under_the_test_runner(self):
        kwargs = self._reload_with_check(IS_PRODUCTION_RUNTIME=True, IS_CI=False, TESTING=True)
        self.assertEqual(kwargs, {"is_production": False, "is_ci": False})

    def test_runs_in_production(self):
        kwargs = self._reload_with_check(IS_PRODUCTION_RUNTIME=True, IS_CI=False, TESTING=False)
        self.assertEqual(kwargs, {"is_production": True, "is_ci": False})


# -- URL mounts (M10 / CFG-15) ---------------------------------------------

class UrlMountTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin = User.objects.create_user(
            username="w6_admin", email="w6_admin@example.com", password="x" * 12, is_superuser=True, is_staff=True,
        )
        cls.student = User.objects.create_user(username="w6_student", email="w6_student@example.com", password="x" * 12)

    def setUp(self):
        caches["default"].clear()
        self.client = APIClient()

    def test_empty_video_mount_is_gone(self):
        with self.assertRaises(Resolver404):
            resolve("/api/video/")

    def test_inicet_recall_api_is_mounted_and_admin_only(self):
        from importers.inicet import views as inicet_views

        self.assertEqual(reverse("importers_inicet:jobs-list"), "/api/imports/inicet/jobs/")
        self.assertIs(resolve("/api/imports/inicet/jobs/").func.view_class, inicet_views.ImportJobListView)
        self.assertEqual(
            resolve("/api/imports/inicet/jobs/1/retry/").func.view_class.task_path,
            "importers.inicet.tasks.run_recall_import",
        )
        self.assertIn(self.client.get("/api/imports/inicet/jobs/").status_code, (401, 403))
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get("/api/imports/inicet/jobs/").status_code, 403)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get("/api/imports/inicet/jobs/").status_code, 200)

    def test_client_ip_diagnostics_is_admin_only(self):
        self.assertIn(self.client.get("/api/health/client-ip/").status_code, (401, 403))
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get("/api/health/client-ip/").status_code, 403)

    def test_client_ip_diagnostics_echoes_the_address_headers(self):
        self.client.force_authenticate(self.admin)
        conf = {**settings.REST_FRAMEWORK, "NUM_PROXIES": 1}
        with override_settings(TRUSTED_CLIENT_IP_HEADER="DO-Connecting-IP", REST_FRAMEWORK=conf):
            response = self.client.get(
                "/api/health/client-ip/", REMOTE_ADDR="10.0.0.1",
                HTTP_X_FORWARDED_FOR="1.2.3.4, 203.0.113.5", HTTP_DO_CONNECTING_IP="203.0.113.5",
            )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["remote_addr"], "10.0.0.1")
        self.assertEqual(data["headers"], {"X-Forwarded-For": "1.2.3.4, 203.0.113.5", "DO-Connecting-IP": "203.0.113.5"})
        self.assertEqual(data["num_proxies"], 1)
        self.assertEqual(data["trusted_client_ip_header"], "DO-Connecting-IP")
        self.assertEqual(data["rate_limit_client_ip"], "203.0.113.5")
        self.assertEqual(data["drf_throttle_ident"], "203.0.113.5")
        self.assertIn("no-store", response["Cache-Control"])


class DeadCodeRemovedTests(SimpleTestCase):
    def test_dead_loaders_and_crawler_stub_are_gone(self):
        for rel in ("load_chunks.py", "load_chunks.ps1", "load_data_custom.py", "load_sequential.py",
                    "split_dump.py", "crack_cms/management/commands/run_crawler.py"):
            self.assertFalse((BACKEND_DIR / rel).exists(), rel)


# -- limiter cache (G6 review: shared 300-entry LocMem 'default') -----------

_LIMITER_CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "w6-default"},
    "kb_retrieval": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "w6-kb"},
    "rate_limit": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "w6-rate-limit"},
}


class LimiterCacheTests(SimpleTestCase):
    def test_rate_limit_alias_is_configured_with_a_large_cap(self):
        conf = settings.CACHES["rate_limit"]
        if conf["BACKEND"].endswith("LocMemCache"):
            self.assertGreaterEqual(conf["OPTIONS"]["MAX_ENTRIES"], 10000)

    @override_settings(CACHES=_LIMITER_CACHES, QUESTION_BANK_RATE_LIMIT=5, QUESTION_BANK_RATE_WINDOW=60,
                       TRUSTED_CLIENT_IP_HEADER="")
    def test_counters_and_token_mappings_use_the_rate_limit_alias(self):
        caches["default"].clear()
        caches["rate_limit"].clear()
        now = 1_800_000_030.0
        user = mock.Mock(is_authenticated=True, pk=42)

        def view(request):
            request.user = user   # what DRF does after authenticating the token
            return HttpResponse("ok")

        request = RequestFactory().get("/api/questions/", REMOTE_ADDR="10.0.0.1", HTTP_AUTHORIZATION="Bearer tok-w6")
        request.user = AnonymousUser()
        with mock.patch.object(rl_middleware, "_now", return_value=now):
            self.assertEqual(rl_middleware.RateLimitMiddleware(view)(request).status_code, 200)
        bucket_key = f"rl_qs:ipb:10.0.0.1:{int(now // 60)}"
        token_key = rl_middleware._token_user_key(rl_middleware._bearer_digest(request))
        self.assertEqual(caches["rate_limit"].get(bucket_key), 1)
        self.assertEqual(caches["rate_limit"].get(token_key), 42)
        self.assertIsNone(caches["default"].get(bucket_key))
        self.assertIsNone(caches["default"].get(token_key))

    @override_settings(CACHES={k: v for k, v in _LIMITER_CACHES.items() if k != "rate_limit"})
    def test_falls_back_to_default_without_the_alias(self):
        self.assertIs(rl_middleware._cache(), caches["default"])

    def test_outside_the_test_runner_the_limiter_has_its_own_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / "empty.env"
            env_file.write_text("", encoding="utf-8")
            env = {
                **os.environ,
                "DJANGO_ENV_FILE": str(env_file), "DEBUG": "True", "DATABASE_URL": "",
                "SUPABASE_DATABASE_URL": "", "SENTRY_DSN": "", "REDIS_URL": "",
            }
            code = (
                "import json, crack_cms.settings as s; "
                "print(json.dumps({k: [v.get('LOCATION'), (v.get('OPTIONS') or {}).get('MAX_ENTRIES')] "
                "for k, v in s.CACHES.items()}))"
            )
            result = subprocess.run(
                [sys.executable, "-c", code], cwd=BACKEND_DIR, env=env, capture_output=True, text=True, timeout=120,
            )
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        caches_conf = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertNotEqual(caches_conf["rate_limit"][0], caches_conf["default"][0])
        self.assertEqual(caches_conf["rate_limit"][1], 50000)


# -- secret scanner (G1 review: masking and user-activity dumps) -----------

class ScanSecretsWave2Tests(SimpleTestCase):
    """Synthetic secrets and fixture markers are assembled at runtime so this
    file never contains a literal the scanner itself would flag."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.scan = _load_module("w6_scan_secrets", REPO_ROOT / "scripts" / "scan_secrets.py")

    def _findings(self, line, **kw):
        return self.scan._scan_line(line, code=kw.get("code", True), prose=kw.get("prose", True))

    def _scan_temp(self, rel_path, content):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / rel_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return [label for _line, label, _masked in self.scan._scan_file(path, Path(rel_path))]

    def test_long_db_url_password_shows_its_length_only(self):
        password = "Zq8rT2" + "vLm9wXp4Kd7sYb31"
        url = "postgresql://" + "postgres.ref:" + password + "@aws-1-ap-south-1.pooler.supabase.com:5432/postgres"
        findings = self._findings(f"DATABASE_URL = {url}")
        self.assertEqual(findings, [("Database URL with inline password", f"<{len(password)} chars>")])

    def test_long_password_literals_and_defaults_show_their_length_only(self):
        password = "Wq7x!pLm2" + "Rt5vZk8Nb3"
        for line in ("CREDS = {'password': '" + password + "'}",
                     'os.getenv("ADMIN_PASSWORD", "' + password + '")'):
            with self.subTest(line=line[:12]):
                findings = self._findings(line)
                self.assertTrue(findings)
                for _label, masked in findings:
                    self.assertEqual(masked, f"<{len(password)} chars>")
                    self.assertNotIn(password[:4], masked)

    def test_provider_keys_show_only_their_type_prefix(self):
        key = "gs" + "k_" + "aB3dE5fG7hJ9kL2mN4pQ6rS8tU0vW1xY3zQ9"
        # One finding: the ElevenLabs "sk_" pattern no longer matches inside it.
        [(label, masked)] = self._findings(f"GROQ = '{key}'")
        self.assertEqual(label, "Groq key")
        self.assertEqual(masked, f"{key[:4]}... ({len(key)} chars)")
        self.assertNotIn(key[-2:], masked.split("(")[0])
        eleven = "s" + "k_" + "Zx9Yw8Vu7Ts6Rq5Po4Nm3Lk2"
        self.assertEqual([lbl for lbl, _ in self._findings(f"KEY = '{eleven}'")], ["ElevenLabs key"])

    def test_student_activity_fixtures_are_flagged(self):
        for model in ("questions." + "questionattempt", "questions." + "flashcard", "accounts." + "tokenbalance",
                      "accounts." + "adminauditlog", "tests_engine." + "testattempt",
                      "analytics." + "usertopicperformance", "questions." + "discussion"):
            row = '[{"model": "' + model + '", "pk": 1, "fields": {"question": 3}}]\n'
            with self.subTest(model=model):
                labels = self._scan_temp("backup/dump.json", row)
                self.assertTrue(any(model in label for label in labels), labels)

    def test_any_fixture_rows_linked_to_a_user_are_flagged(self):
        rows = '[{"model": "' + "blog_engine." + 'comment", "pk": 1, "fields": {"' + 'user": 7, "body": "hi"}}]\n'
        labels = self._scan_temp("exports/comments.json", rows)
        self.assertTrue(any("linked to a user" in label for label in labels), labels)

    def test_student_activity_sql_dumps_are_flagged(self):
        sql = "INSERT INTO " + "questions_" + "questionattempt VALUES (1, 2, 'A');\n"
        self.assertTrue(any("SQL rows" in label for label in self._scan_temp("backup/sql/attempts.sql", sql)))

    def test_content_fixtures_and_api_samples_are_not_flagged(self):
        content = '[{"model": "' + "questions." + 'question", "pk": 1, "fields": {"verified_by": 1, "year": 2024}}]\n'
        self.assertEqual(self._scan_temp("backend/fixtures/cms_fixture.json", content), [])
        sample = '{"' + 'user": 5, "score": 3}\n'
        self.assertEqual(self._scan_temp("docs/api_sample.json", sample), [])

    def test_scanner_output_never_prints_a_long_password(self):
        password = "Hk4!pQ9" + "mWz2Lx7Rv5Q7"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "deploy_settings.py"
            path.write_text('DB = os.getenv("DB_PASSWORD", "' + password + '")\n', encoding="utf-8")
            out = io.StringIO()
            with mock.patch("sys.stdout", out):
                self.assertEqual(self.scan.main([str(path)]), 1)
        self.assertNotIn(password[:4], out.getvalue())
        self.assertNotIn(password[-2:], out.getvalue().replace(str(path), ""))


# -- static config ----------------------------------------------------------

VERCEL_JSON = REPO_ROOT / "frontend" / "vercel.json"
CI_YML = REPO_ROOT / ".github" / "workflows" / "ci.yml"


@unittest.skipUnless(VERCEL_JSON.exists(), "frontend/vercel.json not in this checkout")
class RazorpayCspTests(SimpleTestCase):
    def test_risk_detection_bundle_and_beacons_are_allowed(self):
        config = json.loads(VERCEL_JSON.read_text(encoding="utf-8"))
        headers = {h["key"]: h["value"] for block in config["headers"] for h in block["headers"]}
        csp = {}
        for directive in headers["Content-Security-Policy"].split(";"):
            parts = directive.split()
            if parts:
                csp[parts[0]] = parts[1:]
        self.assertIn("https://cdn.razorpay.com", csp["script-src"])
        # lumberjack-cx / lumberjack-metrics beacons and the API.
        self.assertIn("https://*.razorpay.com", csp["connect-src"])
        self.assertIn("https://checkout.razorpay.com", csp["script-src"])
        self.assertIn("https://api.razorpay.com", csp["frame-src"])


@unittest.skipUnless(CI_YML.exists() and yaml is not None, "ci.yml / PyYAML not available")
class CiWorkflowTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.jobs = yaml.safe_load(CI_YML.read_text(encoding="utf-8"))["jobs"]

    def _step(self, job, needle):
        return next(step for step in self.jobs[job]["steps"] if needle in str(step.get("run", "")))

    def test_secret_scan_is_a_blocking_step(self):
        step = self._step("security", "scan_secrets.py")
        self.assertEqual(step["run"].strip(), "python scripts/scan_secrets.py --all-tracked")
        self.assertNotIn("continue-on-error", step)
        steps = self.jobs["security"]["steps"]
        setup_python = next(i for i, s in enumerate(steps) if "setup-python" in str(s.get("uses", "")))
        self.assertGreater(steps.index(step), setup_python)

    def test_bandit_gate_uses_the_per_site_baseline_not_a_tree_wide_b324_skip(self):
        gate = self._step("security", "-lll -iii")["run"]
        self.assertNotIn("B324", gate)
        self.assertIn("-b .bandit-baseline.json", gate)
        baseline = json.loads((REPO_ROOT / ".bandit-baseline.json").read_text(encoding="utf-8"))
        self.assertTrue(baseline["results"])
        for entry in baseline["results"]:
            self.assertEqual(entry["test_id"], "B324")
            self.assertTrue(entry["filename"].startswith("backend/"), entry["filename"])
            self.assertNotIn("\\", entry["filename"])
            self.assertTrue((REPO_ROOT / entry["filename"]).exists(), entry["filename"])
        self.assertFalse((REPO_ROOT / ".bandit.yml").exists())

    def test_frontend_unit_tests_run_on_node_22(self):
        job = self.jobs["frontend-unit"]
        node = next(s for s in job["steps"] if "setup-node" in str(s.get("uses", "")))
        self.assertEqual(str(node["with"]["node-version"]), "22")
        self.assertEqual(self._step("frontend-unit", "test:unit")["run"].strip(), "npm run test:unit")
        scripts = json.loads((REPO_ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))["scripts"]
        self.assertIn("--test", scripts["test:unit"])
        self.assertIn("tests/unit/", scripts["test:unit"])


class DeployScriptWave2Tests(SimpleTestCase):
    def _commands(self, path):
        return [line.strip() for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.strip().startswith("#")]

    def test_relink_step_has_no_stale_fixture_flag(self):
        relink = [c for c in self._commands(BACKEND_DIR / "build.sh") if "relink_fixture_images" in c]
        self.assertEqual(len(relink), 1)
        self.assertNotIn("--fixture", relink[0])
        self.assertIn("--apply", relink[0])

    def test_one_time_neet_pg_cleanup_is_documented(self):
        text = (BACKEND_DIR / "build.sh").read_text(encoding="utf-8")
        self.assertIn("import_neet_pg --replace --dry-run", text)

    def test_ship_kb_stages_explicit_paths_only(self):
        commands = self._commands(REPO_ROOT / "SHIP_KB.sh")
        self.assertFalse([c for c in commands if c in ("git add -A", "git add .", "git add --all")])
        self.assertTrue([c for c in commands if c.startswith('git add -- "${existing_paths[@]}"')])
