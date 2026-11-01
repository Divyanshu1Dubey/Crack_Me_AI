"""seed_question_bank: the explicit, idempotent deploy seed step (review of
QB-15 -- request-time bootstrapping was removed and nothing replaced it, so
a fresh database had no subjects and no CMS questions)."""
from __future__ import annotations

import json
import re
import tempfile
from io import StringIO
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase

from questions.management.commands import load_exam_fixture as loader
from questions.management.commands import seed_question_bank as seed
from questions.models import Question, RemovedQuestion, Subject, Topic, compute_stem_hash

STEM_1 = "Seed fixture question one: drug of choice for absence seizures?"
STEM_2 = "Seed fixture question two: most common site of berry aneurysm?"


def _fixture_rows():
    question = {
        "option_a": "Ethosuximide", "option_b": "Phenytoin", "option_c": "Carbamazepine", "option_d": "Gabapentin",
        "correct_answer": "A", "year": 2024, "subject": "SDM", "topic": "Seed Topic", "difficulty": "medium",
        "explanation": "Fixture explanation.", "paper": 1, "exam_source": "UPSC CMS", "is_active": True,
    }
    return [
        {"model": "questions.subject", "pk": 1, "fields": {"name": "Seed Medicine", "code": "SDM", "paper": 1}},
        {"model": "questions.topic", "pk": 1, "fields": {"subject": "SDM", "name": "Seed Topic"}},
        {"model": "questions.question", "fields": {**question, "question_text": STEM_1}},
        {"model": "questions.question", "fields": {**question, "question_text": STEM_2, "correct_answer": "B"}},
    ]


def run(*args):
    out = StringIO()
    call_command("seed_question_bank", *args, stdout=out, stderr=StringIO())
    return out.getvalue()


class SeedQuestionBankTests(TestCase):
    def setUp(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "cms_fixture.json").write_text(json.dumps(_fixture_rows()), encoding="utf-8")
        (tmp / "images" / "cms").mkdir(parents=True)
        for module in (loader, seed):
            patcher = mock.patch.object(module, "FIXTURES_DIR", tmp)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _cms(self):
        return Question.objects.filter(exam_type="cms", exam_source="UPSC CMS")

    def test_empty_bank_is_seeded_with_subjects_topics_and_questions(self):
        output = run()
        self.assertIn("loading", output)
        self.assertEqual(set(self._cms().values_list("question_text", flat=True)), {STEM_1, STEM_2})
        subject = Subject.objects.get(code="SDM")
        self.assertEqual(subject.exam_type, "cms")
        self.assertTrue(Topic.objects.filter(subject=subject, name="Seed Topic").exists())

    def test_existing_bank_is_never_overwritten(self):
        run()
        Question.objects.filter(question_text=STEM_1).update(explanation="Edited in production.", is_active=False)
        with mock.patch.object(seed, "call_command") as load:
            output = run()
        load.assert_not_called()
        self.assertIn("not seeded", output)
        row = Question.objects.get(question_text=STEM_1)
        self.assertEqual(row.explanation, "Edited in production.")
        self.assertFalse(row.is_active)
        self.assertEqual(self._cms().count(), 2)

    def test_rows_of_another_exam_under_exam_type_cms_do_not_count(self):
        # The old NEET PG import stored its rows as exam_type="cms".
        subject = Subject.objects.create(name="Legacy", code="LGC")
        Question.objects.create(
            question_text="Legacy NEET PG row", option_a="a", option_b="b", option_c="c", option_d="d",
            correct_answer="A", year=2020, subject=subject, exam_type="cms", exam_source="NEET PG",
        )
        self.assertTrue(seed.bank_is_empty("cms"))
        run()
        self.assertEqual(self._cms().count(), 2)

    def test_admin_removed_questions_stay_removed(self):
        RemovedQuestion.objects.create(exam_source="UPSC CMS", year=2024, question_text_hash=compute_stem_hash(STEM_1))
        run()
        self.assertEqual(list(self._cms().values_list("question_text", flat=True)), [STEM_2])

    def test_a_live_bank_does_not_need_the_fixture(self):
        run()
        with mock.patch.object(seed, "FIXTURES_DIR", Path(tempfile.mkdtemp())):   # fixture missing
            self.assertFalse(seed.bank_is_empty("cms"))
            self.assertIn("not seeded", run())

    def test_dry_run_writes_nothing(self):
        output = run("--dry-run")
        self.assertIn("would load", output)
        self.assertFalse(Question.objects.exists())

    def test_unknown_exam_is_rejected(self):
        with self.assertRaises(CommandError):
            run("usmle")


class DeploySeedStepTests(SimpleTestCase):
    def test_build_sh_seeds_after_migrating(self):
        commands = [
            line.strip() for line in (Path(settings.BASE_DIR) / "build.sh").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        migrate = next(i for i, line in enumerate(commands) if re.search(r"manage\.py migrate\b", line))
        seed_step = next(i for i, line in enumerate(commands) if "manage.py seed_question_bank" in line)
        self.assertGreater(seed_step, migrate)
        # Not `load_exam_fixture` on every deploy: that would overwrite a live bank.
        self.assertFalse([line for line in commands if "load_exam_fixture" in line])

    def test_the_real_cms_fixture_is_seedable(self):
        self.assertEqual(seed.fixture_exam_sources("cms"), {"UPSC CMS"})
