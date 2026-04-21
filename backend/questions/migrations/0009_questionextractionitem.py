from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('questions', '0008_questionimportjob'),
    ]

    operations = [
        migrations.CreateModel(
            name='QuestionExtractionItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('pending', 'Pending Review'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('published', 'Published')], default='pending', max_length=20)),
                ('raw_text', models.TextField(blank=True)),
                ('question_text', models.TextField(blank=True)),
                ('option_a', models.TextField(blank=True)),
                ('option_b', models.TextField(blank=True)),
                ('option_c', models.TextField(blank=True)),
                ('option_d', models.TextField(blank=True)),
                ('correct_answer', models.CharField(blank=True, choices=[('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')], max_length=1)),
                ('explanation', models.TextField(blank=True)),
                ('year', models.IntegerField(blank=True, null=True)),
                ('paper', models.IntegerField(default=0)),
                ('tags', models.JSONField(blank=True, default=list)),
                ('review_note', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('job', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='questions.questionimportjob')),
                ('published_question', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='source_extraction_items', to='questions.question')),
                ('subject', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='extraction_items', to='questions.subject')),
                ('topic', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='extraction_items', to='questions.topic')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
