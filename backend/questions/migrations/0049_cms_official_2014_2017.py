"""One-time data step (2026-11-08): UPSC CMS 2014-2017 completed from the official papers with their official keys.

questions.cms_official applies questions/data/cms_official_2014_2017.json, prepared from the text layer of
"UPSC CMS 2009-2025 with Answer Key.pdf" (8 papers, 960 questions):

* 939 official questions the bank lacked are added, numbered as in the paper, with the key of the paper's key
  table; match-the-list questions as a table with their code options written out; the page numbers the text layer
  ran into 37 last options (2017) removed; the transcription's spelling slips corrected on 68 questions (each
  correction listed in the data file).
* 21 live copies already in the bank without a year are tagged with year, paper, number and the paper's section as
  subject (18 change subject); their keys already are the official ones.
* 7 rows are hidden: 5 second live copies of those 21 and 2 broken copies of 2017 Paper II Q96 (another question's
  stem over its statements); five official questions whose only live copy is in the NEET PG bank are added to the
  CMS bank and the NEET PG rows are left alone.
* Paper I of these years ends with a General Ability section (91-120): the subject "General Ability" is created if
  missing. One key the table prints unreadably (2015 Paper II Q60, "Dc") is added for review (needs_review).

Rows change only while they hold the planned content, key, paper and active flag; an added question is skipped
when the bank already has it (same opening words and options). Never fails the deploy.
"""
from django.db import migrations, transaction


def forward(apps, schema_editor):
    from questions import cms_official

    question_model = apps.get_model('questions', 'Question')
    if not question_model.objects.filter(exam_type='cms').exists():
        return  # a fresh database (or a test run): seed_question_bank loads the fixture there, not this plan
    try:
        with transaction.atomic():
            results = cms_official.apply_plan(
                question_model=question_model,
                snapshot_model=apps.get_model('questions', 'QuestionRevisionSnapshot'),
                key_change_model=apps.get_model('questions', 'AnswerKeyChange'),
                subject_model=apps.get_model('questions', 'Subject'),
                data=cms_official.load_data(cms_official.DATA_2014_2017))
    except Exception as exc:  # noqa: BLE001 - the deploy goes on; nothing was written
        print(f'\n  CMS 2014-2017 import NOT applied ({type(exc).__name__}: {exc})')
        return
    if not any(' applied' in name for name in results):
        return
    print('\n  CMS 2014-2017 import: ' + ', '.join(f'{k} {v}' for k, v in sorted(results.items())))


class Migration(migrations.Migration):

    dependencies = [
        ('questions', '0048_cms_official_2026'),
    ]

    operations = [
        migrations.RunPython(forward, migrations.RunPython.noop),
    ]
