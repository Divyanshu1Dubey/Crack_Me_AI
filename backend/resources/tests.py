from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import TestCase, override_settings

from resources import views


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
