import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase, override_settings

from questions.models import Question, Subject, Topic
from video_engine.services import ENGINE_VERSION, VideoGeneratorService


class _FakeSlide:
    def save(self, path, _format):
        Path(path).write_bytes(b"fake-png-bytes")


@override_settings(MEDIA_ROOT=tempfile.gettempdir())
class VideoGeneratorServiceTests(TestCase):
    def setUp(self):
        subject = Subject.objects.create(name="Medicine", code="MED", paper=1)
        topic = Topic.objects.create(subject=subject, name="Cardiology")
        self.question = Question.objects.create(
            question_text="What is the most likely diagnosis?",
            option_a="Option A",
            option_b="Option B",
            option_c="Option C",
            option_d="Option D",
            correct_answer="A",
            year=2024,
            subject=subject,
            topic=topic,
            explanation="Because the clinical presentation supports option A.",
            difficulty="medium",
        )

    @patch.object(VideoGeneratorService, "_cleanup")
    @patch.object(VideoGeneratorService, "_save_script_cache")
    @patch.object(VideoGeneratorService, "_write_vtt")
    @patch.object(VideoGeneratorService, "_assemble", return_value=42.4)
    @patch.object(VideoGeneratorService, "_tts", return_value=True)
    @patch.object(VideoGeneratorService, "_upload")
    @patch.object(VideoGeneratorService, "_build_sections")
    def test_generate_for_question_persists_video_metadata_and_upload_content_types(
        self,
        mock_build_sections,
        mock_upload,
        *_mocks,
    ):
        mock_build_sections.return_value = [
            {"slide": _FakeSlide(), "narration": "Intro narration", "min_dur": 5, "title": "Intro"},
            {"slide": _FakeSlide(), "narration": "Outro narration", "min_dur": 6, "title": "Outro"},
        ]
        mock_upload.side_effect = lambda _path, file_name, _ctype="application/octet-stream": f"https://dev.local/videos/{file_name}"

        service = VideoGeneratorService()
        result = service.generate_for_question(self.question.id)

        self.assertTrue(result)
        self.question.refresh_from_db()
        self.assertEqual(self.question.video_status, "completed")
        self.assertEqual(self.question.video_duration, 42)
        self.assertEqual(self.question.video_version, ENGINE_VERSION)
        self.assertTrue(self.question.video_thumbnail.endswith(".png"))
        self.assertEqual(self.question.video_error, "")

        content_types = [call.args[2] for call in mock_upload.call_args_list]
        self.assertIn("video/mp4", content_types)
        self.assertIn("image/png", content_types)
        self.assertIn("text/vtt", content_types)

    def test_save_script_cache_writes_local_script_file(self):
        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                service = VideoGeneratorService()
                with patch.object(service, "_upload", return_value="https://dev.local/script.json"):
                    script = {"question_id": self.question.id, "scenes": [{"title": "Intro"}]}
                    service._save_script_cache(script, "abc123def4567890")

                local_path = Path(media_root) / "video_engine" / "scripts" / f"q_{self.question.id}_abc123def4567890_script.json"
                self.assertTrue(local_path.exists())
                self.assertIn('"question_id":', local_path.read_text(encoding="utf-8"))
