"""Cap the stored time limit of Paper 1 / Paper 2 mocks at 120 minutes.

Paper mocks generated before the 120-minutes-per-paper rule (1.5 minutes per
question) were stored with 180 minutes for 120 questions. /simulator and the
real UPSC CMS paper are 2 hours, and the player's clock reads the stored
``time_limit_minutes``. New paper mocks already get 120 minutes
(``tests_engine.views._cms_paper_minutes``); this fixes the existing rows.

Only limits above 120 are lowered, so the migration is idempotent and leaves
shorter (partial) paper tests alone. The reverse is a no-op: the old values
were wrong.
"""
from django.db import migrations

CMS_PAPER_MINUTES = 120


def cap_paper_mock_time_limits(apps, schema_editor):
    Test = apps.get_model('tests_engine', 'Test')
    Test.objects.filter(
        test_type__in=('paper1', 'paper2'),
        time_limit_minutes__gt=CMS_PAPER_MINUTES,
    ).update(time_limit_minutes=CMS_PAPER_MINUTES)


class Migration(migrations.Migration):

    dependencies = [
        ('tests_engine', '0008_testattempt_is_late_retire_free_preview'),
    ]

    operations = [
        migrations.RunPython(cap_paper_mock_time_limits, migrations.RunPython.noop),
    ]
