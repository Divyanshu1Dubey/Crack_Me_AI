from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tests_engine', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='test',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, null=True),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='test',
            name='version',
            field=models.PositiveIntegerField(default=1),
        ),
    ]
