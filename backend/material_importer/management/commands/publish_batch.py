"""Manage batch → tests pipeline from the CLI.

Usage:
    python manage.py publish_batch --batch 12              # one batch
    python manage.py publish_batch --all-pending           # every batch with
                                                         # approved rows
    python manage.py publish_batch --batch 12 --max-per-test 50
"""
from __future__ import annotations

import argparse

from django.core.management.base import BaseCommand

from ...mock_test_builder import publish_batch, publish_batch_and_build_tests
from ...models import ExtractedQuestion, ImportBatch


class Command(BaseCommand):
    help = "Publish approved extracted questions to the live Question bank and build auto-tests."

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--batch", type=int, default=None, help="Single batch id.")
        parser.add_argument(
            "--all-pending",
            action="store_true",
            help="Process every batch that has at least one approved-but-unpublished row.",
        )
        parser.add_argument("--max-per-test", type=int, default=100)
        parser.add_argument(
            "--only-publish",
            action="store_true",
            help="Publish only; do NOT auto-build tests.",
        )

    def handle(self, *args, **opts):
        if not opts["batch"] and not opts["all_pending"]:
            self.stderr.write("Pass --batch N or --all-pending.")
            return

        if opts["batch"]:
            batches = list(ImportBatch.objects.filter(pk=opts["batch"]))
        else:
            pending_ids = (
                ExtractedQuestion.objects.filter(
                    status="approved", published_question__isnull=True
                )
                .values_list("material__batch_id", flat=True)
                .distinct()
            )
            batches = list(ImportBatch.objects.filter(pk__in=list(pending_ids)))

        for batch in batches:
            if opts["only_publish"]:
                n = publish_batch(batch.id)
                self.stdout.write(self.style.SUCCESS(
                    f"Batch#{batch.id}: published {n} new Questions (no tests built)."
                ))
            else:
                res = publish_batch_and_build_tests(
                    batch.id, max_per_test=opts["max_per_test"]
                )
                self.stdout.write(self.style.SUCCESS(
                    f"Batch#{batch.id}: published={res['published']} tests_built={res['tests_built']}"
                ))
