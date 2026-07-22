"""`python manage.py neetpg_rollback --job-id <id> [--hard-revert False]`

Soft-delete every Question whose QuestionSource bridge points at a
QuestionImportJob row. Refuses to run unless the operator passes
`--confirm` so accidental invocations are no-ops.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from questions.models import Question, QuestionImportJob


class Command(BaseCommand):
    help = "Soft-delete Questions written by a NEET PG recall import job."

    def add_arguments(self, parser):
        parser.add_argument("--job-id", type=int, required=True)
        parser.add_argument("--confirm", action="store_true",
                            help="Required to actually mutate rows.")
        parser.add_argument("--re-activate", action="store_true",
                            help="Reverse soft-delete (set is_active=True).")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        job_id = opts["job_id"]
        confirm = bool(opts.get("confirm"))
        dry_run = bool(opts.get("dry_run"))
        reactivate = bool(opts.get("re_activate"))

        job = QuestionImportJob.objects.filter(id=job_id, job_type="pdf").first()
        if not job:
            raise CommandError(f"no QuestionImportJob id={job_id} (job_type='pdf')")
        if not confirm and not dry_run:
            raise CommandError(
                "refusing to mutate rows without --confirm (use --dry-run to preview)"
            )

        qs = Question.objects.filter(
            recall_sources__import_job_id=str(job.id),
        ).distinct()
        candidates = qs.count()
        self.stdout.write(f"job_id={job.id} source={job.source_filename} "
                          f"candidates={candidates} action={'re-activate' if reactivate else 'soft-delete'}")

        if dry_run or candidates == 0:
            self.stdout.write(self.style.WARNING("(dry-run; no rows modified)"))
            return

        if reactivate:
            n = qs.filter(is_active=False).update(is_active=True)
            self.stdout.write(self.style.SUCCESS(f"re-activated {n} question(s)"))
        else:
            n = qs.filter(is_active=True).update(is_active=False)
            self.stdout.write(self.style.SUCCESS(f"soft-deleted {n} question(s)"))
