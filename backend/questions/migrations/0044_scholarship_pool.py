"""One-time data step: open the scholarship challenge with the reviewed pool (fixtures/scholarship_pool.json).

Flags the file's questions ``is_scholarship_eligible`` when they still hold the key and the stem/options
the file was reviewed for and pass ``questions.scholarship_pool.pool_refusal`` (text only, four options,
not free showcase ...); the others are skipped. As a migration it runs once per database, so an admin's
later changes in the questions editor (toggle, "Scholarship pool" filter) stay. Only that flag is written:
no key, no explanation. Uses the historical models. A database without these questions (tests, a fresh
install) is left as it is. Never fails the deploy.
"""
from pathlib import Path

from django.conf import settings
from django.db import migrations, transaction

POOL = Path(settings.BASE_DIR) / 'fixtures' / 'scholarship_pool.json'


def forward(apps, schema_editor):
    if not POOL.is_file():
        return
    from questions import scholarship_pool as pool

    Question = apps.get_model('questions', 'Question')
    Showcase = apps.get_model('accounts', 'FreeShowcaseQuestion')
    try:
        with transaction.atomic():
            entries = pool.load_pool(POOL)['questions']
            plan = pool.plan_pool(entries, question_model=Question, showcase_model=Showcase)
            if not any(row['reason'] != 'missing' for row in plan):
                return  # none of these questions exist here
            added = pool.set_eligible([row['id'] for row in plan if row['action'] == 'add'], True,
                                      question_model=Question)
    except Exception as exc:  # noqa: BLE001 - the deploy goes on; the command can be run by hand
        print(f'\n  scholarship pool NOT applied ({type(exc).__name__}: {exc}); '
              'run: python manage.py apply_scholarship_pool --apply')
        return
    skipped = [f"{row['id']} ({row['reason']})" for row in plan if row['action'] == 'skip']
    print(f'\n  scholarship pool: {added} questions added, '
          f'{pool.eligible_count(question_model=Question)} in the challenge'
          + (f"; skipped: {', '.join(skipped)}" if skipped else ''))


class Migration(migrations.Migration):

    dependencies = [
        ('questions', '0043_import_cms_2026_papers'),
        ('accounts', '0030_customuser_ui_preferences'),
    ]

    operations = [
        migrations.RunPython(forward, migrations.RunPython.noop),
    ]
