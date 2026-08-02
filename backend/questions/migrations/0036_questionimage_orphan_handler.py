# Hand-written migration: reclassify ORPHAN admin-uploaded QuestionImage rows.
#
# Bug context (2026-08-01, escalation): migration 0035 ran on Render
# before its orphan-handling branch was added. The first deploy landed
# the "token-referenced" branch (which required [[img:N]] in the
# explanation text) but missed rows where the admin's modal save
# crashed before the token landed in the database. The result: rows
# like QuestionImage #7456 (uploaded to question #2005's explanation
# field) stayed on role='illustration' and continued to render in the
# stem pane for students.
#
# This migration runs a second pass: any admin-uploaded row whose role
# is still 'illustration', which is NOT referenced from question_text,
# AND whose parent question has a non-empty explanation-class field is
# treated as an orphan and reclassified to role='explanation' with the
# [[img:N]] token auto-appended to question.explanation.
#
# Idempotent: only matches rows still on role='illustration'. Safe to
# re-run on every deploy until the orphan pool is drained.
#
# Independent of 0035: 0035 covers the token-referenced branch, this
# migration covers the orphan branch. Together they sweep the entire
# legacy admin-upload pool.

from django.db import migrations


def _handle_orphan_explanation_images(apps, schema_editor):
    Question = apps.get_model("questions", "Question")
    QuestionImage = apps.get_model("questions", "QuestionImage")

    updated = 0
    orphaned_appended = 0
    admin_imgs = QuestionImage.objects.filter(
        uploaded_by_admin=True,
        role="illustration",
    ).only("id", "question_id", "role")

    by_question: dict = {}
    for img in admin_imgs.iterator(chunk_size=500):
        by_question.setdefault(img.question_id, []).append(img.id)

    for question_id, image_ids in by_question.items():
        try:
            q = Question.objects.only(
                "id", "question_text", "explanation",
                "concept_explanation", "mnemonic",
            ).get(pk=question_id)
        except Question.DoesNotExist:
            continue

        stem = (q.question_text or "")
        expl = (q.explanation or "") + (q.concept_explanation or "") + (q.mnemonic or "")

        orphan_ids = []
        for img_id in image_ids:
            token = f"[[img:{img_id}]]"
            # Skip stem-referenced images.
            if token in stem:
                continue
            # Skip token-referenced rows (0035 already handled those).
            if token in expl:
                continue
            # Conservative gate: parent question must have SOME
            # explanation-class text. Without that, we can't be sure
            # the admin intended this as an explanation image.
            if (q.explanation or "") or (q.concept_explanation or "") or (q.mnemonic or ""):
                orphan_ids.append(img_id)

        if orphan_ids:
            updated += QuestionImage.objects.filter(
                id__in=orphan_ids
            ).update(role="explanation")
            for img_id in orphan_ids:
                token = f"[[img:{img_id}]]"
                if token not in expl:
                    q.explanation = ((q.explanation or "") + "\n\n" + token).strip()
                    q.save(update_fields=["explanation"])
                    orphaned_appended += 1
                    expl = (q.explanation or "") + (q.concept_explanation or "") + (q.mnemonic or "")

    print(
        f"[0036] Reclassified {updated} orphan QuestionImage row(s) to role='explanation'; "
        f"auto-appended {orphaned_appended} orphan token(s) to question.explanation"
    )


def _noop_reverse(apps, schema_editor):
    # We don't track which rows were originally 'illustration' vs
    # truly meant to be 'illustration'. Leaving them on 'explanation'
    # is the safer permanent state.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("questions", "0035_questionimage_explanation_role_backfill"),
    ]

    operations = [
        migrations.RunPython(_handle_orphan_explanation_images, _noop_reverse),
    ]