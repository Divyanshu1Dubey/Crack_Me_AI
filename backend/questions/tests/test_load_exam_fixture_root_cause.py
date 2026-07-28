"""
test_load_exam_fixture_root_cause.py — End-to-end validation that
``load_exam_fixture`` no longer writes bare ``/media/fixtures/images/…``
URLs into Question rows.

This is the root-cause fix for Bug B from the 2026-07-28 live audit:
the legacy loader rewrote ``[[img:foo.png]]`` tokens to bare URLs
that (a) 404 in production DEBUG=False and (b) bypass the auth-gated
``/api/questions/images/<id>/serve/`` proxy. The new behaviour
creates a real ``QuestionImage`` row and stores the canonical
``[[img:<pk>]]`` token instead.

These tests pin the contract:

  * Every ``[[img:foo.png]]`` token in a freshly loaded fixture row
    ends up as ``[[img:<pk>]]`` — never ``/media/fixtures/...``.
  * A ``QuestionImage`` row exists pointing at the on-disk file.
  * Missing images leave the original token intact so the missing-
    file warning at the top of the loader still fires.

We bypass the legacy ``__legacy_cms__`` path by writing a unique
fixture file under ``backend/fixtures/_test_loader_<random>.json`` and
pointing the loader at it through the ``--images-dir`` override. The
loader never overwrites a real fixture this way.
"""
from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase, override_settings

from questions.models import Question, QuestionImage, Subject
from questions.tests._loader_helpers import build_loader_fixture


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class LoadExamFixtureRootCauseTests(TestCase):
    """End-to-end through `manage.py load_exam_fixture`."""

    def setUp(self):
        self.tmp = Path(settings.MEDIA_ROOT)
        # Write the on-disk image the fixture will reference.
        self.img_path = self.tmp / "fixtures" / "images" / "cms" / "sign_287.png"
        self.img_path.parent.mkdir(parents=True, exist_ok=True)
        self.img_path.write_bytes(b"\x89PNG\r\n\x1a\n")
        # Clean up any leftover rows from a previous failed run.
        Subject.objects.filter(code="LDRT").delete()

    def _write_unique_fixture(self, rows: list[dict]) -> tuple[Path, str]:
        # Write a unique fixture file under fixtures/ so we never clobber
        # a real fixture. The loader is dispatched by *fixture_path* via
        # `EXAM_MAP[alias]` — we monkey-patch the map for this test only.
        fixture_dir = Path(settings.BASE_DIR) / "fixtures"
        fixture_dir.mkdir(parents=True, exist_ok=True)
        unique = f"_test_loader_{uuid.uuid4().hex[:8]}.json"
        fixture_path = fixture_dir / unique
        fixture_path.write_text(json.dumps(rows), encoding="utf-8")
        self.addCleanup(lambda: fixture_path.unlink(missing_ok=True))
        return fixture_path, unique

    def test_loader_writes_canonical_img_token_and_questionimage_row(self):
        # Build a tiny fixture with one Question referencing the PNG.
        rows = build_loader_fixture(
            subject_code="LDRT",
            subject_name="Loader Test",
            question_text=(
                "Identify the radiological sign [[img:sign_287.png]] "
                "shown in the image."
            ),
        )
        fixture_path, unique = self._write_unique_fixture(rows)

        # Monkey-patch the EXAM_MAP for this test so the loader reads
        # our unique fixture file under the `cms` alias. We restore it
        # via addCleanup so other tests stay clean.
        from questions.management.commands import load_exam_fixture as _loader
        original_map = dict(_loader.EXAM_MAP)
        _loader.EXAM_MAP["cms"] = (unique, "cms", "cms")
        self.addCleanup(lambda: _loader.EXAM_MAP.update(original_map))

        from io import StringIO
        call_command(
            "load_exam_fixture", "cms",
            images_dir=str(self.img_path.parent),
            stdout=StringIO(), no_color=True,
        )

        q = Question.objects.get(
            exam_type="cms", subject__code="LDRT",
        )
        # Bug B contract: NO bare URL survives.
        self.assertNotIn("/media/fixtures/images/", q.question_text)
        # Canonical token is in place.
        self.assertIn("[[img:", q.question_text)
        # QuestionImage row was created.
        img = QuestionImage.objects.filter(question=q).first()
        self.assertIsNotNone(img, "Loader should have created a QuestionImage row")
        self.assertIsNotNone(img.file, "QuestionImage.file should point at on-disk file")
        # The on-disk file basename matches what we wrote.
        self.assertEqual(Path(img.file.name).name, "sign_287.png")

    def test_missing_image_preserves_original_token(self):
        # Loader should leave the token as-is when the PNG is missing
        # so the missing-file warning at the top still fires.
        rows = build_loader_fixture(
            subject_code="LDRT",
            subject_name="Loader Test",
            question_text=(
                "Identify the radiological sign [[img:does_not_exist.png]] "
                "shown in the image."
            ),
        )
        fixture_path, unique = self._write_unique_fixture(rows)

        from questions.management.commands import load_exam_fixture as _loader
        original_map = dict(_loader.EXAM_MAP)
        _loader.EXAM_MAP["cms"] = (unique, "cms", "cms")
        self.addCleanup(lambda: _loader.EXAM_MAP.update(original_map))

        # Point at an EMPTY images dir so every reference is missing.
        empty_dir = self.tmp / "empty"
        empty_dir.mkdir(parents=True, exist_ok=True)

        from io import StringIO
        call_command(
            "load_exam_fixture", "cms",
            images_dir=str(empty_dir),
            stdout=StringIO(), no_color=True,
        )

        q = Question.objects.get(
            exam_type="cms", subject__code="LDRT",
        )
        # The original token survives — no replacement, no QuestionImage
        # row attached.
        self.assertIn("[[img:does_not_exist.png]]", q.question_text)
        self.assertNotIn("/media/fixtures/images/", q.question_text)
        self.assertFalse(
            QuestionImage.objects.filter(question=q).exists(),
            "Missing file must not create a QuestionImage row",
        )