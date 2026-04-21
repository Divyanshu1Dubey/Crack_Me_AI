from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('questions', '0011_adminaipromptversion_questionaioperationlog'),
        ('textbooks', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TextbookChunk',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('book_name', models.CharField(blank=True, max_length=255)),
                ('page_number', models.IntegerField(default=0)),
                ('chunk_text', models.TextField()),
                ('quality_score', models.FloatField(default=0.0)),
                ('is_approved', models.BooleanField(default=False)),
                ('is_rejected', models.BooleanField(default=False)),
                ('merged_from_ids', models.JSONField(blank=True, default=list)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('textbook', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='chunks', to='textbooks.textbook')),
                ('upload', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='chunks', to='textbooks.pdfupload')),
            ],
            options={
                'ordering': ['book_name', 'page_number', 'id'],
            },
        ),
        migrations.CreateModel(
            name='QuestionReferenceOverride',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('chapter', models.CharField(blank=True, max_length=200)),
                ('page_number', models.CharField(blank=True, max_length=50)),
                ('excerpt', models.TextField(blank=True)),
                ('screenshot', models.ImageField(blank=True, null=True, upload_to='question_reference_overrides/')),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='question_reference_overrides', to=settings.AUTH_USER_MODEL)),
                ('question', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reference_overrides', to='questions.question')),
                ('textbook', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='question_overrides', to='textbooks.textbook')),
            ],
            options={
                'ordering': ['-updated_at'],
            },
        ),
        migrations.AddIndex(
            model_name='textbookchunk',
            index=models.Index(fields=['book_name', 'page_number'], name='textbooks_t_book_na_95d5a9_idx'),
        ),
        migrations.AddIndex(
            model_name='textbookchunk',
            index=models.Index(fields=['is_approved', 'is_rejected'], name='textbooks_t_is_appr_297f49_idx'),
        ),
        migrations.AddIndex(
            model_name='questionreferenceoverride',
            index=models.Index(fields=['question', 'is_active'], name='textbooks_q_question_bfa14e_idx'),
        ),
    ]
