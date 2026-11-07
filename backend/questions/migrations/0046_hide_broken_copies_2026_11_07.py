"""One-time data step (2026-11-07): hide seven questions the owner approved (questions.content_repairs.HIDES_2026_11_07).

The owner's rule: a question is hidden only when it is a duplicate or wrong. These are:
- three duplicates: #12605 (of #12321), #22456 (of #6477, without its data table) and #22631 (of #2210,
  without its ECG table);
- two seed demo questions whose image never existed ("[image unavailable: ...]");
- two NEET PG questions whose source book omits the data they ask about (#15370 lab values, #15618 list).

Each is hidden only while it is active and still holds the stem and options it was judged on; a duplicate only
while its kept copy is active with the same key. A QuestionRevisionSnapshot is stored first and nothing is
deleted. Uses the historical models. A database without these questions is left as it is. Never fails the deploy.
"""
from django.db import migrations, transaction


def forward(apps, schema_editor):
    from questions import content_repairs as repairs

    Question = apps.get_model('questions', 'Question')
    Snapshot = apps.get_model('questions', 'QuestionRevisionSnapshot')
    try:
        with transaction.atomic():
            results = repairs.apply_hides(repairs.HIDES_2026_11_07, question_model=Question, snapshot_model=Snapshot)
    except Exception as exc:  # noqa: BLE001 - the deploy goes on; nothing was written
        print(f'\n  question hides NOT applied ({type(exc).__name__}: {exc})')
        return
    if all(status == 'missing' for _, status in results):
        return  # none of these questions exist here
    print('\n  question hides: ' + ', '.join(f'#{pk} {status}' for pk, status in results))


class Migration(migrations.Migration):

    dependencies = [
        ('questions', '0045_content_repairs_2026_11_07'),
    ]

    operations = [
        migrations.RunPython(forward, migrations.RunPython.noop),
    ]
