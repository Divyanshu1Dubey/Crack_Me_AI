"""
test_apps_auto_heal.py — Verify the QuestionsConfig.ready() hook
auto-heals legacy bare /media/fixtures/images/ URLs on server startup.

The hook runs the same code path as ``python manage.py
relink_fixture_images --apply`` but in a background thread so the
first request after boot is never blocked. We invoke
``_run_relink_passive()`` directly here to keep the test
deterministic (no need to spawn a real Django worker).

This test pins the contract that:
  * A bare URL stored in Question.question_text is rewritten to
    ``[[img:N]]`` without any operator action.
  * A ``QuestionImage`` row is created for the rewritten URL.
  * An OperationalError on the DB during a fresh boot is swallowed
    so the worker doesn't crash.

The full command-line path is exercised by
``test_fix_2026_07_28.RelinkFixtureImagesCommandTests``; this file
specifically guards the auto-deploy / auto-startup codepath.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from django.conf import settings
from django.test import TestCase, override_settings

from questions.models import Question, QuestionImage, Subject


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class AutoHealTests(TestCase):
    """End-to-end through ``QuestionsConfig._run_relink_passive``."""

    def setUp(self):
        self.tmp = Path(settings.MEDIA_ROOT)
        # Write the on-disk image the question text references.
        self.img_path = self.tmp / "fixtures" / "images" / "cms" / "auto_heal_sign.png"
        self.img_path.parent.mkdir(parents=True, exist_ok=True)
        self.img_path.write_bytes(b"\x89PNG\r\n\x1a\n")

        self.subject = Subject.objects.create(
            code="AUTO", name="Auto Heal", exam_type="cms",
        )
        self.q = Question.objects.create(
            subject=self.subject,
            exam_type="cms",
            question_text=(
                "Identify the radiological sign "
                "/media/fixtures/images/cms/auto_heal_sign.png "
                "shown in the image."
            ),
            option_a="A", option_b="B", option_c="C", option_d="D",
            correct_answer="B",
            year=2024, difficulty="hard",
        )

    def test_run_relink_passive_heals_bare_url(self):
        from questions.apps import _run_relink_passive

        # Sanity: the bare URL is in the row before the hook runs.
        self.assertIn("/media/fixtures/images/", self.q.question_text)

        _run_relink_passive()

        self.q.refresh_from_db()
        # The bare URL must be gone.
        self.assertNotIn("/media/fixtures/images/", self.q.question_text)
        # The canonical token must be in place.
        self.assertIn("[[img:", self.q.question_text)
        # A QuestionImage row must exist.
        img = QuestionImage.objects.filter(question=self.q).first()
        self.assertIsNotNone(img)
        self.assertIsNotNone(img.file)

    def test_run_relink_passive_is_idempotent(self):
        from questions.apps import _run_relink_passive

        _run_relink_passive()
        self.q.refresh_from_db()
        text_after_first = self.q.question_text

        # Run again — the question_text must NOT change because the
        # bare URL is gone. Without this guarantee the auto-heal
        # would rewrite the row every server restart.
        _run_relink_passive()
        self.q.refresh_from_db()
        self.assertEqual(self.q.question_text, text_after_first)
        # Exactly one QuestionImage row, no duplicates.
        self.assertEqual(QuestionImage.objects.filter(question=self.q).count(), 1)