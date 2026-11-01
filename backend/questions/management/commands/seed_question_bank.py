"""seed_question_bank -- give a fresh database its question bank (deploy step).

Request-time bootstrapping (public GETs running loaddata on an empty table)
was removed (QB-15), so a new environment -- a fresh deploy database,
staging, a fresh local database -- started with no subjects and no CMS
questions. build.sh runs this after ``migrate`` on every deploy:

* for each exam (default ``cms``) whose bank is empty -- no question with the
  fixture's exam_type and exam_source -- it runs ``load_exam_fixture <exam>``
  (fixtures/<exam>_fixture.json: subjects, topics and questions; admin
  removals recorded as ``RemovedQuestion`` tombstones are honoured);
* a bank that already has questions is left alone. Loading the fixture over
  a live bank would overwrite whatever changed there since the export (AI
  explanations, answer fixes, deactivations): re-sync on purpose with
  ``python manage.py load_exam_fixture <exam>``.

Idempotent: once a bank exists, every later run is a no-op. ``--dry-run``
only reports.
"""
from __future__ import annotations

import json

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from questions.management.commands.load_exam_fixture import EXAM_MAP, FIXTURES_DIR
from questions.models import Question

SEEDABLE_EXAMS = sorted(alias for alias in EXAM_MAP if not alias.startswith("__"))


def fixture_exam_sources(exam: str) -> set[str]:
    """``exam_source`` values of the question rows in the exam's fixture."""
    fixture_name = EXAM_MAP[exam][0]
    path = FIXTURES_DIR / fixture_name
    if not path.exists():
        raise CommandError(f"Fixture not found: {path}")
    rows = json.loads(path.read_text(encoding="utf-8"))
    return {
        row["fields"]["exam_source"]
        for row in rows
        if isinstance(row, dict) and row.get("model") == "questions.question"
        and isinstance(row.get("fields"), dict) and row["fields"].get("exam_source")
    }


def bank_is_empty(exam: str) -> bool:
    """No question of this exam yet. Matching on exam_source as well keeps
    rows of another exam stored under the same exam_type (the old NEET PG
    import wrote exam_type='cms') from hiding an empty CMS bank. A live bank
    is recognised without reading the fixture, so a deploy of an existing
    database never depends on it."""
    rows = Question.objects.filter(exam_type=EXAM_MAP[exam][1])
    if not rows.exists():
        return True
    try:
        sources = fixture_exam_sources(exam)
    except CommandError:
        return False   # nothing to compare with (and nothing to seed from)
    return bool(sources) and not rows.filter(exam_source__in=sources).exists()


class Command(BaseCommand):
    help = (
        "Load fixtures/<exam>_fixture.json into an empty question bank (default: cms). "
        "Banks that already have questions are left untouched."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "exams", nargs="*",
            help=f"Exam fixtures to seed when their bank is empty: {', '.join(SEEDABLE_EXAMS)} (default: cms).",
        )
        parser.add_argument("--dry-run", action="store_true", help="Report only; write nothing.")

    def handle(self, *args, **options):
        exams = options["exams"] or ["cms"]
        unknown = [exam for exam in exams if exam not in SEEDABLE_EXAMS]
        if unknown:
            raise CommandError(f"Unknown exam(s) {unknown}; choose from {SEEDABLE_EXAMS}.")
        for exam in dict.fromkeys(exams):
            if not bank_is_empty(exam):
                self.stdout.write(
                    f"{exam}: question bank present; not seeded "
                    f"(re-sync deliberately with `load_exam_fixture {exam}`)."
                )
                continue
            if options["dry_run"]:
                self.stdout.write(self.style.WARNING(f"{exam}: question bank empty; would load {EXAM_MAP[exam][0]}."))
                continue
            self.stdout.write(f"{exam}: question bank empty; loading {EXAM_MAP[exam][0]} ...")
            call_command("load_exam_fixture", exam, stdout=self.stdout, stderr=self.stderr)
