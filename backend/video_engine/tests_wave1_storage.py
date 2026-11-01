"""Regression test for the video engine storage handling (wave 1, G11: M10).

Without storage credentials the engine used to "upload" to a fake
https://dev.local/ URL and mark the video completed. It must now fail
honestly, before rendering anything.
"""
from __future__ import annotations

import os
from unittest.mock import patch

from django.test import TestCase

from questions.models import Question, Subject
from video_engine.services import VideoGeneratorService


class MissingStorageTests(TestCase):
    def setUp(self):
        subject = Subject.objects.create(name="Medicine VE", code="MEDVE")
        self.q = Question.objects.create(
            question_text="Which drug is first-line?", option_a="a", option_b="b",
            option_c="c", option_d="d", correct_answer="A", year=2020, subject=subject,
        )

    def _env_without_storage(self):
        env = {k: v for k, v in os.environ.items()
               if k not in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY")}
        return patch.dict(os.environ, env, clear=True)

    def test_generation_fails_instead_of_saving_a_fake_url(self):
        with self._env_without_storage():
            service = VideoGeneratorService()
            with patch.object(service, "_build_or_load_script") as build:
                ok = service.generate_for_question(self.q.id)
            build.assert_not_called()  # failed fast, before any rendering work
        self.assertFalse(ok)
        self.q.refresh_from_db()
        self.assertEqual(self.q.video_status, "failed")
        self.assertIn("storage is not configured", self.q.video_error)
        self.assertNotIn("dev.local", self.q.video_url or "")

    def test_upload_returns_none_without_credentials(self):
        with self._env_without_storage():
            self.assertIsNone(VideoGeneratorService()._upload(__file__, "x.mp4"))
