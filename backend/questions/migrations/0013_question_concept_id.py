from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('questions', '0012_questionrevisionsnapshot_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='question',
            name='concept_id',
            field=models.CharField(blank=True, db_index=True, help_text='Stable concept identifier for linking related PYQs', max_length=120),
        ),
    ]
