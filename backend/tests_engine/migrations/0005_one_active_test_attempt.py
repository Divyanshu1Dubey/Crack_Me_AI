from django.db import migrations, models
from django.db.models import Count, Max


def dedupe_active_attempts(apps, schema_editor):
    """Self-heal before the unique constraint lands.

    Some production DBs already have multiple active TestAttempt rows for
    the same (user, test) — the previous migration crashed when Postgres
    refused to build the unique index with `DETAIL: Key (user_id, test_id)
    duplicated`. We keep the most recent active attempt per (user, test)
    and mark older duplicates as completed (with `completed_at=now`) so
    the partial unique constraint can apply without losing history.
    """
    TestAttempt = apps.get_model("tests_engine", "TestAttempt")
    from django.utils import timezone

    dups = (
        TestAttempt.objects
        .filter(is_completed=False)
        .values("user_id", "test_id")
        .annotate(n=Count("id"), latest_id=Max("id"))
        .filter(n__gt=1)
    )
    fixed = 0
    for d in dups:
        keep_id = d["latest_id"]
        n = TestAttempt.objects.filter(
            user_id=d["user_id"],
            test_id=d["test_id"],
            is_completed=False,
        ).exclude(id=keep_id).update(
            is_completed=True,
            completed_at=timezone.now(),
        )
        fixed += n
    if fixed:
        print(f"[dedupe_active_attempts] marked {fixed} older active rows as completed")


def reverse_noop(apps, schema_editor):
    # Nothing to undo: we just flipped a boolean so the unique index can
    # build. The "completed" rows remain in the analytics trail.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('tests_engine', '0004_test_exam_type'),
        ('accounts', '0017_alter_tokentransaction_transaction_type'),
    ]

    operations = [
        migrations.RunPython(dedupe_active_attempts, reverse_noop),
        migrations.AddConstraint(
            model_name='testattempt',
            constraint=models.UniqueConstraint(
                fields=('user', 'test'),
                condition=models.Q(is_completed=False),
                name='one_active_test_attempt_per_user',
            ),
        ),
    ]