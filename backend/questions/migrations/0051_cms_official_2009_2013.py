"""One-time data step (2026-11-09): UPSC CMS 2009-2013 added from the official papers with their official keys.

questions.cms_official applies questions/data/cms_official_2009_2013.json: the ten papers of "UPSC CMS 2009-2025 with
Answer Key.pdf" are scans; their text was read by OCR in four renderings, merged word by word, and every flagged word
was checked on the page image (docs/audit/CMS_OFFICIAL_2009_2013.md). The keys are the papers' answer-key pages (a
text layer). 1,200 questions are added, numbered as in the paper, with the paper's section as subject (Paper I of
2009 starts with General Ability 1-30; 2010-2013 end with it, 91-120), match-the-list questions as tables, and the
official key; the two questions UPSC dropped (2013 Paper I Q108, Paper II Q69) are added without a key and flagged
dropped (never scored). None of these questions was in the bank yet. An added question is skipped when the bank
already has it (same opening words and options). Never fails the deploy; nothing on an empty bank.
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
                data=cms_official.load_data(cms_official.DATA_2009_2013))
    except Exception as exc:  # noqa: BLE001 - the deploy goes on; nothing was written
        print(f'\n  CMS 2009-2013 import NOT applied ({type(exc).__name__}: {exc})')
        return
    if not any(' applied' in name for name in results):
        return
    print('\n  CMS 2009-2013 import: ' + ', '.join(f'{k} {v}' for k, v in sorted(results.items())))


class Migration(migrations.Migration):

    dependencies = [
        ('questions', '0050_explanation_batch'),
    ]

    operations = [
        migrations.RunPython(forward, migrations.RunPython.noop),
    ]
