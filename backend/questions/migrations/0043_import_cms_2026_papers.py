"""One-time data step: import the UPSC CMS 2026 papers (fixtures/pyq/cms_2026.json) into a live bank.

The paper file and ``manage.py import_pyq_paper`` ship in the same release as the site's bank figures
(frontend/src/lib/bankStats.ts: 2,100+ PYQs, 2018-2026). As a migration, the deploy that ships the
figures also ships the questions, on either Railway start path (both run ``migrate``), without a manual
step. Skipped on a database without a live CMS bank (tests, a fresh install: ``seed_question_bank``
fills those later). The importer is idempotent: a paper number already in the bank is skipped.

It never fails the deploy: an error is printed and the import can be run by hand
(``python manage.py import_pyq_paper fixtures/pyq/cms_2026.json --apply``). It runs the importer with the
live models, which match the schema of this release; on a database migrated from an older state the
savepoint keeps a failure from breaking the migration. No key is verified by this: each question gets its
source's printed key as a SourceKey signal and the answer-key audit runs (see import_pyq_paper).
"""
from pathlib import Path

from django.conf import settings
from django.db import migrations, transaction

PAPER = Path(settings.BASE_DIR) / 'fixtures' / 'pyq' / 'cms_2026.json'
LIVE_BANK_MIN = 1000  # active CMS questions: a production-like bank, never a test or fresh database


def forward(apps, schema_editor):
    Question = apps.get_model('questions', 'Question')
    if Question.objects.filter(exam_type='cms', is_active=True).count() < LIVE_BANK_MIN or not PAPER.is_file():
        return
    from questions.management.commands.import_pyq_paper import apply_import, load_paper, plan_import

    try:
        with transaction.atomic():
            data = load_paper(PAPER)
            created = apply_import(data, plan_import(data))
    except Exception as exc:  # noqa: BLE001 - the deploy goes on; the command can be run by hand
        print(f'\n  CMS 2026 papers NOT imported ({type(exc).__name__}: {exc}); '
              'run: python manage.py import_pyq_paper fixtures/pyq/cms_2026.json --apply')
        return
    hidden = sum(1 for q in created if not q.is_active)
    print(f'\n  CMS 2026 papers: {len(created)} questions created ({hidden} hidden until their figure is added)')
    if not created:
        return
    try:
        with transaction.atomic():
            from key_audit.services import audit_questions
            from questions.models import Question as LiveQuestion

            audit_questions(LiveQuestion.objects.filter(pk__in=[q.pk for q in created]), save=True)
    except Exception as exc:  # noqa: BLE001 - the questions stand; the audit can be rerun
        print(f'  answer-key audit not run ({type(exc).__name__}); run: python manage.py audit_answer_keys --apply')


class Migration(migrations.Migration):

    dependencies = [
        ('questions', '0042_medical_accuracy_schema'),
        ('key_audit', '0002_source_keys_and_decision_context'),
    ]

    operations = [
        migrations.RunPython(forward, migrations.RunPython.noop),
    ]
