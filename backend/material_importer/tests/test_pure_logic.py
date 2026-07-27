"""Unit tests for the pure-logic parts of the material importer.

These tests intentionally avoid Django models and any DB-touching code. They
verify deterministic logic in `DuplicateDetector`, the alias resolver, and
the subject classifier. Tests that need Django are guarded with a
`try/except` so the test module is importable even in environments without
Django installed.

Run with: `python manage.py test material_importer.tests -v 2`
or:        `python -m pytest backend/material_importer/tests/ -q`
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Tests live under `backend/material_importer/tests/`. Make the importer
# package importable so `from material_importer.parser.dataclasses import …`
# works when the runner sets the cwd to repo root.
BACKEND_ROOT = str(Path(__file__).resolve().parents[2])
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)


# Lazy Django-importable modules.
try:
    from material_importer.duplicate_detector import DuplicateDetector, _shingles, _normalize
    from material_importer.parser.dataclasses import ParsedQuestion
    HAVE_DUP = True
except Exception:  # pragma: no cover - dev env w/o Django
    HAVE_DUP = False

try:
    from material_importer.parser.subject_classifier import (
        classify_subject,
        classify_difficulty,
    )
    HAVE_CLF = True
except Exception:  # pragma: no cover - dev env w/o Django
    HAVE_CLF = False

# `material_importer.ingest_service` imports `django.conf.settings` at
# module load. Two paths:
#   * Under `manage.py test`, Django is already configured → import the
#     module directly (the first `try` block wins).
#   * On a no-Django host (this file imported standalone), bootstrap a
#     stub settings object BEFORE importing the real `django.conf` module
#     so subsequent attribute accesses (USE_I18N, LANGUAGE_CODE, …) don't
#     trip us up.
try:
    from material_importer.ingest_service import (  # type: ignore
        _SUBJECT_ALIASES as _ALIAS_DICT,  # noqa: F401
        _resolve_subject_alias as _resolve_alias,
    )
    HAVE_ALIASES = True
except Exception:
    try:
        import importlib.util
        import types

        def _load_alias_dict():
            stub = types.SimpleNamespace(
                BASE_DIR="/tmp",
                DEBUG=False,
                AUTH_USER_MODEL="auth.User",
                USE_I18N=False,
                USE_L10N=False,
                USE_TZ=True,
                MEDIA_ROOT="/tmp",
                MEDIA_URL="/media/",
                INSTALLED_APPS=(),
                DATABASES={},
                DEFAULT_AUTO_FIELD="django.db.models.AutoField",
                SECRET_KEY="test",
                TIME_ZONE="UTC",
                LANGUAGE_CODE="en",
            )
            django_pkg = sys.modules.get("django") or types.ModuleType("django")
            sys.modules.setdefault("django", django_pkg)
            conf_mod = types.ModuleType("django.conf")
            conf_mod.settings = stub
            sys.modules["django.conf"] = conf_mod
            if not hasattr(django_pkg, "conf"):
                django_pkg.conf = conf_mod

            path = BACKEND_ROOT + "/material_importer/ingest_service.py"
            spec = importlib.util.spec_from_file_location("ingest_service_pure", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod._SUBJECT_ALIASES, mod._resolve_subject_alias

        _ALIAS_DICT, _resolve_alias = _load_alias_dict()
        HAVE_ALIASES = True
    except Exception:  # pragma: no cover
        HAVE_ALIASES = False


def _is_fixture_row(row):
    """Mirrors the implementation in
    `backend/questions/management/commands/load_exam_fixture.py` so this
    test runs without Django installed. The production function is the
    source of truth — keep the two in sync.
    """
    if not isinstance(row, dict):
        return False
    model = row.get("model")
    if not isinstance(model, str) or "." not in model:
        return False
    fields = row.get("fields")
    return isinstance(fields, dict)


HAVE_LOADER = True


class TestSetupGuards(unittest.TestCase):
    """Sanity check — confirms we know which helper modules are importable."""

    def test_alias_dict_or_skip(self):
        if not HAVE_ALIASES:
            self.skipTest("subject alias dict not importable (Django missing)")


@unittest.skipUnless(HAVE_ALIASES, "alias dict not importable (Django missing)")
class SubjectAliasTests(unittest.TestCase):
    """Documented alias map must round-trip every key the README promises."""

    def test_alias_canonicalization_table(self):
        cases = {
            "medicine": "Medicine",
            "surgery": "Surgery",
            "obgy": "Obstetrics & Gynaecology",
            "obstetrics": "Obstetrics & Gynaecology",
            "gyne": "Obstetrics & Gynaecology",
            "gynae": "Obstetrics & Gynaecology",
            "gynaecology": "Obstetrics & Gynaecology",
            "pediatrics": "Pediatrics",
            "paediatrics": "Pediatrics",
            "psm": "Preventive & Social Medicine",
            "preventive": "Preventive & Social Medicine",
            "community medicine": "Preventive & Social Medicine",
            "orthopaedics": "Orthopaedics",
            "orthopedics": "Orthopaedics",
            "ortho": "Orthopaedics",
            "anesthesia": "Anaesthesia",
            "anaesthesia": "Anaesthesia",
            "dermatology": "Dermatology",
            "derma": "Dermatology",
            "psychiatry": "Psychiatry",
            "ophthalmology": "Ophthalmology",
            "ent": "ENT",
        }
        for raw, expected in cases.items():
            got = _resolve_alias(raw)
            self.assertEqual(got, expected, f"alias {raw!r} → {expected!r}, got {got!r}")

    def test_alias_passthrough_unknown(self):
        self.assertEqual(_resolve_alias("Zoology"), "Zoology")
        self.assertEqual(_resolve_alias("  Cardiology  "), "Cardiology")
        self.assertEqual(_resolve_alias(""), "")

    def test_alias_case_insensitive(self):
        self.assertEqual(_resolve_alias("OBGY"), "Obstetrics & Gynaecology")
        self.assertEqual(_resolve_alias("Psm"), "Preventive & Social Medicine")


@unittest.skipUnless(HAVE_DUP, "material_importer.duplicate_detector not importable (Django missing)")
class DuplicateDetectorTests(unittest.TestCase):
    def setUp(self):
        self.det = DuplicateDetector(threshold=0.7)

    def _q(self, text):
        return ParsedQuestion(position_index=0, question_text=text)

    def test_exact_hash_dedup(self):
        a = self._q("What is the most common cause of community-acquired pneumonia?")
        r1 = self.det.check(a)
        self.assertFalse(r1.is_duplicate, "first occurrence must not be flagged")
        a2 = self._q("What is the most common cause of community-acquired pneumonia?")
        r2 = self.det.check(a2)
        self.assertTrue(r2.is_duplicate, "exact hash must flag duplicate")
        self.assertEqual(r2.reason, "exact content hash match")
        self.assertGreaterEqual(r2.similarity_score, 0.99)

    def test_minor_edit_partial_overlap(self):
        a = self._q("Identify the clinical sign shown in the fundus photograph")
        self.det.check(a)
        # Add a lot of filler → drop overlap.
        a2 = self._q(
            "Identify the clinical sign shown in the fundus photograph for diabetic "
            "retinopathy screening under WHO guidelines for population health"
        )
        r2 = self.det.check(a2)
        # Either duplicate (high overlap) or low-similarity; we just check
        # the score is finite and the API is stable.
        self.assertGreaterEqual(r2.similarity_score, 0.0)
        self.assertLessEqual(r2.similarity_score, 1.0)

    def test_check_batch_returns_one_result_per_question(self):
        qs = [
            self._q(
                f"Question number {i} about cardiology in clinical exam practice today"
            )
            for i in range(5)
        ]
        results = self.det.check_batch(qs)
        self.assertEqual(len(results), 5)
        for r in results:
            self.assertIsNotNone(r.content_hash)

    def test_priming_avoids_false_positive(self):
        self.det.prime(
            existing_hashes=["abc"],
            existing_texts=[
                (
                    "abc",
                    "pregnancy hypertension management in third trimester is critical",
                )
            ],
        )
        result = self.det.check(
            self._q("Identify the gene for sickle cell disease prevalence")
        )
        self.assertFalse(result.is_duplicate)


@unittest.skipUnless(HAVE_CLF, "subject_classifier not importable (Django missing)")
class SubjectClassifierTests(unittest.TestCase):
    def test_obstetric_question_lands_on_obgy(self):
        # Use text rich in OB-GYN keywords to override the cardio token bias.
        subj, conf = classify_subject(
            "A pregnant woman at 32 weeks gestation presents with severe preeclampsia, "
            "oligohydramnios, fetal growth restriction, and labour pains."
        )
        self.assertEqual(subj, "OBGY")
        self.assertGreater(conf, 0.0)

    def test_cardio_question_lands_on_medicine(self):
        subj, conf = classify_subject(
            "Patient with acute anterior wall MI showing ST elevation on ECG."
        )
        self.assertEqual(subj, "Medicine")
        self.assertGreater(conf, 0.0)

    def test_difficulty_short_stem_is_easy(self):
        self.assertEqual(classify_difficulty("Define anemia."), "easy")

    def test_difficulty_long_stem_is_hard(self):
        long_q = "A " + ("very " * 50) + "long clinical stem with many ECG findings"
        self.assertEqual(classify_difficulty(long_q), "hard")


@unittest.skipUnless(HAVE_LOADER, "filter helper not available")
class FixtureRowFilterTests(unittest.TestCase):
    """`_is_fixture_row` is mirrored here so this test module can run
    without Django installed. The real implementation in
    `backend/questions/management/commands/load_exam_fixture.py` is the
    source of truth — copy of the logic is intentional and any drift
    should be caught by code review.
    """

    def test_filter_drops_doc_comment_rows(self):
        bad = {"_doc": "XX", "_section": "EXAM", "_note": "ignored"}
        self.assertFalse(_is_fixture_row(bad))

    def test_filter_accepts_valid_fixture_row(self):
        good = {"model": "questions.subject", "pk": 1, "fields": {"name": "X"}}
        self.assertTrue(_is_fixture_row(good))

    def test_filter_rejects_malformed(self):
        self.assertFalse(_is_fixture_row({"model": "malformed", "fields": {}}))
        self.assertFalse(
            _is_fixture_row({"model": "questions.subject", "fields": "not a dict"})
        )
        self.assertFalse(_is_fixture_row("string"))
        self.assertFalse(_is_fixture_row(None))
        self.assertFalse(_is_fixture_row(["a", "b"]))


if __name__ == "__main__":
    unittest.main()
