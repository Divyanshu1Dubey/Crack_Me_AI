"""One-off cleanup: old seed_data demo questions stored as PYQs of a year.

``seed_data`` inserts 15 hand-written demo questions. Releases before the
fix stored them with years 2019-2023 and ``exam_source='UPSC CMS'``, so the
live bank shows them as UPSC CMS PYQs of those years. ``seed_data`` now
inserts them with year=0 ("Expert Curated"), but rows created earlier keep
their year. This command finds those rows — same stem, first option and
answer as a seed sample, with a non-zero year — and sets year=0.

Dry run by default; nothing is written without ``--apply``.

    python manage.py cleanup_seed_samples                 # report only
    python manage.py cleanup_seed_samples --apply         # set year=0
    python manage.py cleanup_seed_samples --apply --deactivate   # also hide them

Rows an admin edited, verified or answer-locked are reported but left alone
unless ``--include-admin-edited`` is passed.
"""
from __future__ import annotations

from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from questions.models import Question


def _stored_forms(value: str, *, stem: bool = False) -> set[str]:
    """``value`` as written by seed_data and as ``Question.save()`` stores it."""
    from questions.text_encoding import normalize_text

    probe = Question()
    normalized = (
        probe._normalize_statement_text(value) if stem else probe._normalize_text_value(value)
    )
    return {value, normalize_text(normalized)}


def find_seed_sample_rows():
    """``(sample, queryset)`` per seed sample: live rows with a non-zero year."""
    from questions.management.commands.seed_data import sample_questions

    for sample in sample_questions(defaultdict(lambda: None), {}):
        rows = (
            Question.objects
            .filter(
                question_text__in=_stored_forms(sample["question_text"], stem=True),
                option_a__in=_stored_forms(sample["option_a"]),
                correct_answer=sample["correct_answer"],
            )
            .exclude(year=0)
            .order_by("id")
        )
        yield sample, rows


class Command(BaseCommand):
    help = ("Set year=0 on the old seed_data demo questions that were stored as PYQs "
            "of a year (dry run unless --apply).")

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Write the changes (default: dry run).")
        parser.add_argument(
            "--deactivate", action="store_true",
            help="Also take the matched rows out of the bank (is_active=False).",
        )
        parser.add_argument(
            "--include-admin-edited", action="store_true",
            help="Also change rows an admin edited, verified or answer-locked.",
        )

    def handle(self, *args, **opts):
        apply = opts["apply"]
        to_fix: list[Question] = []
        protected: list[Question] = []
        for sample, rows in find_seed_sample_rows():
            for q in rows:
                is_protected = q.admin_edited or q.is_verified_by_admin or q.lock_answer
                if is_protected and not opts["include_admin_edited"]:
                    protected.append(q)
                    continue
                to_fix.append(q)
                self.stdout.write(
                    f"  #{q.id} year={q.year} source={q.exam_source!r} active={q.is_active}: "
                    f"{sample['question_text'][:70]}"
                )

        for q in protected:
            self.stdout.write(self.style.WARNING(
                f"  skipped #{q.id} year={q.year} (admin-edited/verified/locked; "
                "use --include-admin-edited to change it)"
            ))

        if not to_fix:
            self.stdout.write(self.style.SUCCESS("No seed demo questions are labelled with a PYQ year."))
            return
        action = "year=0" + (" + is_active=False" if opts["deactivate"] else "")
        if not apply:
            self.stdout.write(self.style.NOTICE(
                f"Dry run: {len(to_fix)} row(s) would get {action}. Re-run with --apply to write."
            ))
            return

        with transaction.atomic():
            for q in to_fix:
                q.year = 0
                fields = ["year"]
                if opts["deactivate"]:
                    q.is_active = False
                    fields.append("is_active")
                # save() (not a queryset update) so post_save cache/search
                # invalidation runs for each row.
                q.save(update_fields=fields)
        self.stdout.write(self.style.SUCCESS(f"Updated {len(to_fix)} row(s): {action}."))
