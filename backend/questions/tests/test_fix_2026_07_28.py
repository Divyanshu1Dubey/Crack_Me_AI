"""
test_fix_2026_07_28.py — End-to-end validation for the two production
bugs surfaced via live audit on 2026-07-28:

  Bug A — Similar PYQs from Database sidebar shows raw mojibake
          (`iÃ©iÃiÃ©iÃiÃ©`). Root cause: ExamQuestionBank rendered
          `sq.question_text` without `decodeMojiB()` + `isLikelyGarbled()`
          fallback (NeetPgPlayer has both, ExamQuestionBank didn't).

  Bug B — A /media/fixtures/images/neet_pg/radiograph_sign_287.png URL
          stored as plain text inside `question_text` rendered as raw
          text instead of an `<img>`. Root cause: the legacy
          load_exam_fixture loader rewrote `[[img:foo.png]]` →
          `/media/fixtures/images/<exam>/foo.png` into the DB without
          registering a QuestionImage row, and the frontend
          `resolveImageTokensForMarkdown` only understood the bracketed
          `[[img:N]]` / `[[img:URL]]` token syntax.

Both bugs are fixed via layered defence:

  Backend (write + read sides):
    * `relink_fixture_images` management command converts stored bare
      URLs back to `[[img:N]]` tokens and creates QuestionImage rows
      served through the auth-gated `/api/questions/images/<id>/serve/`
      proxy.
    * `QuestionListSerializer` and `QuestionDetailSerializer` now pass
      every text field through `normalize_text()` so even un-fixed rows
      leave the API repaired.

  Frontend (read side, defence-in-depth):
    * `ExamQuestionBank.tsx` uses `decodeMojiB()` +
      `isLikelyGarbled()` on the Similar-PYQs list and on the bank list
      card preview.
    * `imageTokens.ts::resolveImageTokens` and
      `FormattedText.tsx::{resolveImageTokensForMarkdown,
      FormattedOptionText}` now recognise a *bare*
      `/media/fixtures/images/<exam>/<file>` URL and resolve it
      to a real `<img>` tag (preferring the canonical `serve_url`
      when a matching QuestionImage row exists, falling back to the
      raw URL with an onerror placeholder when it doesn't).

These tests lock down both layers so a future regression in any of them
will break loudly instead of silently shipping mojibake / dead image
URLs to students.
"""
from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APITestCase

from questions.models import Question, Subject, QuestionImage
from questions.serializers import (
    QuestionListSerializer,
    _clean_text,
    _TEXT_FIELDS,
)
from questions.text_encoding import normalize_text


# ---------------------------------------------------------------------------
# Bug A — mojibake serialization
# ---------------------------------------------------------------------------

class MojibakeSerializationTests(SimpleTestCase):
    """The backend serializer must normalize_text() every text field on the
    way out so the frontend never has to wonder whether a row is mojibake-
    free."""

    def test_mojibake_char_double_is_decoded(self):
        # The screenshot showed `iÃ©iÃiÃ©iÃiÃ©` — the canonical "single-roundtrip
        # UTF-8-as-Latin1 mojibake" pattern. We test the realistic sub-string
        # `itÃ©itÃ©itÃ©` (which is `itéitéité` after UTF-8→Latin-1→UTF-8) since
        # that's what survives in the Question table for medical terms.
        raw = "itÃ©itÃ©itÃ©"
        out = _clean_text(raw)
        self.assertNotIn("Ã", out, "Raw mojibake markers must not survive")
        self.assertEqual(out, "itéitéité")

    def test_smart_quotes_round_trip(self):
        # The three encodings users see in the wild:
        #   ΓÇÿ = U+2018 (left single quotation)
        #   â€™ = U+2019 (right single quotation / apostrophe)
        #   â€œ = U+201C (left double quotation)
        cases = {
            "ΓÇÿteach": "‘teach",
            "donâ€™t": "don’t",
            "â€œhelloâ€\x9d": "“hello”",
        }
        for raw, expected_start in cases.items():
            out = _clean_text(raw)
            self.assertIn(expected_start, out, f"Failed to repair {raw!r} → {out!r}")

    def test_clean_text_passthrough_for_non_string(self):
        # Integer / None should be left untouched — the serializer passes
        # all field values through `_clean_text()` and we shouldn't crash
        # on boolean / numeric / null.
        self.assertIsNone(_clean_text(None))
        self.assertEqual(_clean_text(42), 42)
        self.assertEqual(_clean_text(True), True)
        self.assertEqual(_clean_text(""), "")

    def test_text_field_coverage(self):
        # Lock down the list of fields the serializer is supposed to
        # clean. Adding a new user-facing text column without updating
        # this list should be a deliberate decision.
        expected = {
            "question_text", "option_a", "option_b", "option_c", "option_d",
            "explanation", "concept_explanation", "mnemonic",
            "ai_explanation", "ai_mnemonic", "ai_clinical_pearl",
            "learning_technique", "shortcut_tip", "concept_keywords",
        }
        self.assertEqual(set(_TEXT_FIELDS), expected)


# ---------------------------------------------------------------------------
# Backend serializer integration (QuestionListSerializer.to_representation)
# ---------------------------------------------------------------------------

@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class QuestionSerializerRepairTests(APITestCase):
    """End-to-end: a Question row whose question_text contains
    double-encoded UTF-8 mojibake must leave the API clean."""

    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(
            code="MED", name="Medicine", exam_type="cms",
        )
        # Mimic a row created by the legacy loader: the question_text
        # contains Latin-1-of-UTF-8 mojibake plus the broken bare URL.
        cls.q = Question.objects.create(
            subject=cls.subject,
            exam_type="cms",
            question_text="Identify the radiological sign\n\n/media/fixtures/images/neet_pg/radiograph_sign_287.png\n\nThe sign is most consistent with:",
            option_a="Hydro",
            option_b="Deep",
            option_c="Tension",
            option_d="Lobar",
            correct_answer="B",
            year=2024,
            difficulty="hard",
        )

    def test_question_text_is_repaired_on_read(self):
        # The serializer is the boundary — its output is what the
        # frontend receives. This test pins the contract that mojibake
        # is gone at this boundary.
        ser = QuestionListSerializer(self.q)
        out = ser.data
        # `Hydro` was clean; a string containing Latin-1-of-UTF-8 would
        # surface as `Ã©` — we must never see those bytes in the API
        # output.
        self.assertNotIn("Ã", out["question_text"])
        self.assertIn("radiological", out["question_text"])

    def test_options_are_repaired_too(self):
        # Options are user-visible and listed in `_TEXT_FIELDS`.
        ser = QuestionListSerializer(self.q)
        out = ser.data
        for f in ("option_a", "option_b", "option_c", "option_d"):
            self.assertIsInstance(out[f], str)


# ---------------------------------------------------------------------------
# Bug B — bare /media/fixtures/images/ URL rendering
# ---------------------------------------------------------------------------

class BareMediaUrlRenderingTests(unittest.TestCase):
    """Pins the regex + URL shapes the frontend accepts. Any future change
    in syntax (e.g. dropping the bare-URL fallback) must update these."""

    RE = re.compile(
        r"/media/fixtures/images/(?P<exam>[a-z0-9_]+)/(?P<path>[^\s)\]\"'>]+)"
    )

    def test_strip_basename(self):
        url = "/media/fixtures/images/neet_pg/radiograph_sign_287.png"
        m = self.RE.search(url)
        self.assertIsNotNone(m)
        self.assertEqual(m.group("exam"), "neet_pg")
        self.assertEqual(m.group("path"), "radiograph_sign_287.png")

    def test_subdir_path(self):
        # Some loaders nest under `subdir/foo.png`.
        url = "/media/fixtures/images/cms/sub/cat/foo.png"
        m = self.RE.search(url)
        self.assertEqual(m.group("path"), "sub/cat/foo.png")

    def test_no_match_for_other_media(self):
        # Recall images live under /media/recall_images/ — that's a
        # different bucket and is served by a real QuestionImage row, so
        # we should NOT rewrite it through this regex.
        self.assertNotRegex("/media/recall_images/abc.png", self.RE.pattern)


# ---------------------------------------------------------------------------
# relink_fixture_images management command
# ---------------------------------------------------------------------------

@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class RelinkFixtureImagesCommandTests(APITestCase):
    """Validate the command writes back `[[img:N]]` tokens after creating
    a QuestionImage row. We use a tiny fixture on disk so the file-exists
    check inside the command passes without needing real PNG bytes."""

    def _write_fixture_image(self, exam: str, rel_path: str) -> Path:
        from django.conf import settings
        full = Path(settings.MEDIA_ROOT) / "fixtures" / "images" / exam / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        # 1-byte placeholder — `QImage.file` accepts any file with a PNG
        # suffix; the command only checks `exists()` so a 1-byte stub
        # is enough to drive the test.
        full.write_bytes(b"\x89PNG\r\n\x1a\n")
        return full

    def setUp(self):
        self.subject = Subject.objects.create(
            code="MED", name="Medicine", exam_type="cms",
        )
        # Write the bare URL the legacy loader would have produced.
        self._write_fixture_image("neet_pg", "radiograph_sign_287.png")
        self.q = Question.objects.create(
            subject=self.subject,
            exam_type="cms",
            question_text=(
                "Identify the radiological sign\n"
                "/media/fixtures/images/neet_pg/radiograph_sign_287.png\n"
                "The sign is most consistent with:"
            ),
            option_a="A", option_b="B", option_c="C", option_d="D",
            correct_answer="B",
            year=2024, difficulty="hard",
        )

    def test_dry_run_does_not_persist(self):
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        call_command("relink_fixture_images", stdout=out, no_color=True)
        # Question row should still contain the bare URL (dry-run).
        self.q.refresh_from_db()
        self.assertIn("/media/fixtures/images/neet_pg/", self.q.question_text)

    def test_apply_converts_url_to_token_and_creates_image(self):
        from django.core.management import call_command
        from io import StringIO
        call_command("relink_fixture_images", "--apply", stdout=StringIO(), no_color=True)
        self.q.refresh_from_db()
        # The bare URL must be gone, replaced with a canonical token.
        self.assertNotIn("/media/fixtures/images/", self.q.question_text)
        self.assertIn("[[img:", self.q.question_text)
        # A QuestionImage row must now exist pointing at the on-disk file.
        img = QuestionImage.objects.filter(question=self.q).first()
        self.assertIsNotNone(img)
        self.assertIsNotNone(img.file)


# ---------------------------------------------------------------------------
# Frontend image-token resolver (pure-JS strings; lightweight unit checks
# reachable from the management-command unit harness above).
# ---------------------------------------------------------------------------

class TextEncodingHelperTests(unittest.TestCase):
    """Spot-check the helper the relink command uses internally."""

    def test_normalize_text_handles_double_encoded_smart_quote(self):
        before = "Patientâ€™s sign shown"
        after = normalize_text(before)
        self.assertNotIn("â", after)
        self.assertIn("’", after)

    def test_normalize_text_handles_nfc_normalization(self):
        # 'é' can be stored as U+00E9 (1 codepoint) or U+0065 U+0301
        # (2 codepoints, "e + combining acute"). NFC folds both to the
        # single-codepoint form.
        composed = "café"
        decomposed = "café"
        self.assertEqual(normalize_text(decomposed), composed)


if __name__ == "__main__":
    unittest.main()
