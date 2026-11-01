"""Infrastructure/config regressions, wave 3 (group Z9): CORS exposes
Retry-After, the client-IP posture warning, build.sh's owner-only cleanups
and its identity-link dry run, the PII dump that left the repository, the
backup scripts' location rule, server-side cursors behind a transaction
pooler and the bounded django-q retries.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase, TestCase

from crack_cms import security

BACKEND_DIR = Path(settings.BASE_DIR)
REPO_ROOT = BACKEND_DIR.parent
SCRIPTS_DIR = BACKEND_DIR / "scripts"


class CorsExposeHeadersTests(TestCase):
    def test_retry_after_is_readable_cross_origin(self):
        self.assertIn("Retry-After", settings.CORS_EXPOSE_HEADERS)
        origin = settings.CORS_ALLOWED_ORIGINS[0]
        res = self.client.get("/api/health/", HTTP_ORIGIN=origin)
        exposed = [h.strip().lower() for h in res.get("Access-Control-Expose-Headers", "").split(",")]
        self.assertIn("retry-after", exposed)


class ClientIpPostureWarningTests(SimpleTestCase):
    def _warnings(self, env):
        base = {"DATABASE_URL": "postgresql://db.internal/app", "SUPABASE_DATABASE_URL": "",
                "DJANGO_SECRET_KEY": "s3cure-" + "w" * 40}
        with mock.patch.dict(os.environ, {**base, **env}, clear=False), \
                mock.patch.object(security.LOG, "warning") as warning:
            security.security_posture_check(is_production=True, is_ci=False)
        return [str(call) for call in warning.call_args_list]

    def test_trusted_header_alone_still_warns_about_drf_throttles(self):
        warnings = self._warnings({"NUM_PROXIES": "", "TRUSTED_CLIENT_IP_HEADER": "DO-Connecting-IP"})
        self.assertTrue([w for w in warnings if "NUM_PROXIES is not set" in w and "DRF" in w], warnings)

    def test_num_proxies_set_is_quiet(self):
        for header in ("", "DO-Connecting-IP"):
            warnings = self._warnings({"NUM_PROXIES": "1", "TRUSTED_CLIENT_IP_HEADER": header})
            self.assertFalse([w for w in warnings if "NUM_PROXIES" in w], (header, warnings))


class DeployScriptWave3Tests(SimpleTestCase):
    def test_build_sh_documents_but_never_runs_the_seed_sample_cleanup(self):
        text = (BACKEND_DIR / "build.sh").read_text(encoding="utf-8")
        commands = [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]
        self.assertFalse([c for c in commands if "cleanup_seed_samples" in c])
        self.assertIn("cleanup_seed_samples --apply", text)
        # No destructive data command runs on deploy (C17).
        for needle in ("--replace", "flush", "cleanup_seed_samples", "remove_from_bank", "delete"):
            self.assertFalse([c for c in commands if needle in c], needle)

    def test_the_student_activity_dump_is_not_in_the_repository(self):
        self.assertFalse((BACKEND_DIR / "questions_backup.json").exists())
        self.assertNotIn("questions_backup.json", (SCRIPTS_DIR / "restore_backup.py").read_text(encoding="utf-8")
                         .split('"""', 2)[2])

    def test_frontend_unit_script_lists_both_test_kinds(self):
        scripts = json.loads((REPO_ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))["scripts"]
        self.assertEqual(
            scripts["test:unit"],
            'node --import ./tests/unit/register-ts-alias.mjs --test "tests/unit/*.test.mjs" "tests/unit/*.test.ts"',
        )


class TransactionPoolerCursorTests(SimpleTestCase):
    """``QuerySet.iterator()`` opens a server-side cursor on PostgreSQL, which a
    transaction-mode pooler (Supabase port 6543) cannot keep across
    transactions: such a connection gets DISABLE_SERVER_SIDE_CURSORS
    (crack_cms/db_config.py, applied in settings.py)."""

    POOLER = "postgresql://postgres@aws-0-xx-region-1.pooler.supabase.com:6543/postgres"
    SESSION = "postgresql://postgres@aws-0-xx-region-1.pooler.supabase.com:5432/postgres"

    @staticmethod
    def _db(url):
        import dj_database_url

        return dj_database_url.parse(url)

    def test_the_transaction_port_is_detected(self):
        from crack_cms.db_config import server_side_cursors_unsupported as unsupported

        self.assertTrue(unsupported(self._db(self.POOLER)))
        self.assertTrue(unsupported(self._db("postgresql://postgres@db.example-ref.supabase.co:6543/postgres")))
        # Session mode (5432, pooler or direct) keeps one server connection
        # per client session, where server-side cursors work.
        self.assertFalse(unsupported(self._db(self.SESSION)))
        self.assertFalse(unsupported(self._db("postgresql://postgres@db.example-ref.supabase.co/postgres")))
        for port in ("", None, "not-a-port"):
            self.assertFalse(unsupported({"PORT": port}), port)
        self.assertFalse(unsupported({}))

    def test_the_env_override_wins(self):
        from crack_cms.db_config import server_side_cursors_unsupported as unsupported

        pooler, session = self._db(self.POOLER), self._db(self.SESSION)
        for value in ("true", "1", "YES", " on "):
            self.assertTrue(unsupported(session, value), value)
        for value in ("false", "0", "no", "off"):
            self.assertFalse(unsupported(pooler, value), value)
        for value in ("", None, "auto"):   # anything else: detection
            self.assertTrue(unsupported(pooler, value), value)
            self.assertFalse(unsupported(session, value), value)

    def test_settings_apply_it_to_postgresql_only(self):
        text = (BACKEND_DIR / "crack_cms" / "settings.py").read_text(encoding="utf-8")
        self.assertIn("server_side_cursors_unsupported(DATABASES['default'], "
                      "os.getenv('DB_DISABLE_SERVER_SIDE_CURSORS'))", text)
        if not settings.DATABASES["default"]["ENGINE"].endswith("postgresql"):
            self.assertNotIn("DISABLE_SERVER_SIDE_CURSORS", settings.DATABASES["default"])


class TaskQueueSettingsTests(SimpleTestCase):
    def test_failed_tasks_are_retried_a_bounded_number_of_times(self):
        from django_q.conf import Conf

        cluster = settings.Q_CLUSTER
        # A failed or timed-out task is not acknowledged (ack_failures off):
        # django-q2 re-presents it every `retry` seconds until max_attempts.
        self.assertFalse(cluster.get("ack_failures", False))
        self.assertEqual(cluster["max_attempts"], 3)
        self.assertEqual(Conf.MAX_ATTEMPTS, 3)
        # retry must exceed timeout, or a task still running is re-delivered.
        self.assertGreater(cluster["retry"], cluster["timeout"])
        self.assertIsInstance(settings.INGESTION_RECOVERY_SCHEDULE_MINUTES, int)
        self.assertIsInstance(settings.INGESTION_MAX_AUTO_RESUMES, int)

    def test_analytics_country_header_is_a_setting(self):
        # Read by analytics/views_internal.py (blank: derived from the
        # trusted client-IP edge there).
        self.assertEqual(settings.ANALYTICS_COUNTRY_HEADER, os.getenv("ANALYTICS_COUNTRY_HEADER", "").strip())


class DeployIdentityReportTests(SimpleTestCase):
    def test_build_sh_reports_unlinked_admin_identities_as_a_dry_run(self):
        text = (BACKEND_DIR / "build.sh").read_text(encoding="utf-8")
        commands = [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]
        link = [c for c in commands if "link_supabase_identity" in c]
        # Dry run (no --apply) that can never fail the build (C17: linking
        # is an owner action, documented in a comment only).
        self.assertEqual(link, ["python manage.py link_supabase_identity --all-privileged || true"])
        self.assertIn("#   python manage.py link_supabase_identity --all-privileged --apply", text)
        # After migrate: the report reads accounts.0023's supabase_uid column.
        self.assertGreater(commands.index(link[0]), commands.index("python manage.py migrate --no-input"))


class BackupScriptLocationTests(SimpleTestCase):
    """The ad-hoc dump scripts refuse locations inside the repository, before
    they touch Django or the database (CFG-05; same rule as
    ``manage.py export_questions_backup``)."""

    WRITERS = ("_backup_export.py", "_export_tables.py", "_export_questions.py", "_export_all_tables.py")

    def _run(self, script, *args):
        env = {k: v for k, v in os.environ.items() if k != "DJANGO_SETTINGS_MODULE"}
        return subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / script), *args],
            cwd=str(BACKEND_DIR), capture_output=True, text=True, timeout=120, env=env,
        )

    def test_safe_paths_rule(self):
        sys.path.insert(0, str(SCRIPTS_DIR))
        try:
            import _safe_paths
        finally:
            sys.path.remove(str(SCRIPTS_DIR))
        self.assertTrue(_safe_paths.inside_a_checkout(REPO_ROOT / "backup" / "db_dumps"))
        self.assertTrue(_safe_paths.inside_a_checkout(BACKEND_DIR))
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(_safe_paths.inside_a_checkout(tmp))
            self.assertEqual(_safe_paths.external_path(tmp, what="x"), Path(tmp).resolve())
        with self.assertRaises(SystemExit):
            _safe_paths.external_path(str(REPO_ROOT / "backup"), what="x")
        with self.assertRaises(SystemExit):
            _safe_paths.external_path("  ", what="x")

    def test_writers_refuse_an_output_dir_inside_the_repository(self):
        target = REPO_ROOT / "backup" / "z9-should-not-exist"
        for script in self.WRITERS:
            with self.subTest(script=script):
                res = self._run(script, "--output-dir", str(target))
                self.assertNotEqual(res.returncode, 0)
                self.assertIn("Refusing", res.stderr)
                self.assertFalse(target.exists())
                missing = self._run(script)
                self.assertEqual(missing.returncode, 2)   # --output-dir is required
                self.assertIn("--output-dir", missing.stderr)

    def test_restore_and_import_refuse_paths_inside_the_repository(self):
        res = self._run("restore_backup.py", str(BACKEND_DIR / "questions_backup.json"))
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("Refusing", res.stderr)
        self.assertEqual(self._run("restore_backup.py").returncode, 2)
        res = self._run("_import_to_railway.py", "--input-dir", str(REPO_ROOT / "backup" / "db_dumps"))
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("Refusing", res.stderr)
