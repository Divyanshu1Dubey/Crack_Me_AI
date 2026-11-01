"""cleanup_seed_samples: old seed_data demo questions stored as PYQs (wave 2, W10)."""
from __future__ import annotations

import io
from collections import defaultdict

from django.core.management import call_command
from django.test import TestCase

from questions.management.commands.seed_data import sample_question_texts, sample_questions
from questions.models import Question, Subject


class CleanupSeedSamplesTests(TestCase):
    def setUp(self):
        self.subject = Subject.objects.create(name="General Medicine W10", code="MEDW10", exam_type="cms")
        samples = sample_questions(defaultdict(lambda: self.subject), {})
        self.ami, self.nephrotic, self.measles = samples[0], samples[1], samples[11]

        def make(sample, **overrides):
            data = {k: v for k, v in sample.items() if k not in {"topic"}}
            data.update(overrides)
            return Question.objects.create(**data)

        # As an older release stored them: a PYQ year and source "UPSC CMS".
        self.old = make(self.ami)                      # year 2023
        self.edited = make(self.nephrotic, admin_edited=True)  # year 2022, admin touched it
        self.already_fixed = make(self.measles, year=0)
        # A real question that shares a stem but not the sample's options.
        self.real = make(self.measles, option_a="10-14 days (real PYQ)", year=2019)

    def _run(self, *flags):
        out = io.StringIO()
        call_command("cleanup_seed_samples", *flags, stdout=out)
        return out.getvalue()

    def test_fifteen_samples(self):
        self.assertEqual(len(sample_question_texts()), 15)

    def test_dry_run_changes_nothing(self):
        out = self._run()
        self.assertIn("Dry run: 1 row(s) would get year=0", out)
        self.assertIn(f"skipped #{self.edited.id}", out)
        self.old.refresh_from_db()
        self.assertEqual(self.old.year, 2023)

    def test_apply_relabels_only_unprotected_sample_rows(self):
        self._run("--apply")
        for q in (self.old, self.edited, self.already_fixed, self.real):
            q.refresh_from_db()
        self.assertEqual(self.old.year, 0)
        self.assertTrue(self.old.is_active)
        self.assertEqual(self.edited.year, 2022, "admin-edited rows are left alone by default")
        self.assertEqual(self.real.year, 2019, "a different question with the same stem is not touched")

    def test_include_admin_edited_and_deactivate(self):
        self._run("--apply", "--include-admin-edited", "--deactivate")
        self.old.refresh_from_db()
        self.edited.refresh_from_db()
        self.real.refresh_from_db()
        self.assertEqual((self.old.year, self.old.is_active), (0, False))
        self.assertEqual((self.edited.year, self.edited.is_active), (0, False))
        self.assertTrue(self.real.is_active)

    def test_nothing_to_do(self):
        Question.objects.filter(pk__in=[self.old.pk, self.edited.pk]).update(year=0)
        self.assertIn("No seed demo questions", self._run("--apply"))
