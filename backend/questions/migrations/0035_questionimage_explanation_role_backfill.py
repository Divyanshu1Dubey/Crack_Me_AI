# Hand-written migration: reclassify legacy admin-uploaded QuestionImage
# rows that should have been `role='explanation'` but were stored as
# `role='illustration'` by the pre-fix upload path.
#
# Bug context (2026-08-01): the admin editor's "Insert image" button in
# the explanation / concept_explanation / mnemonic field used to upload
# the file via POST /api/questions/images/ without sending `role`, so
# the backend persisted `role='illustration'` (the model default).
# The public serializer then returned every row under `images`, and the
# bank stem pane rendered the explanation figure next to the question
# before the student attempted it.
#
# Heuristic for the backfill (deliberately conservative — only rows
# uploaded by an admin are eligible, never recall-imported ones):
#   1. The row is `uploaded_by_admin=True`.
#   2. The row's `role` is still the default ('illustration').
#   3. The row's `id` does NOT appear as a `[[img:N]]` token in the
#      question's stem (`question_text`). If it IS referenced from
#      the stem, the image legitimately belongs in the stem pane.
#   4. The row's `id` DOES appear as a `[[img:N]]` token in any of
#      `explanation`, `concept_explanation`, or `mnemonic`. If none
#      of these reference the image, we leave it alone — the admin
#      might have deleted the inline reference but still want the
#      image attached.
#
# This is idempotent: the same row will not be re-promoted because we
# only touch rows where `role='illustration'`. Re-running is safe.
#
# Performance: a single UPDATE via the Django ORM, scoped to the small
# set of `uploaded_by_admin=True` rows, is fast enough on a 5k-row
# QuestionImage table (~1k admin uploads). For larger datasets the
#   .filter(id__in=[...]).update(role='explanation')   pattern below
# is still O(N) on the candidate set.

from django.db import migrations


def _backfill_explanation_role(apps, schema_editor):
    Question = apps.get_model("questions", "Question")
    QuestionImage = apps.get_model("questions", "QuestionImage")

    updated = 0
    # Process question-by-question so the per-row Python check stays
    # cheap. `uploaded_by_admin=True` is a db_index, so the candidate
    # scan is index-only.
    admin_imgs = QuestionImage.objects.filter(
        uploaded_by_admin=True,
        role="illustration",
    ).only("id", "question_id", "role")

    # Group by question so we only pull question_text / explanation /
    # concept_explanation / mnemonic once per question.
    by_question: dict[int, list[int]] = {}
    for img in admin_imgs.iterator(chunk_size=500):
        by_question.setdefault(img.question_id, []).append(img.id)

    for question_id, image_ids in by_question.items():
        try:
            q = Question.objects.only(
                "question_text", "explanation",
                "concept_explanation", "mnemonic",
            ).get(pk=question_id)
        except Question.DoesNotExist:
            continue

        stem = (q.question_text or "")
        expl = (q.explanation or "") + (q.concept_explanation or "") + (q.mnemonic or "")

        eligible: list[int] = []
        for img_id in image_ids:
            token = f"[[img:{img_id}]]"
            # Skip if the image is referenced from the stem — it's a
            # legitimate stem image.
            if token in stem:
                continue
            # Promote only if the image is referenced from an
            # explanation-class field. Otherwise the admin may have
            # orphaned the image (deleted the inline reference) and we
            # don't want to silently reclassify it.
            if token in expl:
                eligible.append(img_id)

        if eligible:
            updated += QuestionImage.objects.filter(id__in=eligible).update(role="explanation")

    # `updated` is local so a global counter isn't useful here. Logging
    # happens via the migration framework's stdout.
    print(f"[0035] Promoted {updated} QuestionImage row(s) to role='explanation'")


def _noop_reverse(apps, schema_editor):
    # Irreversible: we don't know which rows were originally 'illustration'
    # vs truly meant to be 'illustration'. Leaving them on
    # 'explanation' is the safer permanent state.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("questions", "0034_questionimage_updated_at_state"),
    ]

    operations = [
        migrations.RunPython(_backfill_explanation_role, _noop_reverse),
    ]