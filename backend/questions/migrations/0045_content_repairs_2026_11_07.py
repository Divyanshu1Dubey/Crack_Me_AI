"""One-time data step (2026-11-07): five reviewed content repairs (questions.content_repairs.REPAIRS_2026_11_07).

#2058, #2065, #2103, #2113 (CMS 2025 Paper I): the locked explanation still argued for the key these
questions had before an earlier correction, so students read an explanation that contradicts the
answer. It is rewritten for the current key, which is not changed; the new text is AI-written
(explanation_origin 'ai', explanation_status 'ai_generated' until an admin reviews it).
#22462 (CMS 2022 Paper II): the five Apgar observations missing from the stem are restored from
Medura_Train/PYQ/2022paper2.txt, and the explanation gains the worked score.

A repair applies only while the question still holds the key and the text it was written for (an admin's
later edit wins), after a QuestionRevisionSnapshot of the previous state. Uses the historical models. A
database without these questions (tests, a fresh install) is left as it is. Never fails the deploy.
"""
from django.db import migrations, transaction


def forward(apps, schema_editor):
    from questions import content_repairs as repairs

    Question = apps.get_model('questions', 'Question')
    Snapshot = apps.get_model('questions', 'QuestionRevisionSnapshot')
    try:
        with transaction.atomic():
            results = repairs.apply_repairs(repairs.REPAIRS_2026_11_07, question_model=Question,
                                            snapshot_model=Snapshot)
    except Exception as exc:  # noqa: BLE001 - the deploy goes on; nothing was written
        print(f'\n  content repairs NOT applied ({type(exc).__name__}: {exc})')
        return
    if all(status == 'missing' for _, status in results):
        return  # none of these questions exist here
    print('\n  content repairs: ' + ', '.join(f'#{pk} {status}' for pk, status in results))


class Migration(migrations.Migration):

    dependencies = [
        ('questions', '0044_scholarship_pool'),
    ]

    operations = [
        migrations.RunPython(forward, migrations.RunPython.noop),
    ]
