from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tests_engine', '0004_test_exam_type'),
        ('accounts', '__latest__'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='testattempt',
            constraint=models.UniqueConstraint(
                fields=('user', 'test'),
                condition=models.Q(is_completed=False),
                name='one_active_test_attempt_per_user',
            ),
        ),
    ]
