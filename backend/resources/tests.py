import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import TestCase, override_settings
from django.urls import reverse

from resources import views


class ExamGuideAttemptsTests(TestCase):
    """UPSC CMS has no attempt cap (only the age limit); the guide used to
    serve the Civil Services 6 / 9 / unlimited rule."""

    def test_eligibility_states_no_fixed_attempt_limit(self):
        res = self.client.get(reverse('exam-guide'))
        self.assertEqual(res.status_code, 200)
        attempts = res.json()['eligibility']['attempts']
        self.assertEqual(attempts, {'all': 'No fixed limit; subject to age ceiling'})

    def test_attempts_faq_matches_the_age_limit_rule(self):
        faq = {row['q']: row['a'] for row in self.client.get(reverse('exam-guide')).json()['faq']}
        answer = faq['How many attempts are allowed?']
        self.assertTrue(answer.startswith('There is no fixed limit on the number of attempts for UPSC CMS.'))
        self.assertIn('below 32 years on 1 August', answer)

    def test_no_civil_services_attempt_counts_anywhere_in_the_guide(self):
        body = json.dumps(self.client.get(reverse('exam-guide')).json())
        for stale in ('6 attempts', '9 attempts', 'Unlimited (up to age limit)'):
            self.assertNotIn(stale, body)

    def test_guide_is_public(self):
        # Anonymous visitors read it on /resources.
        self.assertEqual(self.client.get(reverse('exam-guide')).status_code, 200)


class ResourceResolverTests(TestCase):
    def test_resolve_resource_path_falls_back_from_copy_prefix(self):
        with TemporaryDirectory() as tmpdir:
            fallback_name = "Performa for OBC_1c21253a-640a-41b9-b4f8-8d59d8552d8a.pdf"
            fallback_path = Path(tmpdir) / fallback_name
            fallback_path.write_bytes(b"%PDF-1.4\n")

            with override_settings(BASE_DIR=tmpdir):
                original = views.MEDURA_DIR
                try:
                    views.MEDURA_DIR = tmpdir
                    resolved = views._resolve_resource_path(
                        "Copy of Performa for OBC_1c21253a-640a-41b9-b4f8-8d59d8552d8a.pdf"
                    )
                    self.assertEqual(resolved, str(fallback_path))
                finally:
                    views.MEDURA_DIR = original

    def test_resolve_resource_path_returns_none_for_missing_file(self):
        with TemporaryDirectory() as tmpdir:
            with override_settings(BASE_DIR=tmpdir):
                original = views.MEDURA_DIR
                try:
                    views.MEDURA_DIR = tmpdir
                    resolved = views._resolve_resource_path("does-not-exist.pdf")
                    self.assertIsNone(resolved)
                finally:
                    views.MEDURA_DIR = original
