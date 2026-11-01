"""ingestion_rollback — soft-delete every ``Question`` produced by one ``ImportJob``.

Phase-1 safe: only soft-deletes (``is_active=False``). UPSC's
``Question`` table is never hard-deleted by the ingestion app.

Matching is exact: the conservative gate stamps
``QuestionSource.import_job_id = "ingestion:<job id>"`` on every question
it writes, and only those questions are touched. (The command used to
match the bare id, i.e. the provenance of the legacy recall importer's
``QuestionImportJob`` with the same number — an unrelated import — while
the ingestion job's own questions, written with an empty id, stayed live.)
Questions that also came from another import, and admin-protected rows,
are left active. Nothing matched → the command stops with an error.
"""
from django.core.management.base import BaseCommand, CommandError

from ingestion.models import ImportJob


class Command(BaseCommand):
    help = "Soft-delete every Question tied to an ImportJob."

    def add_arguments(self, parser):
        parser.add_argument("job_id", type=int)
        parser.add_argument("--dry-run", action="store_true",
                            help="Only report how many questions would be soft-deleted.")

    def handle(self, *args, **opts):
        job_id = opts["job_id"]
        job = ImportJob.objects.filter(id=job_id).first()
        if not job:
            raise CommandError(f"job {job_id} not found")

        from importers.neetpg.db_writer import DjangoWriter
        from ingestion.conservative_gate import source_job_ref
        from questions.models import QuestionSource

        ref = source_job_ref(job)
        linked = QuestionSource.objects.filter(import_job_id=ref).values("question_id").distinct().count()
        if linked == 0:
            hint = ""
            if job.retry_of_id:
                hint = f" (it is a retry of job {job.retry_of_id}; that job may own the questions)"
            raise CommandError(
                f"No questions carry provenance '{ref}' — nothing to roll back{hint}."
            )
        if opts["dry_run"]:
            self.stdout.write(f"job {job_id}: {linked} question(s) linked to '{ref}' (dry run).")
            return

        writer = DjangoWriter(import_job=None, exam_type=job.parent_exam, source_job_ref=ref)
        n = writer.rollback_for_job()
        self.stdout.write(self.style.SUCCESS(
            f"Soft-deleted {n} of {linked} Question rows linked to job {job_id} "
            f"(the rest also belong to another import or were edited by an admin)."
        ))
