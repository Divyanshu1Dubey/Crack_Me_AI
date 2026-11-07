"""One-time data step (2026-11-07): UPSC CMS 2018-2025 made to match the official papers and keys.

questions.cms_official applies questions/data/cms_official_2018_2025.json, prepared from the owner's copy of the
official question papers and UPSC answer keys ("UPSC CMS 2009-2025 with Answer Key.pdf", Series A): every paper
gets its 120 questions numbered as in the official paper, every key the official one (AnswerKeyChange with the
official key as evidence; the old key is kept there), questions UPSC dropped are marked dropped, second copies and
questions that are not in the official paper are hidden (snapshot first, nothing deleted), questions the bank
lacked are added with the text typed from the scans, text damaged on import is repaired, and mojibake is decoded.

Every row is changed only while it still holds the content, key, paper and active flag it was planned for, so an
admin's later edit wins and a second run changes nothing. Uses the historical models. Never fails the deploy.
"""
from django.db import migrations, models, transaction


def forward(apps, schema_editor):
    from questions import cms_official

    def model(app, name):
        try:
            return apps.get_model(app, name)
        except LookupError:
            return None

    extra = [(model(app, name), field) for app, name, field in (
        ('key_audit', 'AuditResolution', 'stem_hash'), ('key_audit', 'SourceKey', 'stem_hash'),
        ('evidence', 'QuestionEvidence', 'content_sha256'), ('questions', 'ExplanationSuggestion', 'draft_stem_hash'),
    )]
    try:
        with transaction.atomic():
            results = cms_official.apply_plan(
                question_model=apps.get_model('questions', 'Question'),
                snapshot_model=apps.get_model('questions', 'QuestionRevisionSnapshot'),
                key_change_model=apps.get_model('questions', 'AnswerKeyChange'),
                subject_model=apps.get_model('questions', 'Subject'),
                audit_model=model('key_audit', 'QuestionAudit'),
                extra_hash_models=[(m, f) for m, f in extra if m is not None])
    except Exception as exc:  # noqa: BLE001 - the deploy goes on; nothing was written
        print(f'\n  CMS official reconciliation NOT applied ({type(exc).__name__}: {exc})')
        return
    if not any(name.endswith(' applied') for name in results):
        return  # a database without these questions (tests, a fresh bank)
    print('\n  CMS official reconciliation: ' + ', '.join(f'{k} {v}' for k, v in sorted(results.items())))


class Migration(migrations.Migration):

    dependencies = [
        ('questions', '0046_hide_broken_copies_2026_11_07'),
        ('key_audit', '0002_source_keys_and_decision_context'),
        ('evidence', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='answerkeychange',
            name='source',
            field=models.CharField(choices=[
                ('editor', 'Question editor'), ('generate_explanation', 'Generate explanation'),
                ('resolve_dispute', 'Resolve dispute'), ('review_queue', 'Answer-key review queue'),
                ('undo_revision', 'Undo to revision'), ('management_command', 'Management command'),
                ('legacy_snapshot', 'Recovered from revision history'), ('official_key', 'Official answer key (UPSC)'),
            ], max_length=24),
        ),
        migrations.RunPython(forward, migrations.RunPython.noop),
    ]
