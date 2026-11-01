"""Wave 1 (G1-secrets) regressions: no committed credentials, safe admin bootstrap.

Covers bootstrap_admin (no default password, create-only, no 'd1'),
sync_single_supabase_admin (explicit password, no partial side effects),
cleanup_supabase_admins (never deletes non-admins), the env-only Supabase
storage script, the Procfile worker, and scripts/scan_secrets.py.

Synthetic secrets are assembled at runtime so this file never contains a
literal that the secret scanner itself would flag. No network is used.
"""
import base64
import importlib.util
import io
import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command, get_commands
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase

User = get_user_model()

BACKEND_DIR = Path(settings.BASE_DIR)
REPO_ROOT = BACKEND_DIR.parent
STRONG_PASSWORD = "Wave1-Bootstrap-9fK2q"
OTHER_STRONG_PASSWORD = "Wave1-Rotated-4hT7w"
BOOTSTRAP_ENV_VARS = (
    "BOOTSTRAP_ADMIN_PASSWORD",
    "DJANGO_SUPERUSER_PASSWORD",
    "BOOTSTRAP_ADMIN_USERNAME",
    "BOOTSTRAP_ADMIN_EMAIL",
    "BOOTSTRAP_DEFAULT_PASSWORD",
    "BOOTSTRAP_STUDENT_USERNAME",
    "BOOTSTRAP_STUDENT_EMAIL",
    "BOOTSTRAP_STUDENT_PASSWORD",
)


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _CleanEnvMixin:
    """Run each test with the given env vars removed (restored afterwards)."""

    env_vars_to_clear = ()

    def setUp(self):
        super().setUp()
        patcher = mock.patch.dict(os.environ, {})
        patcher.start()
        self.addCleanup(patcher.stop)
        for name in self.env_vars_to_clear:
            os.environ.pop(name, None)


class BootstrapAdminTests(_CleanEnvMixin, TestCase):
    env_vars_to_clear = BOOTSTRAP_ENV_VARS

    def _run(self):
        out, err = io.StringIO(), io.StringIO()
        call_command("bootstrap_admin", stdout=out, stderr=err)
        return out.getvalue() + err.getvalue()

    def test_refuses_to_run_without_password(self):
        with self.assertRaisesMessage(CommandError, "BOOTSTRAP_ADMIN_PASSWORD"):
            self._run()
        self.assertFalse(User.objects.exists())

    def test_removed_shared_default_password_is_not_used(self):
        os.environ["BOOTSTRAP_DEFAULT_PASSWORD"] = STRONG_PASSWORD
        os.environ["BOOTSTRAP_STUDENT_PASSWORD"] = STRONG_PASSWORD
        with self.assertRaises(CommandError):
            self._run()
        self.assertFalse(User.objects.exists())

    def test_creates_missing_admin_superuser_and_no_student(self):
        os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = STRONG_PASSWORD
        output = self._run()

        admin = User.objects.get(username="admin")
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_active)
        self.assertEqual(admin.role, "admin")
        self.assertEqual(admin.email, "admin@cracklabs.app")
        self.assertTrue(admin.check_password(STRONG_PASSWORD))
        self.assertFalse(User.objects.filter(username="d1").exists())
        self.assertEqual(User.objects.count(), 1)
        self.assertIn("Created admin superuser 'admin'", output)
        self.assertNotIn(STRONG_PASSWORD, output)

    def test_django_superuser_password_alias_and_custom_identity(self):
        os.environ["DJANGO_SUPERUSER_PASSWORD"] = STRONG_PASSWORD
        os.environ["BOOTSTRAP_ADMIN_USERNAME"] = "ops-admin"
        os.environ["BOOTSTRAP_ADMIN_EMAIL"] = "ops@cracklabs.app"
        self._run()
        admin = User.objects.get(username="ops-admin")
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.check_password(STRONG_PASSWORD))

    def test_never_resets_an_existing_password(self):
        User.objects.create_superuser(username="admin", email="admin@cracklabs.app", password=STRONG_PASSWORD)
        os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = OTHER_STRONG_PASSWORD

        output = self._run()
        self._run()  # every release used to re-apply the password

        admin = User.objects.get(username="admin")
        self.assertTrue(admin.check_password(STRONG_PASSWORD))
        self.assertFalse(admin.check_password(OTHER_STRONG_PASSWORD))
        self.assertIn("left unchanged (password not reset)", output)

    def test_does_not_promote_or_reactivate_an_existing_account(self):
        user = User.objects.create_user(username="admin", email="admin@cracklabs.app", password=STRONG_PASSWORD)
        user.is_active = False
        user.save(update_fields=["is_active"])
        os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = OTHER_STRONG_PASSWORD

        output = self._run()

        user.refresh_from_db()
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_active)
        self.assertEqual(user.role, "student")
        self.assertTrue(user.check_password(STRONG_PASSWORD))
        self.assertIn("not a staff superuser", output)

    def test_refuses_a_second_admin_for_an_email_already_in_use(self):
        User.objects.create_user(username="renamed-admin", email="Admin@CrackLabs.app", password=STRONG_PASSWORD)
        os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = OTHER_STRONG_PASSWORD
        with self.assertRaisesMessage(CommandError, "already uses"):
            self._run()
        self.assertFalse(User.objects.filter(username="admin").exists())

    def test_rejects_weak_password(self):
        os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = "password"
        with self.assertRaisesMessage(CommandError, "password validators"):
            self._run()
        self.assertFalse(User.objects.exists())


class SyncSingleSupabaseAdminTests(_CleanEnvMixin, TestCase):
    env_vars_to_clear = ("SUPABASE_ADMIN_PASSWORD", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY")
    module = "accounts.management.commands.sync_single_supabase_admin"

    def test_refuses_without_explicit_password(self):
        os.environ["SUPABASE_URL"] = "http://supabase.invalid"
        os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "test-service-role-key"
        with mock.patch(f"{self.module}.upsert_supabase_auth_user") as upsert:
            with self.assertRaisesMessage(CommandError, "explicit admin password"):
                call_command("sync_single_supabase_admin", stdout=io.StringIO())
        upsert.assert_not_called()
        self.assertFalse(User.objects.exists())

    def test_no_local_changes_when_supabase_is_not_configured(self):
        with self.assertRaisesMessage(CommandError, "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY"):
            call_command("sync_single_supabase_admin", "--password", STRONG_PASSWORD, stdout=io.StringIO())
        self.assertFalse(User.objects.exists())

    def test_password_from_env_var_is_used_for_both_sides(self):
        os.environ["SUPABASE_URL"] = "http://supabase.invalid"
        os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "test-service-role-key"
        os.environ["SUPABASE_ADMIN_PASSWORD"] = STRONG_PASSWORD
        with mock.patch(f"{self.module}.upsert_supabase_auth_user", return_value=True) as upsert, \
                mock.patch(f"{self.module}.list_supabase_auth_users", return_value=[]), \
                mock.patch(f"{self.module}.delete_supabase_auth_user") as delete:
            call_command("sync_single_supabase_admin", stdout=io.StringIO())

        user = User.objects.get(username="deeksha")
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.check_password(STRONG_PASSWORD))
        self.assertEqual(upsert.call_args.kwargs["password"], STRONG_PASSWORD)
        delete.assert_not_called()

    def test_weak_password_is_rejected_before_any_change(self):
        os.environ["SUPABASE_URL"] = "http://supabase.invalid"
        os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "test-service-role-key"
        with mock.patch(f"{self.module}.upsert_supabase_auth_user") as upsert:
            with self.assertRaisesMessage(CommandError, "password validators"):
                call_command("sync_single_supabase_admin", "--password", "12345678", stdout=io.StringIO())
        upsert.assert_not_called()
        self.assertFalse(User.objects.exists())


def _supabase_user(uid, email, full_name, app_metadata=None, user_metadata_extra=None):
    user_metadata = {"full_name": full_name, **(user_metadata_extra or {})}
    return SimpleNamespace(id=uid, email=email, user_metadata=user_metadata, app_metadata=app_metadata or {})


class CleanupSupabaseAdminsTests(_CleanEnvMixin, SimpleTestCase):
    env_vars_to_clear = ("NEXT_PUBLIC_SUPABASE_URL", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY")
    module_name = "accounts.management.commands.cleanup_supabase_admins"

    def setUp(self):
        super().setUp()
        os.environ["SUPABASE_URL"] = "http://supabase.invalid"
        os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "test-service-role-key"
        self.users = [
            _supabase_user("u-student", "student@mail.test", "A Student", {"provider": "email"}),
            # user_metadata is writable by the user: it must not make anyone an admin
            _supabase_user("u-sneaky", "sneaky@mail.test", "Sneaky", {}, {"role": "admin", "is_admin": True}),
            _supabase_user("u-keep", "meduraa.web@gmail.com", "deeksha", {"role": "admin"}),
            _supabase_user("u-old-admin", "old-admin@mail.test", "Old Admin", {"is_admin": True}),
        ]
        self.supabase = mock.Mock()
        self.supabase.auth.admin.list_users.side_effect = self._list_users
        patcher = mock.patch(f"{self.module_name}.create_client", return_value=self.supabase)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _list_users(self, page=None, per_page=None):
        if page is None:  # unpaginated call: Supabase returns the first page only
            return self.users[:50]
        start = (page - 1) * per_page
        return self.users[start:start + per_page]

    def _run(self, *args):
        out = io.StringIO()
        call_command("cleanup_supabase_admins", *args, stdout=out)
        return out.getvalue()

    def _deleted_ids(self):
        return [c.args[0] for c in self.supabase.auth.admin.delete_user.call_args_list]

    def test_confirm_deletes_only_the_other_admins(self):
        output = self._run("--confirm")
        self.assertEqual(self._deleted_ids(), ["u-old-admin"])
        self.assertIn("Keeping admin: deeksha", output)
        self.assertNotIn("student@mail.test", output)  # non-admins are not even listed

    def test_dry_run_deletes_nothing(self):
        output = self._run()
        self.supabase.auth.admin.delete_user.assert_not_called()
        self.assertIn("1 admin users will be DELETED", output)

    def test_only_students_means_nothing_is_deleted(self):
        self.users = [u for u in self.users if u.id in {"u-student", "u-sneaky"}]
        output = self._run("--confirm")
        self.supabase.auth.admin.delete_user.assert_not_called()
        self.assertIn("sync_single_supabase_admin", output)

    def test_admins_beyond_the_first_page_are_found(self):
        self.users = [_supabase_user(f"u-s{i}", f"s{i}@mail.test", f"S{i}") for i in range(3)] + [
            _supabase_user("u-late-admin", "late@mail.test", "Late", {"role": "admin"}),
        ]
        with mock.patch(f"{self.module_name}.PAGE_SIZE", 2):
            self._run("--confirm")
        self.assertEqual(self._deleted_ids(), ["u-late-admin"])


class DownloadStorageScriptTests(_CleanEnvMixin, SimpleTestCase):
    env_vars_to_clear = ("SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY")

    def setUp(self):
        super().setUp()
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("network used on import")):
            self.module = _load_module("g1_download_storage", BACKEND_DIR / "scripts" / "_download_storage.py")

    def test_no_credentials_are_embedded(self):
        self.assertEqual(self.module.SUPABASE_URL, "")
        self.assertEqual(self.module.SERVICE_ROLE_KEY, "")

    def test_missing_env_fails_closed(self):
        with self.assertRaises(SystemExit) as ctx:
            self.module.load_supabase_config({})
        self.assertIn("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY", str(ctx.exception))

    def test_reads_credentials_from_env(self):
        url, key = self.module.load_supabase_config(
            {"NEXT_PUBLIC_SUPABASE_URL": "https://project.supabase.invalid/", "SUPABASE_SERVICE_ROLE_KEY": "test-key"}
        )
        self.assertEqual((url, key), ("https://project.supabase.invalid", "test-key"))

    def test_main_exits_before_any_request_without_env(self):
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("network used")):
            with self.assertRaises(SystemExit):
                self.module.main()


class ProcfileTests(SimpleTestCase):
    def setUp(self):
        lines = (BACKEND_DIR / "Procfile").read_text(encoding="utf-8").splitlines()
        self.processes = dict(line.split(":", 1) for line in lines if line.strip())

    def test_release_only_migrates(self):
        release = self.processes["release"]
        self.assertIn("manage.py migrate", release)
        self.assertNotIn("bootstrap_admin", release)
        self.assertNotIn("seed_data", release)

    def test_django_q_worker_is_declared(self):
        self.assertEqual(self.processes["worker"].strip(), "python manage.py qcluster")
        self.assertIn("qcluster", get_commands())


class ScanSecretsTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.scan = _load_module("g1_scan_secrets", REPO_ROOT / "scripts" / "scan_secrets.py")

    # -- helpers --------------------------------------------------------
    @staticmethod
    def _b64(obj):
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")

    def _jwt(self, role):
        return ".".join([self._b64({"alg": "HS256", "typ": "JWT"}), self._b64({"iss": "supabase", "role": role}), "s" * 24])

    def _labels(self, line, *, code=True, prose=True):
        return [label for label, _masked in self.scan._scan_line(line, code=code, prose=prose)]

    def _scan_temp(self, rel_path, content, encoding="utf-8"):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / rel_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding=encoding)
            return [label for _line, label, _masked in self.scan._scan_file(path, Path(rel_path))]

    # -- credentials ----------------------------------------------------
    def test_detects_supabase_service_role_and_anon_jwts(self):
        self.assertIn("Supabase service_role key (JWT)", self._labels(f'KEY = "{self._jwt("service_role")}"'))
        self.assertTrue(any("anon" in label for label in self._labels(f"key={self._jwt('anon')}")))

    def test_detects_database_urls_with_inline_password(self):
        password = "Zq8" + "rT2vLm9wX"
        remote = "postgresql://" + "postgres.ref:" + password + "@aws-1-ap-south-1.pooler.supabase.com:5432/postgres"
        self.assertIn("Database URL with inline password", self._labels(f"DATABASE_URL = {remote}"))
        for safe in (
            "postgresql://postgres:[YOUR-PASSWORD]@db.ref.supabase.co:5432/postgres",
            "postgresql://postgres:postgres@127.0.0.1:54322/postgres",
            "postgresql://postgres:<RAILWAY_DB_PASSWORD>@tramway.proxy.rlwy.net:24963/railway",
            "rediss://default:xxx@xxx.upstash.io:6379",
        ):
            self.assertEqual(self._labels(safe), [], safe)

    def test_detects_hard_coded_secret_defaults(self):
        password = "Wq7" + "x!pLm2"
        env_default = 'os.getenv("ADMIN_PASSWORD", "' + password + '")'
        cli_default = 'parser.add_argument("--password", default="' + password + '", help="x")'
        self.assertIn("Hard-coded default for ADMIN_PASSWORD", self._labels(env_default))
        self.assertIn("Hard-coded default for a secret CLI option", self._labels(cli_default))
        for safe in (
            'os.getenv("DAILY_FREE_TOKENS", "10")',
            'os.getenv("TOKEN_MODEL", "gpt4o-mini")',
            'os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")',
            'parser.add_argument("--password", default="", help="x")',
        ):
            self.assertEqual(self._labels(safe), [], safe)

    def test_password_literals_in_code_but_not_in_tests_or_docs(self):
        password = "Wq7" + "x!pLm2"
        js = "var CREDS = { username: 'admin', password: '" + password + "' };\n"
        self.assertIn("Password literal", self._scan_temp("tools/export.js", js))
        self.assertEqual(self._scan_temp("frontend/tests/e2e/login.spec.ts", js), [])
        self.assertEqual(self._scan_temp("docs/API.md", '{"password": "' + password + '"}\n'), [])
        prose = 'msg = "create it with email admin@cracklabs.app and password ' + password + '"\n'
        self.assertIn("Password in text", self._scan_temp("backend/cmd.py", prose))

    def test_output_never_reveals_short_secrets(self):
        password = "Wq7" + "x!pLm2"
        self.assertEqual(self.scan._mask(password), "<9 chars>")
        self.assertTrue(self.scan._mask("k" * 40).startswith("kkkk..."))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings_local.py"
            path.write_text('ADMIN = os.getenv("ADMIN_PASSWORD", "' + password + '")\n', encoding="utf-8")
            out = io.StringIO()
            with mock.patch("sys.stdout", out):
                exit_code = self.scan.main([str(path)])
        self.assertEqual(exit_code, 1)
        self.assertIn("Hard-coded default for ADMIN_PASSWORD", out.getvalue())
        self.assertNotIn(password, out.getvalue())
        self.assertNotIn(password[:4], out.getvalue())

    def test_allowlist_marker_suppresses_a_line(self):
        line = f'KEY = "{self._jwt("service_role")}"  # {self.scan.ALLOW_MARKER}\n'
        self.assertEqual(self._scan_temp("backend/settings_example.py", line), [])

    # -- personal data --------------------------------------------------
    def test_detects_user_fixture_and_sql_dumps(self):
        fixture = '[{"model": "' + "accounts." + 'customuser", "pk": 1, "fields": {}}]\n'
        self.assertTrue(any("accounts.customuser" in label for label in self._scan_temp("dump.json", fixture)))
        cased = '[{"model": "accounts.' + 'Subscription", "pk": 1, "fields": {}}]\n'
        self.assertTrue(any("accounts.subscription" in label for label in self._scan_temp("backup/x.json", cased)))
        sql = "INSERT INTO " + "accounts_" + "customuser VALUES (1);\n"
        self.assertTrue(any("SQL rows" in label for label in self._scan_temp("backup/sql/users.sql", sql)))
        content_fixture = '[{"model": "questions.question", "pk": 1, "fields": {}}]\n'
        self.assertEqual(self._scan_temp("backend/fixtures/cms_fixture.json", content_fixture), [])

    def test_detects_files_with_many_email_addresses(self):
        rows = "\n".join(f'{{"email": "student{i}' + '@mail-provider.in"}' for i in range(12))
        self.assertTrue(any("distinct email addresses" in label for label in self._scan_temp("export.json", rows)))
        few = "\n".join(f"contact{i}" + "@cracklabs.app" for i in range(3))
        self.assertEqual(self._scan_temp("README.md", few), [])

    def test_utf16_dumps_are_not_skipped_as_binary(self):
        fixture = '[{"model": "' + "sessions." + 'session", "pk": "k", "fields": {}}]\n'
        labels = self._scan_temp("backend/data_export.json", fixture, encoding="utf-16")
        self.assertTrue(any("sessions.session" in label for label in labels))

    # -- the files fixed in this wave stay clean -------------------------
    def test_fixed_files_contain_no_credentials(self):
        files = [
            BACKEND_DIR / "accounts" / "management" / "commands" / "bootstrap_admin.py",
            BACKEND_DIR / "accounts" / "management" / "commands" / "sync_single_supabase_admin.py",
            BACKEND_DIR / "accounts" / "management" / "commands" / "cleanup_supabase_admins.py",
            BACKEND_DIR / "scripts" / "_download_storage.py",
            BACKEND_DIR / "MIGRATION_STATUS.md",
            BACKEND_DIR / "Procfile",
            REPO_ROOT / "google_apps_script.js",
            REPO_ROOT / "backup" / "MIGRATION_STATUS.md",
            REPO_ROOT / "scripts" / "scan_secrets.py",
        ]
        for path in files:
            with self.subTest(path=path.name):
                self.assertTrue(path.exists(), path)
                self.assertEqual(self.scan._scan_file(path, path.relative_to(REPO_ROOT)), [])
