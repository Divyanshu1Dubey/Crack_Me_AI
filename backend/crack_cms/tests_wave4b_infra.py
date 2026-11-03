"""Infrastructure regressions, wave 4b (group Z9 follow-ups).

* build.sh lists the legacy is_subscribed accounts without a plan on every
  deploy, as a dry run that never writes and never fails the build.
* The production-audit workflow never puts the QA / live-audit credentials
  into an artifact: Playwright's HTML report titles fill steps with the typed
  value (`Fill "<password>"`), traces record inputs and the auth traffic, and
  the error-context page snapshot lists every <input> value. The runs use the
  line reporter with tracing and page snapshots off, and the uploads are
  allowlists.
"""
from __future__ import annotations

import io
import unittest
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

try:  # PyYAML ships with the dev / CI requirements
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

BACKEND_DIR = Path(settings.BASE_DIR)
REPO_ROOT = BACKEND_DIR.parent
AUDIT_YML = REPO_ROOT / ".github" / "workflows" / "production-audit.yml"


def _commands(path):
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")]


class DeployLegacySubscriptionReportTests(SimpleTestCase):
    def test_build_sh_reports_legacy_flags_as_a_dry_run(self):
        commands = _commands(BACKEND_DIR / "build.sh")
        report = [c for c in commands if "reconcile_legacy_subscriptions" in c]
        # Report only: no --apply / --clear-unproven, and it cannot fail the build.
        self.assertEqual(report, ["python manage.py reconcile_legacy_subscriptions || true"])
        # After migrate (it reads accounts.0026's rows) and next to the
        # identity-link dry run.
        self.assertGreater(commands.index(report[0]), commands.index("python manage.py migrate --no-input"))
        self.assertEqual(
            commands.index(report[0]),
            commands.index("python manage.py link_supabase_identity --all-privileged || true") + 1,
        )
        text = (BACKEND_DIR / "build.sh").read_text(encoding="utf-8")
        self.assertIn("#   python manage.py reconcile_legacy_subscriptions --apply --clear-unproven", text)



class DeployLegacySubscriptionDryRunTests(TestCase):
    def test_the_deploy_invocation_writes_nothing(self):
        from accounts.models import Subscription

        User = get_user_model()
        flagged = User.objects.create_user(username="z9b-flagged", email="z9b-flagged@example.com",
                                           password="unused-pw-1", is_subscribed=True)
        out = io.StringIO()
        call_command("reconcile_legacy_subscriptions", stdout=out)  # exactly what build.sh runs
        self.assertIn("Dry run", out.getvalue())
        flagged.refresh_from_db()
        self.assertTrue(flagged.is_subscribed)
        self.assertFalse(Subscription.objects.filter(user=flagged).exists())


@unittest.skipUnless(AUDIT_YML.exists() and yaml is not None, "production-audit.yml / PyYAML not available")
class ProductionAuditArtifactTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.jobs = yaml.safe_load(AUDIT_YML.read_text(encoding="utf-8"))["jobs"]

    def _runs(self, job):
        return [s for s in self.jobs[job]["steps"] if "playwright test" in str(s.get("run", ""))]

    def _uploads(self, job):
        return [s for s in self.jobs[job]["steps"] if "upload-artifact" in str(s.get("uses", ""))]

    def test_playwright_runs_record_no_trace_page_snapshot_or_report_steps(self):
        for job in ("visual-snapshots", "live-audit"):
            runs = self._runs(job)
            self.assertEqual(len(runs), 1, job)
            command = runs[0]["run"]
            self.assertIn("--trace off", command, job)
            self.assertIn("--reporter=line ", command, job)
            for reporter in ("html", "json", "blob"):
                self.assertNotIn(reporter, command.split("--reporter=", 1)[1].split()[0], job)
            self.assertEqual(str(runs[0]["env"].get("PLAYWRIGHT_NO_COPY_PROMPT")), "1", job)

    def test_uploads_are_allowlists_without_reports_traces_or_failure_screenshots(self):
        allowed_suffixes = ("-actual.png", "-expected.png", "-diff.png", "-linux.png", "/bug-report.json")
        for job in ("visual-snapshots", "live-audit"):
            uploads = self._uploads(job)
            self.assertTrue(uploads, job)
            for step in uploads:
                paths = [p.strip() for p in str(step["with"]["path"]).splitlines() if p.strip()]
                for path in paths:
                    with self.subTest(job=job, path=path):
                        self.assertNotIn("playwright-report", path)
                        self.assertTrue(path.endswith(allowed_suffixes), path)
                        for banned in (".zip", ".webm", ".md", "storage", ".auth", "test-failed"):
                            self.assertNotIn(banned, path)

    def test_the_visual_job_gets_only_the_qa_student_credentials(self):
        env = self._runs("visual-snapshots")[0]["env"]
        self.assertFalse([key for key in env if key.startswith("LIVE_AUDIT_")])
        self.assertIn("QA_TEST_USER_PASSWORD", env)
        live_env = self._runs("live-audit")[0]["env"]
        self.assertFalse([key for key in live_env if key.startswith("QA_")])
