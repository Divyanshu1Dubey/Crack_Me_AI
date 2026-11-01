"""seed_jobs.py (repo root) creates no placeholder listings (wave 3, Z8)."""
from __future__ import annotations

import contextlib
import importlib.util
import io
from pathlib import Path

from django.conf import settings
from django.test import TestCase

from jobs.models import Job


def _load_seed_script():
    path = Path(settings.BASE_DIR).parent / "seed_jobs.py"
    spec = importlib.util.spec_from_file_location("z8_seed_jobs_script", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # django.setup() is a no-op once apps are ready
    return module


class SeedJobsScriptTests(TestCase):
    def _job(self, title, **kw):
        return Job.objects.create(title=title, hospital="H", location="L", description="d",
                                  apply_link="https://example.org/apply", **kw)

    def test_seeds_nothing_and_removes_old_placeholders_only_on_request(self):
        script = _load_seed_script()
        real = self._job("Medical Officer, CGHS")
        stale = self._job(script.PLACEHOLDER_TITLES[0])
        edited = self._job(script.PLACEHOLDER_TITLES[1], admin_edited=True)

        with contextlib.redirect_stdout(io.StringIO()) as out:
            script.seed_jobs()
        self.assertEqual(set(Job.objects.values_list("id", flat=True)), {real.id, stale.id, edited.id})
        self.assertIn("--delete-placeholders", out.getvalue())

        with contextlib.redirect_stdout(io.StringIO()):
            script.seed_jobs(delete_placeholders=True)
        self.assertEqual(set(Job.objects.values_list("id", flat=True)), {real.id, edited.id})
        self.assertFalse(Job.objects.filter(title__icontains="coming soon", admin_edited=False).exists())
