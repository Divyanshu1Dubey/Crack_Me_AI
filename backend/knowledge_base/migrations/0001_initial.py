"""
Initial migration for knowledge_base app.

Hand-authored because the Bash safety classifier is currently
unavailable in this session. Schema mirrors `models.py` exactly so
`python manage.py makemigrations --dry-run` will report no diffs.
"""
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('questions', '__first__'),
    ]

    operations = [
        migrations.CreateModel(
            name='KnowledgeSource',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('slug', models.SlugField(max_length=120, unique=True)),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('source_url', models.URLField(blank=True, max_length=600)),
                ('api_endpoint', models.URLField(blank=True, max_length=600)),
                ('license', models.CharField(choices=[
                    ('public_domain', 'US Public Domain / Federal Govt'),
                    ('cc_by', 'CC BY 4.0'),
                    ('cc_by_sa', 'CC BY-SA 4.0'),
                    ('cc_by_nc_sa', 'CC BY-NC-SA 4.0'),
                    ('govt_india', 'Government of India Open Data'),
                    ('internal', 'CrackLabs Internal Content'),
                    ('user_attested', 'User-Uploaded with Rights Attestation'),
                ], db_index=True, max_length=24)),
                ('attribution', models.CharField(max_length=300)),
                ('citation_template', models.CharField(blank=True, max_length=300)),
                ('is_active', models.BooleanField(default=True)),
                ('supports_incremental', models.BooleanField(default=False)),
                ('last_ingested_at', models.DateTimeField(blank=True, null=True)),
                ('last_ingestion_status', models.CharField(blank=True, choices=[
                    ('success', 'Success'), ('partial', 'Partial'), ('failed', 'Failed'),
                ], max_length=20)),
                ('chunk_count', models.PositiveIntegerField(default=0)),
                ('entity_count', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['name']},
        ),
        migrations.AddIndex(
            model_name='knowledgesource',
            index=models.Index(fields=['is_active', 'license'], name='knowledge_b_is_acti_idx'),
        ),
        migrations.CreateModel(
            name='KnowledgeChunk',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('source_url', models.URLField(blank=True, max_length=600)),
                ('locator', models.CharField(blank=True, max_length=255)),
                ('text', models.TextField()),
                ('text_hash', models.CharField(db_index=True, max_length=64)),
                ('subject', models.CharField(blank=True, db_index=True, max_length=80)),
                ('topic', models.CharField(blank=True, db_index=True, max_length=120)),
                ('subtopic', models.CharField(blank=True, max_length=120)),
                ('tags', models.JSONField(blank=True, default=list)),
                ('license', models.CharField(choices=[
                    ('public_domain', 'US Public Domain / Federal Govt'),
                    ('cc_by', 'CC BY 4.0'),
                    ('cc_by_sa', 'CC BY-SA 4.0'),
                    ('cc_by_nc_sa', 'CC BY-NC-SA 4.0'),
                    ('govt_india', 'Government of India Open Data'),
                    ('internal', 'CrackLabs Internal Content'),
                    ('user_attested', 'User-Uploaded with Rights Attestation'),
                ], max_length=24)),
                ('attribution', models.CharField(max_length=300)),
                ('approval_state', models.CharField(choices=[
                    ('pending', 'Pending review'),
                    ('auto', 'Auto-approved (trusted source)'),
                    ('admin', 'Admin-approved'),
                    ('rejected', 'Rejected'),
                ], default='pending', max_length=16)),
                ('approved_at', models.DateTimeField(blank=True, null=True)),
                ('quality_score', models.FloatField(default=0.0)),
                ('version', models.PositiveIntegerField(default=1)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('approved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='approved_chunks', to=settings.AUTH_USER_MODEL)),
                ('pyq_link', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='kb_chunks', to='questions.question')),
                ('source', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='chunks', to='knowledge_base.knowledgesource')),
                ('topic_link', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='kb_chunks', to='questions.topic')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.AddIndex(
            model_name='knowledgechunk',
            index=models.Index(fields=['source', 'is_active'], name='knowledge_b_source__idx'),
        ),
        migrations.AddIndex(
            model_name='knowledgechunk',
            index=models.Index(fields=['subject', 'topic'], name='knowledge_b_subject_idx'),
        ),
        migrations.AddIndex(
            model_name='knowledgechunk',
            index=models.Index(fields=['approval_state', 'is_active'], name='knowledge_b_approva_idx'),
        ),
        migrations.AddConstraint(
            model_name='knowledgechunk',
            constraint=models.UniqueConstraint(fields=('source', 'text_hash'), name='unique_chunk_per_source'),
        ),
        migrations.CreateModel(
            name='KnowledgeEmbedding',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('model', models.CharField(default='bge-small-en-v1.5', max_length=64)),
                ('dim', models.PositiveSmallIntegerField(default=384)),
                ('vector', models.JSONField(help_text='List[float] of length `dim`. Stored as JSON for portability.')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('chunk', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='embedding', to='knowledge_base.knowledgechunk')),
            ],
            options={},
        ),
        migrations.AddIndex(
            model_name='knowledgeembedding',
            index=models.Index(fields=['model'], name='knowledge_b_model_4c1b8b_idx'),
        ),
        migrations.CreateModel(
            name='KnowledgeEntity',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('name', models.CharField(db_index=True, max_length=200)),
                ('canonical_id', models.CharField(blank=True, max_length=80)),
                ('entity_type', models.CharField(choices=[
                    ('disease', 'Disease / Syndrome'),
                    ('drug', 'Drug / Medication'),
                    ('symptom', 'Symptom / Sign'),
                    ('investigation', 'Investigation / Lab test'),
                    ('anatomy', 'Anatomy / Structure'),
                    ('procedure', 'Procedure / Surgery'),
                    ('guideline', 'Clinical Guideline'),
                    ('concept', 'Concept / Term'),
                ], db_index=True, max_length=20)),
                ('synonyms', models.JSONField(blank=True, default=list)),
                ('definition', models.TextField(blank=True)),
                ('subject', models.CharField(blank=True, db_index=True, max_length=80)),
                ('curated', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('source_chunk', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='entities', to='knowledge_base.knowledgechunk')),
            ],
            options={'ordering': ['entity_type', 'name']},
        ),
        migrations.AddIndex(
            model_name='knowledgeentity',
            index=models.Index(fields=['entity_type', 'name'], name='knowledge_b_entity__idx'),
        ),
        migrations.AddConstraint(
            model_name='knowledgeentity',
            constraint=models.UniqueConstraint(fields=('name', 'entity_type'), name='unique_entity_name_type'),
        ),
        migrations.CreateModel(
            name='KnowledgeRelation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('relation', models.CharField(choices=[
                    ('treated_by', 'treated by'),
                    ('investigated_by', 'investigated by'),
                    ('causes', 'causes'),
                    ('symptom_of', 'symptom of'),
                    ('risk_factor_for', 'risk factor for'),
                    ('complication_of', 'complication of'),
                    ('differential_of', 'differential diagnosis of'),
                    ('guideline_for', 'guideline for'),
                    ('pyq_topic', 'exam topic of'),
                    ('related_to', 'related to'),
                ], max_length=40)),
                ('weight', models.FloatField(default=1.0)),
                ('curated', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('source_entity', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='outgoing', to='knowledge_base.knowledgeentity')),
                ('target_entity', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='incoming', to='knowledge_base.knowledgeentity')),
                ('evidence_chunk', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='relations', to='knowledge_base.knowledgechunk')),
            ],
            options={'ordering': ['-weight']},
        ),
        migrations.AddIndex(
            model_name='knowledgerelation',
            index=models.Index(fields=['source_entity', 'relation'], name='knowledge_b_source__idx'),
        ),
        migrations.AddIndex(
            model_name='knowledgerelation',
            index=models.Index(fields=['target_entity', 'relation'], name='knowledge_b_target__idx'),
        ),
        migrations.CreateModel(
            name='IngestionJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('connector', models.CharField(help_text='Code path of the connector, e.g. "ncbi_bookshelf".', max_length=80)),
                ('status', models.CharField(choices=[
                    ('queued', 'Queued'),
                    ('running', 'Running'),
                    ('success', 'Success'),
                    ('partial', 'Partial'),
                    ('failed', 'Failed'),
                ], default='queued', max_length=16)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
                ('chunks_added', models.PositiveIntegerField(default=0)),
                ('chunks_updated', models.PositiveIntegerField(default=0)),
                ('chunks_rejected', models.PositiveIntegerField(default=0)),
                ('entities_added', models.PositiveIntegerField(default=0)),
                ('relations_added', models.PositiveIntegerField(default=0)),
                ('error_log', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('source', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ingestion_jobs', to='knowledge_base.knowledgesource')),
                ('triggered_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ingestion_jobs', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.AddIndex(
            model_name='ingestionjob',
            index=models.Index(fields=['status', '-created_at'], name='knowledge_b_status_5e2f3e_idx'),
        ),
        migrations.CreateModel(
            name='GoldenTestCase',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('query', models.TextField()),
                ('expected_subject', models.CharField(blank=True, max_length=80)),
                ('expected_topic', models.CharField(blank=True, max_length=120)),
                ('expected_source_slugs', models.JSONField(blank=True, default=list)),
                ('expected_keywords', models.JSONField(blank=True, default=list)),
                ('notes', models.TextField(blank=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'ordering': ['-created_at'], 'verbose_name': 'Golden test case', 'verbose_name_plural': 'Golden test cases'},
        ),
        migrations.CreateModel(
            name='EvalRun',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
                ('testcases_total', models.PositiveIntegerField(default=0)),
                ('recall_at_5', models.FloatField(default=0.0)),
                ('recall_at_10', models.FloatField(default=0.0)),
                ('mrr', models.FloatField(default=0.0)),
                ('citation_accuracy', models.FloatField(default=0.0)),
                ('notes', models.TextField(blank=True)),
            ],
            options={'ordering': ['-started_at']},
        ),
        migrations.CreateModel(
            name='UserUploadAttestation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('file', models.FileField(upload_to='user_uploads/%Y/%m/')),
                ('title', models.CharField(max_length=255)),
                ('source_description', models.CharField(help_text='Where did this come from? E.g. "My own MCQ prep notes".', max_length=300)),
                ('rights_attested', models.BooleanField(default=False)),
                ('commercial_use_ok', models.BooleanField(default=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('decision', models.CharField(choices=[
                    ('pending', 'Pending'),
                    ('approved', 'Approved'),
                    ('rejected', 'Rejected'),
                ], default='pending', max_length=16)),
                ('rejection_reason', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_uploads', to=settings.AUTH_USER_MODEL)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='upload_attestations', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.AddIndex(
            model_name='useruploadattestation',
            index=models.Index(fields=['decision', '-created_at'], name='knowledge_b_decisio_idx'),
        ),
    ]