"""Regression tests for seed_data (L11) and relink_fixture_images (M8), wave 1 G11."""
from __future__ import annotations

import io
import json
import shutil
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase, override_settings

from questions.models import Question, QuestionImage, RemovedQuestion, Subject, compute_stem_hash

SAMPLE_STEM = "Which of the following is the most common cause of acute myocardial infarction?"


class SeedDataTests(TestCase):
    @override_settings(DEBUG=False)
    def test_samples_skipped_in_production(self):
        call_command("seed_data", stdout=io.StringIO())
        self.assertTrue(Subject.objects.filter(code="MED").exists())
        self.assertFalse(Question.objects.filter(question_text=SAMPLE_STEM).exists())

    @override_settings(DEBUG=False)
    def test_samples_are_not_pyqs_respect_tombstones_and_existing_rows(self):
        RemovedQuestion.objects.create(exam_source="UPSC CMS", year=2023,
                                       question_text_hash=compute_stem_hash(SAMPLE_STEM))
        call_command("seed_data", "--with-samples", stdout=io.StringIO())
        self.assertFalse(Question.objects.filter(question_text=SAMPLE_STEM).exists(),
                         "a tombstoned sample must not come back")
        samples = Question.objects.all()
        self.assertTrue(samples.exists())
        self.assertEqual(set(samples.values_list("year", flat=True)), {0})

        # An admin edit to a sample is never reverted or duplicated.
        q = samples.first()
        Question.objects.filter(pk=q.pk).update(explanation="Admin explanation")
        before = Question.objects.count()
        call_command("seed_data", "--with-samples", stdout=io.StringIO())
        self.assertEqual(Question.objects.count(), before)
        q.refresh_from_db()
        self.assertEqual(q.explanation, "Admin explanation")


class RelinkFixtureImagesTests(TestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp(prefix="g11_relink_media_")
        self.base = tempfile.mkdtemp(prefix="g11_relink_base_")
        self._override = override_settings(MEDIA_ROOT=self.media, BASE_DIR=Path(self.base))
        self._override.enable()
        self.subject = Subject.objects.create(name="Radiology RL", code="RADRL")
        self.url = "/media/fixtures/images/neet_pg/sign_287.png"

    def tearDown(self):
        self._override.disable()
        shutil.rmtree(self.media, ignore_errors=True)
        shutil.rmtree(self.base, ignore_errors=True)

    def _question(self, text):
        return Question.objects.create(question_text=text, option_a="a", option_b="b", option_c="c",
                                       option_d="d", correct_answer="A", year=2021, subject=self.subject)

    def test_missing_image_url_is_left_untouched(self):
        q = self._question(f"Identify the sign ![img]({self.url})")
        call_command("relink_fixture_images", "--apply", stdout=io.StringIO())
        q.refresh_from_db()
        self.assertIn(self.url, q.question_text, "a missing file must never destroy the URL")
        self.assertNotIn("image unavailable", q.question_text)

    def test_mark_missing_is_reversible(self):
        q = self._question(f"Identify the sign ![img]({self.url})")
        call_command("relink_fixture_images", "--apply", "--mark-missing", stdout=io.StringIO())
        q.refresh_from_db()
        self.assertIn("[image unavailable: neet_pg/sign_287.png]", q.question_text)

        # The image arrives later (only under BASE_DIR): the marker is relinked.
        img_dir = Path(self.base) / "fixtures" / "images" / "neet_pg"
        img_dir.mkdir(parents=True)
        (img_dir / "sign_287.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")
        call_command("relink_fixture_images", "--apply", stdout=io.StringIO())
        q.refresh_from_db()
        img = QuestionImage.objects.get(question=q)
        self.assertIn(f"[[img:{img.id}]]", q.question_text)
        self.assertTrue((Path(self.media) / img.file.name).exists(), "file copied into MEDIA_ROOT")

    def test_fixture_mirror_writes_only_real_image_ids(self):
        img_dir = Path(self.media) / "fixtures" / "images" / "neet_pg"
        img_dir.mkdir(parents=True)
        (img_dir / "sign_287.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")
        q = self._question(f"Identify the sign ![img]({self.url})")
        fixture = Path(self.base) / "fixture.json"
        fixture.write_text(json.dumps([
            {"model": "questions.question", "pk": q.pk, "fields": {"question_text": q.question_text}},
            {"model": "questions.question", "pk": 999999,
             "fields": {"question_text": "Other ![x](/media/fixtures/images/neet_pg/missing.png)"}},
        ]), encoding="utf-8")
        call_command("relink_fixture_images", "--apply", "--fixture", str(fixture), stdout=io.StringIO())
        data = json.loads(fixture.read_text(encoding="utf-8"))
        img = QuestionImage.objects.get(question=q)
        self.assertIn(f"[[img:{img.id}]]", data[0]["fields"]["question_text"])
        self.assertIn("/media/fixtures/images/neet_pg/missing.png", data[1]["fields"]["question_text"])
        self.assertNotIn("10000001", fixture.read_text(encoding="utf-8"))
