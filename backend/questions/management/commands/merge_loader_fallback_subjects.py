"""
merge_loader_fallback_subjects.py — One-time idempotent migration.

The ``material_importer/publishing.py`` falls back to creating a Subject
row named "Imported" whenever a published question has no detectable
medical subject. In production we ended up with multiple "Imported"
Subject rows (one per exam_type), each owning its own question set.
They all show as "Expert Curated" in the question-bank filter
dropdown after the serializer rename, which is confusing — users see
two identical "Expert Curated (NNN)" entries.

This management command merges every ``Subject.name == "Imported"`` row
into a single canonical row, then re-points every Question that
referred to a non-canonical "Imported" Subject at the canonical one.
Safe to re-run; idempotent.

Usage:

    python manage.py merge_loader_fallback_subjects                # dry-run
    python manage.py merge_loader_fallback_subjects --apply
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from questions.models import Subject, Question


class Command(BaseCommand):
    help = (
        "Merge every duplicate loader-created 'Imported' Subject into a single "
        "canonical 'Imported' Subject so the Question Bank filter shows ONE "
        "'Expert Curated' entry instead of multiple identical rows."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Perform the migration. Without this flag the command prints the plan and exits.",
        )

    def handle(self, *args, **options):
        rows = list(Subject.objects.filter(name__iexact="Imported").order_by("id"))
        if len(rows) <= 1:
            self.stdout.write(self.style.SUCCESS(
                "merge_loader_fallback_subjects: nothing to merge "
                f"({len(rows)} 'Imported' Subject row exists)."
            ))
            return

        # The smallest id is the canonical bucket; everything else gets re-pointed
        # at it and deleted.
        canonical = rows[0]
        duplicates = rows[1:]
        question_total = sum(r.questions.count() for r in rows)
        self.stdout.write(
            f"merge_loader_fallback_subjects: planning merge of {len(duplicates)} "
            f"duplicate(s) into Subject id={canonical.id}. Total affected questions: "
            f"{question_total}."
        )

        if not options["apply"]:
            self.stdout.write(self.style.WARNING(
                "Dry-run only — re-run with --apply to commit. "
                "No changes written."
            ))
            return

        with transaction.atomic():
            moved = 0
            for dup in duplicates:
                qs = Question.objects.filter(subject=dup)
                count = qs.count()
                qs.update(subject=canonical)
                moved += count
                dup.delete()
                self.stdout.write(f"  - re-pointed {count:>5d} questions from Subject id={dup.id}")
            self.stdout.write(self.style.SUCCESS(
                f"merge_loader_fallback_subjects: re-pointed {moved} questions to "
                f"canonical Subject id={canonical.id}, deleted {len(duplicates)} duplicate row(s)."
            ))
