from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('questions', '0009_questionextractionitem'),
    ]

    operations = [
        migrations.AddField(
            model_name='question',
            name='ai_answer',
            field=models.TextField(blank=True, default='', help_text='AI-generated answer rationale'),
        ),
        migrations.AddField(
            model_name='question',
            name='ai_mnemonic',
            field=models.TextField(blank=True, default='', help_text='AI-generated mnemonic'),
        ),
        migrations.AddField(
            model_name='question',
            name='ai_references',
            field=models.JSONField(blank=True, default=list, help_text='AI-generated references'),
        ),
        migrations.AddField(
            model_name='question',
            name='admin_answer_override',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='question',
            name='admin_explanation_override',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='question',
            name='admin_mnemonic_override',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='question',
            name='admin_references_override',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='question',
            name='lock_answer',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='question',
            name='lock_explanation',
            field=models.BooleanField(default=False),
        ),
    ]
