from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('questions', '0007_question_verification_fields'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='QuestionImportJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('job_type', models.CharField(choices=[('csv', 'CSV Import'), ('json', 'JSON Import'), ('word', 'Word Extraction'), ('pdf', 'PDF Extraction')], max_length=20)),
                ('status', models.CharField(choices=[('queued', 'Queued'), ('processing', 'Processing'), ('completed', 'Completed'), ('failed', 'Failed')], default='queued', max_length=20)),
                ('source_filename', models.CharField(blank=True, max_length=255)),
                ('stored_file_path', models.CharField(blank=True, max_length=500)),
                ('summary', models.JSONField(blank=True, default=dict)),
                ('error_report', models.JSONField(blank=True, default=list)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='question_import_jobs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
