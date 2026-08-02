"""One-shot fix for orphan admin-uploaded QuestionImage rows.

Background
----------
Bug 2026-08-01: the admin editor's "Insert image" button in the
explanation / concept_explanation / mnemonic editor used to upload
the file via POST /api/questions/images/ without sending `role`,
so the backend persisted `role='illustration'` (the model default).
The public serializer then returned every row under `images`, and
the bank stem pane rendered the explanation figure next to the
question before the student attempted it.

The earlier commit (9cdc769) added a backfill migration that
reclassifies rows whose `[[img:N]]` token appears in `explanation` /
`concept_explanation` / `mnemonic`. That handles every row where
the admin's modal save also persisted the token in the explanation
text — but **NOT** the orphan rows where the modal save crashed
(network error, etc.) before the token landed in the database.

This command handles the orphan case: any row whose
`uploaded_by_admin=True`, `role='illustration'`, AND which has
NO `[[img:N]]` token anywhere in the parent question's text fields
is treated as an orphan and reclassified to `role='explanation'`,
with the `[[img:N]]` token auto-appended to `explanation`. This
makes the row discoverable by both the runtime heuristic and the
read-end `stem_images` filter.

Idempotent: re-running this command is safe because the WHERE
clause only matches rows still on the legacy `role='illustration'`
default.

Usage::

    python manage.py fix_explanation_orphans            # dry run
    python manage.py fix_explanation_orphans --apply    # apply changes
    python manage.py fix_explanation_orphans --question-id 2005  # limit scope
"""
from django.core.management.base import BaseCommand

from questions.models import Question, QuestionImage


class Command(BaseCommand):
    help = (
        "Reclassify orphan admin-uploaded QuestionImage rows that should "
        "have been 'explanation' but were stored as 'illustration' by "
        "the pre-fix upload path. See module docstring for context."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually persist the reclassification. Default is dry-run.",
        )
        parser.add_argument(
            "--question-id",
            type=int,
            default=None,
            help="Limit scope to a single question id (useful for spot-fixing).",
        )

    def handle(self, *args, **options):
        apply = options["apply"]
        question_id = options.get("question_id")

        qs = QuestionImage.objects.filter(
            uploaded_by_admin=True,
            role="illustration",
        )
        if question_id is not None:
            qs = qs.filter(question_id=question_id)

        orphans = []
        for img in qs.iterator(chunk_size=500):
            q = Question.objects.only(
                "id", "question_text", "explanation",
                "concept_explanation", "mnemonic",
            ).filter(pk=img.question_id).first()
            if q is None:
                continue
            stem = q.question_text or ""
            expl = (
                (q.explanation or "")
                + (q.concept_explanation or "")
                + (q.mnemonic or "")
            )
            token = f"[[img:{img.id}]]"
            # Skip rows that ARE referenced from the stem — they're
            # legitimate stem images, not orphans.
            if token in stem:
                continue
            # If the token already lives somewhere in the explanation
            # cluster, the backfill migration (0035) will already have
            # reclassified it. We only handle the truly-orphan case.
            if token in expl:
                continue
            orphans.append((img, q))

        if not orphans:
            self.stdout.write(self.style.SUCCESS(
                "No orphan rows found. Nothing to do."
            ))
            return

        self.stdout.write(f"{'Would reclassify' if not apply else 'Reclassifying'} "
                          f"{len(orphans)} orphan row(s):")
        for img, q in orphans:
            self.stdout.write(
                f"  QuestionImage #{img.id} (question #{q.id}, "
                f"sha256_short={img.sha256_short})"
            )
            if apply:
                img.role = "explanation"
                img.save(update_fields=["role", "updated_at"])
                # Also append the token to explanation so future
                # migrations / runtime heuristic can find it.
                token = f"[[img:{img.id}]]"
                if token not in (q.explanation or ""):
                    q.explanation = ((q.explanation or "") + "\n\n" + token).strip()
                    q.save(update_fields=["explanation", "updated_at"])

        if apply:
            self.stdout.write(self.style.SUCCESS(
                f"\nReclassified {len(orphans)} orphan row(s) to 'explanation'."
            ))
        else:
            self.stdout.write(self.style.WARNING(
                "\nDry run — pass --apply to persist."
            ))