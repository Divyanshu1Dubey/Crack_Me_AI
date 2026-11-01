"""Cap the stored time limit of Paper 1 / Paper 2 mocks at 120 minutes.

Paper mocks generated before the 120-minutes-per-paper rule (1.5 minutes per
question) were stored with 180 minutes for 120 questions. /simulator and the
real UPSC CMS paper are 2 hours, and the player's clock reads the stored
``time_limit_minutes``. New paper mocks already get 120 minutes
(``tests_engine.views._cms_paper_minutes``); this fixes the existing rows.

Only limits above 120 are lowered, so the migration is idempotent and leaves
shorter (partial) paper tests alone. The reverse is a no-op: the old values
were wrong.

A test with an attempt still in progress inside its old limit (started less
than the old limit + the submit grace ago) keeps that limit: /submit/ judges
lateness and caps the duration with the test's current limit, so lowering it
under a student who is, say, 150 minutes into a 180-minute mock would flag
them late (no XP) and cut their recorded time, and their reloaded clock would
jump to zero. Those few generated tests keep their old limit. To cap them
once their attempts are over, run in ``manage.py shell``::

    from django.apps import apps
    import importlib
    importlib.import_module(
        'tests_engine.migrations.0009_cap_paper_mock_time_limits'
    ).cap_paper_mock_time_limits(apps, None)
"""
from datetime import timedelta

from django.db import migrations
from django.db.models import Exists, Max, OuterRef
from django.utils import timezone

CMS_PAPER_MINUTES = 120
# tests_engine.views.LATE_SUBMIT_GRACE_SECONDS
LATE_SUBMIT_GRACE_SECONDS = 120


def cap_paper_mock_time_limits(apps, schema_editor):
    Test = apps.get_model('tests_engine', 'Test')
    TestAttempt = apps.get_model('tests_engine', 'TestAttempt')
    over = Test.objects.filter(
        test_type__in=('paper1', 'paper2'),
        time_limit_minutes__gt=CMS_PAPER_MINUTES,
    )
    longest = over.aggregate(longest=Max('time_limit_minutes'))['longest']
    if not longest:
        return
    # Conservative: the longest old limit bounds every test's window.
    may_be_on_time = TestAttempt.objects.filter(
        test=OuterRef('pk'),
        is_completed=False,
        started_at__gte=timezone.now() - timedelta(minutes=longest, seconds=LATE_SUBMIT_GRACE_SECONDS),
    )
    over.exclude(Exists(may_be_on_time)).update(time_limit_minutes=CMS_PAPER_MINUTES)


class Migration(migrations.Migration):

    dependencies = [
        ('tests_engine', '0008_testattempt_is_late_retire_free_preview'),
    ]

    operations = [
        migrations.RunPython(cap_paper_mock_time_limits, migrations.RunPython.noop),
    ]
