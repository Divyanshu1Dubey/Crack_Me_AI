# Hand-written migration (0037): rigorous cleanup of admin-uploaded
# QuestionImage rows that should have been role='explanation'.
#
# Bug context (2026-08-01, escalation after 0036): migrations 0035 and
# 0036 both have heuristics that skip rows when the [[img:N]] token is
# already present in the explanation text. On the live production data
# for question #2005, the admin manually added the [[img:7456]] token
# to the explanation AFTER the original upload + initial 0035 deploy,
# so neither migration's "promote" branch fired — but the row's
# stored role was never updated. The result: image 7456 stays on
# role='illustration' and renders in the stem pane.
#
# This migration is the rigorous cleanup: any admin-uploaded row
# (uploaded_by_admin=True) whose id IS referenced from the explanation
# text via [[img:N]] is unconditionally promoted to role='explanation',
# regardless of the stored role. The previous migrations had
# precondition gates that this one drops — we know the admin intended
# an explanation-class field when they put a token there.
#
# Idempotent: safe to re-run on every deploy. Only matches rows still
# on a non-explanation role. (Rows already on 'explanation' aren't
# touched and return 0 affected.)

from django.db import migrations


def _strict_explanation_promotion(apps, schema_editor):
    Question = apps.get_model("questions", "Question")
    QuestionImage = apps.get_model("questions", "QuestionImage")

    # Find every question that has at least one explanation-class
    # field containing a [[img:N]] token whose matching QuestionImage
    # row is admin-uploaded but NOT already on role='explanation'.
    candidates = []
    for q in Question.objects.exclude(
        explanation="", concept_explanation="", mnemonic=""
    ).only("id", "explanation", "concept_explanation", "mnemonic").iterator(chunk_size=200):
        expl = (q.explanation or "") + (q.concept_explanation or "") + (q.mnemonic or "")
        # Extract every [[img:N]] token referenced from explanation text.
        import re
        for match in re.finditer(r"\[\[img:(\d+)\]\]", expl):
            try:
                img_id = int(match.group(1))
            except ValueError:
                continue
            candidates.append(img_id)

    if not candidates:
        print("[0037] No [[img:N]] references found in any question explanation.")
        return

    # Now query QuestionImage rows by id — only those that are
    # admin-uploaded and on a non-explanation role get promoted.
    rows = QuestionImage.objects.filter(
        id__in=set(candidates),
        uploaded_by_admin=True,
    ).exclude(role="explanation").only("id", "role", "uploaded_by_admin")

    ids_to_promote = [r.id for r in rows]
    if not ids_to_promote:
        print(
            f"[0037] {len(candidates)} [[img:N]] reference(s) found but "
            f"all underlying rows are already on role='explanation' (or not admin-uploaded). "
            f"Nothing to do."
        )
        return

    promoted = QuestionImage.objects.filter(id__in=ids_to_promote).update(role="explanation")
    print(
        f"[0037] Strict cleanup: promoted {promoted} admin-uploaded "
        f"QuestionImage row(s) to role='explanation' because their id "
        f"was referenced from at least one explanation-class text field."
    )


def _noop_reverse(apps, schema_editor):
    # No-op: we don't track which rows this touched, and the role
    # promotion is correct even if the migration is reversed.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("questions", "0036_questionimage_orphan_handler"),
    ]

    operations = [
        migrations.RunPython(_strict_explanation_promotion, _noop_reverse),
    ]