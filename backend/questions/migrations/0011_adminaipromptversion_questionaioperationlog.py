from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('questions', '0010_question_ai_override_lock_fields'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AdminAIPromptVersion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120)),
                ('prompt_text', models.TextField()),
                ('is_active', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ai_prompt_versions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='QuestionAIOperationLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('operation_type', models.CharField(choices=[('regenerate', 'Force Regenerate'), ('override', 'Admin Override')], max_length=30)),
                ('provider', models.CharField(blank=True, max_length=80)),
                ('tokens_used', models.IntegerField(default=0)),
                ('response_excerpt', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ai_operation_logs', to=settings.AUTH_USER_MODEL)),
                ('prompt_version', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='operation_logs', to='questions.adminaipromptversion')),
                ('question', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ai_operation_logs', to='questions.question')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
