"""One-time data step (2026-11-08): UPSC CMS 2026 matched to the official question papers (Series A).

questions.cms_official applies questions/data/cms_official_2026.json, prepared from the official 2026 papers
(QP-CMSE-26 Paper I / Paper II, Test Booklet Series A): the 240 questions (imported from a publisher's solutions,
which follow another booklet series) get the number of the official Series-A paper, text whose layout broke on
import is repaired with the same words (statements numbered, tables joined, case-scenario references renumbered, a
publisher note removed from an option), and the 16 figures cropped from the official papers are attached; the 14
questions that were hidden only because their figure was missing become live. Keys are not touched: there is no
official 2026 key yet.

Rows change only while they hold the planned content, key, paper and active flag. Never fails the deploy.
"""
from django.db import migrations, transaction


def forward(apps, schema_editor):
    from questions import cms_official

    try:
        with transaction.atomic():
            results = cms_official.apply_plan(
                question_model=apps.get_model('questions', 'Question'),
                snapshot_model=apps.get_model('questions', 'QuestionRevisionSnapshot'),
                key_change_model=apps.get_model('questions', 'AnswerKeyChange'),
                subject_model=apps.get_model('questions', 'Subject'),
                image_model=apps.get_model('questions', 'QuestionImage'),
                data=cms_official.load_data(cms_official.DATA_2026))
    except Exception as exc:  # noqa: BLE001 - the deploy goes on; nothing was written
        print(f'\n  CMS 2026 official papers NOT applied ({type(exc).__name__}: {exc})')
        return
    if not any(' applied' in name for name in results):
        return  # a database without these questions (tests, a fresh bank)
    print('\n  CMS 2026 official papers: ' + ', '.join(f'{k} {v}' for k, v in sorted(results.items())))


class Migration(migrations.Migration):

    dependencies = [
        ('questions', '0047_cms_official_2018_2025'),
    ]

    operations = [
        migrations.RunPython(forward, migrations.RunPython.noop),
    ]
